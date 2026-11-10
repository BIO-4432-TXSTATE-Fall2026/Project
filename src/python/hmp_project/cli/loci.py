"""``loci``: the filter's reference -- every catalog locus with its flanks, as FASTA.

The gate in ``filter`` keeps a read if it shares a k-mer with this reference, so each
tract is written with ``--flank`` bases either side: a read that reaches into a locus
from its anchor is as wanted as one that sits on the repeat.

Records that come out byte-identical are written once. Six genomes per genus repeat
near-identical loci, and duplicate sequence only inflates the gate's k-mer table. That
is not the locus merge -- loci that differ by a base stay apart -- just enough to keep
the table small.

Genomes are read through inTRuder's :func:`~intruder.trcore.io.read_fasta`, the reader
the catalog was built with, so contig names here are the catalog's by construction.
It is imported when the command runs, since intruder and pyfastx live in the catalog
environment rather than the default one.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LociResult:
    loci: int = 0
    records: int = 0


def add_parser(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "loci", help="write each catalog locus and its flanks as the filter's reference FASTA"
    )
    parser.add_argument("catalog", type=Path, metavar="CATALOG", help="a TR catalog TSV")
    parser.add_argument(
        "--genomes",
        type=Path,
        required=True,
        metavar="TSV",
        help="genome name and FASTA path per line, named as the catalog names them",
    )
    parser.add_argument("--flank", type=int, default=50, help="bases kept either side")
    parser.add_argument("--out", type=Path, default=Path("tr-loci.fa"))
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> None:
    if args.flank < 0:
        raise SystemExit("--flank must not be negative")
    try:
        result = build_loci(args.catalog, read_genomes(args.genomes), args.out, flank=args.flank)
    except ValueError as error:
        raise SystemExit(f"{args.catalog}: {error}") from None
    print(f"{args.catalog}: {result.loci} loci -> {result.records} records in {args.out}")


def read_genomes(path: Path) -> dict[str, Path]:
    genomes: dict[str, Path] = {}
    for line in path.read_text().splitlines():
        if line.strip():
            name, fasta = line.split("\t")
            genomes[name] = Path(fasta)
    return genomes


def read_catalog(path: Path) -> dict[tuple[str, str], list[tuple[int, int]]]:
    """The catalog's loci, grouped by ``(genome, contig)``. Coordinates are 0-based
    half-open, as inTRuder writes them, so they slice a contig directly.
    """
    loci: dict[tuple[str, str], list[tuple[int, int]]] = defaultdict(list)
    with path.open(newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            loci[row["genome"], row["contig"]].append((int(row["start"]), int(row["end"])))
    return loci


def build_loci(catalog: Path, genomes: dict[str, Path], out: Path, *, flank: int) -> LociResult:
    """Write every locus in ``catalog``, padded by ``flank`` and clipped to its contig,
    to ``out`` as FASTA, skipping any record whose sequence was already written.

    Fails rather than writing a partial reference when a locus names a genome or contig
    that ``genomes`` cannot supply: a gate missing loci passes a sample's reads short
    without saying so.
    """
    from intruder.trcore.io import read_fasta

    loci = read_catalog(catalog)
    missing = sorted({genome for genome, _ in loci} - genomes.keys())
    if missing:
        raise ValueError(f"no FASTA for genomes {missing}")

    result = LociResult()
    seen: set[str] = set()
    out.parent.mkdir(parents=True, exist_ok=True)
    partial = out.with_name(f".{out.name}.part")
    with partial.open("w") as f:
        for genome in sorted({genome for genome, _ in loci}):
            for record in read_fasta(genomes[genome]):
                intervals = loci.pop((genome, record.name), [])
                length = len(record.sequence)
                for start, end in sorted(intervals):
                    result.loci += 1
                    left, right = max(0, start - flank), min(length, end + flank)
                    sequence = record.sequence[left:right]
                    if sequence in seen:
                        continue
                    seen.add(sequence)
                    f.write(f">{genome}|{record.name}:{left}-{right}\n{sequence}\n")
                    result.records += 1
    if loci:
        unmatched = sorted(f"{genome}/{contig}" for genome, contig in loci)
        partial.unlink()
        raise ValueError(f"contigs not in their genome's FASTA: {unmatched}")
    partial.replace(out)
    return result
