from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from hmp_project.manifest import Spec
from hmp_project.providers import Provider, RemoteObject


class FakeProvider(Provider):
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects: dict[str, tuple[bytes, datetime]] = {}
        self.downloads: list[str] = []
        for key, data in objects.items():
            self.put(key, data)

    def put(self, key: str, data: bytes, when: datetime | None = None) -> None:
        self.objects[key] = (data, when or datetime(2014, 3, 17, tzinfo=UTC))

    def uri(self, key: str) -> str:
        return f"fake://bucket/{key}"

    def list_objects(self, prefix: str) -> Iterator[RemoteObject]:
        for key, (data, when) in sorted(self.objects.items()):
            if key.startswith(prefix):
                yield RemoteObject(key, len(data), hashlib.md5(data).hexdigest(), when)

    def download(self, obj: RemoteObject, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(self.objects[obj.key][0])
        self.downloads.append(obj.key)

    def describe(self) -> dict[str, Any]:
        return {"type": "fake"}


@pytest.fixture
def make_provider():
    """Build a :class:`FakeProvider` from ``{key: contents}``."""
    return FakeProvider


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider(
        {
            "HHS/HMQCP/otu_table_v13.txt.gz": b"v13",
            "HHS/HMQCP/otu_table_v13.txt.gz.old": b"old",
            "HHS/HMQCP/nested/otu_table_v35.txt.gz": b"v35",
            "HHS/HMQCPX/unrelated.txt": b"no",
        }
    )


@pytest.fixture
def write_spec(tmp_path: Path):
    def write(name: str = "demo", **fields: Any) -> Spec:
        path = tmp_path / "manifests" / f"{name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"dataset": "hmp", "prefix": "HHS/HMQCP", **fields}))
        return Spec.load(path)

    return write
