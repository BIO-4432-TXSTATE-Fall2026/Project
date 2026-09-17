from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from hmp_project.manifest import Spec, sha256_file
from hmp_project.sync import sync

V13 = "HHS/HMQCP/otu_table_v13.txt.gz"
V35 = "HHS/HMQCP/nested/otu_table_v35.txt.gz"


def lock_of(spec: Spec) -> dict:
    return json.loads(spec.lock_path.read_text())


def test_first_sync_downloads_selection_and_writes_lock(tmp_path, provider, write_spec):
    spec = write_spec(exclude=["*.old"])

    result = sync(spec, tmp_path / "data", provider=provider)

    assert provider.downloads == [V35, V13]
    assert (tmp_path / "data/demo/otu_table_v13.txt.gz").read_bytes() == b"v13"
    assert (tmp_path / "data/demo/nested/otu_table_v35.txt.gz").read_bytes() == b"v35"
    assert result.added == [V35, V13]

    lock = lock_of(spec)
    assert lock["source"] == "fake://bucket/HHS/HMQCP/"
    assert [f["key"] for f in lock["files"]] == [V35, V13]
    assert lock["files"][1]["sha256"] == sha256_file(tmp_path / "data/demo/otu_table_v13.txt.gz")
    assert lock["files"][1]["last_modified"] == "2014-03-17T00:00:00Z"
    [entry] = lock["history"]
    assert entry["downloaded"] == [V35, V13]
    assert entry["tooling"]["provider"] == {"type": "fake"}


def test_resync_without_changes_downloads_nothing_and_keeps_history(tmp_path, provider, write_spec):
    spec = write_spec(exclude=["*.old"])
    sync(spec, tmp_path / "data", provider=provider)
    provider.downloads.clear()

    result = sync(spec, tmp_path / "data", provider=provider)

    assert provider.downloads == []
    assert result.added == result.changed == result.removed == []
    assert len(lock_of(spec)["history"]) == 1


def test_upstream_changes_are_refetched_and_recorded(tmp_path, provider, write_spec):
    spec = write_spec(exclude=["*.old"])
    sync(spec, tmp_path / "data", provider=provider)
    provider.downloads.clear()
    provider.put(V13, b"v13 revised", when=datetime(2020, 1, 1, tzinfo=UTC))
    del provider.objects[V35]

    result = sync(spec, tmp_path / "data", provider=provider)

    assert provider.downloads == [V13]
    assert result.changed == [V13]
    assert result.removed == [V35]
    assert (tmp_path / "data/demo/nested/otu_table_v35.txt.gz").exists()  # never deleted
    lock = lock_of(spec)
    assert [f["key"] for f in lock["files"]] == [V13]
    assert lock["history"][-1]["changed"] == [V13]
    assert lock["history"][-1]["removed"] == [V35]


def test_locally_missing_file_is_refetched_without_being_reported_changed(
    tmp_path, provider, write_spec
):
    spec = write_spec(exclude=["*.old"])
    sync(spec, tmp_path / "data", provider=provider)
    provider.downloads.clear()
    (tmp_path / "data/demo/otu_table_v13.txt.gz").unlink()

    result = sync(spec, tmp_path / "data", provider=provider)

    assert provider.downloads == [V13]
    assert result.changed == []
    assert lock_of(spec)["history"][-1]["downloaded"] == [V13]


def test_dry_run_writes_nothing(tmp_path, provider, write_spec):
    spec = write_spec()

    result = sync(spec, tmp_path / "data", provider=provider, dry_run=True)

    assert len(result.downloaded) == 3
    assert provider.downloads == []
    assert not spec.lock_path.exists()
    assert not (tmp_path / "data").exists()


def test_dry_run_reports_upstream_change_as_changed_not_removed(tmp_path, provider, write_spec):
    spec = write_spec(exclude=["*.old"])
    sync(spec, tmp_path / "data", provider=provider)
    provider.put(V13, b"v13 revised")

    result = sync(spec, tmp_path / "data", provider=provider, dry_run=True)

    assert result.changed == [V13]
    assert result.removed == []


def test_no_download_records_listing_then_real_sync_fills_hashes(tmp_path, provider, write_spec):
    spec = write_spec(exclude=["*.old"])

    result = sync(spec, tmp_path / "data", provider=provider, download=False)

    assert provider.downloads == []
    assert result.added == [V35, V13]
    assert not (tmp_path / "data").exists()
    lock = lock_of(spec)
    assert [(f["key"], f["sha256"], f["downloaded_at"]) for f in lock["files"]] == [
        (V35, None, None),
        (V13, None, None),
    ]
    assert lock["history"][-1]["downloaded"] == []

    result = sync(spec, tmp_path / "data", provider=provider)

    assert provider.downloads == [V35, V13]
    assert result.added == result.changed == []
    assert all(f["sha256"] for f in lock_of(spec)["files"])


def test_include_filters_relative_to_prefix(tmp_path, provider, write_spec):
    spec = write_spec(include=["nested/*"])

    sync(spec, tmp_path / "data", provider=provider)

    assert provider.downloads == [V35]


def test_spec_rejects_unknown_fields_and_lockfiles(tmp_path, write_spec):
    spec = write_spec()
    with pytest.raises(ValueError, match="lockfile"):
        Spec.load(spec.lock_path)

    spec.path.write_text(json.dumps({"dataset": "hmp", "prefix": "x", "bucket": "y"}))
    with pytest.raises(ValueError, match="unknown spec fields"):
        Spec.load(spec.path)


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ({"dataset": "sra", "prefix": "sra/", "accessions": ["SRR059395"]}, "not both"),
        ({"dataset": "sra"}, "not both"),
        ({"dataset": "sra", "accessions": []}, "'accessions' is empty"),
    ],
)
def test_spec_requires_exactly_one_of_prefix_and_accessions(write_spec, raw, message):
    spec = write_spec()
    spec.path.write_text(json.dumps(raw))

    with pytest.raises(ValueError, match=message):
        Spec.load(spec.path)


def test_accession_spec_fetches_only_its_runs_each_in_its_own_directory(tmp_path, make_provider):
    provider = make_provider(
        {
            "sra/ERR1014220/ERR1014220": b"one",
            "sra/ERR1014221/ERR1014221": b"two",
            "sra/ERR9999999/ERR9999999": b"not selected",
        }
    )
    path = tmp_path / "manifests" / "salter.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"dataset": "sra", "accessions": ["ERR1014220", "ERR1014221"]}))
    spec = Spec.load(path)

    result = sync(spec, tmp_path / "data", provider=provider)

    assert (tmp_path / "data/salter/ERR1014220/ERR1014220").read_bytes() == b"one"
    assert (tmp_path / "data/salter/ERR1014221/ERR1014221").read_bytes() == b"two"
    assert not (tmp_path / "data/salter/ERR9999999").exists()
    assert result.files == 2
    assert lock_of(spec)["source"] == "fake://bucket/sra/"


def test_a_single_accession_still_gets_its_own_directory(tmp_path, make_provider):
    provider = make_provider({"sra/ERR1014220/ERR1014220": b"one"})
    path = tmp_path / "manifests" / "one.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"dataset": "sra", "accessions": ["ERR1014220"]}))

    sync(Spec.load(path), tmp_path / "data", provider=provider)

    assert (tmp_path / "data/one/ERR1014220/ERR1014220").read_bytes() == b"one"
