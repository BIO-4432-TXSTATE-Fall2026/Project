"""Command line interface. Specs and lockfiles in ``manifests/`` are only ever written here.

One module per subcommand, each exposing ``add_parser`` to register its arguments and
handler. :data:`SUBCOMMANDS` fixes the order they appear in ``--help``.
"""

from __future__ import annotations

import argparse

from hmp_project.cli import convert, extract, new, sync

SUBCOMMANDS = (new, sync, convert, extract)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hmp_project")
    commands = parser.add_subparsers(dest="command", required=True)
    for subcommand in SUBCOMMANDS:
        subcommand.add_parser(commands)
    args = parser.parse_args(argv)
    args.handler(args)
    return 0


__all__ = ["SUBCOMMANDS", "main"]
