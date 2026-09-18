from __future__ import annotations

import pytest

from hmp_project.cli import main
from hmp_project.manifest.sync import sync


def test_cli_convert_reports_errors_without_a_traceback(tmp_path, provider, write_spec):
    spec = write_spec(exclude=["*.old"])
    sync(spec, tmp_path / "data", provider=provider)

    with pytest.raises(SystemExit, match="demo: HMPDataset files are used as downloaded"):
        main(["convert", str(spec.path), f"--data-dir={tmp_path / 'data'}"])
