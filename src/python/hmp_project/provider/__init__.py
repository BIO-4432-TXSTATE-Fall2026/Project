"""Providers download remote objects as-is. They do no preprocessing."""

from hmp_project.provider.base import Provider, RemoteObject
from hmp_project.provider.s3 import S3Provider

__all__ = ["Provider", "RemoteObject", "S3Provider"]
