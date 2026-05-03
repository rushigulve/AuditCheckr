"""
SharePoint document provider — STUB.

Implement `list_documents` and `fetch_document` using the
Microsoft Graph API (e.g. via the `Office365-REST-Python-Client`
or `msal` + `requests` libraries).

Register in providers/__init__.py:
    from .sharepoint import SharePointProvider
    REGISTRY["sharepoint"] = SharePointProvider
"""
from __future__ import annotations

from .base import DocumentProvider


class SharePointProvider(DocumentProvider):
    provider_id = "sharepoint"

    def __init__(self, site_url: str, client_id: str, client_secret: str, library: str = "Documents"):
        self.site_url      = site_url
        self.client_id     = client_id
        self.client_secret = client_secret
        self.library       = library

    def list_documents(self) -> list[str]:
        raise NotImplementedError("SharePoint provider not yet implemented.")

    def fetch_document(self, doc_id: str) -> bytes:
        raise NotImplementedError("SharePoint provider not yet implemented.")
