"""Datasets select what to fetch from a provider and where it lands locally.

Specs and locks are not this package's concern: building a dataset from a spec is
:func:`hmp_project.manifest.dataset.open_dataset`.
"""

from __future__ import annotations

from hmp_project.datasets.base import Dataset, S3Dataset
from hmp_project.datasets.hmp import HMPDataset
from hmp_project.datasets.hmpdcc import HMPDCCDataset
from hmp_project.datasets.pmc import PMCDataset
from hmp_project.datasets.slacken import SlackenDataset
from hmp_project.datasets.sra import SRADataset
from hmp_project.datasets.sra_metadata import SRAMetadataDataset

DATASETS: dict[str, type[S3Dataset]] = {
    "hmp": HMPDataset,
    "hmpdcc": HMPDCCDataset,
    "pmc": PMCDataset,
    "slacken": SlackenDataset,
    "sra": SRADataset,
    "sra-metadata": SRAMetadataDataset,
}

__all__ = [
    "DATASETS",
    "Dataset",
    "HMPDCCDataset",
    "HMPDataset",
    "PMCDataset",
    "S3Dataset",
    "SRADataset",
    "SRAMetadataDataset",
    "SlackenDataset",
]
