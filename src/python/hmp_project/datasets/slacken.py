from __future__ import annotations

import hashlib
import os
import re
import tempfile
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import ClassVar

from hmp_project.datasets.base import S3Dataset
from hmp_project.providers import Provider, RemoteObject

ASSEMBLY_ACCESSION = re.compile(r"GCF_[0-9]{9}\.[0-9]+")
LIBRARY = "index/rspc-224/library/bacteria/"
LIBRARY_FASTA = "library.fna"
INDEX_FILES = ("library.fna.fai", "manifest.txt", "assembly_summary.filter.txt")


def _sequences(fai: Iterable[str]) -> Iterator[tuple[str, int, int]]:
    """Yield ``(taxid, length, end)`` for each sequence in a Kraken2 library's ``.fai``,
    where ``end`` is the byte just past the sequence's last line.
    """
    for line in fai:
        name, length, offset, line_bases, line_width = line.split("\t")[:5]
        length, line_bases = int(length), int(line_bases)
        lines = -(-length // line_bases) if line_bases else 0
        yield (
            name.split("|")[1],
            length,
            int(offset) + length + lines * (int(line_width) - line_bases),
        )


def assembly_spans(
    fai: Iterable[str], manifest: Iterable[str], summary: Iterable[str]
) -> Iterator[tuple[str, int, int]]:
    """Yield ``(accession, start, end)``: the bytes of ``library.fna`` holding each
    assembly, headers included.

    Kraken2 names sequences ``kraken:taxid|<taxid>|<sequence accession>``, without the
    assembly, so assemblies are recovered from order: the library concatenates the
    manifest's files sorted by path, each assembly's sequences together. An assembly is
    the run of sequences with its taxid whose lengths add up to its genome size. One
    whose next sequence has another taxid is absent from the library; one whose run does
    not add up is skipped rather than guessed at.
    """
    assemblies: dict[str, tuple[str, int]] = {}
    for line in summary:
        if line.startswith("#"):
            continue
        fields = line.rstrip("\n").split("\t")
        assemblies[fields[0]] = (fields[5], int(fields[25]))
    paths = sorted(line.partition("=")[2].strip() for line in manifest if line.startswith("output"))

    sequences = _sequences(fai)
    current = next(sequences, None)
    end = 0
    for path in paths:
        match = ASSEMBLY_ACCESSION.search(path)
        if match is None or match.group() not in assemblies:
            raise ValueError(f"manifest file {path!r} names no assembly in the summary")
        accession = match.group()
        taxid, size = assemblies[accession]
        start, total = end, 0
        while current is not None and current[0] == taxid and total < size:
            total, end = total + current[1], current[2]
            current = next(sequences, None)
        if total and total == size:
            yield accession, start, end
    if current is not None:
        raise ValueError("library.fna.fai has sequences that no manifest assembly accounts for")


def _cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "hmp_project" / "slacken"


class SlackenDataset(S3Dataset):
    """RefSeq bacterial genomes from the Slacken metagenomic reference libraries bucket.

    Selected by RefSeq assembly accession (``GCF_...``): each becomes one FASTA file,
    ``<accession>/<accession>.fna``, cut by byte range from the library's single
    ``library.fna`` (RefSeq release 224, about 580 GB), so only that genome is
    downloaded. Headers keep Kraken2's ``kraken:taxid|<taxid>|`` prefix. Locks record the
    library's ETag, so a rebuilt library marks every genome changed.

    Finding an assembly's bytes needs the library's index files (about 700 MB). They are
    fetched once per library version and reduced to a small table under
    ``$XDG_CACHE_HOME/hmp_project/slacken``. A ``prefix`` selects bucket objects as is,
    e.g. ``index/rspc-224/library/bacteria`` with ``assembly_summary.filter.txt``
    included, to choose accessions. See https://registry.opendata.aws/slacken/.
    """

    BUCKETS: ClassVar[dict[str, str]] = {"us-east-1": "slacken"}

    def __init__(
        self,
        prefix: str = "",
        *,
        accessions: Iterable[str] = (),
        region: str | None = None,
        include: Iterable[str] = ("*",),
        exclude: Iterable[str] = (),
        provider: Provider | None = None,
    ) -> None:
        super().__init__(
            prefix,
            accessions=accessions,
            region=region,
            include=include,
            exclude=exclude,
            provider=provider,
        )
        self._ranges: dict[str, tuple[RemoteObject, int, int]] = {}

    @classmethod
    def accession_prefix(cls, accession: str) -> str:
        if not ASSEMBLY_ACCESSION.fullmatch(accession):
            raise ValueError(
                f"{accession!r} is not a RefSeq assembly accession (GCF_, nine digits, and a "
                "version, e.g. GCF_000009505.1)"
            )
        return f"{LIBRARY}{accession}/"

    def select(self) -> list[RemoteObject]:
        if not self.accessions:
            return super().select()
        listing = {
            obj.key.removeprefix(LIBRARY): obj for obj in self.provider.list_objects(LIBRARY)
        }
        missing = [name for name in (LIBRARY_FASTA, *INDEX_FILES) if name not in listing]
        if missing:
            raise ValueError(f"{self.provider.uri(LIBRARY)} lacks {', '.join(missing)}")
        library = listing[LIBRARY_FASTA]
        spans = self._spans(listing)

        self._ranges.clear()
        selected = []
        for accession in dict.fromkeys(self.accessions):
            if accession not in spans:
                raise ValueError(
                    f"{accession} is not in {self.provider.uri(LIBRARY)}, or its sequences "
                    "there do not add up to its genome size"
                )
            key = f"{self.accession_prefix(accession)}{accession}.fna"
            if not self.matches(key):
                continue
            start, end = spans[accession]
            self._ranges[key] = (library, start, end)
            selected.append(RemoteObject(key, end - start, library.etag, library.last_modified))
        return sorted(selected, key=lambda obj: obj.key)

    def download(self, obj: RemoteObject, dest: Path) -> None:
        if obj.key not in self._ranges:
            super().download(obj, dest)
            return
        library, start, end = self._ranges[obj.key]
        self.provider.download_range(library, start, end, dest)

    def _spans(self, listing: dict[str, RemoteObject]) -> dict[str, tuple[int, int]]:
        """Assembly spans for this version of the library, built once and cached."""
        etags = "\n".join(listing[name].etag for name in (LIBRARY_FASTA, *INDEX_FILES))
        cached = _cache_dir() / f"bacteria-{hashlib.sha256(etags.encode()).hexdigest()[:16]}.tsv"
        if not cached.is_file():
            cached.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=cached.parent) as work:
                paths = [Path(work) / name for name in INDEX_FILES]
                for name, path in zip(INDEX_FILES, paths, strict=True):
                    self.provider.download(listing[name], path)
                partial = Path(work) / cached.name
                with (
                    paths[0].open() as fai,
                    paths[1].open() as manifest,
                    paths[2].open() as summary,
                    partial.open("w") as out,
                ):
                    for accession, start, end in assembly_spans(fai, manifest, summary):
                        out.write(f"{accession}\t{start}\t{end}\n")
                os.replace(partial, cached)
        spans = {}
        with cached.open() as f:
            for line in f:
                accession, start, end = line.split("\t")
                spans[accession] = (int(start), int(end))
        return spans
