from __future__ import annotations

import bz2
import csv
import gzip
import io
import tarfile

import pytest

from hmp_project.cli import filter as filter_cli
from hmp_project.cli import main
from hmp_project.manifest import open_dataset
from hmp_project.manifest.sync import sync

KEY = "HHS/HMQCP/SRS013950.tar.bz2"


def fastq(mate: str, n: int) -> bytes:
    suffix = "" if mate == "singleton" else f"/{mate}"
    return b"".join(f"@read{i}{suffix}\nACGTACGTAC\n+\nIIIIIIIIII\n".encode() for i in range(n))


def tarball(members: list[tuple[str, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for name, data in members:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return bz2.compress(buffer.getvalue())


# Singleton first, then .2 before .1: the orders the real tarballs arrive in vary, and
# routing by position is exactly what this pins against.
ODD_ORDER = [
    ("SRS013950/SRS013950.singleton.fastq", fastq("singleton", 3)),
    ("SRS013950/SRS013950.2.fastq", fastq("2", 5)),
    ("SRS013950/SRS013950.1.fastq", fastq("1", 5)),
]


@pytest.fixture
def sample(tmp_path, make_provider, write_spec, monkeypatch):
    provider = make_provider({KEY: tarball(ODD_ORDER)})
    spec = write_spec()
    sync(spec, tmp_path / "data", provider=provider, download=False)
    monkeypatch.setattr(filter_cli, "open_dataset", lambda spec: open_dataset(spec, provider))
    return spec, provider


def run_filter(spec, tmp_path, *extra: str) -> None:
    main(
        [
            "filter",
            str(spec.path),
            f"--key={KEY}",
            "--gate=none",
            "--decompressor=bzip2",
            f"--out-dir={tmp_path / 'out'}",
            *extra,
        ]
    )


def read_counts(path) -> dict[str, str]:
    with path.open() as f:
        return next(csv.DictReader(f, delimiter="\t"))


def test_filter_streams_every_member_whatever_its_order(tmp_path, sample):
    spec, provider = sample
    run_filter(spec, tmp_path)

    out = tmp_path / "out"
    reads = gzip.decompress((out / "SRS013950.loci.fastq.gz").read_bytes())
    assert reads.count(b"\n") == 4 * 13
    assert reads.count(b"/1\n") == 5 and reads.count(b"/2\n") == 5

    counts = read_counts(out / "SRS013950.counts.tsv")
    assert (counts["reads_1"], counts["reads_2"], counts["reads_singleton"]) == ("5", "5", "3")
    assert counts["reads_seen"] == counts["reads_passed"] == counts["reads_written"] == "13"
    assert counts["spec"] == "demo"
    assert int(counts["bytes_read"]) == len(provider.objects[KEY][0])
    assert provider.downloads == [f"{KEY}[0:]"]


def test_filter_max_reads_caps_writing_but_not_counting(tmp_path, sample):
    spec, _ = sample
    run_filter(spec, tmp_path, "--max-reads=4")

    out = tmp_path / "out"
    reads = gzip.decompress((out / "SRS013950.loci.fastq.gz").read_bytes())
    assert reads.count(b"\n") == 4 * 4
    counts = read_counts(out / "SRS013950.counts.tsv")
    assert (counts["reads_passed"], counts["reads_written"]) == ("13", "4")


def test_filter_fails_on_a_truncated_stream(tmp_path, sample):
    spec, provider = sample
    data = provider.objects[KEY][0]
    provider.put(KEY, data[: len(data) // 2])
    # Re-synced so the lock's ETag matches the truncated body: what is under test is
    # the decompressor's failure reaching the exit status, not the ETag guard.
    sync(spec, tmp_path / "data", provider=provider, download=False)

    with pytest.raises(SystemExit, match="bzip2 exited with status"):
        run_filter(spec, tmp_path)
    assert not list((tmp_path / "out").glob("*.fastq.gz"))


def test_filter_refuses_a_changed_object(tmp_path, sample):
    spec, provider = sample
    provider.put(KEY, tarball(ODD_ORDER[:1]))

    with pytest.raises(OSError, match="changed"):
        run_filter(spec, tmp_path)


def test_filter_rejects_a_member_it_cannot_route(tmp_path, sample):
    spec, provider = sample
    provider.put(KEY, tarball([("SRS013950/notes.txt", b"hello\n"), *ODD_ORDER]))
    sync(spec, tmp_path / "data", provider=provider, download=False)

    with pytest.raises(SystemExit, match="unexpected tar member"):
        run_filter(spec, tmp_path)


def test_filter_rejects_a_key_not_in_the_lock(tmp_path, sample):
    spec, _ = sample
    with pytest.raises(SystemExit, match="not in"):
        main(["filter", str(spec.path), "--key=nope.tar.bz2", "--gate=none"])


def test_sample_name():
    assert filter_cli.sample_name("HHS/HMASM/WGS/stool/SRS011084.tar.bz2") == "SRS011084"


class Flaky(io.BytesIO):
    """Raises once ``fail_at`` bytes have been read, the way a timed-out GET does."""

    def __init__(self, data: bytes, fail_at: int) -> None:
        super().__init__(data)
        self.fail_at = fail_at

    def read(self, size: int = -1) -> bytes:
        if self.tell() >= self.fail_at:
            raise TimeoutError("read timed out")
        return super().read(min(size, self.fail_at - self.tell()))


def test_filter_resumes_a_dropped_stream_where_it_stopped(tmp_path, monkeypatch):
    monkeypatch.setattr(filter_cli.time, "sleep", lambda _: None)
    data = tarball(ODD_ORDER)
    starts: list[int] = []

    def open_body(start: int) -> io.BytesIO:
        starts.append(start)
        # Every connection drops after 200 bytes, so the sample needs many of them.
        return Flaky(data[start:], 200)

    out = tmp_path / "out.fastq.gz"
    result = filter_cli.filter_sample(
        open_body, out, gate=["cat"], decompressor=["bzip2", "-dc"], size=len(data)
    )

    assert starts == list(range(0, len(data), 200))
    assert result.bytes_read == len(data)
    assert result.seen == result.passed == 13
    assert gzip.decompress(out.read_bytes()).count(b"\n") == 4 * 13


def test_filter_gives_up_on_a_stream_that_stops_moving(tmp_path, monkeypatch):
    monkeypatch.setattr(filter_cli.time, "sleep", lambda _: None)
    data = tarball(ODD_ORDER)
    starts: list[int] = []

    def open_body(start: int) -> io.BytesIO:
        starts.append(start)
        return Flaky(data[start:], 0 if start else 100)

    out = tmp_path / "out.fastq.gz"
    with pytest.raises(RuntimeError, match="read timed out"):
        filter_cli.filter_sample(
            open_body, out, gate=["cat"], decompressor=["bzip2", "-dc"], resumes=3
        )
    # The first connection, then three resumes from where it stopped, then no more.
    assert starts == [0, 100, 100, 100]
    assert not out.exists()
