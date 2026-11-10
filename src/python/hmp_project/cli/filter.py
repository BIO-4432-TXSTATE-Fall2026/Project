"""``filter``: stream one sample's reads from the remote through a k-mer gate.

An HMP sample is a ``.tar.bz2`` of up to three FASTQs -- ``.1``, ``.2`` and
``.singleton`` -- that decompresses to tens of gigabytes. None of it may land on disk, so
the whole sample is one pipe, owned here rather than by a shell::

    open_stream(key) -> decompressor -dc -> tarfile (mode 'r|') -> gate -> gzip writer

Python rather than a shell pipeline because every stage's exit status is checked: a
transfer that dies part way through must fail the sample, not quietly hand on the reads
that arrived. A truncated sample looks like a shallow one, which is the worst error
available to a cross-sample entropy measurement.

Members arrive in whatever order the tarball was written -- it varies between samples --
so they are routed by name, never by position. Every mate feeds one gate single-ended:
the read names already carry ``/1`` and ``/2``, so the survivors re-pair by name later.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import gzip
import re
import subprocess
import sys
import tarfile
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import IO, BinaryIO

from hmp_project.manifest import Spec, open_dataset, read_lock
from hmp_project.providers import RemoteObject

CHUNK = 1 << 20

#: Consecutive failed reads from the remote before a sample gives up. Reset whenever
#: bytes arrive, so a long stream may drop many times as long as it keeps moving.
RESUMES = 6

#: ``SRS011140.1.fastq``, ``SRS011140.singleton.fastq``, possibly under a directory.
MEMBER = re.compile(r"\.(1|2|singleton)\.f(?:ast)?q$")
MATES = ("1", "2", "singleton")

COUNTS_COLUMNS = (
    "sample",
    "spec",
    "key",
    "reads_1",
    "reads_2",
    "reads_singleton",
    "reads_seen",
    "reads_passed",
    "reads_written",
    "bytes_read",
    "bytes_decompressed",
    "elapsed_s",
)


@dataclass
class FilterResult:
    reads: dict[str, int] = field(default_factory=lambda: dict.fromkeys(MATES, 0))
    passed: int = 0
    written: int = 0
    bytes_read: int = 0
    bytes_decompressed: int = 0
    elapsed: float = 0.0

    @property
    def seen(self) -> int:
        return sum(self.reads.values())


def add_parser(commands: argparse._SubParsersAction) -> None:
    parser = commands.add_parser(
        "filter", help="stream one sample's reads through a k-mer gate, keeping the hits"
    )
    parser.add_argument("spec", type=Path, metavar="SPEC", help="the spec whose lock lists KEY")
    parser.add_argument("--key", required=True, help="the sample's object key, from the lock")
    parser.add_argument("--sample", help="output name; default: the key's file name, unsuffixed")
    parser.add_argument("--ref", type=Path, help="the gate's reference FASTA, from `loci`")
    parser.add_argument(
        "--gate",
        choices=("bbduk", "none"),
        default="bbduk",
        help="none passes every read through, for wiring checks without bbduk",
    )
    parser.add_argument("--k", type=int, default=25, help="bbduk k-mer length")
    parser.add_argument("--hdist", type=int, default=1, help="bbduk Hamming distance")
    parser.add_argument("--threads", type=int, default=2, help="bbduk threads")
    parser.add_argument("--memory", default="6g", help="bbduk Java heap, as -Xmx takes it")
    parser.add_argument("--decompressor", choices=("lbzip2", "bzip2"), default="lbzip2")
    parser.add_argument("--decompressor-threads", type=int, default=4, help="lbzip2 only")
    parser.add_argument(
        "--max-reads", type=int, help="stop writing after this many hits; counting goes on"
    )
    parser.add_argument("--out-dir", type=Path, default=Path("."))
    parser.add_argument(
        "--resumes",
        type=int,
        default=RESUMES,
        help="consecutive failed reads from the remote before giving up",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> None:
    if args.gate == "bbduk" and args.ref is None:
        raise SystemExit("--gate bbduk needs --ref")
    spec = Spec.load(args.spec)
    try:
        obj = locked_object(spec, args.key)
    except ValueError as error:
        raise SystemExit(f"{spec.name}: {error}") from None
    sample = args.sample or sample_name(args.key)
    reads = args.out_dir / f"{sample}.loci.fastq.gz"
    counts = args.out_dir / f"{sample}.counts.tsv"
    provider = open_dataset(spec).provider
    # Opened once here, so an object that no longer matches the lock fails at once
    # rather than being retried as if it were a dropped connection.
    opened = [provider.open_stream(obj)]
    try:
        result = filter_sample(
            lambda start: opened.pop() if opened else provider.open_stream(obj, start),
            reads,
            size=obj.size,
            resumes=args.resumes,
            gate=gate_command(args),
            decompressor=decompressor_command(args.decompressor, args.decompressor_threads),
            max_reads=args.max_reads,
        )
    except RuntimeError as error:
        raise SystemExit(f"{sample}: {error}") from None
    write_counts(counts, sample, spec, args.key, result)
    capped = f"; capped at {result.written}" if result.written < result.passed else ""
    print(
        f"{sample}: {result.passed} of {result.seen} reads passed "
        f"({result.bytes_read / 1e9:.2f} GB read in {result.elapsed:.0f} s){capped} -> {reads}"
    )


def sample_name(key: str) -> str:
    """``.../subgingival_plaque/SRS013950.tar.bz2`` is ``SRS013950``."""
    return key.rsplit("/", 1)[-1].split(".", 1)[0]


def locked_object(spec: Spec, key: str) -> RemoteObject:
    """The lock's record for ``key``. Read from the lock, not listed from the remote, so
    the ETag the stream is checked against is the one the pipeline was planned from.
    """
    lock = read_lock(spec.lock_path)
    if lock is None:
        raise ValueError(f"{spec.lock_path} not found; sync the spec first")
    for record in lock["files"]:
        if record["key"] == key:
            modified = datetime.fromisoformat(record["last_modified"])
            return RemoteObject(key, record["size"], record["etag"], modified)
    raise ValueError(f"{key} is not in {spec.lock_path}")


def decompressor_command(name: str, threads: int) -> list[str]:
    return ["lbzip2", "-dc", "-n", str(threads)] if name == "lbzip2" else ["bzip2", "-dc"]


def gate_command(args: argparse.Namespace) -> list[str]:
    if args.gate == "none":
        return ["cat"]
    # int=f because bbduk otherwise sniffs the first two names, sees /1 and /2, and
    # treats the stream as interleaved pairs -- which it is not: mates arrive member by
    # member, so it would pair unrelated reads and gate them together.
    return [
        "bbduk.sh",
        f"-Xmx{args.memory}",
        "in=stdin.fq",
        "out=null",
        "outm=stdout.fq",
        f"ref={args.ref}",
        f"k={args.k}",
        f"hdist={args.hdist}",
        f"threads={args.threads}",
        "int=f",
    ]


def filter_sample(
    open_body: Callable[[int], BinaryIO],
    out: Path,
    *,
    gate: list[str],
    decompressor: list[str],
    size: int | None = None,
    max_reads: int | None = None,
    resumes: int = RESUMES,
) -> FilterResult:
    """Pipe a compressed tarball through ``decompressor`` and ``gate`` into gzipped FASTQ
    at ``out``, and count what went past. ``open_body(start)`` opens the remote object
    from byte ``start``; it is called again from where the stream stopped whenever a read
    fails, up to ``resumes`` times in a row. ``size``, if given, is checked at the end.

    Three threads, so no pipe can fill while its reader waits on another: one feeds the
    remote's bytes to the decompressor, this one demultiplexes the tar into the gate, and
    one drains the gate into the writer. Any stage failing raises, and ``out`` only
    appears once all of them have exited cleanly.
    """
    result = FilterResult()
    started = time.monotonic()
    out.parent.mkdir(parents=True, exist_ok=True)
    partial = out.with_name(f".{out.name}.part")
    errors: list[str] = []

    unpack = subprocess.Popen(decompressor, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    screen = subprocess.Popen(gate, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def feed() -> None:
        try:
            for chunk in _resumable(open_body, result, resumes):
                unpack.stdin.write(chunk)
            if size is not None and result.bytes_read != size:
                errors.append(f"read {result.bytes_read} bytes of {size}")
        except BrokenPipeError:
            pass  # the decompressor died; its exit status says why
        except BaseException as error:
            errors.append(f"reading the remote: {error!r}")
        finally:
            _close(unpack.stdin)

    def drain() -> None:
        try:
            with gzip.open(partial, "wb", compresslevel=6) as writer:
                result.passed, result.written = _write_records(screen.stdout, writer, max_reads)
        except BaseException as error:
            errors.append(f"writing {out.name}: {error!r}")

    feeder = threading.Thread(target=feed, daemon=True)
    drainer = threading.Thread(target=drain, daemon=True)
    feeder.start()
    drainer.start()
    try:
        _demultiplex(unpack.stdout, screen.stdin, result)
    except BrokenPipeError:
        pass  # the gate died; its exit status below says why
    except (RuntimeError, tarfile.TarError) as error:
        errors.append(str(error))
    finally:
        _close(screen.stdin)
        # Drained before waiting, so a decompressor still writing cannot block on a
        # pipe nobody reads -- the case when the tar ends before the stream does.
        while unpack.stdout.read(CHUNK):
            pass
        feeder.join()
        drainer.join()
        for command, process in ((decompressor, unpack), (gate, screen)):
            if (status := process.wait()) != 0:
                errors.append(f"{command[0]} exited with status {status}")

    # Every failure is reported, not just the first: a dropped connection also leaves
    # the decompressor complaining about a truncated stream, and both are the story.
    if errors:
        partial.unlink(missing_ok=True)
        raise RuntimeError("; ".join(errors))
    partial.replace(out)
    result.elapsed = time.monotonic() - started
    return result


def _resumable(
    open_body: Callable[[int], BinaryIO], result: FilterResult, resumes: int
) -> Iterator[bytes]:
    """Yield the remote object's bytes in order, reopening it from the last byte received
    whenever a read fails.

    One GET over a whole sample does not survive: a 2 GB object takes an hour or more to
    pass through the gate, and when the gate falls behind, the reader stops reading and
    the connection times out or is cut. The first real run lost every attempt that way.
    A ranged reopen continues the same bytes, and the ETag guard in ``open_stream``
    refuses the reopen if the object changed in between.
    """
    failures = 0
    while True:
        try:
            body = open_body(result.bytes_read)
            try:
                while chunk := body.read(CHUNK):
                    result.bytes_read += len(chunk)
                    failures = 0
                    yield chunk
            finally:
                body.close()
            return
        except GeneratorExit:
            raise
        except Exception as error:
            failures += 1
            if failures > resumes:
                raise
            wait = min(2**failures, 60)
            print(
                f"read failed at byte {result.bytes_read} ({error!r}); "
                f"resuming in {wait} s ({failures}/{resumes})",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(wait)


def _demultiplex(stream: IO[bytes], gate: IO[bytes], result: FilterResult) -> None:
    """Copy every FASTQ member of the tar on ``stream`` into ``gate``, counting reads per
    mate. Copied in chunks rather than parsed: the gate sees every byte, so counting
    newlines is all the reading this side has to do.
    """
    with tarfile.open(fileobj=stream, mode="r|") as tar:
        for member in tar:
            if not member.isfile():
                continue
            match = MEMBER.search(member.name)
            if match is None:
                raise RuntimeError(f"unexpected tar member {member.name!r}")
            source = tar.extractfile(member)
            lines, last = 0, b"\n"
            while chunk := source.read(CHUNK):
                lines += chunk.count(b"\n")
                last = chunk[-1:]
                result.bytes_decompressed += len(chunk)
                gate.write(chunk)
            if last != b"\n" or lines % 4:
                raise RuntimeError(f"{member.name} is not whole FASTQ records ({lines} lines)")
            result.reads[match.group(1)] += lines // 4


def _write_records(stream: IO[bytes], writer: IO[bytes], max_reads: int | None) -> tuple[int, int]:
    """Copy the four-line records on ``stream`` to ``writer``, up to ``max_reads`` of them,
    and return how many arrived and how many were written. Reading continues past the cap
    so the gate is never blocked and the count stays true.
    """
    passed = written = 0
    record: list[bytes] = []
    for line in stream:
        record.append(line)
        if len(record) < 4:
            continue
        passed += 1
        if max_reads is None or written < max_reads:
            writer.write(b"".join(record))
            written += 1
        record.clear()
    if record:
        raise RuntimeError(f"gate output ended mid-record ({len(record)} lines)")
    return passed, written


def _close(pipe: IO[bytes]) -> None:
    with contextlib.suppress(BrokenPipeError):
        pipe.close()


def write_counts(path: Path, sample: str, spec: Spec, key: str, result: FilterResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(COUNTS_COLUMNS)
        writer.writerow(
            [
                sample,
                spec.name,
                key,
                *(result.reads[mate] for mate in MATES),
                result.seen,
                result.passed,
                result.written,
                result.bytes_read,
                result.bytes_decompressed,
                f"{result.elapsed:.1f}",
            ]
        )
