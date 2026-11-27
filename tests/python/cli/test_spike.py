from __future__ import annotations

import csv

import pytest

from hmp_project.cli import main
from hmp_project.cli import spike_check as check_cli

PANEL = (
    "locus_id\tgenome\trep_length\tmotif_length\n"
    "L000001\tg1\t30\t3\n"
    "L000002\tg1\t20\t2\n"
    "L000003\tg1\t12\t4\n"
    "L000001\tg2\t33\t3\n"
    "L000004\tg2\t40\t5\n"
)
ALLELES = (
    "sample\tlocus_id\tallele_bp\treads\n"
    # g1@1000: L000001 exact, L000002 one unit off, L000003 far off, L000004 unexpected.
    # L000001 also has a minority wrong allele that the modal call ignores.
    "g1@1000\tL000001\t30\t9\n"
    "g1@1000\tL000001\t33\t2\n"
    "g1@1000\tL000002\t22\t4\n"
    "g1@1000\tL000003\t20\t3\n"
    "g1@1000\tL000004\t40\t5\n"
    "g1@10\tL000001\t30\t1\n"
    "H1\tL000001\t30\t8\n"
    "H1\tL000009\t50\t3\n"
    "H2\tL000002\t20\t5\n"
)
STATS = "sample\treads_in\n" + "".join(f"{s}\t1\n" for s in ("g1@10", "g1@1000", "g2@10"))


def write(tmp_path, name: str, text: str):
    path = tmp_path / name
    path.write_text(text)
    return path


def rows(path) -> list[dict[str, str]]:
    with path.open() as f:
        return list(csv.DictReader(f, delimiter="\t"))


def test_spike_check_scores_modal_calls_against_the_panel(tmp_path):
    out = tmp_path / "spike-check.tsv"
    main(
        [
            "spike-check",
            f"--panel={write(tmp_path, 'panel.tsv', PANEL)}",
            f"--alleles={write(tmp_path, 'alleles.tsv', ALLELES)}",
            f"--stats={write(tmp_path, 'stats.tsv', STATS)}",
            f"--out={out}",
        ]
    )
    by_sample = {(r["genome"], r["reads"]): r for r in rows(out)}
    deep = by_sample[("g1", "1000")]
    assert deep["loci_expected"] == "3"
    assert deep["loci_called"] == "3"
    assert deep["exact_fraction"] == "0.3333"
    assert deep["within_one_unit_fraction"] == "0.6667"
    assert deep["loci_unexpected"] == "1"
    assert by_sample[("g1", "10")]["exact_fraction"] == "1.0000"
    # A sample with no allele at all is still reported, with nothing to score.
    empty = by_sample[("g2", "10")]
    assert (empty["loci_called"], empty["exact_fraction"]) == ("0", "NA")


def test_a_tie_between_alleles_goes_to_the_shorter():
    from collections import Counter

    counts = Counter({("L1", 30): 2, ("L1", 33): 2, ("L2", 9): 1})
    assert check_cli.modal_calls(counts) == {"L1": 30, "L2": 9}


def test_spike_check_rejects_a_sample_that_is_not_a_spike(tmp_path):
    not_a_spike = "sample\treads_in\nSRS1\t1\n"
    with pytest.raises(SystemExit, match="not a spike sample"):
        main(
            [
                "spike-check",
                f"--panel={write(tmp_path, 'panel.tsv', PANEL)}",
                f"--alleles={write(tmp_path, 'alleles.tsv', ALLELES)}",
                f"--stats={write(tmp_path, 'stats.tsv', not_a_spike)}",
            ]
        )


def test_split_sample_keeps_dots_and_at_signs_in_a_genome_name():
    assert check_cli.split_sample("GCF_000009045.2@1000") == ("GCF_000009045.2", 1000)
    assert check_cli.split_sample("a@b@10") == ("a@b", 10)


def run_mix(tmp_path, *extra: str):
    spikes = "".join(
        line + "\n" for line in ALLELES.splitlines() if line.startswith(("sample", "g"))
    )
    hosts = "".join(
        line + "\n" for line in ALLELES.splitlines() if line.startswith(("sample", "H"))
    )
    main(
        [
            "spike-mix",
            f"--panel={write(tmp_path, 'panel.tsv', PANEL)}",
            f"--hosts={write(tmp_path, 'hosts.tsv', hosts)}",
            f"--spikes={write(tmp_path, 'spikes.tsv', spikes)}",
            f"--out={tmp_path / 'alleles-spiked.tsv'}",
            f"--labels={tmp_path / 'spike-labels.tsv'}",
            *extra,
        ]
    )
    return rows(tmp_path / "alleles-spiked.tsv"), rows(tmp_path / "spike-labels.tsv")


def test_spike_mix_sums_the_host_and_the_genome_per_depth(tmp_path):
    alleles, _ = run_mix(tmp_path)
    samples = {r["sample"] for r in alleles}
    assert samples == {f"{h}+g1@{n}" for h in ("H1", "H2") for n in (10, 1000)}
    mixed = {(r["sample"], r["locus_id"], r["allele_bp"]): int(r["reads"]) for r in alleles}
    assert mixed[("H1+g1@10", "L000001", "30")] == 9  # 8 host + 1 spike
    assert mixed[("H1+g1@1000", "L000001", "30")] == 17
    assert mixed[("H1+g1@1000", "L000009", "50")] == 3  # host only
    assert mixed[("H2+g1@10", "L000001", "30")] == 1  # spike only


def test_spike_labels_mark_the_loci_the_genome_is_a_member_of(tmp_path):
    _, labels = run_mix(tmp_path)
    by_key = {(r["sample"], r["locus_id"]): r for r in labels}
    member = by_key[("H1+g1@1000", "L000001")]
    assert member == {
        "sample": "H1+g1@1000",
        "host": "H1",
        "batch": "g1",
        "reads": "1000",
        "locus_id": "L000001",
        "contaminant": "true",
    }
    assert by_key[("H1+g1@1000", "L000009")]["contaminant"] == "false"
    assert by_key[("H1+g1@1000", "L000004")]["contaminant"] == "false"  # g2's, not g1's


def test_spike_mix_takes_the_named_hosts_and_rejects_an_unknown_one(tmp_path):
    alleles, _ = run_mix(tmp_path, "--host-samples=H2")
    assert {r["sample"].split("+")[0] for r in alleles} == {"H2"}
    with pytest.raises(SystemExit, match=r"not in .*hosts\.tsv: H9"):
        run_mix(tmp_path, "--host-samples=H9")
