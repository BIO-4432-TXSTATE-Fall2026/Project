"""``extract``: reduce a spec's synced metadata table to the rows a project cares about."""

from __future__ import annotations

import argparse
from pathlib import Path

from hmp_project.manifest import Spec
from hmp_project.manifest.extract import accessions_in_lock, extract


def add_parser(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "extract", help="write the rows of a spec's synced metadata table to a TSV"
    )
    parser.add_argument("spec", type=Path, metavar="SPEC")
    parser.add_argument(
        "--accession",
        action="append",
        default=[],
        metavar="ACC",
        help="repeatable; keep rows naming this sample or study, e.g. ERP006808",
    )
    parser.add_argument(
        "--from-lock",
        action="append",
        default=[],
        type=Path,
        metavar="LOCK",
        help="repeatable; keep rows for every accession named in this lockfile's keys",
    )
    parser.add_argument(
        "--profile",
        metavar="NAME",
        help="add the columns a study encodes in free text, e.g. salter (kit, dilution)",
    )
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, help="default: <data-dir>/derived/<spec>.tsv")
    parser.add_argument(
        "--force", action="store_true", help="rebuild even if the output is newer than the lock"
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> None:
    spec = Spec.load(args.spec)
    accessions = set(args.accession)
    try:
        for lock in args.from_lock:
            accessions |= accessions_in_lock(lock)
        result = extract(
            spec,
            args.data_dir,
            accessions=accessions,
            out=args.out,
            force=args.force,
            profile=args.profile,
        )
    except ValueError as error:
        raise SystemExit(f"{spec.name}: {error}") from None
    if result.skipped:
        print(f"{spec.name}: {result.output} is newer than the lock; nothing to do (--force)")
        return
    missing = f"; {len(result.missing)} not downloaded" if result.missing else ""
    print(
        f"{spec.name}: {result.rows} rows for {len(accessions)} accessions "
        f"from {result.files} files -> {result.output}{missing}"
    )
