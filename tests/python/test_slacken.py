from __future__ import annotations

import json

import pytest

from hmp_project.datasets import SlackenDataset, open_dataset
from hmp_project.datasets.slacken import LIBRARY, assembly_spans
from hmp_project.manifest import Spec
from hmp_project.sync import sync

LINE_BASES = 4

# (accession, taxid, genome size in the summary, sequences in the library). The third is
# absent from the library, and the fourth's sequences fall short of its genome size.
ASSEMBLIES = [
    ("GCF_000000001.1", "10", 9, [("NZ_A1.1", "ACGTACGTA")]),
    ("GCF_000000002.1", "10", 6, [("NZ_B1.1", "GGGG"), ("NZ_B2.1", "TT")]),
    ("GCF_000000003.1", "20", 5, []),
    ("GCF_000000004.1", "30", 8, [("NZ_D1.1", "CCC")]),
    ("GCF_000000005.1", "10", 5, [("NZ_E1.1", "AAAAC")]),
]


def _record(accession: str, taxid: str, size: int) -> str:
    fields = ["na"] * 26
    fields[0], fields[5], fields[25] = accession, taxid, str(size)
    return "\t".join(fields) + "\n"


def _library() -> tuple[dict[str, bytes], dict[str, bytes]]:
    """Library files for ``ASSEMBLIES``, and each assembly's expected FASTA."""
    fasta, fai, expected = b"", "", {}
    for accession, taxid, _, sequences in ASSEMBLIES:
        start = len(fasta)
        for name, bases in sequences:
            fasta += f">kraken:taxid|{taxid}|{name} {accession}\n".encode()
            fai += f"kraken:taxid|{taxid}|{name}\t{len(bases)}\t{len(fasta)}\t{LINE_BASES}\t5\n"
            lines = [bases[i : i + LINE_BASES] for i in range(0, len(bases), LINE_BASES)]
            fasta += "".join(f"{line}\n" for line in lines).encode()
        expected[accession] = fasta[start:]
    # Listed out of order: the library follows the manifest sorted by path.
    manifest = "".join(
        f"output = all/GCF/000/000/00{accession[-3]}/{accession}_X/{accession}_X_genomic.fna.gz\n"
        f"url = https://example.org/{accession}\n"
        for accession, *_ in reversed(ASSEMBLIES)
    )
    summary = "".join(_record(accession, taxid, size) for accession, taxid, size, _ in ASSEMBLIES)
    files = {
        "library.fna": fasta,
        "library.fna.fai": fai.encode(),
        "manifest.txt": manifest.encode(),
        "assembly_summary.filter.txt": summary.encode(),
    }
    return {f"{LIBRARY}{name}": data for name, data in files.items()}, expected


@pytest.fixture(autouse=True)
def cache(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    return tmp_path / "cache"


@pytest.fixture
def library(make_provider):
    objects, expected = _library()
    return make_provider(objects), expected


def test_assembly_spans_cover_each_complete_assembly_by_manifest_path_order():
    objects, expected = _library()
    text = {key.removeprefix(LIBRARY): data.decode() for key, data in objects.items()}
    fasta = objects[f"{LIBRARY}library.fna"]

    spans = list(
        assembly_spans(
            text["library.fna.fai"].splitlines(),
            text["manifest.txt"].splitlines(),
            text["assembly_summary.filter.txt"].splitlines(),
        )
    )

    assert [accession for accession, *_ in spans] == [
        "GCF_000000001.1",
        "GCF_000000002.1",
        "GCF_000000005.1",
    ]
    for accession, start, end in spans:
        assert fasta[start:end] == expected[accession]


def test_assembly_spans_reject_sequences_left_over():
    fai = ["kraken:taxid|10|NZ_A1.1\t4\t10\t4\t5", "kraken:taxid|99|NZ_Z1.1\t4\t25\t4\t5"]
    manifest = ["output = all/GCF/000/000/001/GCF_000000001.1_X/x.fna.gz"]
    summary = [_record("GCF_000000001.1", "10", 4)]

    with pytest.raises(ValueError, match="no manifest assembly accounts for"):
        list(assembly_spans(fai, manifest, summary))


def test_sync_writes_each_assembly_cut_from_the_library(tmp_path, library):
    provider, expected = library
    path = tmp_path / "refs.json"
    accessions = ["GCF_000000005.1", "GCF_000000002.1"]
    path.write_text(json.dumps({"dataset": "slacken", "accessions": accessions}))
    spec = Spec.load(path)

    result = sync(spec, tmp_path / "data", provider=provider)

    root = tmp_path / "data" / "refs"
    for accession in accessions:
        assert (root / accession / f"{accession}.fna").read_bytes() == expected[accession]
    lock = json.loads(spec.lock_path.read_text())
    library_etag = next(provider.list_objects(f"{LIBRARY}library.fna")).etag
    assert lock["source"] == "fake://bucket/index/rspc-224/library/bacteria/"
    assert {record["etag"] for record in lock["files"]} == {library_etag}
    assert result.downloaded == [
        f"{LIBRARY}GCF_000000002.1/GCF_000000002.1.fna",
        f"{LIBRARY}GCF_000000005.1/GCF_000000005.1.fna",
    ]


def test_index_files_are_fetched_once_per_library_version(library):
    provider, _ = library
    SlackenDataset(accessions=["GCF_000000001.1"], provider=provider).select()
    provider.downloads.clear()

    SlackenDataset(accessions=["GCF_000000002.1"], provider=provider).select()
    assert provider.downloads == []

    provider.put(f"{LIBRARY}manifest.txt", provider.objects[f"{LIBRARY}manifest.txt"][0] + b"\n")
    SlackenDataset(accessions=["GCF_000000002.1"], provider=provider).select()
    assert len(provider.downloads) == 3


@pytest.mark.parametrize("accession", ["GCF_000000003.1", "GCF_000000004.1", "GCF_000000009.1"])
def test_select_rejects_assemblies_the_library_cannot_supply(library, accession):
    provider, _ = library

    with pytest.raises(ValueError, match=f"{accession} is not in"):
        SlackenDataset(accessions=[accession], provider=provider).select()


@pytest.mark.parametrize("accession", ["GCA_000000001.1", "GCF_000000001", "GCF_1.1", "../x"])
def test_accession_prefix_rejects_non_refseq_assembly_accessions(accession):
    with pytest.raises(ValueError, match="is not a RefSeq assembly accession"):
        SlackenDataset.accession_prefix(accession)


def test_prefix_selects_bucket_objects_as_is(tmp_path, library):
    provider, _ = library
    path = tmp_path / "summary.json"
    spec_fields = {"prefix": LIBRARY, "include": ["assembly_summary*"]}
    path.write_text(json.dumps({"dataset": "slacken", **spec_fields}))

    dataset = open_dataset(Spec.load(path), provider)

    assert [obj.key for obj in dataset.select()] == [f"{LIBRARY}assembly_summary.filter.txt"]
