from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RemoteObject:
    """One file as the remote reports it."""

    key: str
    size: int
    etag: str
    last_modified: datetime


class Provider(ABC):
    """Lists and downloads objects from a remote store, byte for byte."""

    @abstractmethod
    def uri(self, key: str) -> str:
        """Return a URI for ``key`` (or a prefix) suitable for recording in a manifest."""

    @abstractmethod
    def list_objects(self, prefix: str) -> Iterator[RemoteObject]:
        """Yield every object whose key starts with ``prefix``."""

    @abstractmethod
    def download(self, obj: RemoteObject, dest: Path) -> None:
        """Write ``obj`` to ``dest``, creating parent directories as needed."""

    @abstractmethod
    def download_range(self, obj: RemoteObject, start: int, end: int, dest: Path) -> None:
        """Write bytes ``[start, end)`` of ``obj`` to ``dest``, creating parent directories
        as needed. Fails if the remote object no longer matches ``obj``'s ETag.
        """

    @abstractmethod
    def describe(self) -> dict[str, Any]:
        """Return the provider's configuration and library versions for the manifest."""
