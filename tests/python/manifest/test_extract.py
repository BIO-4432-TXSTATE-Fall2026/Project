from __future__ import annotations

import gzip
import json

import pytest

from hmp_project.manifest import Spec
from hmp_project.manifest.extract import accessions_in_lock, extract
from hmp_project.manifest.sync import sync

# One HMP sample's Illumina WGS run and its 16S run, plus a run belonging to nobody.
ROWS = [
    {
        "acc": "SRR060082",
        "sample_acc": "SRS011084",
        "sra_study": "SRP002163",
        "center_name": "BCM",
        "releasedate": "2010-07-15",
        "platform": "ILLUMINA",
        "instrument": "Illumina Genome Analyzer II",
        "librarylayout": "PAIRED",
        "assay_type": "WGS",
        "mbases": "5766",
    },
    {
        "acc": "SRR045646",
        "sample_acc": "SRS011084",
        "sra_study": "SRP002163",
        "center_name": "WUGSC",
        "releasedate": "2010-08-09",
        "platform": "LS454",
        "instrument": "454 GS FLX Titanium",
        "librarylayout": "SINGLE",
        "assay_type": "AMPLICON",
        "mbases": "392",
    },
    {
        "acc": "SRR999999",
        "sample_acc": "SRS999999",
        "sra_study": "SRP999999",
        "center_name": "SOMEWHERE",
        "releasedate": "2017-03-15",
        "platform": "LS454",
        "instrument": "454 GS FLX Titanium",
        "librarylayout": "SINGLE",
        "assay_type": "CTS",
        "mbases": "3",
    },
]

# Three Salter et al. (2014) runs, whose kit and dilution step are only in the sample
# alias: one plain, one whose kit name itself contains the separator, and the negative
# water control, which names neither.
SALTER = [
    {
        "acc": acc,
        "sample_acc": sample,
        "sra_study": "ERP006808",
        "center_name": "UBP-CNRS",
        "releasedate": "2014-08-31",
        "platform": "ILLUMINA",
        "instrument": "Illumina MiSeq",
        "librarylayout": "PAIRED",
        "assay_type": "WGS",
        "mbases": "0",
        "jattr": json.dumps({"alias_sam": [alias]}),
    }
    for acc, sample, alias in [
        ("ERR588923", "ERS534918", "CAMBIO_4"),
        ("ERR588939", "ERS534934", "MP_BIO_10"),
        ("ERR588954", "ERS534949", "Water"),
    ]
]


def shard(rows):
    return gzip.compress(b"".join(json.dumps(row).encode() + b"\n" for row in rows))


@pytest.fixture
def freeze(tmp_path, make_provider):
    """An ``sra-metadata`` spec over two synced JSON Lines shards."""
    provider = make_provider(
        {
            "sra/metadata_json/sra.metadata.000.json.gz": shard(ROWS[:2]),
            "sra/metadata_json/sra.metadata.001.json.gz": shard(ROWS[2:] + SALTER),
        }
    )
    path = tmp_path / "manifests" / "freeze.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"dataset": "sra-metadata", "prefix": "sra/metadata_json"}))
    spec = Spec.load(path)
    sync(spec, tmp_path / "data", provider=provider)
    return spec, provider


def read_tsv(path):
    header, *lines = path.read_text().splitlines()
    return [dict(zip(header.split("\t"), line.split("\t"), strict=True)) for line in lines]


def test_extract_keeps_only_the_wanted_samples(tmp_path, freeze):
    spec, provider = freeze

    result = extract(spec, tmp_path / "data", accessions={"SRS011084"}, provider=provider)

    assert result.files == 2
    assert result.rows == 2
    assert result.missing == []
    assert result.output == tmp_path / "data/derived/freeze.tsv"
    rows = read_tsv(result.output)
    assert [row["run"] for row in rows] == ["SRR045646", "SRR060082"]  # sorted, not shard order
    assert [row["center"] for row in rows] == ["WUGSC", "BCM"]
    assert [row["releasedate"] for row in rows] == ["2010-08-09", "2010-07-15"]


def test_extract_keeps_both_platforms_so_callers_can_filter(tmp_path, freeze):
    spec, provider = freeze

    extract(spec, tmp_path / "data", accessions={"SRS011084"}, provider=provider)

    rows = read_tsv(tmp_path / "data/derived/freeze.tsv")
    assert {row["platform"] for row in rows} == {"ILLUMINA", "LS454"}
    assert {row["assay_type"] for row in rows} == {"WGS", "AMPLICON"}


