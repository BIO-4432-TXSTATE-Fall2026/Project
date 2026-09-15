"""Providers download remote objects as-is. They do no preprocessing."""

from hmp_project.providers.base import Provider, RemoteObject
from hmp_project.providers.s3 import S3Provider

__all__ = ["Provider", "RemoteObject", "S3Provider"]
