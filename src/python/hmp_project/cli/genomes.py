"""``genomes``: list the genomes in a synced spec, one FASTA file per genome.

Writes a two-column TSV, genome name then FASTA path, for every genome the spec's lock
lists. The repeat finder and ``loci`` read genomes from this list, so both name each
genome the same way.

For each genome the command:

- **Names it** after its directory (``--name-from dir``, the HMP and slacken layout) or
  its file name (``--name-from file``).
- **Makes it readable by inTRuder**, which opens plain or gzip FASTA only. bzip2 files
  are decompressed and GenBank files are converted to FASTA, both in place.
- **Checks it is one file.** A genome with two sequence files, such as an HMP draft
  shipped as both contigs and scaffolds, is an error: the spec has to choose one.

The list comes from the lock rather than the directory, so it holds exactly the files
that were synced. A file the lock lists but the disk lacks is an error.
"""

from __future__ import annotations

import argparse
import bz2
import shutil
from collections import defaultdict
from pathlib import Path

from hmp_project.manifest import Spec, open_dataset, read_lock
from hmp_project.providers import Provider

FASTA_SUFFIXES = (".fsa", ".fna", ".fa", ".fasta")
GENBANK_SUFFIXES = (".gbk", ".gb", ".gbff")
NAME_FROM = ("dir", "file")


def add_parser(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "genomes", help="list a synced spec's genomes as name and FASTA path, one per genome"
    )
    parser.add_argument("spec", type=Path, metavar="SPEC")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument(
        "--name-from",
        choices=NAME_FROM,
        default="dir",
        help="name a genome by its directory (HMP, slacken) or by its file name",
    )
    parser.add_argument("--out", type=Path, default=Path("genomes.tsv"))
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> None:
    spec = Spec.load(args.spec)
    try:
        genomes = list_genomes(spec, args.data_dir, name_from=args.name_from)
    except ValueError as error:
        raise SystemExit(f"{spec.name}: {error}") from None
    args.out.write_text("".join(f"{name}\t{path}\n" for name, path in genomes.items()))
    print(f"{spec.name}: {len(genomes)} genomes -> {args.out}")


def _sequence_kind(name: str) -> str | None:
    """``fasta``, ``genbank`` or ``None`` from a file name, ignoring a compression suffix."""
    lower = name.lower()
    for suffix in (".gz", ".bz2"):
        lower = lower.removesuffix(suffix)
    if lower.endswith(FASTA_SUFFIXES):
        return "fasta"
    if lower.endswith(GENBANK_SUFFIXES):
        return "genbank"
    return None


def genome_name(path: Path, name_from: str) -> str:
    """The genome a file holds: its directory, or its file name without the compression
    and sequence suffixes, so ``GCF_000009045.2.fna.gz`` keeps its assembly version.
    """
    if name_from == "dir":
        return path.parent.name
    name = path.name
    for suffix in (".gz", ".bz2"):
        name = name.removesuffix(suffix)
    for suffix in FASTA_SUFFIXES + GENBANK_SUFFIXES:
        if name.lower().endswith(suffix):
            return name[: -len(suffix)]
    return name


def list_genomes(
    spec: Spec, data_dir: Path, *, name_from: str = "dir", provider: Provider | None = None
) -> dict[str, Path]:
    """Map each genome in ``spec``'s synced files to one readable FASTA, sorted by name.

    Raises ``ValueError`` if a genome has more than one sequence file, if a listed file
    is not on disk, or if the spec holds no sequence files.
    """
    if name_from not in NAME_FROM:
        raise ValueError(f"name_from must be one of {NAME_FROM}, got {name_from!r}")
    lock = read_lock(spec.lock_path)
    if lock is None:
        raise ValueError(f"{spec.lock_path} not found; sync the spec first")
    dataset = open_dataset(spec, provider)
    root = data_dir / spec.name

    files: dict[str, list[Path]] = defaultdict(list)
    missing = []
    for record in lock["files"]:
        path = dataset.local_path(record["key"], root)
        if _sequence_kind(path.name) is None:
            continue
        if not path.is_file():
            missing.append(record["key"])
            continue
        files[genome_name(path, name_from)].append(path)
    if missing:
        raise ValueError(f"{len(missing)} listed files not downloaded, e.g. {missing[0]}")
    if not files:
        raise ValueError("no FASTA or GenBank files in the lock")
    shared = {name: paths for name, paths in files.items() if len(paths) > 1}
    if shared:
        name, paths = next(iter(sorted(shared.items())))
        listed = ", ".join(p.name for p in sorted(paths))
        raise ValueError(
            f"{len(shared)} genomes have more than one sequence file, e.g. {name}: {listed}; "
            "narrow the spec so each genome is one file"
        )
    return {name: readable_fasta(paths[0]) for name, paths in sorted(files.items())}


def readable_fasta(path: Path) -> Path:
    """Return a plain or gzip FASTA for the genome at ``path``, decompressing bzip2 and
    converting GenBank in place. The original file is removed, so the directory still
    holds one file per genome.
    """
    if path.name.lower().endswith(".bz2"):
        plain = path.with_name(path.name[: -len(".bz2")])
        with bz2.open(path, "rb") as src, plain.open("wb") as dest:
            shutil.copyfileobj(src, dest)
        path.unlink()
        path = plain
    if _sequence_kind(path.name) == "genbank":
        fasta = path.with_name(f"{path.name}.fa")
        if path.name.lower().endswith(".gz"):
            raise ValueError(f"{path.name}: gzip-compressed GenBank is not supported")
        genbank_to_fasta(path, fasta)
        path.unlink()
        path = fasta
    return path


def genbank_to_fasta(src: Path, dest: Path) -> int:
    """Write each record of the GenBank file ``src`` to ``dest`` as FASTA, and return
    the number of records.

    Each record is named by its ``VERSION`` accession, as a FASTA header from GenBank or
    RefSeq would be, or by its ``LOCUS`` name if it has none. A record with no sequence
    is an error, since leaving it out would drop a contig from the genome.
    """
    count = 0
    locus = version = None
    sequence: list[str] | None = None
    with src.open() as lines, dest.open("w") as out:
        for line in lines:
            if sequence is not None:
                if line.startswith("//"):
                    name = version or locus
                    if not sequence:
                        raise ValueError(f"{src.name}: record {name} has no sequence")
                    out.write(f">{name}\n")
                    joined = "".join(sequence)
                    for i in range(0, len(joined), 80):
                        out.write(joined[i : i + 80] + "\n")
                    count += 1
                    locus = version = sequence = None
                else:
                    sequence.append("".join(line.split()[1:]).upper())
            elif line.startswith("LOCUS"):
                locus = line.split()[1]
            elif line.startswith("VERSION") and len(line.split()) > 1:
                version = line.split()[1]
            elif line.startswith("ORIGIN"):
                if locus is None:
                    raise ValueError(f"{src.name}: ORIGIN before any LOCUS line")
                sequence = []
    if sequence is not None:
        raise ValueError(f"{src.name}: last record has no closing //")
    if count == 0:
        raise ValueError(f"{src.name}: no sequence records")
    return count
