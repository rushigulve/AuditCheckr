"""Local filesystem document provider."""
from __future__ import annotations

from pathlib import Path

from .base import DocumentProvider


class LocalFileSystemProvider(DocumentProvider):
    """
    Reads .docx files from a local directory or a single explicit path.

    Usage in CLI:
        --provider-a local --path-a ./contracts/v1.docx
        --provider-a local --path-a ./contracts/          # scans recursively
    """

    provider_id = "local"

    def __init__(self, path: str = "."):
        self._path = Path(path)

    def list_documents(self) -> list[str]:
        if self._path.is_file():
            return [str(self._path)]
        return sorted(str(p) for p in self._path.rglob("*.docx"))

    def fetch_document(self, doc_id: str) -> bytes:
        return Path(doc_id).read_bytes()
