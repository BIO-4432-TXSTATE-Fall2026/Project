"""``loci``: merge the catalogs' repeat calls into loci and write the filter's reference.

A locus is a place a read can be assigned to and an allele length measured at. The
catalogs list repeat *calls*, which are neither unique nor independent: one tract is often
called twice, and the same locus recurs, flanks and all, in every genome of a genus. This
command turns calls into loci in two steps.

**Within a genome**, calls on one contig whose gap is smaller than ``--anchor`` become one
locus spanning their union. A read measures a tract by finding the same unique sequence on
each side of it, so each side needs ``--anchor`` bases free of called repeat.

**Across genomes**, loci with the same canonical motif and the same anchor pair are one
group and share a ``locus_id`` (``L000001``, numbered in sorted key order so a rerun
numbers them identically). The canonical motif folds rotation and reverse complement. The
anchor pair is oriented to the lexicographically smaller of ``(left, right)`` and
``(rc(right), rc(left))``, so a locus on the other strand lands in the same group.

Three things are dropped and counted. A locus whose anchor runs off its contig has no
anchor to read. A group whose longest member is longer than ``--max-rep-length`` cannot be
spanned by a read: a 100 bp read with two 20 bp anchors spans about 60 bp. And a record
whose sequence is byte-identical to another record of its group is written once.

Outputs:

- ``--table``: one row per member, with the group's single anchor pair.
- ``--out``: each member's locus padded by ``--flank`` bases, as the gate's reference.
  A read that reaches into a locus from its flank is as wanted as one on the repeat.
- ``--stats``: what each step dropped and kept, in total and per spec.

A catalog's spec is named by its file: ``tr-catalog.kit.tsv`` is the spec ``kit``.

Genomes are read through inTRuder's :func:`~intruder.trcore.io.read_fasta`, the reader
the catalogs were built with, so contig names here are theirs by construction. It and the
motif functions are imported when the command runs, since intruder and pyfastx live in
the catalog environment rather than the default one.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

TABLE_COLUMNS = (
    "locus_id",
    "spec",
    "genome",
    "contig",
    "start",
    "end",
    "motif",
    "motif_length",
    "rep_length",
    "purity",
    "n_calls",
    "motifs",
    "left_anchor",
    "right_anchor",
)
STATS_COLUMNS = ("metric", "spec", "value")
STATS_METRICS = (
    "calls",
    "regions",
    "edge_drops",
    "long_groups",
    "long_members",
    "groups",
    "members",
)

#: A locus's id is the first field of its FASTA header, ahead of this separator.
ID_SEPARATOR = "|"


@dataclass(frozen=True)
class Call:
    """One row of a catalog. Coordinates are 0-based half-open, as inTRuder writes them."""

    start: int
    end: int
    motif: str
    purity: str


@dataclass
class Region:
    """Calls merged into one locus in one genome, with its anchors and padded sequence."""

    spec: str
    genome: str
    contig: str
    start: int
    end: int
    motif: str
    purity: str
    n_calls: int
    motifs: str
    left_anchor: str
    right_anchor: str
    padded_start: int
    padded_end: int
    sequence: str

    @property
    def rep_length(self) -> int:
        return self.end - self.start


@dataclass
class LociStats:
    """Counts per metric and spec; ``"all"`` is the total over every spec."""

    counts: dict[tuple[str, str], int] = field(default_factory=lambda: defaultdict(int))

    def add(self, metric: str, spec: str, amount: int = 1) -> None:
        self.counts[metric, spec] += amount
        self.counts[metric, "all"] += amount

    def add_group(self, metric: str, specs: set[str]) -> None:
        """Count one group once in total, and once in each spec it has a member in."""
        for spec in specs:
            self.counts[metric, spec] += 1
        self.counts[metric, "all"] += 1

    def get(self, metric: str, spec: str = "all") -> int:
        return self.counts.get((metric, spec), 0)

    def specs(self) -> list[str]:
        return sorted({spec for _, spec in self.counts if spec != "all"})


def add_parser(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "loci", help="merge catalog calls into loci and write the filter's reference FASTA"
    )
    parser.add_argument(
        "catalogs", type=Path, nargs="+", metavar="CATALOG", help="TR catalog TSVs, one per spec"
    )
    parser.add_argument(
        "--genomes",
        type=Path,
        required=True,
        metavar="TSV",
        help="genome name and FASTA path per line, named as the catalogs name them",
    )
    parser.add_argument("--flank", type=int, default=50, help="bases kept either side in --out")
    parser.add_argument(
        "--anchor",
        type=int,
        default=20,
        help="anchor length; calls closer than this merge into one locus",
    )
    parser.add_argument(
        "--max-rep-length",
        type=int,
        default=60,
        help="drop groups whose longest member is longer than this",
    )
    parser.add_argument("--table", type=Path, default=Path("tr-loci.tsv"))
    parser.add_argument("--stats", type=Path, default=Path("tr-loci-stats.tsv"))
    parser.add_argument("--out", type=Path, default=Path("tr-loci.fa"))
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> None:
    for option in ("flank", "anchor", "max_rep_length"):
        if getattr(args, option) < 0:
            raise SystemExit(f"--{option.replace('_', '-')} must not be negative")
    try:
        stats = build_loci(
            args.catalogs,
            read_genomes(args.genomes),
            table=args.table,
            stats_path=args.stats,
            out=args.out,
            flank=args.flank,
            anchor=args.anchor,
            max_rep_length=args.max_rep_length,
        )
    except ValueError as error:
        raise SystemExit(str(error)) from None
    print(
        f"{stats.get('calls')} calls -> {stats.get('regions')} regions -> "
        f"{stats.get('groups')} groups, {stats.get('members')} members "
        f"(dropped {stats.get('edge_drops')} at a contig edge, "
        f"{stats.get('long_groups')} groups too long) -> {args.table}, {args.out}"
    )


def read_genomes(path: Path) -> dict[str, Path]:
    genomes: dict[str, Path] = {}
    for line in path.read_text().splitlines():
        if line.strip():
            name, fasta = line.split("\t")
            if name in genomes:
                raise ValueError(f"{path}: genome {name} is listed twice")
            genomes[name] = Path(fasta)
    return genomes


def spec_name(catalog: Path) -> str:
    """``tr-catalog.kit.tsv`` is ``kit``; a file not named that way is named by its stem."""
    return catalog.name.removesuffix(".tsv").removeprefix("tr-catalog.")


def read_catalog(path: Path) -> dict[tuple[str, str], list[Call]]:
    """The catalog's calls, grouped by ``(genome, contig)`` and sorted by position."""
    calls: dict[tuple[str, str], list[Call]] = defaultdict(list)
    with path.open(newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            call = Call(int(row["start"]), int(row["end"]), row["motif"], row["purity"])
            calls[row["genome"], row["contig"]].append(call)
    for group in calls.values():
        group.sort(key=lambda call: (call.start, call.end))
    return calls


def merge_calls(calls: list[Call], anchor: int) -> list[list[Call]]:
    """Split position-sorted ``calls`` into runs whose consecutive gap is below ``anchor``.
    Overlapping calls have a negative gap, so they always merge.
    """
    runs: list[list[Call]] = []
    run_end = 0
    for call in calls:
        if runs and call.start - run_end < anchor:
            runs[-1].append(call)
            run_end = max(run_end, call.end)
        else:
            runs.append([call])
            run_end = call.end
    return runs


def oriented_anchors(left: str, right: str) -> tuple[str, str]:
    """The anchor pair as read from whichever strand sorts first, so one locus seen on
    either strand has one pair.
    """
    from intruder.trcore.motifs import reverse_complement

    return min((left, right), (reverse_complement(right), reverse_complement(left)))


def build_loci(
    catalogs: list[Path],
    genomes: dict[str, Path],
    *,
    table: Path,
    stats_path: Path,
    out: Path,
    flank: int,
    anchor: int,
    max_rep_length: int,
) -> LociStats:
    """Merge ``catalogs`` into loci, and write their table, statistics and padded FASTA.

    Fails rather than writing a partial reference when a call names a genome or contig
    that ``genomes`` cannot supply, or when two catalogs name the same genome: a gate
    missing loci passes a sample's reads short without saying so.
    """
    from intruder.trcore.io import read_fasta
    from intruder.trcore.motifs import MotifEquivalence, canonical_motif

    equivalence = MotifEquivalence(circular=True, reverse_complement=True)

    def canonical(motif: str) -> str:
        return canonical_motif(motif, equivalence)

    by_spec: dict[str, dict[tuple[str, str], list[Call]]] = {}
    owner: dict[str, str] = {}
    for catalog in catalogs:
        spec = spec_name(catalog)
        if spec in by_spec:
            raise ValueError(f"two catalogs are named for spec {spec}")
        by_spec[spec] = read_catalog(catalog)
        for genome in {genome for genome, _ in by_spec[spec]}:
            if genome in owner:
                raise ValueError(f"genome {genome} is in both {owner[genome]} and {spec}")
            owner[genome] = spec
    missing = sorted(owner.keys() - genomes.keys())
    if missing:
        raise ValueError(f"no FASTA for genomes {missing}")

    stats = LociStats()
    regions: list[Region] = []
    for genome in sorted(owner):
        spec = owner[genome]
        pending = {key: calls for key, calls in by_spec[spec].items() if key[0] == genome}
        for record in read_fasta(genomes[genome]):
            length = len(record.sequence)
            for calls in merge_calls(pending.pop((genome, record.name), []), anchor):
                stats.add("calls", spec, len(calls))
                stats.add("regions", spec)
                start = min(call.start for call in calls)
                end = max(call.end for call in calls)
                if start - anchor < 0 or end + anchor > length:
                    stats.add("edge_drops", spec)
                    continue
                longest = max(calls, key=lambda call: call.end - call.start)
                left, right = oriented_anchors(
                    record.sequence[start - anchor : start], record.sequence[end : end + anchor]
                )
                padded = max(0, start - flank), min(length, end + flank)
                regions.append(
                    Region(
                        spec=spec,
                        genome=genome,
                        contig=record.name,
                        start=start,
                        end=end,
                        motif=canonical(longest.motif),
                        purity=longest.purity,
                        n_calls=len(calls),
                        motifs=",".join(sorted({canonical(call.motif) for call in calls})),
                        left_anchor=left,
                        right_anchor=right,
                        padded_start=padded[0],
                        padded_end=padded[1],
                        sequence=record.sequence[padded[0] : padded[1]],
                    )
                )
        if pending:
            unmatched = sorted(f"{genome}/{contig}" for _, contig in pending)
            raise ValueError(f"contigs not in their genome's FASTA: {unmatched}")

    groups: dict[tuple[str, str, str], list[Region]] = defaultdict(list)
    for region in regions:
        groups[region.motif, region.left_anchor, region.right_anchor].append(region)

    kept: list[list[Region]] = []
    for key in sorted(groups):
        members = groups[key]
        too_long = max(m.rep_length for m in members) > max_rep_length
        stats.add_group("long_groups" if too_long else "groups", {m.spec for m in members})
        for m in members:
            stats.add("long_members" if too_long else "members", m.spec)
        if not too_long:
            kept.append(sorted(members, key=lambda m: (m.spec, m.genome, m.contig, m.start)))

    write_outputs(kept, stats, table=table, stats_path=stats_path, out=out)
    return stats


def locus_id(number: int) -> str:
    return f"L{number:06d}"


def _write_atomically(path: Path, write) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f".{path.name}.part")
    with partial.open("w", newline="") as f:
        write(f)
    partial.replace(path)


