"""The bridge from a spec to the dataset it names.

Lives here rather than in ``hmp_project.datasets`` so that package stays unaware of
specs and locks: datasets select objects from a provider, and nothing more.
"""

from __future__ import annotations

from hmp_project.datasets import DATASETS, Dataset
from hmp_project.manifest.spec import Spec
from hmp_project.providers import Provider


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
        return factory(
            spec.prefix,
            accessions=spec.accessions,
            region=region,
            include=spec.include,
            exclude=spec.exclude,
            provider=provider,
        )
    except ValueError as error:
        raise ValueError(f"{spec.path}: {spec.dataset}: {error}") from None
