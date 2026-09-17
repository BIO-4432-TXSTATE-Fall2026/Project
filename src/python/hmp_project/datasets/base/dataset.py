from __future__ import annotations

from collections.abc import Iterable
from fnmatch import fnmatchcase
from pathlib import Path

from hmp_project.providers import Provider, RemoteObject


def _as_prefix(prefix: str) -> str:
    return prefix if not prefix or prefix.endswith("/") else f"{prefix}/"


def parent_prefix(prefix: str) -> str:
    """The prefix one ``/``-delimited level above ``prefix``; ``""`` at the top."""
    head, _, _ = _as_prefix(prefix).rstrip("/").rpartition("/")
    return _as_prefix(head)


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

    Globs match, and local paths are mirrored, relative to ``root_prefix``. It defaults to
    the prefixes' common parent rather than each prefix, so two prefixes holding the same
    filename stay distinct on disk; with a single prefix that parent is the prefix itself.
    """

    def __init__(
        self,
        provider: Provider,
        prefixes: Iterable[str],
        *,
        include: Iterable[str] = ("*",),
        exclude: Iterable[str] = (),
        root_prefix: str | None = None,
    ) -> None:
        self.provider = provider
        self.prefixes = tuple(dict.fromkeys(_as_prefix(prefix) for prefix in prefixes))
        if not self.prefixes:
            raise ValueError("a dataset needs at least one prefix")
        common = _common_prefix(self.prefixes)
        self.root_prefix = common if root_prefix is None else _as_prefix(root_prefix)
        if not common.startswith(self.root_prefix):
            raise ValueError(f"root prefix {root_prefix!r} does not contain every prefix")
        self.include = tuple(include)
        self.exclude = tuple(exclude)

    def matches(self, key: str) -> bool:
        """Whether ``key`` passes the globs, relative to ``root_prefix``."""
        relative = key.removeprefix(self.root_prefix)
        if not relative or relative.endswith("/"):  # directory placeholder objects
            return False
        return any(fnmatchcase(relative, p) for p in self.include) and not any(
            fnmatchcase(relative, p) for p in self.exclude
        )

    def select(self) -> list[RemoteObject]:
        # Keyed by key, so overlapping prefixes yield each object once.
        selected: dict[str, RemoteObject] = {}
        for prefix in self.prefixes:
            for obj in self.provider.list_objects(prefix):
                if self.matches(obj.key):
                    selected[obj.key] = obj
        return sorted(selected.values(), key=lambda obj: obj.key)

    def download(self, obj: RemoteObject, dest: Path) -> None:
        """Write a selected object to ``dest``. Datasets whose selected objects are not
        remote objects themselves, such as byte ranges of one, override this.
        """
        self.provider.download(obj, dest)

    def local_path(self, key: str, root: Path) -> Path:
        """Where the object at ``key`` is stored under ``root``, mirroring the key below
        ``root_prefix``.
        """
        parts = [part for part in key.removeprefix(self.root_prefix).split("/") if part]
        if not parts or any(part in (".", "..") for part in parts):
            raise ValueError(f"refusing to map key {key!r} to a local path")
        return root.joinpath(*parts)

    def convert(self, path: Path, *, threads: int | None = None) -> list[Path]:
        """Derive analysis-ready files beside the synced file at ``path`` and return their
        paths. The synced file is kept, since ``sync`` checks it against the lock.
        Datasets whose files are usable as downloaded do not override this.
        """
        raise ValueError(f"{type(self).__name__} files are used as downloaded; nothing to convert")