def write_outputs(
    groups: list[list[Region]], stats: LociStats, *, table: Path, stats_path: Path, out: Path
) -> None:
    def write_table(f) -> None:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(TABLE_COLUMNS)
        for number, members in enumerate(groups, start=1):
            for m in members:
                writer.writerow(
                    (
                        locus_id(number),
                        m.spec,
                        m.genome,
                        m.contig,
                        m.start,
                        m.end,
                        m.motif,
                        len(m.motif),
                        m.rep_length,
                        m.purity,
                        m.n_calls,
                        m.motifs,
                        m.left_anchor,
                        m.right_anchor,
                    )
                )

    def write_fasta(f) -> None:
        for number, members in enumerate(groups, start=1):
            seen: set[str] = set()
            for m in members:
                if m.sequence in seen:
                    continue
                seen.add(m.sequence)
                name = f"{locus_id(number)}{ID_SEPARATOR}{m.genome}{ID_SEPARATOR}{m.contig}"
                f.write(f">{name}:{m.padded_start}-{m.padded_end}\n{m.sequence}\n")

    def write_stats(f) -> None:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(STATS_COLUMNS)
        for spec in ("all", *stats.specs()):
            for metric in STATS_METRICS:
                writer.writerow((metric, spec, stats.get(metric, spec)))

    _write_atomically(table, write_table)
    _write_atomically(stats_path, write_stats)
    _write_atomically(out, write_fasta)
