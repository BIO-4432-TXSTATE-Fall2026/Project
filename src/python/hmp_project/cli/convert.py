"""``convert``: derive analysis-ready files from a spec's synced files."""

from __future__ import annotations

import argparse
from pathlib import Path

from hmp_project.manifest import Spec
from hmp_project.manifest.convert import convert


def add_parser(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "convert", help="derive analysis-ready files from a spec's synced files"
    )
    parser.add_argument("specs", nargs="+", type=Path, metavar="SPEC")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--threads", type=int, help="worker threads; default: the converter's own")
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> None:
    for path in args.specs:
        spec = Spec.load(path)
        try:
            result = convert(spec, args.data_dir, threads=args.threads)
        except (RuntimeError, ValueError) as error:
            raise SystemExit(f"{spec.name}: {error}") from None
        missing = f"; {len(result.missing)} not downloaded" if result.missing else ""
        print(f"{spec.name}: {result.files} files converted to {len(result.outputs)}{missing}")
