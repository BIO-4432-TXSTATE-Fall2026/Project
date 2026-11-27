from __future__ import annotations

import csv
import gzip
import random

import pytest

from hmp_project.cli import alleles as alleles_cli
from hmp_project.cli import main

rng = random.Random(7)


def dna(n: int) -> str:
    return "".join(rng.choice("ACGT") for _ in range(n))


L1, R1 = dna(20), dna(20)  # locus L000001's anchors
L2, R2 = dna(20), dna(20)  # locus L000002's
PANEL_HEADER = "locus_id\tgenome\tleft_anchor\tright_anchor\n"
PANEL = PANEL_HEADER + f"L000001\ta\t{L1}\t{R1}\nL000001\tb\t{L1}\t{R1}\nL000002\ta\t{L2}\t{R2}\n"


def repeat(units: int, motif: str = "CAG") -> str:
    return motif * units


def rc(sequence: str) -> str:
    return alleles_cli.reverse_complement(sequence)


def record(name: str, sequence: str, *matches: str) -> str:
    header = "\t".join([f"@{name}", *(f"{m}|a|c:0-9=7" for m in matches)])
    return f"{header}\n{sequence}\n+\n{'I' * len(sequence)}\n"


def call(*reads: str, mismatches: int = 1, anchors=None):
    anchors = anchors or {"L000001": (L1, R1), "L000002": (L2, R2)}
    import io

    return alleles_cli.call_alleles(io.StringIO("".join(reads)), anchors, mismatches)


def test_a_spanning_read_gives_the_gap_between_its_anchors():
    read = record("r/1", dna(5) + L1 + repeat(8) + R1 + dna(5), "L000001")
    alleles, stats = call(read)
    assert alleles == {("L000001", 24): 1}
    assert (stats["reads_in"], stats["spanning"], stats["flanking"]) == (1, 1, 0)


def test_the_reverse_complement_of_a_read_is_called_the_same():
    read = record("r/1", rc(L1 + repeat(11) + R1), "L000001")
    assert call(read)[0] == {("L000001", 33): 1}


def test_one_anchor_mismatch_is_tolerated_and_two_are_not():
    one = L1[:7] + ("A" if L1[7] != "A" else "C") + L1[8:]
    two = one[:15] + ("A" if one[15] != "A" else "C") + one[16:]
    ok = record("a/1", one + repeat(6) + R1, "L000001")
    bad = record("b/1", two + repeat(6) + R1, "L000001")
    alleles, stats = call(ok, bad)
    assert alleles == {("L000001", 18): 1}
    # The bad read still shows the right anchor, so it flanks.
    assert (stats["spanning"], stats["flanking"]) == (1, 1)
    assert call(ok, mismatches=0)[1]["spanning"] == 0


def test_a_read_with_one_anchor_is_flanking_and_gives_no_length():
    read = record("r/1", dna(10) + L1 + repeat(10), "L000001")
    alleles, stats = call(read)
    assert not alleles
    assert (stats["spanning"], stats["flanking"], stats["unassigned"]) == (0, 1, 0)


def test_a_read_that_shows_none_of_its_candidates_is_unassigned():
    alleles, stats = call(record("r/1", dna(60), "L000001"), record("s/1", dna(60)))
    assert not alleles
    assert (stats["reads_in"], stats["unassigned"]) == (2, 2)


def test_a_read_goes_to_the_locus_with_fewer_mismatches():
    off = L2[:3] + ("A" if L2[3] != "A" else "C") + L2[4:]
    read = record("r/1", L2 + repeat(5) + R2, "L000001", "L000002")
    alleles, stats = call(read, anchors={"L000001": (off, R2), "L000002": (L2, R2)})
    assert alleles == {("L000002", 15): 1}
    assert stats["ambiguous"] == 0


def test_a_tie_between_loci_is_ambiguous_and_counts_nowhere():
    same = {"L000001": (L1, R1), "L000002": (L1, R1)}
    read = record("r/1", L1 + repeat(5) + R1, "L000001", "L000002")
    alleles, stats = call(read, anchors=same)
    assert not alleles
    assert (stats["ambiguous"], stats["spanning"]) == (1, 0)


def test_spanning_beats_flanking_across_loci():
    read = record("r/1", L1 + repeat(4) + R1 + L2, "L000001", "L000002")
    alleles, stats = call(read)
    assert alleles == {("L000001", 12): 1}
    assert (stats["spanning"], stats["ambiguous"]) == (1, 0)


