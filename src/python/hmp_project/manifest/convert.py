"""Derive analysis-ready files from a spec's synced files, e.g. FASTQ from SRA archives."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from hmp_project.manifest.dataset import open_dataset
from hmp_project.manifest.lock import read_lock
from hmp_project.manifest.spec import Spec
from hmp_project.providers import Provider


@dataclass
class ConvertResult:
    files: int = 0
    outputs: list[Path] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


def convert(
    spec: Spec,
    data_dir: Path,
    *,
    threads: int | None = None,
    provider: Provider | None = None,
) -> ConvertResult:
    """Convert every file in the spec's lock that is on disk under ``data_dir/<spec name>``.

    Works from the lock rather than the remote, so it runs offline. Files the lock lists
    but that were never downloaded (``sync --no-download``) are reported as missing.
    """
    lock = read_lock(spec.lock_path)
    if lock is None:
        raise ValueError(f"{spec.lock_path} not found; sync the spec first")
    dataset = open_dataset(spec, provider)
    root = data_dir / spec.name

    result = ConvertResult()
    for record in lock["files"]:
        path = dataset.local_path(record["key"], root)
        if record["sha256"] is None or not path.is_file():
            result.missing.append(record["key"])
            continue
        result.outputs.extend(dataset.convert(path, threads=threads))
        result.files += 1
    return result