def test_extract_matches_a_study_as_well_as_a_sample(tmp_path, freeze):
    spec, provider = freeze

    result = extract(spec, tmp_path / "data", accessions={"SRP999999"}, provider=provider)

    assert [row["run"] for row in read_tsv(result.output)] == ["SRR999999"]


def test_extract_profile_reads_the_kit_and_dilution_out_of_the_sample_alias(tmp_path, freeze):
    spec, provider = freeze

    result = extract(
        spec, tmp_path / "data", accessions={"ERP006808"}, profile="salter", provider=provider
    )

    rows = read_tsv(result.output)
    assert [(row["run"], row["alias"], row["kit"], row["dilution"]) for row in rows] == [
        ("ERR588923", "CAMBIO_4", "CAMBIO", "4"),
        # The separator is in the kit name too, so only the trailing number is the step.
        ("ERR588939", "MP_BIO_10", "MP_BIO", "10"),
        # The water control is a kitless, dilutionless row rather than a missing one.
        ("ERR588954", "Water", "", ""),
    ]


def test_extract_adds_no_profile_columns_when_no_profile_is_named(tmp_path, freeze):
    spec, provider = freeze

    result = extract(spec, tmp_path / "data", accessions={"ERP006808"}, provider=provider)

    assert all(column not in read_tsv(result.output)[0] for column in ("alias", "kit", "dilution"))


def test_extract_rejects_an_unknown_profile(tmp_path, freeze):
    spec, provider = freeze

    with pytest.raises(ValueError, match="unknown extract profile 'zeller'"):
        extract(
            spec, tmp_path / "data", accessions={"ERP006808"}, profile="zeller", provider=provider
        )


def test_extract_reports_shards_that_were_never_downloaded(tmp_path, freeze):
    spec, provider = freeze
    (tmp_path / "data/freeze/sra.metadata.001.json.gz").unlink()

    result = extract(spec, tmp_path / "data", accessions={"SRS999999"}, provider=provider)

    assert result.files == 1
    assert result.rows == 0
    assert result.missing == ["sra/metadata_json/sra.metadata.001.json.gz"]


def test_extract_skips_rebuilding_output_newer_than_the_lock(tmp_path, freeze):
    spec, provider = freeze
    extract(spec, tmp_path / "data", accessions={"SRS011084"}, provider=provider)
    out = tmp_path / "data/derived/freeze.tsv"
    out.write_text("stale\n")

    result = extract(spec, tmp_path / "data", accessions={"SRS011084"}, provider=provider)

    assert result.skipped
    assert out.read_text() == "stale\n"

    forced = extract(
        spec, tmp_path / "data", accessions={"SRS011084"}, force=True, provider=provider
    )
    assert not forced.skipped
    assert forced.rows == 2


def test_extract_needs_accessions_and_a_synced_spec(tmp_path, freeze):
    spec, provider = freeze

    with pytest.raises(ValueError, match="no accessions to look for"):
        extract(spec, tmp_path / "data", accessions=set(), provider=provider)

    other = tmp_path / "manifests" / "unsynced.json"
    other.write_text(json.dumps({"dataset": "sra-metadata", "prefix": "sra/metadata_json"}))
    with pytest.raises(ValueError, match="sync the spec first"):
        extract(Spec.load(other), tmp_path / "data", accessions={"SRS011084"})


def test_extract_rejects_datasets_that_are_not_metadata_tables(tmp_path, provider, write_spec):
    spec = write_spec(exclude=["*.old"])
    sync(spec, tmp_path / "data", provider=provider)

    with pytest.raises(ValueError, match="HMPDataset is not a metadata table"):
        extract(spec, tmp_path / "data", accessions={"SRS011084"}, provider=provider)


def test_accessions_in_lock_reads_the_samples_a_spec_already_covers(tmp_path, make_provider):
    provider = make_provider(
        {
            "HHS/HMASM/WGS/stool/SRS011084.tar.bz2": b"a",
            "HHS/HMASM/WGS/stool/SRS011239.tar.bz2": b"b",
        }
    )
    path = tmp_path / "manifests" / "hmp-stool.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"dataset": "hmp", "prefix": "HHS/HMASM/WGS/stool"}))
    spec = Spec.load(path)
    sync(spec, tmp_path / "data", download=False, provider=provider)

    assert accessions_in_lock(spec.lock_path) == {"SRS011084", "SRS011239"}
