from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import ClassVar

from hmp_project.datasets.base import S3Dataset

RUN_ACCESSION = re.compile(r"[DES]RR[0-9]{6,}")


class SRADataset(S3Dataset):
    """NCBI Sequence Read Archive run data from the AWS Open Data bucket.

    Selected by run accession, not by prefix: each run is a single object at
    ``sra/<accession>/<accession>``, and the bucket holds every public SRA run (tens of
    millions of objects), so a prefix broad enough to cover several runs would take
    hours to list. Map samples or studies to run accessions with the ``sra-metadata``
    dataset first.

    Each object is an ``.sra`` archive rather than FASTQ; :meth:`convert` extracts the
    reads. Single runs reach tens of gigabytes, and their FASTQ several times that.
    See https://registry.opendata.aws/ncbi-sra/.
    """

    BUCKETS: ClassVar[dict[str, str]] = {"us-east-1": "sra-pub-run-odp"}

    @classmethod
    def accession_prefix(cls, accession: str) -> str:
        if not RUN_ACCESSION.fullmatch(accession):
            raise ValueError(
                f"{accession!r} is not an SRA run accession (DRR, ERR, or SRR followed by "
                "at least six digits; sample and study accessions such as SRS or ERP "
                "name no runs)"
            )
        return f"sra/{accession}/"

    def convert(self, path: Path, *, threads: int | None = None) -> list[Path]:
        """Extract uncompressed FASTQ from the ``.sra`` archive at ``path`` into its
        directory with ``fasterq-dump``: ``<run>_1.fastq`` and ``<run>_2.fastq`` for
        paired reads and ``<run>.fastq`` for unpaired ones.

        FASTQ newer than the archive is kept as is, so reruns only convert new or
        re-synced runs. Output is written to a temporary directory beside the archive
        and moved into place, so an interrupted run leaves no partial FASTQ; that
        directory needs free space of about the FASTQ's size again.
        """
        outputs = [path.with_name(f"{path.name}{suffix}.fastq") for suffix in ("", "_1", "_2")]
        existing = [output for output in outputs if output.is_file()]
        if existing and all(o.stat().st_mtime >= path.stat().st_mtime for o in existing):
            return existing

        fasterq_dump = shutil.which("fasterq-dump")
        if fasterq_dump is None:
            raise RuntimeError(
                "fasterq-dump not found; it is installed in the sra environment "
                "(pixi run convert, or pixi run -e sra ...)"
            )
        for output in existing:
            output.unlink()
        with tempfile.TemporaryDirectory(prefix=".fasterq-dump-", dir=path.parent) as work:
            out = Path(work) / "out"
            command = [fasterq_dump, str(path), "--outdir", str(out), "--temp", work]
            if threads is not None:
                command += ["--threads", str(threads)]
            try:
                subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
            except subprocess.CalledProcessError as error:
                raise RuntimeError(
                    f"fasterq-dump failed on {path} (exit {error.returncode})"
                ) from None
            for output in outputs:
                if (out / output.name).is_file():
                    (out / output.name).replace(output)
        return [output for output in outputs if output.is_file()]
