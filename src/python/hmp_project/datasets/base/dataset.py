from __future__ import annotations

from collections.abc import Iterable
from fnmatch import fnmatchcase
from pathlib import Path

from hmp_project.providers import Provider, RemoteObject


class Dataset:
    """The objects under ``prefix`` whose key, relative to the prefix, matches an
    ``include`` glob and no ``exclude`` glob. Globs follow :func:`fnmatch.fnmatchcase`,
    so ``*`` also matches ``/``.
    """

    def __init__(
        self,
        provider: Provider,
        prefix: str,
        *,
        include: Iterable[str] = ("*",),
        exclude: Iterable[str] = (),
    ) -> None:
        self.provider = provider
        self.prefix = prefix if not prefix or prefix.endswith("/") else f"{prefix}/"
        self.include = tuple(include)
        self.exclude = tuple(exclude)

    def select(self) -> list[RemoteObject]:
        selected = []
        for obj in self.provider.list_objects(self.prefix):
            relative = obj.key.removeprefix(self.prefix)
            if not relative or relative.endswith("/"):  # directory placeholder objects
                continue
            if any(fnmatchcase(relative, p) for p in self.include) and not any(
                fnmatchcase(relative, p) for p in self.exclude
            ):
                selected.append(obj)
        return sorted(selected, key=lambda obj: obj.key)

    def local_path(self, obj: RemoteObject, root: Path) -> Path:
        """Where ``obj`` is stored under ``root``, mirroring its key below the prefix."""
        parts = [part for part in obj.key.removeprefix(self.prefix).split("/") if part]
        if not parts or any(part in (".", "..") for part in parts):
            raise ValueError(f"refusing to map key {obj.key!r} to a local path")
        return root.joinpath(*parts)
