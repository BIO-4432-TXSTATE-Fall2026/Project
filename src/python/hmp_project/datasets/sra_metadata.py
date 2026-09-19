from __future__ import annotations

import gzip
import json
import re
from collections.abc import Container, Iterator
from pathlib import Path
from typing import Any, ClassVar

from hmp_project.datasets.base import Profile, S3Dataset

# The identifying accessions of a row, searched without parsing it. Rows that match
# neither are the overwhelming majority, and parsing all of them is the slow part.
SAMPLE = re.compile(rb'"sample_acc"\s*:\s*"([^"]+)"')
STUDY = re.compile(rb'"sra_study"\s*:\s*"([^"]+)"')

# Source field -> column name. Renamed where the source name says less than it could.
FIELDS = {
    "acc": "run",
    "sample_acc": "sample",
    "sra_study": "study",
    "bioproject": "bioproject",
    "biosample": "biosample",
    "center_name": "center",
    "releasedate": "releasedate",
    "platform": "platform",
    "instrument": "instrument",
    "librarylayout": "librarylayout",
    "libraryselection": "libraryselection",
    "assay_type": "assay_type",
    "mbases": "mbases",
}

# Salter et al. (2014) name each sample "<KIT>_<step>" — "CAMBIO_4", "MP_BIO_10" — so the
# extraction kit and the dilution step are one split apart. Underscores are kept in the
# kit, since the alias is what the negative control and the dilution runs have in common.
SALTER_ALIAS = re.compile(r"(?P<kit>.+)_(?P<dilution>[0-9]+)")


def _attribute(row: dict[str, Any], key: str) -> str:
    """One sample attribute of ``row``, out of the ``jattr`` blob where SRA keeps whatever
    the submitter sent alongside the fixed fields.

    Values arrive as bare scalars or as one-element lists depending on the attribute, and
    both mean the same thing here.
    """
    value = json.loads(row.get("jattr") or "{}").get(key)
    if isinstance(value, list):
        value = value[0] if value else None
    return "" if value is None else str(value)


def _salter(row: dict[str, Any]) -> dict[str, str]:
    """The extraction kit and dilution step of a Salter et al. (2014) run.

    ``alias`` is kept beside the two parsed columns so the split stays checkable in the
    committed table rather than only in this function. The negative water control is
    ``Water``, which names no kit and no step, so both come back empty.
    """
    alias = _attribute(row, "alias_sam")
    match = SALTER_ALIAS.fullmatch(alias)
    return {
        "alias": alias,
        "kit": match["kit"] if match else "",
        "dilution": match["dilution"] if match else "",
    }


class SRAMetadataDataset(S3Dataset):
    """NCBI Sequence Read Archive metadata from the AWS Open Data bucket.

    Two copies of the same table live here, and they behave very differently:

    ``sra/metadata_json/`` is one frozen snapshot, ``09_01_2020``, 60 gzipped JSON Lines
    files totalling about 2.2 GB, untouched since September 2020. Stable keys mean a
    re-sync reports nothing changed, so a lock over it stays meaningful, and JSON Lines
    needs no Parquet reader. It covers everything released up to 2020-09-01, which
    includes HMP1, Salter et al. (2014), and Zeller et al. (2014). Prefer it.

    ``sra/metadata/`` is the current table: 30 Parquet files, about 13 GB, rewritten by a
    fresh Trino query every day, so every key changes nightly and a lock over it churns
    without meaning. Only worth the trouble for runs released after the freeze.

    Neither is partitioned by accession, so there is no way to fetch just the rows for one
    sample; :meth:`extract` reads whole files and keeps the rows it wants.
    See https://registry.opendata.aws/ncbi-sra/.
    """

    BUCKETS: ClassVar[dict[str, str]] = {"us-east-1": "sra-pub-metadata-us-east-1"}
    EXTRACT_COLUMNS: ClassVar[tuple[str, ...]] = tuple(FIELDS.values())
    EXTRACT_PROFILES: ClassVar[dict[str, Profile]] = {
        "salter": Profile(("alias", "kit", "dilution"), _salter)
    }

    def extract(
        self, path: Path, accessions: Container[str], *, profile: Profile | None = None
    ) -> Iterator[dict[str, str]]:
        """Yield the rows of the JSON Lines file at ``path`` whose sample or study is in
        ``accessions``, with ``profile``'s columns appended if it is given.

        A sample's rows are not all alike: an HMP sample carries its 16S amplicon runs
        alongside its WGS runs, so ``platform`` and ``assay_type`` are kept for callers to
        filter on. Rows naming neither a sample nor a study are skipped rather than parsed.
        """
        with gzip.open(path, "rb") as f:
            for line in f:
                sample, study = SAMPLE.search(line), STUDY.search(line)
                if not (
                    (sample and sample.group(1).decode() in accessions)
                    or (study and study.group(1).decode() in accessions)
                ):
                    continue
                row = json.loads(line)
                extracted = {column: str(row.get(field) or "") for field, column in FIELDS.items()}
                yield extracted if profile is None else extracted | profile.read(row)
