from __future__ import annotations

import json

import pytest

from hmp_project.cli import main


def test_new_writes_spec_and_refuses_overwrite(tmp_path):
    manifests = tmp_path / "manifests"
    argv = [
        "new",
        "hmp-hmqcp",
        "--dataset=hmp",
        "--prefix=HHS/HMQCP",
        "--include=otu_table_psn_v*.txt.gz",
        "--exclude=*.old",
        f"--manifests-dir={manifests}",
    ]

    assert main(argv) == 0
    assert json.loads((manifests / "hmp-hmqcp.json").read_text()) == {
        "dataset": "hmp",
        "prefix": "HHS/HMQCP",
        "include": ["otu_table_psn_v*.txt.gz"],
        "exclude": ["*.old"],
    }
    with pytest.raises(SystemExit, match="already exists"):
        main(argv)


@pytest.mark.parametrize("name", ["Bad Name", "../escape", "demo.lock"])
def test_new_rejects_bad_names(tmp_path, name):
    with pytest.raises(SystemExit, match="invalid spec name"):
        main(["new", name, "--dataset=hmp", "--prefix=x", f"--manifests-dir={tmp_path}"])


def test_new_writes_an_accession_spec(tmp_path):
    argv = [
        "new",
        "salter",
        "--dataset=sra",
        "--accession=ERR1014220",
        "--accession=ERR1014221",
        f"--manifests-dir={tmp_path}",
    ]

    assert main(argv) == 0
    assert json.loads((tmp_path / "salter.json").read_text()) == {
        "dataset": "sra",
        "accessions": ["ERR1014220", "ERR1014221"],
        "include": ["*"],
    }


def test_new_rejects_an_accession_that_names_no_run(tmp_path):
    argv = ["new", "salter", "--dataset=sra", "--accession=SRS011098"]

    with pytest.raises(SystemExit, match="is not an SRA run accession"):
        main([*argv, f"--manifests-dir={tmp_path}"])
    assert not (tmp_path / "salter.json").exists()


@pytest.mark.parametrize("extra", [[], ["--prefix=sra/", "--accession=SRR059395"]])
def test_new_requires_exactly_one_of_prefix_and_accession(tmp_path, extra):
    argv = ["new", "demo", "--dataset=sra", *extra, f"--manifests-dir={tmp_path}"]

    with pytest.raises(SystemExit, match="either --prefix or --accession"):
        main(argv)
    assert not (tmp_path / "demo.json").exists()
