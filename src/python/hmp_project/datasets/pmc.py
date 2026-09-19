from __future__ import annotations

from typing import ClassVar

from hmp_project.datasets.base import S3Dataset


class PMCDataset(S3Dataset):
    """PubMed Central open-access articles, one ``<PMCID>.<version>/`` prefix each.

    Each prefix holds the article as XML, text, and PDF beside its supplementary files
    under the publisher's names, e.g. ``PMC10653788.1/mbio.01607-23-s0004.xlsx``. Only
    the open-access subset is here. See https://registry.opendata.aws/ncbi-pmc/.
    """

    BUCKETS: ClassVar[dict[str, str]] = {"us-east-1": "pmc-oa-opendata"}
