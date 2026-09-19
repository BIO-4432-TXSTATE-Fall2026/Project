"""``<name>.json``: what to fetch. Written by the ``new`` command."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LOCK_SUFFIX = ".lock.json"
MANIFESTS_DIR = "manifests"
SPEC_FIELDS = {"description", "dataset", "region", "prefix", "accessions", "include", "exclude"}


@dataclass(frozen=True)
class Spec:
    path: Path
    dataset: str
    prefix: str = ""
    accessions: tuple[str, ...] = ()  # an alternative to prefix, for datasets that take them
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
        if ("prefix" in raw) == ("accessions" in raw):
            raise ValueError(f"{path}: give either 'prefix' or 'accessions', not both")
        accessions = tuple(raw.get("accessions") or ())
        if "accessions" in raw and not accessions:
            raise ValueError(f"{path}: 'accessions' is empty")
        return cls(
            path=path,
            dataset=raw["dataset"],
            prefix=raw.get("prefix", ""),
            accessions=accessions,
            include=tuple(raw.get("include", ["*"])),
            exclude=tuple(raw.get("exclude", [])),
            description=raw.get("description", ""),
            region=raw.get("region"),
        )

    @property
    def name(self) -> str:
        """The spec's path under the nearest ``manifests/`` directory, without ``.json``,
        so ``manifests/contaminants/kit.json`` is ``contaminants/kit``. A spec outside one,
        such as a copy staged into a pipeline work directory, is named by its stem.
        """
        parts = self.path.with_suffix("").parts
        for i in range(len(parts) - 2, -1, -1):
            if parts[i] == MANIFESTS_DIR:
                return "/".join(parts[i + 1 :])
        return self.path.stem

    @property
    def lock_path(self) -> Path:
        return self.path.with_name(f"{self.path.stem}{LOCK_SUFFIX}")


def write_spec(
    path: Path,
    *,
    dataset: str,
    include: list[str],
    exclude: list[str],
    prefix: str | None = None,
    accessions: list[str] | None = None,
    description: str = "",
    region: str | None = None,
) -> Spec:
    """Create a new spec file. Refuses to overwrite, since the lock is tied to the spec."""
    if path.name.endswith(LOCK_SUFFIX):
        raise ValueError(f"{path}: spec names must not end in {LOCK_SUFFIX}")
    if (prefix is None) == (not accessions):
        raise ValueError(f"{path}: give either a prefix or accessions, not both")
    raw: dict[str, Any] = {"dataset": dataset}
    if region:
        raw["region"] = region
    raw |= {"accessions": list(accessions)} if accessions else {"prefix": prefix}
    raw["include"] = include
    if exclude:
        raw["exclude"] = exclude
    if description:
        raw = {"description": description, **raw}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as f:
        f.write(json.dumps(raw, indent=2) + "\n")
    return Spec.load(path)
