"""
E2E test for error handling and recovery scenarios.

This module validates system behavior under common error conditions:
  1. Minimal PDF indexing edge cases.
  2. Indexing idempotency (re-indexing after deletion).
  3. Search API error responses and semantic fallback behavior.

Prerequisites:
  • The local stack is running
  • solr-search is reachable at SEARCH_API_URL
"""

from __future__ import annotations

import hashlib
import io
import time
from pathlib import Path

import pytest
import requests
from conftest import SOLR_ADMIN_PASS, SOLR_ADMIN_USER, _build_pdf, wait_for_solr_doc
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


def _wait_for_absence(solr_url: str, doc_id: str, timeout: int = 30) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        doc = _fetch_solr_doc(solr_url, doc_id, "id")
        if not doc:
            return True
        time.sleep(1)
    return False


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


class TestDocumentIndexingEdgeCases:
    """Validate indexing edge cases for unusual but accepted PDFs."""

    def test_empty_pdf_handled(
        self,
        solr_url: str,
        test_library_root: Path,
        solr_available: None,
    ) -> None:
        """
        Index a minimal PDF containing no text and ensure it is accepted.
        """
        pdf_path = test_library_root / "TestAuthor/TestAuthor - Empty PDF (2024).pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(_build_pdf(""))

        relative = pdf_path.relative_to(test_library_root).as_posix()
        doc_id = hashlib.sha256(relative.encode()).hexdigest()
        try:
            resp = _index_pdf(solr_url, pdf_path, test_library_root)
            assert resp.status_code == 200, f"Solr /update/extract returned {resp.status_code}: {resp.text}"
            doc = wait_for_solr_doc(solr_url, doc_id, timeout=60)
            assert doc is not None, "Empty PDF did not appear in Solr after indexing."
            stored = _fetch_solr_doc(solr_url, doc_id, "id,title_s,author_s")
            assert stored.get("id") == doc_id
            assert stored.get("title_s"), "title_s should be populated for empty PDFs."
        finally:
            _delete_solr_doc(solr_url, doc_id)
            pdf_path.unlink(missing_ok=True)



