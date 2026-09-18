from __future__ import annotations

import json

import pytest

from hmp_project.manifest import Spec, open_dataset


def test_open_dataset_rejects_spec_region_the_dataset_lacks(write_spec, provider):
    spec = write_spec(region="eu-west-1")

    with pytest.raises(ValueError, match=r"demo\.json: hmp: region 'eu-west-1' is not available"):
        open_dataset(spec, provider)


def test_open_dataset_reports_a_bad_accession_with_the_spec_path(tmp_path):
    path = tmp_path / "salter.json"
    path.write_text(json.dumps({"dataset": "sra", "accessions": ["SRS011098"]}))

    with pytest.raises(ValueError, match=r"salter\.json: sra: 'SRS011098' is not an SRA run"):
        open_dataset(Spec.load(path))
