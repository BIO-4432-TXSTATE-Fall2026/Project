"""``panel``: the final locus panel, after the screens.

Joins ``tr-loci.tsv`` with the two screens' fragment counts and keeps the loci a read
could be assigned to unambiguously:

- **Human screen** (``--human``): CHM13 cut into fragments and run through the gate's own
  k-mer match. A locus any human fragment hits is excluded, because a read that matches
  it cannot be told from host.
- **Mock screen** (``--mock``): the same, over the mock community's genomes. It annotates
  and never excludes. Most target genera and every kit genus are not in the mock
  community, so a locus with no mock hit is the usual case, not a failed one.

Outputs:

- ``--table``: ``tr-loci.tsv``'s columns for the kept loci, then ``human_fragments`` (always
  zero here) and ``mock_fragments``.
- ``--out``: the gate's reference, the kept loci's records from ``tr-loci.fa``.

A screen that names a locus the table lacks is from a different ``tr-loci.tsv``, and is an
error.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

ID_SEPARATOR = "|"
SCREEN_COLUMNS = ("human_fragments", "mock_fragments")


def add_parser(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "panel", help="drop loci the human screen hit and annotate with the mock screen"
    )
    parser.add_argument("loci", type=Path, metavar="TR_LOCI_TSV", help="from `loci --table`")
    parser.add_argument("fasta", type=Path, metavar="TR_LOCI_FA", help="from `loci --out`")
    parser.add_argument("--human", type=Path, required=True, metavar="TSV")
    parser.add_argument("--mock", type=Path, required=True, metavar="TSV")
    parser.add_argument("--table", type=Path, default=Path("tr-panel.tsv"))
    parser.add_argument("--out", type=Path, default=Path("tr-panel.fa"))
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> None:
    try:
        summary = build_panel(
            args.loci, args.fasta, args.human, args.mock, table=args.table, out=args.out
        )
    except ValueError as error:
        raise SystemExit(str(error)) from None
    print(
        f"{summary['groups']} groups: {summary['excluded']} excluded by the human screen, "
        f"{summary['kept']} kept ({summary['annotated']} hit by the mock screen) "
        f"-> {args.table}, {args.out}"
    )


def read_screen(path: Path) -> dict[str, int]:
    with path.open(newline="") as f:
        return {row["locus_id"]: int(row["fragments"]) for row in csv.DictReader(f, delimiter="\t")}


def build_panel(
    loci: Path, fasta: Path, human: Path, mock: Path, *, table: Path, out: Path
) -> dict[str, int]:
    """Write the panel's table and FASTA, and return counts of groups in, excluded, kept
    and kept with a mock hit.
    """
    with loci.open(newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        columns = list(reader.fieldnames or [])
        rows = list(reader)
    known = {row["locus_id"] for row in rows}
    screens = {"human": read_screen(human), "mock": read_screen(mock)}
    for name, counts in screens.items():
        unknown = sorted(counts.keys() - known)
        if unknown:
            raise ValueError(f"the {name} screen names loci not in {loci}, e.g. {unknown[0]}")

    human_hits, mock_hits = screens["human"], screens["mock"]
    excluded = {locus for locus in known if human_hits.get(locus, 0) > 0}
    kept = known - excluded

    table.parent.mkdir(parents=True, exist_ok=True)
    partial = table.with_name(f".{table.name}.part")
    with partial.open("w", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow([*columns, *SCREEN_COLUMNS])
        for row in rows:
            locus = row["locus_id"]
            if locus in kept:
                writer.writerow(
                    [*(row[c] for c in columns), human_hits.get(locus, 0), mock_hits.get(locus, 0)]
                )
    partial.replace(table)

    write_kept_records(fasta, kept, out)
    return {
        "groups": len(known),
        "excluded": len(excluded),
        "kept": len(kept),
        "annotated": sum(1 for locus in kept if mock_hits.get(locus, 0) > 0),
    }


def write_kept_records(fasta: Path, kept: set[str], out: Path) -> None:
    """Copy the records of ``fasta`` whose locus id is in ``kept``, in order."""
    out.parent.mkdir(parents=True, exist_ok=True)
    partial = out.with_name(f".{out.name}.part")
    keeping = False
    with fasta.open() as src, partial.open("w") as dest:
        for line in src:
            if line.startswith(">"):
                keeping = line[1:].split(ID_SEPARATOR, 1)[0] in kept
            if keeping:
                dest.write(line)
    partial.replace(out)