def test_mates_of_one_fragment_count_once_and_agree():
    body = L1 + repeat(7) + R1
    mate1 = record("frag/1", body, "L000001")
    mate2 = record("frag/2", rc(body), "L000001")
    other = record("solo", body, "L000001")
    alleles, stats = call(mate1, mate2, other)
    assert alleles == {("L000001", 21): 2}
    assert (stats["spanning"], stats["pairs_collapsed"], stats["pairs_discordant"]) == (3, 1, 0)


def test_mates_that_span_different_lengths_are_discordant_and_count_once():
    mate1 = record("frag/1", L1 + repeat(7) + R1, "L000001")
    mate2 = record("frag/2", L1 + repeat(8) + R1, "L000001")
    alleles, stats = call(mate1, mate2)
    assert alleles == {("L000001", 21): 1}
    assert (stats["pairs_collapsed"], stats["pairs_discordant"]) == (1, 1)


def test_a_mate_that_flanks_does_not_hide_its_mates_span():
    mate1 = record("frag/1", dna(5) + L1 + repeat(5), "L000001")
    mate2 = record("frag/2", L1 + repeat(7) + R1, "L000001")
    alleles, stats = call(mate1, mate2)
    assert alleles == {("L000001", 21): 1}
    assert (stats["pairs_collapsed"], stats["pairs_discordant"]) == (1, 0)


def test_illumina_comments_are_not_part_of_the_fragment_stem():
    stem, loci = alleles_cli.parse_header("@SYN_1_a 1:\tL000001|g|c:0-9=5\tL000002|g|c:0-9=2\n")
    assert (stem, loci) == ("SYN_1_a", ["L000001", "L000002"])
    assert alleles_cli.parse_header("@SRR1.7/2\tL000003|g|c:0-9=5\n")[0] == "SRR1.7"


def test_a_header_that_is_not_a_match_is_an_error():
    with pytest.raises(ValueError, match="name=count"):
        alleles_cli.parse_header("@r/1\tnonsense\n")


def test_a_locus_the_panel_lacks_is_an_error():
    with pytest.raises(ValueError, match="not in the panel"):
        call(record("r/1", dna(40), "L999999"))


def test_find_anchor_agrees_with_a_brute_force_scan():
    for _ in range(50):
        anchor = dna(20)
        mutated = list(anchor)
        mutated[rng.randrange(20)] = rng.choice("ACGT")
        sequence = dna(10) + "".join(mutated) + dna(10)
        brute = [
            (i, d)
            for i in range(len(sequence) - 19)
            if (d := sum(a != b for a, b in zip(sequence[i : i + 20], anchor, strict=True))) <= 1
        ]
        assert alleles_cli.find_anchor(sequence, anchor, 1) == brute


def test_the_command_writes_the_tables(tmp_path):
    panel = tmp_path / "tr-panel.tsv"
    panel.write_text(PANEL)
    reads = tmp_path / "S1.loci.fastq.gz"
    body = L1 + repeat(6) + R1
    with gzip.open(reads, "wt") as f:
        f.write(record("f/1", body, "L000001") + record("f/2", rc(body), "L000001"))
        f.write(record("g/1", dna(50), "L000002"))
    main(["alleles", str(reads), f"--panel={panel}", f"--out-dir={tmp_path / 'out'}"])
    with (tmp_path / "out" / "S1.alleles.tsv").open() as f:
        assert list(csv.reader(f, delimiter="\t")) == [
            ["sample", "locus_id", "allele_bp", "reads"],
            ["S1", "L000001", "18", "1"],
        ]
    with (tmp_path / "out" / "S1.allele-stats.tsv").open() as f:
        row = next(csv.DictReader(f, delimiter="\t"))
    assert row == {
        "sample": "S1",
        "reads_in": "3",
        "spanning": "2",
        "flanking": "0",
        "ambiguous": "0",
        "unassigned": "1",
        "pairs_collapsed": "1",
        "pairs_discordant": "0",
    }


def test_anchor_option_matches_only_the_bases_next_to_the_repeat(tmp_path):
    panel = tmp_path / "tr-panel.tsv"
    panel.write_text(PANEL)
    anchors = alleles_cli.read_anchors(panel, 10)
    assert anchors["L000001"] == (L1[10:], R1[:10])
    with pytest.raises(ValueError, match="longer"):
        alleles_cli.read_anchors(panel, 30)
