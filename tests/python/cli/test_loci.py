from __future__ import annotations

import csv
import gzip
import random

import pytest

# intruder and pyfastx live in the catalog environment: `pixi run -e test-catalog test`.
pytest.importorskip("intruder.trcore.io")
pytest.importorskip("pyfastx")

from hmp_project.cli import main
from hmp_project.cli.loci import Call, merge_calls

HEADER = "genome\tcontig\tstart\tend\tmotif\tpurity\tmotif_length\trep_length\trep_units\n"
COMPLEMENT = str.maketrans("ACGT", "TGCA")


def rc(sequence: str) -> str:
    return sequence.translate(COMPLEMENT)[::-1]


def catalog_row(genome: str, contig: str, start: int, end: int, motif: str = "CA") -> str:
    return f"{genome}\t{contig}\t{start}\t{end}\t{motif}\t1.0\t{len(motif)}\t{end - start}\t1\n"


class Contig:
    """A contig built from random unique stretches and named tracts, remembering where
    each tract sits so a test can write the catalog row the finder would have.
    """

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.sequence = ""

    def unique(self, length: int) -> str:
        piece = "".join(self.rng.choice("ACGT") for _ in range(length))
        self.sequence += piece
        return piece

    def tract(self, unit: str, copies: int) -> tuple[int, int]:
        start = len(self.sequence)
        self.sequence += unit * copies
        return start, len(self.sequence)


