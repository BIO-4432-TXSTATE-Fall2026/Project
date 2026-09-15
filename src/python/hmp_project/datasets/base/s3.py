from __future__ import annotations

from collections.abc import Iterable
from typing import ClassVar

from hmp_project.datasets.base.dataset import Dataset
from hmp_project.provider import Provider, S3Provider


class S3Dataset(Dataset):
    """A dataset served from S3. ``BUCKETS`` maps each region the data is hosted in to
    the bucket there; the first entry is the default.
    """

    BUCKETS: ClassVar[dict[str, str]]

    def __init__(
        self,
        prefix: str,
        *,
        region: str | None = None,
        include: Iterable[str] = ("*",),
        exclude: Iterable[str] = (),
        provider: Provider | None = None,
    ) -> None:
        self.region = self.resolve_region(region)
        provider = provider or S3Provider(self.BUCKETS[self.region], region=self.region)
        super().__init__(provider, prefix, include=include, exclude=exclude)

    @classmethod
    def resolve_region(cls, region: str | None = None) -> str:
        """Return the region code ``region`` names: a code such as ``us-east-1``, or an
        unambiguous hyphen-delimited part of one such as ``east``. ``None`` is the default.
        """
        available = list(cls.BUCKETS)
        if region is None:
            return available[0]
        wanted = region.strip().lower()
        if wanted in cls.BUCKETS:
            return wanted
        matches = [code for code in available if f"-{wanted}-" in f"-{code}-"]
        if len(matches) == 1:
            return matches[0]
        if matches:
            raise ValueError(f"region {region!r} is ambiguous (matches: {', '.join(matches)})")
        raise ValueError(f"region {region!r} is not available (available: {', '.join(available)})")
