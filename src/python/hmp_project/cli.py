"""Command line interface. Specs and lockfiles in ``manifests/`` are only ever written here."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from hmp_project.datasets import DATASETS
from hmp_project.manifest import Spec, write_spec
from hmp_project.sync import sync

NAME = re.compile(r"[a-z0-9][a-z0-9._-]*")


def _size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1000:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1000
    return f"{n:.1f} TB"


def _new(args: argparse.Namespace) -> None:
    if not NAME.fullmatch(args.name) or args.name.endswith(".lock"):
        raise SystemExit(f"invalid spec name {args.name!r}: use lowercase letters, digits, . _ -")
    path = args.manifests_dir / f"{args.name}.json"
    try:
        spec = write_spec(
            path,
            dataset=args.dataset,
            prefix=args.prefix,
            include=args.include or ["*"],
            exclude=args.exclude,
            description=args.description,
        )
    except FileExistsError:
        raise SystemExit(f"{path} already exists") from None
    print(f"wrote {spec.path}; run `sync {spec.path}` to download")


def _sync(args: argparse.Namespace) -> None:
    for path in args.specs:
        spec = Spec.load(path)
        result = sync(spec, args.data_dir, dry_run=args.dry_run, download=not args.no_download)
        verb = "would download" if args.dry_run else "downloaded"
        print(
            f"{spec.name}: {result.files} files ({_size(result.bytes)}); "
            f"{len(result.added)} added, {len(result.changed)} changed, "
            f"{len(result.removed)} removed; {verb} {len(result.downloaded)}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hmp_project")
    commands = parser.add_subparsers(dest="command", required=True)

    new = commands.add_parser("new", help="create a dataset spec in the manifests directory")
    new.add_argument("name", help="spec name; becomes <manifests-dir>/<name>.json")
    new.add_argument("--dataset", required=True, choices=sorted(DATASETS))
    new.add_argument("--prefix", required=True, help="remote prefix, e.g. HHS/HMQCP")
    new.add_argument(
        "--include", action="append", default=[], metavar="GLOB", help="repeatable; default *"
    )
    new.add_argument("--exclude", action="append", default=[], metavar="GLOB", help="repeatable")
    new.add_argument("--description", default="")
    new.add_argument("--manifests-dir", type=Path, default=Path("manifests"))
    new.set_defaults(handler=_new)

    sync_parser = commands.add_parser(
        "sync", help="download the files a spec selects and update its lockfile"
    )
    sync_parser.add_argument("specs", nargs="+", type=Path, metavar="SPEC")
    sync_parser.add_argument("--data-dir", type=Path, default=Path("data"))
    sync_parser.add_argument(
        "--dry-run", action="store_true", help="report what would change; write nothing"
    )
    sync_parser.add_argument(
        "--no-download",
        action="store_true",
        help="record the remote listing in the lockfile without downloading files",
    )
    sync_parser.set_defaults(handler=_sync)

    args = parser.parse_args(argv)
    args.handler(args)
    return 0
