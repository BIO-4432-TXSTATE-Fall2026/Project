from __future__ import annotations

import json
from typing import ClassVar

import boto3
import pytest

from hmp_project.cli import main
from hmp_project.datasets import DATASETS, S3Dataset, SRAMetadataDataset, open_dataset


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


def test_open_dataset_rejects_spec_region_the_dataset_lacks(write_spec, provider):
    spec = write_spec(region="eu-west-1")

    with pytest.raises(ValueError, match=r"demo\.json: hmp: region 'eu-west-1' is not available"):
        open_dataset(spec, provider)


def test_new_records_resolved_region(tmp_path):
    argv = ["new", "sra", "--dataset=sra-metadata", "--region=east", "--prefix=sra/metadata"]

    assert main([*argv, f"--manifests-dir={tmp_path}"]) == 0
    assert json.loads((tmp_path / "sra.json").read_text()) == {
        "dataset": "sra-metadata",
        "region": "us-east-1",
        "prefix": "sra/metadata",
        "include": ["*"],
    }


def test_new_rejects_unavailable_region(tmp_path):
    argv = ["new", "sra", "--dataset=sra-metadata", "--region=west", "--prefix=sra/metadata"]

    with pytest.raises(SystemExit, match="sra-metadata: region 'west' is not available"):
        main([*argv, f"--manifests-dir={tmp_path}"])
    assert not (tmp_path / "sra.json").exists()
