from __future__ import annotations

import re
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

    Each object is an ``.sra`` archive rather than FASTQ, so reads need ``fasterq-dump``
    from sra-tools afterwards. Single runs reach tens of gigabytes.
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
