from __future__ import annotations

import json
import os
import stat

import pytest

from hmp_project.manifest import Spec
from hmp_project.manifest.convert import convert
from hmp_project.manifest.sync import sync

# Stands in for fasterq-dump: writes paired FASTQ for its first argument into --outdir
# and logs each call, or fails without output when FAKE_FAIL is set.
FAKE_FASTERQ_DUMP = """#!/bin/sh
src=$1; shift
while [ $# -gt 0 ]; do
  if [ "$1" = --outdir ]; then out=$2; shift; fi
  shift
done
echo "$src" >> "$FAKE_LOG"
[ -n "$FAKE_FAIL" ] && exit 3
name=$(basename "$src")
mkdir -p "$out"
printf '@%s.1\\nACGT\\n+\\nIIII\\n' "$name" > "$out/${name}_1.fastq"
printf '@%s.1\\nTGCA\\n+\\nIIII\\n' "$name" > "$out/${name}_2.fastq"
"""


@pytest.fixture
def fasterq_dump(tmp_path, monkeypatch):
    """Put a fake fasterq-dump first on PATH; returns a function listing its calls."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "fasterq-dump"
    script.write_text(FAKE_FASTERQ_DUMP)
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "fasterq-dump.log"
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_LOG", str(log))
    return lambda: log.read_text().split() if log.exists() else []


@pytest.fixture
def synced_runs(tmp_path, make_provider):
    """An ``sra`` spec for two runs, synced into ``tmp_path/data``."""
    provider = make_provider(
        {"sra/ERR1014220/ERR1014220": b"one", "sra/ERR1014221/ERR1014221": b"two"}
    )
    path = tmp_path / "manifests" / "salter.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"dataset": "sra", "accessions": ["ERR1014220", "ERR1014221"]}))
    spec = Spec.load(path)
    sync(spec, tmp_path / "data", provider=provider)
    return spec, provider


def test_convert_writes_fastq_beside_each_run_and_keeps_the_archive(
    tmp_path, fasterq_dump, synced_runs
):
    spec, provider = synced_runs
    run = tmp_path / "data/salter/ERR1014220"

    result = convert(spec, tmp_path / "data", provider=provider)

    assert result.files == 2
    assert result.missing == []
    assert (run / "ERR1014220_1.fastq").read_text().startswith("@ERR1014220.1")
    assert (run / "ERR1014220_2.fastq").is_file()
    assert (run / "ERR1014220").read_bytes() == b"one"
    assert sorted(p.name for p in run.iterdir()) == [  # no temporary directory left behind
        "ERR1014220",
        "ERR1014220_1.fastq",
        "ERR1014220_2.fastq",
    ]
    assert len(fasterq_dump()) == 2


def test_convert_skips_runs_already_converted_and_redoes_resynced_ones(
    tmp_path, fasterq_dump, synced_runs
):
    spec, provider = synced_runs
    convert(spec, tmp_path / "data", provider=provider)
    archive = tmp_path / "data/salter/ERR1014221/ERR1014221"
    later = archive.stat().st_mtime + 60
    os.utime(archive, (later, later))  # as if sync fetched a newer copy

    result = convert(spec, tmp_path / "data", provider=provider)

    assert result.files == 2
    assert len(result.outputs) == 4
    calls = fasterq_dump()
    assert len(calls) == 3
    assert calls[-1] == str(archive)


def test_convert_resync_leaves_the_lock_and_archive_untouched(tmp_path, fasterq_dump, synced_runs):
    spec, provider = synced_runs
    convert(spec, tmp_path / "data", provider=provider)
    provider.downloads.clear()

    result = sync(spec, tmp_path / "data", provider=provider)

    assert provider.downloads == []
    assert result.added == result.changed == result.removed == []


def test_failed_conversion_leaves_no_fastq(tmp_path, fasterq_dump, synced_runs, monkeypatch):
    spec, provider = synced_runs
    monkeypatch.setenv("FAKE_FAIL", "1")

    with pytest.raises(RuntimeError, match=r"fasterq-dump failed on .*ERR1014220 \(exit 3\)"):
        convert(spec, tmp_path / "data", provider=provider)

    run = tmp_path / "data/salter/ERR1014220"
    assert sorted(p.name for p in run.iterdir()) == ["ERR1014220"]


def test_convert_reports_runs_that_were_never_downloaded(tmp_path, fasterq_dump, synced_runs):
    spec, provider = synced_runs
    (tmp_path / "data/salter/ERR1014221/ERR1014221").unlink()

    result = convert(spec, tmp_path / "data", provider=provider)

    assert result.files == 1
    assert result.missing == ["sra/ERR1014221/ERR1014221"]


def test_convert_without_fasterq_dump_names_the_environment(tmp_path, synced_runs, monkeypatch):
    spec, provider = synced_runs
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))

    with pytest.raises(RuntimeError, match=r"fasterq-dump not found.*sra environment"):
        convert(spec, tmp_path / "data", provider=provider)


def test_convert_needs_a_synced_spec(tmp_path):
    path = tmp_path / "salter.json"
    path.write_text(json.dumps({"dataset": "sra", "accessions": ["ERR1014220"]}))

    with pytest.raises(ValueError, match="sync the spec first"):
        convert(Spec.load(path), tmp_path / "data")


def test_convert_rejects_datasets_used_as_downloaded(tmp_path, provider, write_spec):
    spec = write_spec(exclude=["*.old"])
    sync(spec, tmp_path / "data", provider=provider)

    with pytest.raises(ValueError, match="HMPDataset files are used as downloaded"):
        convert(spec, tmp_path / "data", provider=provider)
