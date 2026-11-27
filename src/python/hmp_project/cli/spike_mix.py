"""``spike-mix``: contaminate real samples' allele tables with simulated genomes' alleles.

For every host sample, simulated genome and depth, the host's allele counts and the
genome's are summed into one sample, ``<host>+<genome>@<reads>``. These are labelled
contaminants for training and testing the contamination model: the host stays as it was
and a known number of a known genome's reads is added.

Mixing the allele tables is the same as mixing the reads. The gate and ``alleles`` judge
each read on its own, so a read's call does not depend on the reads beside it, and the
host's calls plus the genome's are the calls of the pooled reads. (Read names are not
shared between a host and a simulation, so no mate pair spans the two.)

Outputs:

- ``--out``: ``alleles-spiked.tsv``, ``sample, locus_id, allele_bp, reads`` in the shape of
  ``alleles.tsv``, counts summed.
- ``--labels``: ``spike-labels.tsv``, ``sample, host, batch, reads, locus_id, contaminant``,
  one row per locus with reads in the mix. ``batch`` is the genome, ``reads`` the simulated
  pairs added, and ``contaminant`` is ``true`` when the locus is a member of that genome in
  the panel: the loci the contaminant can contribute to.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from collections.abc import Iterable, Iterator
from pathlib import Path

from hmp_project.cli.alleles import ALLELE_COLUMNS, read_table
from hmp_project.cli.spike_check import read_expected, split_sample

LABEL_COLUMNS = ("sample", "host", "batch", "reads", "locus_id", "contaminant")


def add_parser(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "spike-mix", help="sum host and simulated-genome allele counts into labelled samples"
    )
    parser.add_argument("--panel", type=Path, required=True, metavar="TSV", help="tr-panel.tsv")
    parser.add_argument("--hosts", type=Path, required=True, metavar="TSV", help="alleles.tsv")
    parser.add_argument(
        "--host-samples",
        help="comma-separated hosts to use; default: every sample in --hosts",
    )
    parser.add_argument("--spikes", type=Path, required=True, metavar="TSV", help="spike alleles")
    parser.add_argument("--out", type=Path, default=Path("alleles-spiked.tsv"))
    parser.add_argument("--labels", type=Path, default=Path("spike-labels.tsv"))
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> None:
    hosts = read_table(args.hosts)
    wanted = [h.strip() for h in args.host_samples.split(",")] if args.host_samples else None
    try:
        if wanted is not None and (missing := [h for h in wanted if h not in hosts]):
            raise ValueError(f"not in {args.hosts}: {', '.join(missing)}")
        expected = read_expected(args.panel)
        count = write(
            args.out, args.labels, mix(hosts, read_table(args.spikes), expected, wanted), expected
        )
    except ValueError as error:
        raise SystemExit(str(error)) from None
    print(f"{count} spiked samples -> {args.out}, {args.labels}")


def mix(
    hosts: dict[str, Counter[tuple[str, int]]],
    spikes: dict[str, Counter[tuple[str, int]]],
    expected: dict,
    wanted: list[str] | None = None,
) -> Iterator[tuple[str, str, str, int, Counter[tuple[str, int]]]]:
    """``(sample, host, genome, reads, summed counts)`` for each host and spike, the sample
    named ``<host>+<genome>@<reads>``. One at a time, so only one mix is ever held."""
    for host in sorted(wanted if wanted is not None else hosts):
        for spike in sorted(spikes):
            genome, depth = split_sample(spike)
            if genome not in expected:
                raise ValueError(f"{spike}: {genome} is not a genome in the panel")
            yield f"{host}+{spike}", host, genome, depth, hosts[host] + spikes[spike]


def write(out: Path, labels: Path, mixed: Iterable, expected: dict) -> int:
    """Write both tables as ``mixed`` yields, and return how many samples there were."""
    count = 0
    with out.open("w", newline="") as f, labels.open("w", newline="") as g:
        alleles = csv.writer(f, delimiter="\t", lineterminator="\n")
        marks = csv.writer(g, delimiter="\t", lineterminator="\n")
        alleles.writerow(ALLELE_COLUMNS)
        marks.writerow(LABEL_COLUMNS)
        for sample, host, genome, depth, counts in mixed:
            count += 1
            for (locus, allele), reads in sorted(counts.items()):
                alleles.writerow([sample, locus, allele, reads])
            for locus in sorted({locus for locus, _ in counts}):
                member = str(locus in expected[genome]).lower()
                marks.writerow([sample, host, genome, depth, locus, member])
    return count
