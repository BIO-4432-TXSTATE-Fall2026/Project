"""The manifest system: the files in ``manifests/`` and the commands that act on them.

``<name>.json`` says what to fetch and is written by the ``new`` command.
``<name>.lock.json`` is written by :mod:`~hmp_project.manifest.sync` and records what was
fetched, plus a history entry for every run that changed something, so upstream changes
stay visible in version control.

The format lives in :mod:`~hmp_project.manifest.spec` and :mod:`~hmp_project.manifest.lock`
and is re-exported here. The operations keep their own modules, since
:func:`~hmp_project.manifest.sync.sync` and :func:`~hmp_project.manifest.convert.convert`
share a name with the module holding them; import those from the submodule.
"""

from __future__ import annotations

from hmp_project.manifest.dataset import open_dataset
from hmp_project.manifest.lock import read_lock, sha256_file, write_lock
from hmp_project.manifest.spec import LOCK_SUFFIX, Spec, write_spec

__all__ = [
    "LOCK_SUFFIX",
    "Spec",
    "open_dataset",
    "read_lock",
    "sha256_file",
    "write_lock",
    "write_spec",
]
