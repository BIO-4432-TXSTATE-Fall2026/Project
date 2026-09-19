"""``new``: create a dataset spec in the manifests directory."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from hmp_project.datasets import DATASETS
from hmp_project.manifest import write_spec

SEGMENT = r"[a-z0-9][a-z0-9._-]*"
NAME = re.compile(rf"{SEGMENT}(/{SEGMENT})*")


def add_parser(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser("new", help="create a dataset spec in the manifests directory")
    parser.add_argument(
        "name", help="spec name, / for subdirectories; becomes <manifests-dir>/<name>.json"
    )
    parser.add_argument("--dataset", required=True, choices=sorted(DATASETS))
    parser.add_argument(
        "--region",
        help="AWS region, or an unambiguous part of one such as east; default: the dataset's first",
    )
    parser.add_argument("--prefix", help="remote prefix, e.g. HHS/HMQCP")
    parser.add_argument(
        "--accession",
        action="append",
        default=[],
        metavar="ACC",
        help="repeatable; select by accession instead of --prefix, e.g. SRR059395",
    )
    parser.add_argument(
        "--include", action="append", default=[], metavar="GLOB", help="repeatable; default *"
    )
    parser.add_argument("--exclude", action="append", default=[], metavar="GLOB", help="repeatable")
    parser.add_argument("--description", default="")
    parser.add_argument("--manifests-dir", type=Path, default=Path("manifests"))
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> None:
    if not NAME.fullmatch(args.name) or args.name.endswith(".lock"):
        raise SystemExit(
            f"invalid spec name {args.name!r}: use lowercase letters, digits, . _ - and /"
        )
    if (args.prefix is None) == (not args.accession):
        raise SystemExit("give either --prefix or --accession, not both")
    path = args.manifests_dir / f"{args.name}.json"
    dataset = DATASETS[args.dataset]
    region = None
    try:
        if args.region is not None:
            region = dataset.resolve_region(args.region)
        for accession in args.accession:
            dataset.accession_prefix(accession)
    except ValueError as error:
        raise SystemExit(f"{args.dataset}: {error}") from None
    try:
        spec = write_spec(
            path,
            dataset=args.dataset,
            region=region,
            prefix=args.prefix,
            accessions=args.accession,
            include=args.include or ["*"],
            exclude=args.exclude,
            description=args.description,
        )
    except FileExistsError:
        raise SystemExit(f"{path} already exists") from None
    print(f"wrote {spec.path}; run `sync {spec.path}` to download")
