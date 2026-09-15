"""Datasets select what to fetch from a provider and where it lands locally."""

from __future__ import annotations

from collections.abc import Callable

from hmp_project.datasets.base import Dataset
from hmp_project.datasets.hmp import HMPDataset
from hmp_project.manifest import Spec
from hmp_project.provider import Provider

DATASETS: dict[str, Callable[..., Dataset]] = {
    "hmp": HMPDataset,
}


def open_dataset(spec: Spec, provider: Provider | None = None) -> Dataset:
    """Build the dataset a spec names. ``provider`` overrides the dataset's default."""
    try:
        factory = DATASETS[spec.dataset]
    except KeyError:
        known = ", ".join(sorted(DATASETS))
        message = f"{spec.path}: unknown dataset {spec.dataset!r} (known: {known})"
        raise ValueError(message) from None
    return factory(spec.prefix, include=spec.include, exclude=spec.exclude, provider=provider)


__all__ = ["DATASETS", "Dataset", "HMPDataset", "open_dataset"]
