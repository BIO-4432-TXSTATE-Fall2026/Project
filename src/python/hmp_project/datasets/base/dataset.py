from __future__ import annotations

from collections.abc import Callable, Container, Iterable, Iterator
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, ClassVar

from hmp_project.providers import Provider, RemoteObject


@dataclass(frozen=True)
class Profile:
    """Extra columns one study encodes in free text, and how to read them out of a row.

    A catalog's generic fields do not carry a study's experimental design. Submitters put
    it in a sample alias or description, in whatever shape they chose, so reading it back
    is per-study work that no generic column can do. A profile keeps one study's shape in
    one documented place, named on the command line by whoever extracts that study's rows,
    rather than leaving every reader of the table to re-guess the convention.
    """

    #: Appended to the dataset's :data:`~Dataset.EXTRACT_COLUMNS`, in this order.
    columns: tuple[str, ...]
    #: A parsed catalog row to the values of :data:`columns`.
    read: Callable[[dict[str, Any]], dict[str, str]]


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

    #: Column order for :meth:`extract`, set by datasets that are metadata tables.
    EXTRACT_COLUMNS: ClassVar[tuple[str, ...]] = ()

    #: The study-specific extras :meth:`extract` can add, by profile name.
    EXTRACT_PROFILES: ClassVar[dict[str, Profile]] = {}

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

    def extract_profile(self, name: str | None) -> Profile | None:
        """The :class:`Profile` called ``name``, or ``None`` for no profile."""
        if name is None:
            return None
        profile = self.EXTRACT_PROFILES.get(name)
        if profile is None:
            known = ", ".join(sorted(self.EXTRACT_PROFILES)) or "none"
            raise ValueError(f"unknown extract profile {name!r} (this dataset has: {known})")
        return profile

    def extract(
        self, path: Path, accessions: Container[str], *, profile: Profile | None = None
    ) -> Iterator[dict[str, str]]:
        """Yield the rows of the metadata table at ``path`` that ``accessions`` names, as
        dicts keyed by :data:`EXTRACT_COLUMNS`, plus ``profile``'s columns if it is given.

        Only datasets that are catalogs rather than payload override this. They own their
        own row format, so nothing above them has to know it.
        """
        raise ValueError(f"{type(self).__name__} is not a metadata table; nothing to extract")
