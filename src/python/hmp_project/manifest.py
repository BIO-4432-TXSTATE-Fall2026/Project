"""Specs and lockfiles in ``manifests/``.

``<name>.json`` is written by hand and says what to fetch. ``<name>.lock.json`` is
written by ``sync`` and records what was fetched, plus a history entry for every run
that changed something, so upstream changes stay visible in version control.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LOCK_SUFFIX = ".lock.json"
SPEC_FIELDS = {"description", "dataset", "region", "prefix", "include", "exclude"}


@dataclass(frozen=True)
class Spec:
    path: Path
    dataset: str
    prefix: str
    include: tuple[str, ...] = ("*",)
    exclude: tuple[str, ...] = ()
    description: str = ""
    region: str | None = None  # None means the dataset's default region

    @classmethod
    def load(cls, path: Path) -> Spec:
        if path.name.endswith(LOCK_SUFFIX):
            raise ValueError(f"{path}: expected a spec, got a lockfile")
        raw = json.loads(path.read_text())
        unknown = raw.keys() - SPEC_FIELDS
        if unknown:
            raise ValueError(f"{path}: unknown spec fields {sorted(unknown)}")
        return cls(
            path=path,
            dataset=raw["dataset"],
            prefix=raw["prefix"],
            include=tuple(raw.get("include", ["*"])),
            exclude=tuple(raw.get("exclude", [])),
            description=raw.get("description", ""),
            region=raw.get("region"),
        )

    @property
    def name(self) -> str:
        return self.path.stem

    @property
    def lock_path(self) -> Path:
        return self.path.with_name(f"{self.name}{LOCK_SUFFIX}")


def write_spec(
    path: Path,
    *,
    dataset: str,
    prefix: str,
    include: list[str],
    exclude: list[str],
    description: str = "",
    region: str | None = None,
) -> Spec:
    """Create a new spec file. Refuses to overwrite, since the lock is tied to the spec."""
    if path.name.endswith(LOCK_SUFFIX):
        raise ValueError(f"{path}: spec names must not end in {LOCK_SUFFIX}")
    raw: dict[str, Any] = {"dataset": dataset}
    if region:
        raw["region"] = region
    raw |= {"prefix": prefix, "include": include}
    if exclude:
        raw["exclude"] = exclude
    if description:
        raw = {"description": description, **raw}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as f:
        f.write(json.dumps(raw, indent=2) + "\n")
    return Spec.load(path)


def read_lock(path: Path) -> dict[str, Any] | None:
    return json.loads(path.read_text()) if path.exists() else None


def write_lock(path: Path, lock: dict[str, Any]) -> None:
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(json.dumps(lock, indent=2) + "\n")
    os.replace(tmp, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()
