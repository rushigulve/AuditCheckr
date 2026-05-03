"""
S3 document provider — STUB.

Implement using `boto3`.  Install: pip install boto3

Register in providers/__init__.py:
    from .s3 import S3Provider
    REGISTRY["s3"] = S3Provider
"""
from __future__ import annotations

from .base import DocumentProvider


class S3Provider(DocumentProvider):
    provider_id = "s3"

    def __init__(self, bucket: str, prefix: str = "", region: str = "us-east-1"):
        self.bucket = bucket
        self.prefix = prefix
        self.region = region

    def list_documents(self) -> list[str]:
        raise NotImplementedError("S3 provider not yet implemented.")

    def fetch_document(self, doc_id: str) -> bytes:
        raise NotImplementedError("S3 provider not yet implemented.")