def read_table(path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def read_stats(path) -> dict[tuple[str, str], int]:
    return {(r["metric"], r["spec"]): int(r["value"]) for r in read_table(path)}


def records(path) -> list[tuple[str, str]]:
    lines = path.read_text().splitlines()
    return list(zip(lines[::2], lines[1::2], strict=True))


@pytest.fixture
def world(tmp_path):
    """Two specs over three genomes.

    ``A`` (spec ``alpha``), one contig, holds five calls:

    - a call 5 bases from the contig start, whose left anchor runs off it;
    - two calls 8 bases apart, which merge into one locus;
    - a locus ``X``, far from every other call;
    - an 80 bp tract, too long for a read to span.

    ``B`` (spec ``beta``) carries ``X`` on the opposite strand; ``C`` (also ``beta``) is
    a same-strand copy of ``X`` with identical padded sequence.
    """
    rng = random.Random(7)
    a = Contig(rng)
    a.unique(5)
    edge = a.tract("CA", 5)
    a.unique(60)
    first = a.tract("CA", 6)
    a.unique(8)
    second = a.tract("CA", 6)
    a.unique(60)
    left_flank = a.unique(60)
    x = a.tract("CA", 6)
    right_flank = a.unique(60)
    long = a.tract("CA", 40)
    a.unique(60)

    b = Contig(rng)
    b.unique(50)
    b.sequence += rc(left_flank + "CA" * 6 + right_flank)
    b_x = (50 + 60, 50 + 60 + 12)
    b.unique(50)

    c = Contig(rng)
    c.sequence = left_flank + "CA" * 6 + right_flank
    c_x = (60, 72)

    fasta = {}
    for name, contig in (("A", a), ("B", b), ("C", c)):
        path = tmp_path / f"{name}.fa" if name != "B" else tmp_path / "B.fa.gz"
        body = f">c1 a description\n{contig.sequence}\n".encode()
        path.write_bytes(gzip.compress(body) if name == "B" else body)
        fasta[name] = path
    genomes = tmp_path / "genomes.tsv"
    genomes.write_text("".join(f"{name}\t{path}\n" for name, path in fasta.items()))

    alpha = tmp_path / "tr-catalog.alpha.tsv"
    alpha.write_text(
        HEADER + "".join(catalog_row("A", "c1", *span) for span in (edge, first, second, x, long))
    )
    beta = tmp_path / "tr-catalog.beta.tsv"
    beta.write_text(
        HEADER + catalog_row("B", "c1", *b_x, motif="TG") + catalog_row("C", "c1", *c_x)
    )
    return {
        "alpha": alpha,
        "beta": beta,
        "genomes": genomes,
        "spans": {"first": first, "second": second, "x": x},
        "dir": tmp_path,
    }


def run_loci(world, *extra) -> dict:
    tmp = world["dir"]
    main(
        [
            "loci",
            str(world["alpha"]),
            str(world["beta"]),
            f"--genomes={world['genomes']}",
            "--flank=10",
            f"--table={tmp / 'tr-loci.tsv'}",
            f"--stats={tmp / 'tr-loci-stats.tsv'}",
            f"--out={tmp / 'tr-loci.fa'}",
            *extra,
        ]
    )
    return {
        "table": read_table(tmp / "tr-loci.tsv"),
        "stats": read_stats(tmp / "tr-loci-stats.tsv"),
        "fasta": records(tmp / "tr-loci.fa"),
    }


def test_merge_calls_joins_a_gap_smaller_than_the_anchor():
    calls = [Call(0, 10, "CA", "1"), Call(25, 30, "CA", "1"), Call(50, 60, "CA", "1")]

    # A gap of exactly the anchor length leaves the anchor clean, so it stays apart.
    assert [len(run) for run in merge_calls(calls, anchor=15)] == [1, 1, 1]
    assert [len(run) for run in merge_calls(calls, anchor=20)] == [2, 1]
    assert [len(run) for run in merge_calls(calls, anchor=21)] == [3]
    # An overlapping call has a negative gap and always merges, whatever the anchor.
    overlapping = [Call(0, 10, "CA", "1"), Call(5, 8, "CA", "1"), Call(9, 14, "CA", "1")]
    assert [len(run) for run in merge_calls(overlapping, anchor=0)] == [3]


def test_loci_merges_drops_and_groups_across_strands(world):
    out = run_loci(world, "--anchor=20", "--max-rep-length=60")
    rows = out["table"]
    stats = out["stats"]

    by_id: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_id.setdefault(row["locus_id"], []).append(row)
    assert sorted(by_id) == ["L000001", "L000002"]

    merged = next(r for r in rows if r["genome"] == "A" and r["n_calls"] == "2")
    first, second, x = (world["spans"][k] for k in ("first", "second", "x"))
    assert (int(merged["start"]), int(merged["end"])) == (first[0], second[1])
    assert merged["rep_length"] == str(second[1] - first[0])
    assert merged["motif"] == "AC" and merged["motif_length"] == "2"
    assert len(by_id[merged["locus_id"]]) == 1

    # X on both strands, plus the same-strand copy, is one group with one anchor pair.
    shared = next(group for group in by_id.values() if len(group) == 3)
    assert [r["genome"] for r in shared] == ["A", "B", "C"]
    assert {r["motif"] for r in shared} == {"AC"}
    assert len({(r["left_anchor"], r["right_anchor"]) for r in shared}) == 1
    assert all(len(r["left_anchor"]) == len(r["right_anchor"]) == 20 for r in shared)
    assert [(int(r["start"]), int(r["end"])) for r in shared if r["genome"] == "A"] == [x]
    assert [r["spec"] for r in shared] == ["alpha", "beta", "beta"]

    # Six calls in alpha and beta together become five regions; one runs off its contig
    # and the 80 bp tract's group is too long; what is left is two groups, four members.
    expected = {
        ("calls", "all"): 7,
        ("regions", "all"): 6,
        ("edge_drops", "all"): 1,
        ("long_groups", "all"): 1,
        ("long_members", "all"): 1,
        ("groups", "all"): 2,
        ("members", "all"): 4,
        ("groups", "alpha"): 2,
        ("groups", "beta"): 1,
        ("members", "alpha"): 2,
        ("members", "beta"): 2,
        ("edge_drops", "alpha"): 1,
        ("long_groups", "alpha"): 1,
    }
    assert {key: stats[key] for key in expected} == expected


def test_loci_fasta_pads_and_writes_identical_sequence_once(world):
    out = run_loci(world, "--anchor=20", "--max-rep-length=60")
    x = world["spans"]["x"]
    shared_id = next(
        r["locus_id"] for r in out["table"] if r["genome"] == "A" and r["n_calls"] == "1"
    )

    group = [(h, s) for h, s in out["fasta"] if h.startswith(f">{shared_id}|")]
    # A and C have byte-identical padded sequence, so C's record is not written; B's is
    # the reverse complement, a different record.
    assert [h.split("|")[1] for h, _ in group] == ["A", "B"]
    assert group[0][0] == f">{shared_id}|A|c1:{x[0] - 10}-{x[1] + 10}"
    assert group[1][1] == rc(group[0][1])
    assert len(group[0][1]) == 12 + 20


def test_loci_numbers_groups_the_same_way_every_run(world):
    first = run_loci(world, "--anchor=20")["table"]
    second = run_loci(world, "--anchor=20")["table"]
    assert first == second


def test_loci_keeps_long_groups_when_the_limit_allows_them(world):
    out = run_loci(world, "--anchor=20", "--max-rep-length=80")
    assert out["stats"][("long_groups", "all")] == 0
    assert out["stats"][("groups", "all")] == 3


def test_loci_refuses_a_genome_in_two_catalogs(world):
    world["beta"].write_text(HEADER + catalog_row("A", "c1", 70, 82))

    with pytest.raises(SystemExit, match="genome A is in both alpha and beta"):
        run_loci(world)


def test_loci_refuses_a_contig_the_genome_lacks(world):
    world["alpha"].write_text(HEADER + catalog_row("A", "c9", 0, 4))

    with pytest.raises(SystemExit, match="A/c9"):
        run_loci(world)
    assert not (world["dir"] / "tr-loci.fa").exists()


def test_loci_refuses_a_genome_with_no_fasta(world):
    world["alpha"].write_text(HEADER + catalog_row("Z", "c1", 0, 4))

    with pytest.raises(SystemExit, match="no FASTA for genomes"):
        run_loci(world)


def test_loci_refuses_a_genome_listed_twice(world):
    with world["genomes"].open("a") as f:
        f.write(f"A\t{world['dir'] / 'A.fa'}\n")

    with pytest.raises(SystemExit, match="listed twice"):
        run_loci(world)
