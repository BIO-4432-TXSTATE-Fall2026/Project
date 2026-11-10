from __future__ import annotations

import bz2
import json
import re

import pytest

from hmp_project.cli.genomes import genbank_to_fasta, genome_name, list_genomes
from hmp_project.manifest import Spec
from hmp_project.manifest.sync import sync

GENBANK = b"""LOCUS       ACIK02000001     12 bp    DNA     linear   BCT 01-JAN-2010
DEFINITION  Example contig one.
VERSION     ACIK02000001.1
FEATURES             Location/Qualifiers
ORIGIN
        1 acgtacgtac gt
//
LOCUS       ACIK02000002      4 bp    DNA     linear   BCT 01-JAN-2010
ORIGIN
        1 ttaa
//
"""


@pytest.fixture
def synced(tmp_path, make_provider):
    """Sync a spec over ``{key: bytes}`` and return a function listing its genomes."""

    def build(objects: dict[str, bytes], **fields):
        provider = make_provider(objects)
        path = tmp_path / "manifests" / "refs.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"dataset": "hmp", "prefix": "reference_genomes", **fields}))
        spec = Spec.load(path)
        sync(spec, tmp_path / "data", provider=provider)
        return lambda **kw: list_genomes(spec, tmp_path / "data", provider=provider, **kw)

    return build


def test_genomes_are_named_by_directory_and_made_readable(synced):
    listing = synced(
        {
            "reference_genomes/111/111.AAAA01000001.nuc.fsa": b">c1\nACGT\n",
            "reference_genomes/222/222.BBBB01000001.nuc.fsa.bz2": bz2.compress(b">c2\nTTTT\n"),
            "reference_genomes/333/333.ACIK02000001.nuc.gbk": GENBANK,
            # Not sequence: carried by a spec, never handed to the finder.
            "reference_genomes/111/strains.xlsx": b"sheet",
        }
    )
    genomes = listing()

    assert list(genomes) == ["111", "222", "333"]
    assert genomes["222"].name == "222.BBBB01000001.nuc.fsa"
    assert genomes["222"].read_text() == ">c2\nTTTT\n"
    assert not genomes["222"].with_name("222.BBBB01000001.nuc.fsa.bz2").exists()
    assert genomes["333"].read_text() == ">ACIK02000001.1\nACGTACGTACGT\n>ACIK02000002\nTTAA\n"


def test_two_files_for_one_genome_are_refused(synced):
    # HMP's draft layout: contigs and scaffolds of one assembly in one directory.
    listing = synced(
        {
            "reference_genomes/444/444.ACBX02000001-ACBX02000073.nuc.fsa": b">c\nA\n",
            "reference_genomes/444/444.GG703852-GG703878.nuc.fsa": b">s\nA\n",
        }
    )
    listed = "444: 444.ACBX02000001-ACBX02000073.nuc.fsa, 444.GG703852-GG703878.nuc.fsa"
    with pytest.raises(ValueError, match=re.escape(listed)):
        listing()


def test_the_spec_can_choose_which_file_stands_for_a_genome(synced):
    listing = synced(
        {
            "reference_genomes/444/444.ACBX02000001-ACBX02000073.nuc.fsa": b">c\nA\n",
            "reference_genomes/444/444.GG703852-GG703878.nuc.fsa": b">s\nA\n",
        },
        exclude=["444/444.GG703852-GG703878.nuc.fsa"],
    )
    assert listing()["444"].name == "444.ACBX02000001-ACBX02000073.nuc.fsa"


def test_a_listed_genome_missing_from_disk_is_an_error(synced):
    listing = synced({"reference_genomes/111/111.nuc.fsa": b">c\nA\n"})
    next(iter(listing().values())).unlink()
    with pytest.raises(ValueError, match="1 listed files not downloaded"):
        listing()


def test_genome_names_from_files_keep_the_assembly_version(tmp_path):
    path = tmp_path / "GCF_000009045.2.fna.gz"
    assert genome_name(path, "file") == "GCF_000009045.2"
    assert genome_name(tmp_path / "x" / "y.fsa", "dir") == "x"


def test_genbank_without_sequence_is_refused(tmp_path):
    src = tmp_path / "a.gbk"
    src.write_text("LOCUS       X  0 bp\nORIGIN\n//\n")
    with pytest.raises(ValueError, match="record X has no sequence"):
        genbank_to_fasta(src, tmp_path / "a.fa")
