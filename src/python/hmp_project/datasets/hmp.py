from __future__ import annotations

from collections.abc import Iterable

from hmp_project.datasets.base import Dataset
from hmp_project.provider import Provider, S3Provider


class HMPDataset(Dataset):
    """Human Microbiome Project data from the AWS Open Data bucket.

    ``prefix`` picks the product, e.g. ``HHS/HMQCP`` or ``HHS/HMSMCP``. Some raw-read
    objects are tens of gigabytes, so narrow ``include`` before syncing those.
    See https://registry.opendata.aws/human-microbiome-project/.
    """

    BUCKET = "human-microbiome-project"
    REGION = "us-west-2"

    def __init__(
        self,
        prefix: str,
        *,
        include: Iterable[str] = ("*",),
        exclude: Iterable[str] = (),
        provider: Provider | None = None,
    ) -> None:
        provider = provider or S3Provider(self.BUCKET, region=self.REGION)
        super().__init__(provider, prefix, include=include, exclude=exclude)
