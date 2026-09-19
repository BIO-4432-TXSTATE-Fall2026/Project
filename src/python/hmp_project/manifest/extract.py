"""Reduce a synced metadata table to the rows a project cares about.

``sync`` brings a catalog down whole, because none of them are partitioned by accession.
``extract`` reads it once and writes the handful of rows that matter to a TSV under
``data/derived/``, which is small enough to commit. The catalog itself can then be
deleted; re-syncing it is how you rebuild.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from hmp_project.manifest.dataset import open_dataset
from hmp_project.manifest.lock import read_lock
from hmp_project.manifest.spec import Spec
from hmp_project.providers import Provider

#: Any SRA accession: run, sample, study, experiment, submission, project.
ACCESSION = re.compile(r"[DES]R[APRSXZ][0-9]{6,}")

DERIVED = "derived"


@dataclass
class ExtractResult:
    files: int = 0
    rows: int = 0
    output: Path | None = None
    missing: list[str] = field(default_factory=list)
    skipped: bool = False


def accessions_in_lock(path: Path) -> set[str]:
    """Every SRA accession named by the keys in the lockfile at ``path``.

    HMP keys are ``.../stool/SRS011084.tar.bz2`` and SRA keys ``sra/SRR059395/SRR059395``,
    so the samples or runs a spec already covers can drive an extract without retyping
    a few hundred accessions.
    """
    lock = read_lock(path)
    if lock is None:
        raise ValueError(f"{path} not found")
    return {a for record in lock["files"] for a in ACCESSION.findall(record["key"])}


def default_output(spec: Spec, data_dir: Path) -> Path:
    return data_dir / DERIVED / f"{spec.name}.tsv"


def extract(
    spec: Spec,
    data_dir: Path,
    *,
    accessions: set[str],
    out: Path | None = None,
    force: bool = False,
    profile: str | None = None,
    provider: Provider | None = None,
) -> ExtractResult:
    """Write the rows of ``spec``'s synced files that ``accessions`` names to ``out``,
    with the extra columns of the extraction ``profile`` if one is named.

    Works from the lock, like ``convert``, so it runs offline. Files the lock lists but
    that are not on disk are reported as missing rather than silently skipped, since a
    partial catalog gives a quietly incomplete table. Output newer than the lock is left
    alone unless ``force``, so re-running after a plain ``sync`` costs nothing.
    """
    lock = read_lock(spec.lock_path)
    if lock is None:
        raise ValueError(f"{spec.lock_path} not found; sync the spec first")
    if not accessions:
        raise ValueError("no accessions to look for; give --accession or --from-lock")
    dataset = open_dataset(spec, provider)
    selected = dataset.extract_profile(profile)
    root = data_dir / spec.name
    out = out or default_output(spec, data_dir)

    result = ExtractResult(output=out)
    if not force and out.is_file() and out.stat().st_mtime >= spec.lock_path.stat().st_mtime:
        result.skipped = True
        return result

    paths = []
    for record in lock["files"]:
        path = dataset.local_path(record["key"], root)
        if path.is_file():
            paths.append(path)
        else:
            result.missing.append(record["key"])

    columns = dataset.EXTRACT_COLUMNS + (selected.columns if selected else ())
    rows: dict[tuple[str, ...], dict[str, str]] = {}
    for path in paths:
        for row in dataset.extract(path, accessions, profile=selected):
            # Keyed, so a run appearing twice cannot double-count a batch label.
            rows.setdefault(tuple(row[c] for c in columns), row)
        result.files += 1

    # Sorted rather than left in shard order: the output is committed, so it has to be
    # the same file every time it is rebuilt.
    out.parent.mkdir(parents=True, exist_ok=True)
    partial = out.with_name(f".{out.name}.part")
    with partial.open("w", newline="") as f:
        writer = csv.DictWriter(f, columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for key in sorted(rows):
            writer.writerow(rows[key])
    partial.replace(out)
    result.rows = len(rows)
    return result
