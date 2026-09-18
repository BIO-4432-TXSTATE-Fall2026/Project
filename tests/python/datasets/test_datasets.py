from __future__ import annotations

from typing import ClassVar

import boto3
import pytest

from hmp_project.datasets import (
    DATASETS,
    Dataset,
    HMPDataset,
    S3Dataset,
    SRADataset,
    SRAMetadataDataset,
)


class TwoRegionDataset(S3Dataset):
    BUCKETS: ClassVar[dict[str, str]] = {
        "us-east-1": "data-use1",
        "us-east-2": "data-use2",
        "eu-west-1": "data-euw1",
    }


@pytest.mark.parametrize(
    ("region", "expected"),
    [
        (None, "us-east-1"),
        ("us-east-2", "us-east-2"),
        ("EU-West-1", "eu-west-1"),
        ("eu", "eu-west-1"),
        ("west", "eu-west-1"),
        ("east-2", "us-east-2"),
    ],
)
def test_resolve_region_accepts_codes_and_unambiguous_parts(region, expected):
    assert TwoRegionDataset.resolve_region(region) == expected


@pytest.mark.parametrize(
    ("region", "message"),
    [
        ("east", "ambiguous"),
        ("ea", "not available"),
        ("us-west-2", "not available"),
        ("", "not available"),
    ],
)
def test_resolve_region_rejects_unavailable_or_ambiguous(region, message):
    with pytest.raises(ValueError, match=message):
        TwoRegionDataset.resolve_region(region)


@pytest.mark.parametrize("name", sorted(DATASETS))
def test_registered_dataset_regions_are_real_s3_regions(name):
    known = set(boto3.session.Session().get_available_regions("s3"))
    assert DATASETS[name].BUCKETS
    assert set(DATASETS[name].BUCKETS) <= known


def test_dataset_uses_the_bucket_for_its_region():
    dataset = SRAMetadataDataset("sra/metadata", region="east")

    assert dataset.region == "us-east-1"
    assert dataset.provider.describe()["bucket"] == "sra-pub-metadata-us-east-1"
    assert dataset.provider.describe()["region"] == "us-east-1"


def test_sra_dataset_turns_accessions_into_one_prefix_each():
    dataset = SRADataset(accessions=["ERR1014220", "SRR059395"])

    assert dataset.region == "us-east-1"
    assert dataset.provider.describe()["bucket"] == "sra-pub-run-odp"
    assert dataset.prefixes == ("sra/ERR1014220/", "sra/SRR059395/")
    assert dataset.root_prefix == "sra/"


@pytest.mark.parametrize(
    "accession",
    ["SRS011098", "ERP006808", "SRR", "SRR12", "sra/SRR059395", "../escape", "", "srr059395"],
)
def test_sra_dataset_rejects_accessions_that_name_no_run(accession):
    with pytest.raises(ValueError, match="is not an SRA run accession"):
        SRADataset.accession_prefix(accession)


def test_prefix_datasets_reject_accessions():
    with pytest.raises(ValueError, match="selects by prefix, not by accession"):
        HMPDataset(accessions=["SRR059395"])


def test_select_spans_every_prefix_and_yields_overlaps_once(make_provider):
    provider = make_provider({"sra/ERR1/ERR1": b"a", "sra/ERR2/ERR2": b"b", "sra/ERR3/ERR3": b"c"})
    dataset = Dataset(provider, ["sra/ERR3/", "sra/ERR1/", "sra/"])

    assert [obj.key for obj in dataset.select()] == [
        "sra/ERR1/ERR1",
        "sra/ERR2/ERR2",
        "sra/ERR3/ERR3",
    ]


def test_sibling_prefixes_holding_the_same_filename_do_not_collide(tmp_path, make_provider):
    provider = make_provider({"wgs/stool/SRS1.tar": b"a", "wgs/tongue_dorsum/SRS1.tar": b"b"})
    dataset = Dataset(provider, ["wgs/stool/", "wgs/tongue_dorsum/"])

    assert dataset.root_prefix == "wgs/"
    assert [dataset.local_path(obj.key, tmp_path) for obj in dataset.select()] == [
        tmp_path / "stool/SRS1.tar",
        tmp_path / "tongue_dorsum/SRS1.tar",
    ]


def test_a_single_prefix_still_mirrors_keys_below_that_prefix(tmp_path, make_provider):
    provider = make_provider({"HHS/HMQCP/nested/otu.txt": b"x"})
    dataset = Dataset(provider, ["HHS/HMQCP"])

    [obj] = dataset.select()
    assert dataset.root_prefix == "HHS/HMQCP/"
    assert dataset.local_path(obj.key, tmp_path) == tmp_path / "nested/otu.txt"
