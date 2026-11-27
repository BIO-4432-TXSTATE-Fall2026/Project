from __future__ import annotations

import pytest

from hmp_project.cli import main

LOCI_HEADER = (
    "locus_id\tspec\tgenome\tcontig\tstart\tend\tmotif\tmotif_length\trep_length\tpurity"
    "\tn_calls\tmotifs\tleft_anchor\tright_anchor\n"
)


def loci_row(locus: str, genome: str, spec: str = "hmp-target") -> str:
    return f"{locus}\t{spec}\t{genome}\tc1\t100\t112\tAC\t2\t12\t1.0\t1\tAC\tAAAA\tCCCC\n"


@pytest.fixture
def inputs(tmp_path):
    table = tmp_path / "tr-loci.tsv"
    table.write_text(
        LOCI_HEADER
        + loci_row("L000001", "a")
        + loci_row("L000001", "b")
        + loci_row("L000002", "a")
        + loci_row("L000003", "c", "kit")
    )
    fasta = tmp_path / "tr-loci.fa"
    fasta.write_text(
        ">L000001|a|c1:50-162\nAAA\n>L000001|b|c1:50-162\nAAT\n"
        ">L000002|a|c1:0-9\nCCC\n>L000003|c|c1:0-9\nGGG\n"
    )
    return tmp_path, table, fasta


def run_panel(inputs, human: str, mock: str) -> tuple:
    tmp, table, fasta = inputs
    (tmp / "human.tsv").write_text(human)
    (tmp / "mock.tsv").write_text(mock)
    main(
        [
            "panel",
            str(table),
            str(fasta),
            f"--human={tmp / 'human.tsv'}",
            f"--mock={tmp / 'mock.tsv'}",
            f"--table={tmp / 'tr-panel.tsv'}",
            f"--out={tmp / 'tr-panel.fa'}",
        ]
    )
    return (tmp / "tr-panel.tsv").read_text().splitlines(), (tmp / "tr-panel.fa").read_text()


def test_a_human_hit_excludes_the_whole_group(inputs):
    table, fasta = run_panel(
        inputs,
        human="locus_id\tfragments\nL000001\t3\n",
        mock="locus_id\tfragments\n",
    )

    assert [line.split("\t")[0] for line in table[1:]] == ["L000002", "L000003"]
    # Every record of the excluded group goes, the kept groups' stay in order.
    assert fasta == ">L000002|a|c1:0-9\nCCC\n>L000003|c|c1:0-9\nGGG\n"


def test_the_mock_screen_annotates_and_never_excludes(inputs):
    table, _ = run_panel(
        inputs,
        human="locus_id\tfragments\n",
        mock="locus_id\tfragments\nL000002\t5\n",
    )

    header = table[0].split("\t")
    assert header[:14] == LOCI_HEADER.rstrip("\n").split("\t")
    assert header[14:] == ["human_fragments", "mock_fragments"]
    rows = [dict(zip(header, line.split("\t"), strict=True)) for line in table[1:]]
    assert [r["locus_id"] for r in rows] == ["L000001", "L000001", "L000002", "L000003"]
    assert [r["mock_fragments"] for r in rows] == ["0", "0", "5", "0"]
    assert {r["human_fragments"] for r in rows} == {"0"}


def test_a_screen_from_another_table_is_refused(inputs):
    with pytest.raises(SystemExit, match="human screen names loci not in"):
        run_panel(inputs, human="locus_id\tfragments\nL009999\t1\n", mock="locus_id\tfragments\n")
