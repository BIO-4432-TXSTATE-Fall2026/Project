"""``<name>.lock.json``: what was fetched. Written by :func:`hmp_project.manifest.sync.sync`.

Every run that changes something appends a history entry, so upstream changes stay
visible in version control.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


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
