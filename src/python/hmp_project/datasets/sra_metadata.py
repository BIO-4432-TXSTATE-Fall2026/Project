from __future__ import annotations

from typing import ClassVar

from hmp_project.datasets.base import S3Dataset


class SRAMetadataDataset(S3Dataset):
    """NCBI Sequence Read Archive metadata from the AWS Open Data bucket.

    ``sra/metadata`` holds one Parquet table with a row per SRA run (sequencing center,
    instrument, sample and BioProject accessions, release date, consent). NCBI appears
    to replace every file with a fresh snapshot daily, so each sync can re-download the
    whole table (about 14 GB). See https://registry.opendata.aws/ncbi-sra/.
    """

    BUCKETS: ClassVar[dict[str, str]] = {"us-east-1": "sra-pub-metadata-us-east-1"}
