"""Bring a dataset's local files and its lockfile in line with its spec."""

from __future__ import annotations

import platform
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

from hmp_project.datasets import open_dataset
from hmp_project.manifest import Spec, read_lock, sha256_file, write_lock
from hmp_project.providers import Provider, RemoteObject


@dataclass
class SyncResult:
    files: int = 0
    bytes: int = 0
    added: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    downloaded: list[str] = field(default_factory=list)


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _matches(record: dict[str, Any], obj: RemoteObject) -> bool:
    return (record["size"], record["etag"], record["last_modified"]) == (
        obj.size,
        obj.etag,
        _timestamp(obj.last_modified),
    )


def sync(
    spec: Spec,
    data_dir: Path,
    *,
    dry_run: bool = False,
    download: bool = True,
    provider: Provider | None = None,
) -> SyncResult:
    """Download new, changed, or locally missing files into ``data_dir/<spec name>``.

    With ``download=False`` the lock records the remote listing only; files never
    fetched have a null ``sha256`` and ``downloaded_at``. Files that disappear
    upstream are dropped from the lock but left on disk. The lock gains a history
    entry only when a run adds, changes, removes, or downloads something, or the
    spec itself changed.
    """
    dataset = open_dataset(spec, provider)
    lock = read_lock(spec.lock_path)
    previous = {record["key"]: record for record in lock["files"]} if lock else {}
    root = data_dir / spec.name
    now = _timestamp(datetime.now(UTC))

    result = SyncResult()
    records = []
    selected = dataset.select()
    for obj in selected:
        dest = dataset.local_path(obj.key, root)
        record = previous.get(obj.key)
        if record is None:
            result.added.append(obj.key)
        elif not _matches(record, obj):
            result.changed.append(obj.key)
        stale = record is not None and not _matches(record, obj)
        present = dest.is_file() and dest.stat().st_size == obj.size

        result.files += 1
        result.bytes += obj.size
        if present and not stale:
            if record is not None and record["sha256"] is not None:
                sha256, downloaded_at = record["sha256"], record["downloaded_at"]
            else:
                # On disk but never hashed (interrupted run, or listed only): adopt it.
                sha256, downloaded_at = sha256_file(dest), now
        elif not download:
            kept = record if record is not None and not stale else None
            sha256 = kept["sha256"] if kept else None
            downloaded_at = kept["downloaded_at"] if kept else None
        else:
            result.downloaded.append(obj.key)
            if dry_run:
                continue
            dataset.provider.download(obj, dest)
            if dest.stat().st_size != obj.size:
                raise OSError(f"{dest}: expected {obj.size} bytes, got {dest.stat().st_size}")
            sha256, downloaded_at = sha256_file(dest), now

        records.append(
            {
                "key": obj.key,
                "size": obj.size,
                "etag": obj.etag,
                "last_modified": _timestamp(obj.last_modified),
                "sha256": sha256,
                "downloaded_at": downloaded_at,
            }
        )

    result.removed = sorted(previous.keys() - {obj.key for obj in selected})
    if dry_run:
        return result

    history = lock["history"] if lock else []
    spec_sha256 = sha256_file(spec.path)
    spec_changed = not history or history[-1]["spec_sha256"] != spec_sha256
    if spec_changed or result.added or result.changed or result.removed or result.downloaded:
        history.append(
            {
                "synced_at": now,
                "spec_sha256": spec_sha256,
                "tooling": {
                    "hmp_project": version("hmp_project"),
                    "python": platform.python_version(),
                    "provider": dataset.provider.describe(),
                },
                "files": result.files,
                "bytes": result.bytes,
                "added": result.added,
                "changed": result.changed,
                "removed": result.removed,
                "downloaded": result.downloaded,
            }
        )

    write_lock(
        spec.lock_path,
        {
            "spec": spec.path.name,
            "dataset": spec.dataset,
            "source": dataset.provider.uri(dataset.root_prefix),
            "files": records,
            "history": history,
        },
    )
    return result
