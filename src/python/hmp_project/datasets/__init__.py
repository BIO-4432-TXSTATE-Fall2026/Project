"""Datasets select what to fetch from a provider and where it lands locally."""

from __future__ import annotations

from hmp_project.datasets.base import Dataset, S3Dataset
from hmp_project.datasets.hmp import HMPDataset
from hmp_project.datasets.sra_metadata import SRAMetadataDataset
from hmp_project.manifest import Spec
from hmp_project.providers import Provider

DATASETS: dict[str, type[S3Dataset]] = {
    "hmp": HMPDataset,
    "sra-metadata": SRAMetadataDataset,
}


def open_dataset(spec: Spec, provider: Provider | None = None) -> Dataset:
    """Build the dataset a spec names. ``provider`` overrides the dataset's default."""
    try:
        factory = DATASETS[spec.dataset]
    except KeyError:
        known = ", ".join(sorted(DATASETS))
        message = f"{spec.path}: unknown dataset {spec.dataset!r} (known: {known})"
        raise ValueError(message) from None
    try:
        region = factory.resolve_region(spec.region)
    except ValueError as error:
        raise ValueError(f"{spec.path}: {spec.dataset}: {error}") from None
    return factory(
        spec.prefix,
        region=region,
        include=spec.include,
        exclude=spec.exclude,
        provider=provider,
    )


__all__ = [
    "DATASETS",
    "Dataset",
    "HMPDataset",
    "S3Dataset",
    "SRAMetadataDataset",
    "open_dataset",
]
