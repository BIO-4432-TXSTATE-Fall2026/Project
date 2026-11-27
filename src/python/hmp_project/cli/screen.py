"""``screen``: count, per locus, the fragments a k-mer screen matched.

Reads the FASTA bbduk writes for the reads that matched a reference, run with
``rename=t``. That option appends the matched references to each header, tab separated,
each with the number of k-mers it hit::

    >chrT desc_100-199<TAB>L000007|a|c:0-1=16<TAB>L000009|b|c:0-1=6

A reference is a record of ``tr-loci.fa``, named ``<locus_id>|<genome>|<contig>:<l>-<r>``,
so the locus id is the name up to the first ``|``. Each locus is counted once per
fragment, however many of its records or k-mers the fragment hit.

bbduk credits a k-mer shared by several references to the first one loaded, so a fragment
is only ever credited to the loci that own the k-mers it hit. Sequence lines are skipped:
only headers carry matches.

Output is ``locus_id`` and ``fragments``, sorted by locus, for the loci that were hit; a
locus missing from it was not matched.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

ID_SEPARATOR = "|"
COLUMNS = ("locus_id", "fragments")


def add_parser(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "screen", help="count per locus the fragments bbduk (rename=t) matched, from stdin"
    )
    parser.add_argument(
        "--in", dest="source", type=Path, help="matched-fragment FASTA; default: stdin"
    )
    parser.add_argument("--out", type=Path, default=Path("screen.tsv"))
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> None:
    try:
        if args.source is None:
            counts = count_fragments(sys.stdin)
        else:
            with args.source.open() as f:
                counts = count_fragments(f)
    except ValueError as error:
        raise SystemExit(str(error)) from None
    args.out.write_text(
        "\t".join(COLUMNS)
        + "\n"
        + "".join(f"{locus}\t{n}\n" for locus, n in sorted(counts.items()))
    )
    print(f"{sum(counts.values())} fragment hits over {len(counts)} loci -> {args.out}")


def matched_loci(header: str) -> set[str]:
    """The locus ids a ``rename=t`` header names. A header with no matches names none."""
    _, *matches = header.rstrip("\n").split("\t")
    loci = set()
    for match in matches:
        name, sep, count = match.rpartition("=")
        if not sep or not count.isdigit() or not name:
            raise ValueError(f"not a matched reference, expected name=count: {match!r}")
        loci.add(name.split(ID_SEPARATOR, 1)[0])
    return loci


def count_fragments(lines: Iterable[str]) -> Counter[str]:
    """Fragments matched per locus id, over the headers in ``lines``."""
    counts: Counter[str] = Counter()
    for line in lines:
        if line.startswith(">"):
            counts.update(matched_loci(line))
    return counts
