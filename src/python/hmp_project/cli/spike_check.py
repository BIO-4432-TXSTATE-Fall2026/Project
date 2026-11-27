"""``spike-check``: score the allele caller against genomes whose repeat lengths are known.

``SIMULATE_READS`` draws reads from each kit genome, so every locus that genome is a member
of has a known allele: the ``rep_length`` of its ``tr-panel.tsv`` row. The reads then go
through the gate and ``alleles`` as any sample's do, in samples named
``<genome>@<reads>``. This compares what was called with what is there, so it checks the
whole path, gate and caller together, with no biology in it.

Per sample the locus's call is its most-supported allele length, a tie going to the shorter.
The output has one row per sample:

- ``genome`` and ``reads`` (the pairs simulated), from the sample name.
- ``loci_expected``: panel loci the genome is a member of.
- ``loci_called``: expected loci with at least one spanning read. Coverage, which grows
  with depth.
- ``exact_fraction``: of the called loci, the share whose call is exactly the true length.
- ``within_one_unit_fraction``: the share within one motif length of it.
- ``loci_unexpected``: loci called that the genome is not a member of, such as a locus of
  another genome whose anchors this one also carries.

Fractions are over called loci, so a shallow sample is not penalised for the loci it did
not reach; ``NA`` when none were called. A genome with several panel rows for one locus
matches any of them.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

from hmp_project.cli.alleles import read_table

COLUMNS = (
    "genome",
    "reads",
    "loci_expected",
    "loci_called",
    "exact_fraction",
    "within_one_unit_fraction",
    "loci_unexpected",
)


def add_parser(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "spike-check", help="compare called alleles with the known lengths of simulated genomes"
    )
    parser.add_argument("--panel", type=Path, required=True, metavar="TSV", help="tr-panel.tsv")
    parser.add_argument("--alleles", type=Path, required=True, metavar="TSV")
    parser.add_argument(
        "--stats",
        type=Path,
        required=True,
        metavar="TSV",
        help="allele-stats.tsv, which lists every sample, including those with no allele",
    )
    parser.add_argument("--out", type=Path, default=Path("spike-check.tsv"))
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> None:
    try:
        rows = check(args.panel, args.alleles, args.stats)
    except ValueError as error:
        raise SystemExit(str(error)) from None
    with args.out.open("w", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    print(f"{len(rows)} spike samples -> {args.out}")


def split_sample(sample: str) -> tuple[str, int]:
    """``GCF_000009045.2@1000`` is ``("GCF_000009045.2", 1000)``."""
    genome, sep, reads = sample.rpartition("@")
    if not sep or not genome or not reads.isdigit():
        raise ValueError(f"{sample!r} is not a spike sample, expected <genome>@<reads>")
    return genome, int(reads)


def read_expected(panel: Path) -> dict[str, dict[str, list[tuple[int, int]]]]:
    """Per genome and locus id, the ``(rep_length, motif_length)`` of its panel rows."""
    expected: dict[str, dict[str, list[tuple[int, int]]]] = defaultdict(lambda: defaultdict(list))
    with panel.open(newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            expected[row["genome"]][row["locus_id"]].append(
                (int(row["rep_length"]), int(row["motif_length"]))
            )
    return expected


def read_samples(stats: Path) -> list[str]:
    with stats.open(newline="") as f:
        return sorted(row["sample"] for row in csv.DictReader(f, delimiter="\t"))


def modal_calls(counts: Counter[tuple[str, int]]) -> dict[str, int]:
    """Each locus's most-supported allele length, the shorter on a tie."""
    best: dict[str, tuple[int, int]] = {}
    for (locus, allele), reads in counts.items():
        if locus not in best or (-reads, allele) < (-best[locus][0], best[locus][1]):
            best[locus] = (reads, allele)
    return {locus: allele for locus, (_, allele) in best.items()}


def check(panel: Path, alleles: Path, stats: Path) -> list[list[str | int]]:
    expected = read_expected(panel)
    table = read_table(alleles)
    rows: list[list[str | int]] = []
    for sample in read_samples(stats):
        genome, reads = split_sample(sample)
        if genome not in expected:
            raise ValueError(f"{sample}: {genome} is not a genome in {panel}")
        truth = expected[genome]
        calls = modal_calls(table.get(sample, Counter()))
        called = {locus: allele for locus, allele in calls.items() if locus in truth}
        exact = sum(
            any(allele == length for length, _ in truth[locus]) for locus, allele in called.items()
        )
        near = sum(
            any(abs(allele - length) <= unit for length, unit in truth[locus])
            for locus, allele in called.items()
        )
        rows.append(
            [
                genome,
                reads,
                len(truth),
                len(called),
                f"{exact / len(called):.4f}" if called else "NA",
                f"{near / len(called):.4f}" if called else "NA",
                len(calls) - len(called),
            ]
        )
    return rows
