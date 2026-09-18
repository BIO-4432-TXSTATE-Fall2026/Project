"""``sync``: download the files a spec selects and update its lockfile."""

from __future__ import annotations

import argparse
from pathlib import Path

from hmp_project.manifest import Spec
from hmp_project.manifest.sync import sync


def format_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1000:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1000
    return f"{n:.1f} TB"


def add_parser(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "sync", help="download the files a spec selects and update its lockfile"
    )
    parser.add_argument("specs", nargs="+", type=Path, metavar="SPEC")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument(
        "--dry-run", action="store_true", help="report what would change; write nothing"
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="record the remote listing in the lockfile without downloading files",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> None:
    for path in args.specs:
        spec = Spec.load(path)
        result = sync(spec, args.data_dir, dry_run=args.dry_run, download=not args.no_download)
        verb = "would download" if args.dry_run else "downloaded"
        print(
            f"{spec.name}: {result.files} files ({format_size(result.bytes)}); "
            f"{len(result.added)} added, {len(result.changed)} changed, "
            f"{len(result.removed)} removed; {verb} {len(result.downloaded)}"
        )