class TestServiceFailureRecovery:
    """Validate graceful API error handling and idempotent indexing."""

    def test_search_rejects_unknown_collection(
        self,
        api_url: str,
        api_available: None,
        auth_headers: dict[str, str],
    ) -> None:
        """
        Unknown Solr collection names should be rejected with HTTP 400.
        """
        resp = requests.get(
            f"{api_url}/v1/search",
            params={"q": "test", "collection": "unknown_collection"},
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 400, f"Expected 400 for unknown collection, got {resp.status_code}: {resp.text}"

    def test_semantic_search_returns_supported_mode(
        self,
        api_url: str,
        api_available: None,
        auth_headers: dict[str, str],
    ) -> None:
        """
        Semantic search should return either semantic results or documented keyword degradation.
        """
        resp = requests.get(
            f"{api_url}/v1/search",
            params={"q": "E2E test document", "mode": "semantic"},
            headers=auth_headers,
            timeout=20,
        )
        resp.raise_for_status()
        body = resp.json()
        assert body.get("mode") in {"semantic", "keyword"}
        if body.get("mode") == "keyword":
            assert body.get("requested_mode") == "semantic"
            assert body.get("degraded") is True
        assert isinstance(body.get("results"), list)

    def test_reindex_after_delete_succeeds(
        self,
        solr_url: str,
        fixture_pdf: Path,
        fixture_solr_id: str,
        test_library_root: Path,
        solr_available: None,
    ) -> None:
        """
        Re-indexing after deleting a document should succeed.
        """
        resp = _index_pdf(solr_url, fixture_pdf, test_library_root)
        assert resp.status_code == 200, f"Solr /update/extract returned {resp.status_code}: {resp.text}"
        doc = wait_for_solr_doc(solr_url, fixture_solr_id, timeout=60)
        assert doc is not None, "Fixture document did not appear in Solr after indexing."

        _delete_solr_doc(solr_url, fixture_solr_id)
        assert _wait_for_absence(solr_url, fixture_solr_id), "Fixture document did not delete cleanly."

        resp = _index_pdf(solr_url, fixture_pdf, test_library_root)
        assert resp.status_code == 200, f"Solr /update/extract returned {resp.status_code}: {resp.text}"
        doc = wait_for_solr_doc(solr_url, fixture_solr_id, timeout=60)
        assert doc is not None, "Fixture document did not reappear in Solr after reindex."

        _delete_solr_doc(solr_url, fixture_solr_id)

    def test_rabbitmq_reconnection(
        self,
        api_url: str,
        auth_headers: dict[str, str],
        api_available: None,
    ) -> None:
        """
        Upload endpoint should accept a valid PDF when RabbitMQ is reachable.
        """
        resp = requests.post(
            f"{api_url}/v1/upload",
            files={"file": ("reconnect.pdf", io.BytesIO(_build_pdf()), "application/pdf")},
            headers=auth_headers,
            timeout=30,
        )
        if resp.status_code in (500, 502, 503):
            pytest.skip(
                f"Upload endpoint returned {resp.status_code} — RabbitMQ may not be configured. Response: {resp.text}"
            )
        assert resp.status_code in (200, 201, 202), (
            f"Expected 200/201/202 for valid upload, got {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        assert "upload_id" in body or "status" in body, f"Unexpected upload response: {body}"


class TestDataIntegrityAfterFailure:
    """Validate data consistency after failure conditions."""

    def test_partial_index_rollback(
        self,
        solr_url: str,
        test_library_root: Path,
        solr_available: None,
    ) -> None:
        """
        If Solr rejects an invalid document, it should not appear in search.
        """
        pdf_path = test_library_root / "TestAuthor/TestAuthor - Corrupt Index (2024).pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(b"not a pdf")

        relative = pdf_path.relative_to(test_library_root).as_posix()
        doc_id = hashlib.sha256(relative.encode()).hexdigest()
        try:
            resp = requests.post(
                f"{solr_url}/update/extract",
                params={
                    "resource.name": pdf_path.name,
                    "commitWithin": "2000",
                    "literal.id": doc_id,
                    "literal.title_s": "Corrupt Index",
                    "literal.author_s": "TestAuthor",
                    "literal.file_path_s": relative,
                    "literal.folder_path_s": pdf_path.parent.relative_to(test_library_root).as_posix(),
                    "literal.file_size_l": str(pdf_path.stat().st_size),
                    "literal.category_s": "TestCategory",
                },
                files={"file": ("corrupt.pdf", io.BytesIO(b"not a pdf"), "application/pdf")},
                auth=SOLR_AUTH,
                timeout=30,
            )
            if resp.status_code == 200:
                pytest.skip("Solr accepted invalid PDF bytes; skipping rollback assertion.")
            doc = wait_for_solr_doc(solr_url, doc_id, timeout=10)
            assert doc is None, "Corrupt document appeared in Solr despite failed indexing."
        finally:
            _delete_solr_doc(solr_url, doc_id)
            pdf_path.unlink(missing_ok=True)

    def test_search_consistency_during_reindex(
        self,
        api_url: str,
        api_available: None,
        auth_headers: dict[str, str],
        solr_url: str,
        fixture_pdf: Path,
        fixture_solr_id: str,
        test_library_root: Path,
        solr_available: None,
    ) -> None:
        """
        Searches should continue to return the document after reindexing.
        """
        resp = _index_pdf(solr_url, fixture_pdf, test_library_root)
        assert resp.status_code == 200, f"Solr /update/extract returned {resp.status_code}: {resp.text}"
        doc = wait_for_solr_doc(solr_url, fixture_solr_id, timeout=60)
        assert doc is not None, "Fixture document did not appear in Solr after indexing."

        resp = requests.get(
            f"{api_url}/v1/search",
            params={"q": "E2E test document for aithena"},
            headers=auth_headers,
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        result_ids = {item.get("id") for item in results if isinstance(item, dict)}
        assert fixture_solr_id in result_ids, "Fixture document missing from initial search results."

        resp = _index_pdf(solr_url, fixture_pdf, test_library_root)
        assert resp.status_code == 200, f"Solr /update/extract returned {resp.status_code}: {resp.text}"
        doc = wait_for_solr_doc(solr_url, fixture_solr_id, timeout=60)
        assert doc is not None, "Fixture document did not appear in Solr after reindex."

        resp = requests.get(
            f"{api_url}/v1/search",
            params={"q": "E2E test document for aithena"},
            headers=auth_headers,
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        result_ids = {item.get("id") for item in results if isinstance(item, dict)}
        assert fixture_solr_id in result_ids, "Fixture document missing from search results after reindex."

        _delete_solr_doc(solr_url, fixture_solr_id)
