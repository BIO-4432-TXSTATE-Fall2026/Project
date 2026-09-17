from __future__ import annotations

from collections.abc import Iterable
from fnmatch import fnmatchcase
from pathlib import Path

from hmp_project.providers import Provider, RemoteObject


def _as_prefix(prefix: str) -> str:
    return prefix if not prefix or prefix.endswith("/") else f"{prefix}/"


def _common_prefix(prefixes: tuple[str, ...]) -> str:
    """The longest ``/``-delimited prefix every entry of ``prefixes`` starts with."""
    shared: list[str] = []
    for parts in zip(*(prefix.split("/")[:-1] for prefix in prefixes), strict=False):
        if len(set(parts)) != 1:
            break
        shared.append(parts[0])
    return "".join(f"{part}/" for part in shared)


class Dataset:
    """The objects under any of ``prefixes`` whose key matches an ``include`` glob and no
    ``exclude`` glob. Globs follow :func:`fnmatch.fnmatchcase`, so ``*`` also matches ``/``.

    Globs match, and local paths are mirrored, relative to the prefixes' common parent
    rather than to each prefix, so two prefixes holding the same filename stay distinct
    on disk. With a single prefix that parent is the prefix itself.
    """

    def __init__(
        self,
        provider: Provider,
        prefixes: Iterable[str],
        *,
        include: Iterable[str] = ("*",),
        exclude: Iterable[str] = (),
    ) -> None:
        self.provider = provider
        self.prefixes = tuple(dict.fromkeys(_as_prefix(prefix) for prefix in prefixes))
        if not self.prefixes:
            raise ValueError("a dataset needs at least one prefix")
        self.root_prefix = _common_prefix(self.prefixes)
        self.include = tuple(include)
        self.exclude = tuple(exclude)

    def select(self) -> list[RemoteObject]:
        # Keyed by key, so overlapping prefixes yield each object once.
        selected: dict[str, RemoteObject] = {}
        for prefix in self.prefixes:
            for obj in self.provider.list_objects(prefix):
                relative = obj.key.removeprefix(self.root_prefix)
                if not relative or relative.endswith("/"):  # directory placeholder objects
                    continue
                if any(fnmatchcase(relative, p) for p in self.include) and not any(
                    fnmatchcase(relative, p) for p in self.exclude
                ):
                    selected[obj.key] = obj
        return sorted(selected.values(), key=lambda obj: obj.key)

    def local_path(self, obj: RemoteObject, root: Path) -> Path:
        """Where ``obj`` is stored under ``root``, mirroring its key below the prefixes'
        common parent.
        """
        parts = [part for part in obj.key.removeprefix(self.root_prefix).split("/") if part]
        if not parts or any(part in (".", "..") for part in parts):
            raise ValueError(f"refusing to map key {obj.key!r} to a local path")
        return root.joinpath(*parts)
