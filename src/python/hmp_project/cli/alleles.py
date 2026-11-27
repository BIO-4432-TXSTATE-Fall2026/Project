"""``alleles``: call each panel locus's repeat length from the reads the gate kept.

Reads ``<sample>.loci.fastq.gz`` from ``filter``, whose headers list the panel loci each
read matched (``@name<TAB>L000007|genome|contig:l-r=16``), and ``tr-panel.tsv``, which
holds each locus's two anchors: the ``--anchor`` bases immediately left and right of the
repeat. A group of genomes shares one anchor pair, so a locus id is a locus across genomes.

For every read and each candidate locus the read or its reverse complement is searched
for the left anchor and then the right anchor downstream of it, each within
``--mismatches`` substitutions (Hamming; no gaps, so an indel in an anchor is a miss):

- **Spanning**: both anchors found. The allele is the gap between them,
  ``right_start - left_end`` bases, the repeat's length as the panel measures it.
- **Flanking**: one anchor found. The read is counted, and gives no length.

A read that matches several loci goes to the one with the fewest mismatches, spanning
before flanking; a tie at the best is **ambiguous** and counts nowhere else. A read none
of whose candidates holds an anchor is **unassigned**.

Mates are one fragment. Reads are grouped by name stem (``/1``, ``/2`` and a trailing
Illumina ``1:``-style comment removed) per locus, so a fragment is counted once. When
both mates span with different lengths the fewer-mismatch call is kept, a tie going to the
first mate, and the fragment is counted as discordant.

Outputs, no stutter correction: raw length counts for the entropy stage.

- ``<sample>.alleles.tsv``: ``sample, locus_id, allele_bp, reads`` -- fragments per
  allele length, spanning only.
- ``<sample>.allele-stats.tsv``: ``sample, reads_in, spanning, flanking, ambiguous,
  unassigned, pairs_collapsed, pairs_discordant``. The first five count reads; the last
  two count fragments with more than one read and the ones whose mates disagree.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import re
from collections import Counter, defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import IO

ID_SEPARATOR = "|"
ALLELE_COLUMNS = ("sample", "locus_id", "allele_bp", "reads")
STATS_COLUMNS = (
    "sample",
    "reads_in",
    "spanning",
    "flanking",
    "ambiguous",
    "unassigned",
    "pairs_collapsed",
    "pairs_discordant",
)
COMPLEMENT = str.maketrans("ACGTacgt", "TGCAtgca")
MATE_SUFFIX = re.compile(r"/[12]$")


@dataclass(frozen=True)
class Call:
    """What one read shows of one locus: ``allele`` is ``None`` for a flanking read."""

    locus: str
    allele: int | None
    mismatches: int

    @property
    def key(self) -> tuple[int, int]:
        """Best first: spanning before flanking, then fewer mismatches."""
        return (self.allele is None, self.mismatches)


def add_parser(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "alleles", help="call repeat lengths per panel locus from the gated reads' anchors"
    )
    parser.add_argument("reads", type=Path, metavar="LOCI_FASTQ", help="from `filter`")
    parser.add_argument("--panel", type=Path, required=True, metavar="TSV", help="tr-panel.tsv")
    parser.add_argument("--sample", help="default: the reads' file name before the first dot")
    parser.add_argument(
        "--anchor",
        type=int,
        help="anchor bases to match, next to the repeat; default: the panel's whole anchor",
    )
    parser.add_argument("--mismatches", type=int, default=1, help="Hamming distance per anchor")
    parser.add_argument("--out-dir", type=Path, default=Path("."))
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> None:
    sample = args.sample or args.reads.name.split(".", 1)[0]
    try:
        anchors = read_anchors(args.panel, args.anchor)
        with open_reads(args.reads) as f:
            alleles, stats = call_alleles(f, anchors, args.mismatches)
    except ValueError as error:
        raise SystemExit(f"{sample}: {error}") from None
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_alleles(args.out_dir / f"{sample}.alleles.tsv", sample, alleles)
    write_stats(args.out_dir / f"{sample}.allele-stats.tsv", sample, stats)
    print(
        f"{sample}: {stats['spanning']} spanning, {stats['flanking']} flanking, "
        f"{stats['ambiguous']} ambiguous of {stats['reads_in']} reads; "
        f"{len(alleles)} locus alleles -> {args.out_dir}"
    )


def open_reads(path: Path) -> IO[str]:
    return gzip.open(path, "rt") if path.suffix == ".gz" else path.open()


def read_anchors(panel: Path, length: int | None = None) -> dict[str, tuple[str, str]]:
    """Each locus id's ``(left, right)`` anchors from ``tr-panel.tsv``, cut to ``length``
    bases next to the repeat. Members of a group share their anchors, so the first row
    stands for the group.
    """
    anchors: dict[str, tuple[str, str]] = {}
    with panel.open(newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["locus_id"] in anchors:
                continue
            left, right = row["left_anchor"].upper(), row["right_anchor"].upper()
            if length is not None:
                if length > min(len(left), len(right)):
                    raise ValueError(
                        f"--anchor {length} is longer than {row['locus_id']}'s anchors"
                    )
                left, right = left[len(left) - length :], right[:length]
            anchors[row["locus_id"]] = (left, right)
    if not anchors:
        raise ValueError(f"{panel} lists no loci")
    return anchors


def reverse_complement(sequence: str) -> str:
    return sequence.translate(COMPLEMENT)[::-1]


def find_anchor(sequence: str, anchor: str, mismatches: int) -> list[tuple[int, int]]:
    """``(position, mismatches)`` for every place ``anchor`` matches ``sequence`` within
    ``mismatches`` substitutions. With that many mismatches, at least one of
    ``mismatches + 1`` pieces of the anchor matches exactly, so only the places a piece
    occurs are compared in full.
    """
    n = len(anchor)
    pieces = mismatches + 1
    bounds = [n * i // pieces for i in range(pieces + 1)]
    found: dict[int, int] = {}
    for start, stop in pairwise(bounds):
        piece = anchor[start:stop]
        at = sequence.find(piece)
        while at != -1:
            position = at - start
            if position >= 0 and position + n <= len(sequence) and position not in found:
                distance = sum(
                    a != b for a, b in zip(sequence[position : position + n], anchor, strict=True)
                )
                if distance <= mismatches:
                    found[position] = distance
            at = sequence.find(piece, at + 1)
    return sorted(found.items())


def call_locus(sequence: str, locus: str, anchors: tuple[str, str], mismatches: int) -> Call | None:
    """The best way ``sequence`` or its reverse complement shows ``locus``, or ``None``."""
    left, right = anchors
    spans: list[Call] = []
    flanks: list[Call] = []
    for strand in (sequence, reverse_complement(sequence)):
        lefts = find_anchor(strand, left, mismatches)
        rights = find_anchor(strand, right, mismatches)
        for lpos, lmm in lefts:
            spans.extend(
                Call(locus, rpos - (lpos + len(left)), lmm + rmm)
                for rpos, rmm in rights
                if rpos >= lpos + len(left)
            )
        flanks.extend(Call(locus, None, mm) for _, mm in lefts + rights)
    if spans:
        return min(spans, key=lambda call: (call.mismatches, call.allele))
    return min(flanks, key=lambda call: call.mismatches, default=None)


def parse_header(header: str) -> tuple[str, list[str]]:
    """The fragment stem and the candidate locus ids from a ``rename=t`` header."""
    name, *matches = header[1:].rstrip("\r\n").split("\t")
    token = name.split(None, 1)[0] if name.strip() else name
    loci = []
    for match in matches:
        ref, sep, count = match.rpartition("=")
        if not sep or not count.isdigit() or not ref:
            raise ValueError(f"not a matched reference, expected name=count: {match!r}")
        locus = ref.split(ID_SEPARATOR, 1)[0]
        if locus not in loci:
            loci.append(locus)
    return MATE_SUFFIX.sub("", token), loci


def records(lines: IO[str]) -> Iterator[tuple[str, str]]:
    """``(header, sequence)`` for each four-line FASTQ record."""
    while header := lines.readline():
        sequence = lines.readline().strip()
        plus, quals = lines.readline(), lines.readline()
        if not header.startswith("@") or not plus.startswith("+") or not quals:
            raise ValueError(f"not FASTQ near {header[:60]!r}")
        yield header, sequence.upper()


def call_alleles(
    lines: IO[str], anchors: dict[str, tuple[str, str]], mismatches: int
) -> tuple[Counter[tuple[str, int]], dict[str, int]]:
    """Allele counts per ``(locus_id, allele_bp)`` and the read statistics."""
    stats = dict.fromkeys(STATS_COLUMNS[1:], 0)
    fragments: dict[tuple[str, str], list[Call]] = defaultdict(list)
    for header, sequence in records(lines):
        stats["reads_in"] += 1
        stem, candidates = parse_header(header)
        calls = []
        for locus in candidates:
            if locus not in anchors:
                raise ValueError(f"{locus} is not in the panel; reads and panel do not match")
            if call := call_locus(sequence, locus, anchors[locus], mismatches):
                calls.append(call)
        if not calls:
            stats["unassigned"] += 1
            continue
        best = min(call.key for call in calls)
        winners = [call for call in calls if call.key == best]
        if len(winners) > 1:
            stats["ambiguous"] += 1
            continue
        call = winners[0]
        stats["flanking" if call.allele is None else "spanning"] += 1
        fragments[(stem, call.locus)].append(call)

    alleles: Counter[tuple[str, int]] = Counter()
    for (_, locus), mates in fragments.items():
        if len(mates) > 1:
            stats["pairs_collapsed"] += 1
        spans = [call for call in mates if call.allele is not None]
        if len({call.allele for call in spans}) > 1:
            stats["pairs_discordant"] += 1
        if spans:
            # min is stable, so a tie keeps the first mate read.
            alleles[(locus, min(spans, key=lambda call: call.mismatches).allele)] += 1
    return alleles, stats


def write_alleles(path: Path, sample: str, alleles: Counter[tuple[str, int]]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(ALLELE_COLUMNS)
        for (locus, allele), reads in sorted(alleles.items()):
            writer.writerow([sample, locus, allele, reads])


def write_stats(path: Path, sample: str, stats: dict[str, int]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(STATS_COLUMNS)
        writer.writerow([sample, *(stats[column] for column in STATS_COLUMNS[1:])])


def read_table(path: Path) -> dict[str, Counter[tuple[str, int]]]:
    """A concatenated ``alleles.tsv`` as fragments per ``(locus_id, allele_bp)``, by sample."""
    samples: dict[str, Counter[tuple[str, int]]] = defaultdict(Counter)
    with path.open(newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            samples[row["sample"]][(row["locus_id"], int(row["allele_bp"]))] += int(row["reads"])
    return samples
