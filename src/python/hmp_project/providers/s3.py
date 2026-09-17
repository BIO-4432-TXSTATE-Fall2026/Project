from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import boto3
from botocore import UNSIGNED
from botocore.config import Config

from hmp_project.providers.base import Provider, RemoteObject


class S3Provider(Provider):
    """Reads one S3 bucket. Anonymous (unsigned) access needs no AWS account."""

    def __init__(self, bucket: str, *, region: str | None = None, anonymous: bool = True) -> None:
        self.bucket = bucket
        self.region = region
        self.anonymous = anonymous
        config = Config(signature_version=UNSIGNED) if anonymous else None
        self._client = boto3.client("s3", region_name=region, config=config)

    def uri(self, key: str) -> str:
        return f"s3://{self.bucket}/{key}"

    def list_objects(self, prefix: str) -> Iterator[RemoteObject]:
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                yield RemoteObject(
                    key=item["Key"],
                    size=item["Size"],
                    etag=item["ETag"].strip('"'),
                    last_modified=item["LastModified"],
                )

    def download(self, obj: RemoteObject, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        # download_file writes to a temporary name and renames, so an interrupted
        # transfer never leaves a truncated file at dest.
        self._client.download_file(self.bucket, obj.key, str(dest))

    def download_range(self, obj: RemoteObject, start: int, end: int, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        response = self._client.get_object(
            Bucket=self.bucket, Key=obj.key, Range=f"bytes={start}-{end - 1}", IfMatch=obj.etag
        )
        # Written beside dest and renamed, like download_file, so no truncated file remains.
        partial = dest.with_name(f".{dest.name}.part")
        with partial.open("wb") as f:
            for chunk in response["Body"].iter_chunks(1 << 20):
                f.write(chunk)
        os.replace(partial, dest)

    def describe(self) -> dict[str, Any]:
        return {
            "type": "s3",
            "bucket": self.bucket,
            "region": self.region,
            "anonymous": self.anonymous,
            "boto3": boto3.__version__,
        }
