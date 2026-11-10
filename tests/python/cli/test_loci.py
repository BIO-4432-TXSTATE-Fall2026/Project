from __future__ import annotations

import gzip

import pytest

# intruder and pyfastx live in the catalog environment: `pixi run -e test-catalog test`.
pytest.importorskip("intruder.trcore.io")
pytest.importorskip("pyfastx")

from hmp_project.cli import main

HEADER = "genome\tcontig\tstart\tend\tmotif\tpurity\tmotif_length\trep_length\trep_units\n"


def catalog_row(genome: str, contig: str, start: int, end: int) -> str:
    return f"{genome}\t{contig}\t{start}\t{end}\tCA\t1.0\t2\t{end - start}\t{(end - start) // 2}\n"


@pytest.fixture
def genomes(tmp_path):
    # Lower case on purpose: inTRuder's reader upper-cases, and the reference has to
    # agree with the catalog the same reader produced. The header carries a description
    # after a tab, which the contig name must not absorb.
    a = tmp_path / "a.fa"
    a.write_text(">c1\tsome description\n" + "ttttt" + "cacacaca" + "ggggg\n>c2\nAAACACACAAA\n")
    b = tmp_path / "b.fa.gz"
    b.write_bytes(gzip.compress(b">c1\nTTTTTCACACACAGGGGG\n"))
    listing = tmp_path / "genomes.tsv"
    listing.write_text(f"A\t{a}\nB\t{b}\n")
    return listing


def records(path) -> list[tuple[str, str]]:
    lines = path.read_text().splitlines()
    return list(zip(lines[::2], lines[1::2], strict=True))


def test_loci_pads_clips_and_dedups(tmp_path, genomes):
    catalog = tmp_path / "catalog.tsv"
    catalog.write_text(
        HEADER
        + catalog_row("A", "c1", 5, 13)
        + catalog_row("A", "c2", 3, 9)
        # B's locus has A's sequence and padding exactly, so it is written once.
        + catalog_row("B", "c1", 5, 13)
    )
    out = tmp_path / "tr-loci.fa"
    main(["loci", str(catalog), f"--genomes={genomes}", "--flank=3", f"--out={out}"])

    assert records(out) == [
        (">A|c1:2-16", "TTTCACACACAGGG"),
        # Clipped at the contig's end rather than padded past it.
        (">A|c2:0-11", "AAACACACAAA"),
    ]


def test_loci_refuses_a_contig_the_genome_lacks(tmp_path, genomes):
    catalog = tmp_path / "catalog.tsv"
    catalog.write_text(HEADER + catalog_row("A", "c9", 0, 4))
    out = tmp_path / "tr-loci.fa"

    with pytest.raises(SystemExit, match="A/c9"):
        main(["loci", str(catalog), f"--genomes={genomes}", f"--out={out}"])
    assert not out.exists()


def test_loci_refuses_a_genome_with_no_fasta(tmp_path, genomes):
    catalog = tmp_path / "catalog.tsv"
    catalog.write_text(HEADER + catalog_row("Z", "c1", 0, 4))

    with pytest.raises(SystemExit, match="no FASTA for genomes"):
        main(["loci", str(catalog), f"--genomes={genomes}", f"--out={tmp_path / 'x.fa'}"])
