from __future__ import annotations

import pytest

from hmp_project.cli import main
from hmp_project.cli.screen import count_fragments, matched_loci

# bbduk.sh ... int=f rename=t outm=stdout.fa, fed by shred.sh length=100 overlap=50. The
# sequence is wrapped at 70 columns, as bbmap writes FASTA. The fragment names are
# shred's: the contig's whole header, then ``_<start>-<end>``. The second fragment hit two
# references, which rename=t lists tab-separated after the name.
BBDUK_OUTPUT = (
    ">chrT desc_100-199\tL000001|g1|c1:0-144=26\n"
    "AGCCCAGCCGTCACGATTGTTATGCGTATAAGCCCGGTTCACTACGTCCGCAGATTTTCATATTATGCAG\n"
    "AAAATCTACTTCGCCTGATACGAGTCGGTT\n"
    ">chrT desc_150-249\tL000001|g1|c1:0-144=76\n"
    "CAGATTTTCATATTATGCAGAAAATCTACTTCGCCTGATACGAGTCGGTTATCTTCGGATCACACACACA\n"
    "CACACACACACACAACTGTATAGTCCCACC\n"
    ">c_0-99\tL000007|a|c:0-1=16\tL000009|b|c:0-1=6\n"
    "ACGT\n"
    ">c_50-139\tL000009|b|c:0-1=16\n"
    "ACGT\n"
)


def test_each_locus_is_counted_once_per_fragment():
    counts = count_fragments(BBDUK_OUTPUT.splitlines(keepends=True))

    assert counts == {"L000001": 2, "L000007": 1, "L000009": 2}


def test_a_locus_hit_through_two_of_its_records_counts_once():
    # tr-loci.fa holds several records per locus, one per distinct member sequence.
    header = ">c_0-99\tL000003|g1|c1:0-9=10\tL000003|g2|c1:5-14=4\tL000004|g1|c2:0-9=1\n"

    assert matched_loci(header) == {"L000003", "L000004"}


def test_a_header_without_matches_names_no_locus():
    assert matched_loci(">c_0-99\n") == set()


def test_a_reference_name_may_contain_an_equals_sign():
    assert matched_loci(">c_0-99\tL000001|g=1|c:0-9=7\n") == {"L000001"}


def test_a_match_without_a_count_is_refused():
    with pytest.raises(ValueError, match="name=count"):
        matched_loci(">c_0-99\tL000001|g1|c1:0-9\n")


def test_screen_writes_the_counts_sorted(tmp_path):
    source = tmp_path / "matched.fa"
    source.write_text(BBDUK_OUTPUT)
    out = tmp_path / "chm13.screen.tsv"

    main(["screen", f"--in={source}", f"--out={out}"])

    assert out.read_text() == "locus_id\tfragments\nL000001\t2\nL000007\t1\nL000009\t2\n"


def test_screen_reads_stdin(tmp_path, monkeypatch):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(BBDUK_OUTPUT))
    out = tmp_path / "screen.tsv"

    main(["screen", f"--out={out}"])

    assert out.read_text().splitlines()[0] == "locus_id\tfragments"
    assert len(out.read_text().splitlines()) == 4


def test_screen_with_no_matches_writes_only_the_header(tmp_path):
    source = tmp_path / "matched.fa"
    source.write_text("")
    out = tmp_path / "screen.tsv"

    main(["screen", f"--in={source}", f"--out={out}"])

    assert out.read_text() == "locus_id\tfragments\n"
