"""
E2E test for PDF attachment extraction and retrieval.

The current stack does not expose attachment-specific endpoints, so these
tests validate the closest production behaviors: document metadata indexing,
document download, and searchability of PDF content.

Prerequisites:
  • The local stack is running with Solr and solr-search reachable
  • E2E_LIBRARY_PATH is configured for the shared document volume
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin

import pytest
import requests
from conftest import SOLR_ADMIN_PASS, SOLR_ADMIN_USER, wait_for_solr_doc
from test_upload_index_search import _index_pdf

SOLR_AUTH = (SOLR_ADMIN_USER, SOLR_ADMIN_PASS)


def _fetch_solr_doc(solr_url: str, doc_id: str, fields: str) -> dict:
    resp = requests.get(
        f"{solr_url}/select",
        params={"q": f"id:{doc_id}", "wt": "json", "fl": fields},
        auth=SOLR_AUTH,
        timeout=10,
    )
    resp.raise_for_status()
    docs = resp.json().get("response", {}).get("docs", [])
    return docs[0] if docs else {}


def _delete_solr_doc(solr_url: str, doc_id: str) -> None:
    resp = requests.post(
        f"{solr_url}/update",
        params={"commit": "true", "wt": "json"},
        json={"delete": {"id": doc_id}},
        auth=SOLR_AUTH,
        timeout=30,
    )
    resp.raise_for_status()


@pytest.fixture(scope="class")
def indexed_fixture_doc(
    solr_url: str,
    fixture_pdf: Path,
    fixture_solr_id: str,
    test_library_root: Path,
    solr_available: None,
) -> str:
    resp = _index_pdf(solr_url, fixture_pdf, test_library_root)
    assert resp.status_code == 200, f"Solr /update/extract returned {resp.status_code}: {resp.text}"
    doc = wait_for_solr_doc(solr_url, fixture_solr_id, timeout=60)
    assert doc is not None, "Fixture document did not appear in Solr after indexing."
    yield fixture_solr_id
    _delete_solr_doc(solr_url, fixture_solr_id)


@pytest.fixture(scope="class")
def api_available(api_url: str) -> None:
    """Skip tests that require the solr-search API if it is not reachable."""
    try:
        resp = requests.get(f"{api_url}/health", timeout=5)
        resp.raise_for_status()
    except Exception as exc:
        pytest.skip(
            "solr-search API not reachable at "
            f"{api_url} — start the stack first (see README.md §E2E Tests). "
            f"Error: {exc}"
        )


class TestDocumentStorageMetadata:
    """Validate document metadata indexing and retrieval."""

    def test_basic_pdf_indexes_without_attachment_metadata(
        self,
        solr_url: str,
        indexed_fixture_doc: str,
        solr_available: None,
    ) -> None:
        """
        Index a PDF and verify the core metadata fields are present while
        attachment-specific fields remain absent.
        """
        doc = _fetch_solr_doc(solr_url, indexed_fixture_doc, "id,file_path_s,title_s,author_s")
        assert doc.get("id") == indexed_fixture_doc
        assert doc.get("file_path_s"), "file_path_s should be populated for indexed documents."
        assert doc.get("title_s"), "title_s should be populated for indexed documents."
        assert "attachment_count" not in doc, "Attachment metadata should not be populated for basic PDFs."

    def test_indexed_pdf_file_path_is_available_on_disk(
        self,
        solr_url: str,
        indexed_fixture_doc: str,
        test_library_root: Path,
        solr_available: None,
    ) -> None:
        """
        Verify the indexed PDF remains accessible on disk at the expected
        library path (mirrors attachment storage expectations).
        """
        doc = _fetch_solr_doc(solr_url, indexed_fixture_doc, "file_path_s")
        file_path = doc.get("file_path_s")
        assert file_path, "file_path_s missing from Solr document."
        full_path = test_library_root / file_path
        assert full_path.exists(), f"Expected PDF at {full_path}, but it does not exist."
        assert full_path.stat().st_size > 0, "PDF stored on disk is empty."

    def test_attachment_retrieval_api(
        self,
        api_url: str,
        api_available: None,
        auth_headers: dict[str, str],
        indexed_fixture_doc: str,
    ) -> None:
        """
        The document download endpoint should return the PDF with a valid
        Content-Disposition header.
        """
        detail = requests.get(
            f"{api_url}/v1/books/{indexed_fixture_doc}",
            headers=auth_headers,
            timeout=10,
        )
        detail.raise_for_status()
        doc_url = detail.json().get("document_url")
        assert doc_url, "document_url missing from book detail response."

        download_url = doc_url if doc_url.startswith(("http://", "https://")) else urljoin(f"{api_url}/", doc_url)
        resp = requests.get(download_url, headers=auth_headers, timeout=15)
        assert resp.status_code == 200, f"Expected 200 downloading document, got {resp.status_code}: {resp.text}"
        assert resp.headers.get("Content-Type") == "application/pdf"
        content_disp = resp.headers.get("Content-Disposition", "")
        assert "inline" in content_disp.lower(), f"Expected inline Content-Disposition, got {content_disp!r}"
        assert resp.content.startswith(b"%PDF-"), "Downloaded content does not look like a PDF."

    def test_attachment_search_in_content(
        self,
        api_url: str,
        api_available: None,
        auth_headers: dict[str, str],
        indexed_fixture_doc: str,
    ) -> None:
        """
        Verify that text content from the PDF is searchable via /v1/search.
        """
        resp = requests.get(
            f"{api_url}/v1/search",
            params={"q": "E2E test document for aithena"},
            headers=auth_headers,
            timeout=15,
        )
        resp.raise_for_status()
        body = resp.json()
        results = body.get("results", [])
        result_ids = {item.get("id") for item in results if isinstance(item, dict)}
        assert indexed_fixture_doc in result_ids, (
            f"Expected indexed document {indexed_fixture_doc} to appear in search results."
        )


class TestAttachmentSecurity:
    """Validate document download safety checks."""

    def test_attachment_download_requires_authentication(
        self,
        api_url: str,
        api_available: None,
    ) -> None:
        """
        Document downloads should require authentication before the token is decoded.
        """
        resp = requests.get(f"{api_url}/documents/not-a-token", timeout=10)
        assert resp.status_code == 401, (
            f"Expected 401 for missing auth, got {resp.status_code}: {resp.text}"
        )

    def test_attachment_path_traversal_prevented(
        self,
        api_url: str,
        api_available: None,
        auth_headers: dict[str, str],
    ) -> None:
        """
        Path traversal attempts should be rejected with 404.
        """
        encoded_path = "..%2F..%2Fetc%2Fpasswd"
        resp = requests.get(f"{api_url}/documents/{encoded_path}", headers=auth_headers, timeout=10)
        assert resp.status_code == 404, (
            f"Expected 404 for traversal token, got {resp.status_code}: {resp.text}"
        )
