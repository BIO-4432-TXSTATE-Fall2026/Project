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
        mixed = mix(hosts, read_table(args.spikes), expected, wanted)
    except ValueError as error:
        raise SystemExit(str(error)) from None
    write(args.out, args.labels, mixed, expected)
    print(f"{len(mixed)} spiked samples -> {args.out}, {args.labels}")


def mix(
    hosts: dict[str, Counter[tuple[str, int]]],
    spikes: dict[str, Counter[tuple[str, int]]],
    expected: dict,
    wanted: list[str] | None = None,
) -> dict[str, tuple[str, str, int, Counter[tuple[str, int]]]]:
    """``<host>+<genome>@<reads>`` to ``(host, genome, reads, summed counts)``."""
    mixed = {}
    for host in sorted(wanted if wanted is not None else hosts):
        for spike in sorted(spikes):
            genome, depth = split_sample(spike)
            if genome not in expected:
                raise ValueError(f"{spike}: {genome} is not a genome in the panel")
            mixed[f"{host}+{spike}"] = (host, genome, depth, hosts[host] + spikes[spike])
    return mixed


def write(out: Path, labels: Path, mixed: dict, expected: dict) -> None:
    with out.open("w", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(ALLELE_COLUMNS)
        for sample, (_, _, _, counts) in mixed.items():
            for (locus, allele), reads in sorted(counts.items()):
                writer.writerow([sample, locus, allele, reads])
    with labels.open("w", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(LABEL_COLUMNS)
        for sample, (host, genome, depth, counts) in mixed.items():
            for locus in sorted({locus for locus, _ in counts}):
                member = str(locus in expected[genome]).lower()
                writer.writerow([sample, host, genome, depth, locus, member])
