from __future__ import annotations

from typing import ClassVar

from hmp_project.datasets.base import S3Dataset


class HMPDataset(S3Dataset):
    """Human Microbiome Project data from the AWS Open Data bucket.

    ``prefix`` picks the product, e.g. ``HHS/HMQCP`` or ``HHS/HMSMCP``. Some raw-read
    objects are tens of gigabytes, so narrow ``include`` before syncing those.
    See https://registry.opendata.aws/human-microbiome-project/.
    """

    BUCKETS: ClassVar[dict[str, str]] = {"us-west-2": "human-microbiome-project"}
