from __future__ import annotations

from typing import ClassVar

from hmp_project.datasets.base import S3Dataset


class HMPDCCDataset(S3Dataset):
    """HMP and iHMP data from the HMP Data Analysis and Coordination Center's bucket.

    ``ihmp/`` holds the iHMP studies (``ibdmdb``, ``momspi``, ``t2d``) and ``hmp1/`` a
    per-run reorganization of HMP phase 1, e.g. ``ihmp/ibdmdb/microbiome/wms/raw``.
    Raw reads are uncompressed FASTQ and ``ihmp/*/host/`` holds human data, so narrow
    ``include`` before syncing. Not part of AWS Open Data; it replaced the retired
    HMP DACC portal.
    """

    BUCKETS: ClassVar[dict[str, str]] = {"us-east-1": "hmpdcc"}
