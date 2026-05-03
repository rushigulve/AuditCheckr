"""Abstract base class every document provider must implement."""
from __future__ import annotations

from abc import ABC, abstractmethod


class DocumentProvider(ABC):
    """
    Plug in any document source by implementing these two methods.
    Registration: add one entry to providers/__init__.py REGISTRY.
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Short unique name used in logs and CLI (e.g. 'local', 's3')."""

    @abstractmethod
    def list_documents(self) -> list[str]:
        """Return all document identifiers available from this source."""

    @abstractmethod
    def fetch_document(self, doc_id: str) -> bytes:
        """Return raw .docx bytes for a given document identifier."""
