from __future__ import annotations

from typing import ClassVar

from hmp_project.datasets.base import S3Dataset


class HumanPangenomicsDataset(S3Dataset):
    """Human reference assemblies from the Human Pangenome Reference Consortium.

    T2T-CHM13 sits under ``T2T/CHM13/assemblies/``, the HPRC samples under ``working/``
    and ``submissions/``. The analysis set of CHM13 v2.0 is
    ``T2T/CHM13/assemblies/analysis_set/chm13v2.0.fa.gz``, a single bgzipped FASTA of
    about 940 MB. See https://registry.opendata.aws/hpgp-data/.
    """

    BUCKETS: ClassVar[dict[str, str]] = {"us-west-2": "human-pangenomics"}
