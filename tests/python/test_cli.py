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
