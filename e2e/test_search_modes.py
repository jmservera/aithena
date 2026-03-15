"""
E2E tests for semantic search, hybrid search, and similar-books behavior.

These tests run against the live solr-search API and verify that the search
mode switching and similar-books endpoints behave correctly.  Tests that
require a working embeddings service are skipped automatically when the
service is not available, so this file runs cleanly in both minimal (keyword
only) and full (semantic + hybrid) stack configurations.

Prerequisites:
  • The stack is running and solr-search is reachable at SEARCH_API_URL.
  • Set SEARCH_API_URL to override (default: http://localhost:8080).

Coverage matrix
~~~~~~~~~~~~~~~

+----------------------------------------+---------+----------------------------+
| Scenario                               | Gated   | Note                       |
+========================================+=========+============================+
| Keyword mode returns results           | Yes     | requires indexed data      |
| Keyword mode response shape            | No      | deterministic              |
| Semantic empty query → 400             | No      | deterministic              |
| Hybrid empty query → 400              | No      | deterministic              |
| Semantic mode returns results          | Yes     | requires embeddings + data |
| Hybrid mode returns results            | Yes     | requires embeddings + data |
| Semantic mode field 'mode' == semantic | Yes     | requires embeddings + data |
| Hybrid mode field 'mode' == hybrid     | Yes     | requires embeddings + data |
| Similar books — unknown id → 404       | No      | deterministic              |
| Similar books — valid id returns list  | Yes     | requires embeddings + data |
| Similar books excludes source doc      | Yes     | requires embeddings + data |
+----------------------------------------+---------+----------------------------+

Deterministic tests (no gating) verify API contracts that hold regardless of
indexed content or embeddings availability.  Data-gated tests skip with an
explicit reason rather than failing.
"""

from __future__ import annotations

import os

import pytest
import requests

SEARCH_API_URL: str = os.environ.get("SEARCH_API_URL", "http://localhost:8080")
SEARCH_ENDPOINT = "/v1/search"
# Maximum number of indexed documents to probe when searching for one with a
# stored embedding vector (used by the any_embedded_document_id fixture).
MAX_EMBEDDING_PROBE_ATTEMPTS = 20


def _similar_endpoint(doc_id: str) -> str:
    """Return the similar-books URL for the given document ID."""
    return f"/v1/books/{doc_id}/similar"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def api_url() -> str:
    """Resolved base URL for the solr-search API."""
    return SEARCH_API_URL.rstrip("/")


@pytest.fixture(scope="session")
def api_available(api_url: str) -> None:
    """Skip all tests in this module if the API is not reachable."""
    try:
        resp = requests.get(f"{api_url}/health", timeout=5)
        resp.raise_for_status()
    except Exception as exc:
        pytest.skip(
            f"solr-search API not reachable at {api_url} — start the stack first "
            f"(see README.md §E2E Tests). Error: {exc}"
        )


@pytest.fixture(scope="session")
def embeddings_available(api_url: str, api_available: None) -> bool:
    """Return True when the embeddings service is reachable via a probe search."""
    try:
        resp = requests.get(
            f"{api_url}{SEARCH_ENDPOINT}",
            params={"q": "test", "mode": "semantic", "limit": "1"},
            timeout=10,
        )
        # 200 = embeddings working; 503/502 = embeddings down
        return resp.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="session")
def any_document_id(api_url: str, api_available: None) -> str | None:
    """Return the Solr id of the first indexed document, or None if no data."""
    try:
        resp = requests.get(
            f"{api_url}{SEARCH_ENDPOINT}",
            params={"q": "*", "mode": "keyword", "limit": "1"},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        docs = resp.json().get("results", [])
        return docs[0]["id"] if docs else None
    except Exception:
        return None


@pytest.fixture(scope="session")
def any_embedded_document_id(api_url: str, api_available: None, embeddings_available: bool) -> str | None:
    """Return the id of a document that has a stored embedding vector, or None.

    Unlike ``any_document_id``, this fixture probes the ``/v1/books/{id}/similar``
    endpoint for each candidate document (up to ``MAX_EMBEDDING_PROBE_ATTEMPTS``) until it finds one that
    returns HTTP 200 — confirming that the document has an embedding stored in
    Solr.  A 422 response means the embedding field is absent for that document.

    This is important because semantic and similar-books tests must exercise the
    actual embedding path; silently skipping on a missing vector gives false
    confidence that the feature works.
    """
    if not embeddings_available:
        return None
    try:
        resp = requests.get(
            f"{api_url}{SEARCH_ENDPOINT}",
            params={"q": "*", "mode": "keyword", "limit": str(MAX_EMBEDDING_PROBE_ATTEMPTS)},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        docs = resp.json().get("results", [])
        for doc in docs:
            doc_id = doc.get("id")
            if not doc_id:
                continue
            try:
                probe = requests.get(
                    f"{api_url}{_similar_endpoint(doc_id)}",
                    params={"limit": "1"},
                    timeout=10,
                )
                if probe.status_code == 200:
                    return doc_id
            except Exception:
                continue
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Keyword mode (deterministic response shape)
# ---------------------------------------------------------------------------


class TestKeywordSearch:
    """Keyword (BM25) search mode — response contract verification."""

    def test_keyword_search_returns_200(self, api_url: str, api_available: None) -> None:
        """GET /v1/search?q=*&mode=keyword must return HTTP 200."""
        resp = requests.get(
            f"{api_url}{SEARCH_ENDPOINT}",
            params={"q": "*", "mode": "keyword"},
            timeout=10,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_keyword_search_response_has_required_fields(
        self, api_url: str, api_available: None
    ) -> None:
        """Keyword search response must include query, total, results, and facets."""
        resp = requests.get(
            f"{api_url}{SEARCH_ENDPOINT}",
            params={"q": "*", "mode": "keyword"},
            timeout=10,
        )
        body = resp.json()
        for field in ("query", "total", "results", "facets"):
            assert field in body, f"'{field}' missing from search response: {body}"

    def test_keyword_search_mode_field_is_keyword(
        self, api_url: str, api_available: None
    ) -> None:
        """The 'mode' field in the keyword search response must be 'keyword'."""
        resp = requests.get(
            f"{api_url}{SEARCH_ENDPOINT}",
            params={"q": "*", "mode": "keyword"},
            timeout=10,
        )
        body = resp.json()
        assert body.get("mode") == "keyword", (
            f"Expected mode='keyword', got {body.get('mode')!r}"
        )

    def test_keyword_search_v1_alias_returns_200(self, api_url: str, api_available: None) -> None:
        """GET /v1/search/ (trailing slash alias) must return HTTP 200."""
        resp = requests.get(
            f"{api_url}/v1/search/",
            params={"q": "*", "mode": "keyword"},
            timeout=10,
        )
        assert resp.status_code == 200

    def test_keyword_search_results_have_id_and_title(
        self, api_url: str, api_available: None, any_document_id: str | None
    ) -> None:
        """Each result in a keyword search must include 'id' and 'title' fields."""
        if not any_document_id:
            pytest.skip("No indexed documents available — keyword result fields cannot be verified.")

        resp = requests.get(
            f"{api_url}{SEARCH_ENDPOINT}",
            params={"q": "*", "mode": "keyword", "limit": "5"},
            timeout=10,
        )
        body = resp.json()
        results = body.get("results", [])
        assert results, "Expected at least one result when indexed documents are present."
        for doc in results:
            assert "id" in doc, f"Result missing 'id': {doc}"
            assert "title" in doc, f"Result missing 'title': {doc}"


# ---------------------------------------------------------------------------
# Semantic search (gated on embeddings service)
# ---------------------------------------------------------------------------


class TestSemanticSearch:
    """Semantic (kNN) search mode — requires embeddings service."""

    def test_semantic_empty_query_returns_400(self, api_url: str, api_available: None) -> None:
        """GET /v1/search with mode=semantic and an empty query must return HTTP 400.

        This is deterministic — the validation happens before the embeddings
        service is called.
        """
        resp = requests.get(
            f"{api_url}{SEARCH_ENDPOINT}",
            params={"q": "", "mode": "semantic"},
            timeout=10,
        )
        assert resp.status_code == 400, (
            f"Expected 400 for empty semantic query, got {resp.status_code}: {resp.text}"
        )

    def test_semantic_search_returns_200_when_embeddings_available(
        self,
        api_url: str,
        api_available: None,
        embeddings_available: bool,
        any_document_id: str | None,
    ) -> None:
        """GET /v1/search?mode=semantic must return HTTP 200 when embeddings service is up.

        Gated: requires embeddings service + at least one indexed document with an embedding.
        """
        if not embeddings_available:
            pytest.skip("Embeddings service is not available in this stack configuration.")
        if not any_document_id:
            pytest.skip("No indexed documents — semantic search cannot be verified.")

        resp = requests.get(
            f"{api_url}{SEARCH_ENDPOINT}",
            params={"q": "book", "mode": "semantic", "limit": "5"},
            timeout=30,
        )
        assert resp.status_code == 200, (
            f"Expected 200 for semantic search, got {resp.status_code}: {resp.text}"
        )

    def test_semantic_search_mode_field_in_response(
        self,
        api_url: str,
        api_available: None,
        embeddings_available: bool,
        any_document_id: str | None,
    ) -> None:
        """Semantic search response must include mode='semantic'.

        Gated: requires embeddings service + indexed data.
        """
        if not embeddings_available:
            pytest.skip("Embeddings service is not available in this stack configuration.")
        if not any_document_id:
            pytest.skip("No indexed documents — semantic mode field cannot be verified.")

        resp = requests.get(
            f"{api_url}{SEARCH_ENDPOINT}",
            params={"q": "book", "mode": "semantic", "limit": "5"},
            timeout=30,
        )
        body = resp.json()
        assert body.get("mode") == "semantic", (
            f"Expected mode='semantic', got {body.get('mode')!r}"
        )

    def test_semantic_search_returns_results_list(
        self,
        api_url: str,
        api_available: None,
        embeddings_available: bool,
        any_document_id: str | None,
    ) -> None:
        """Semantic search response must include a 'results' list.

        Gated: requires embeddings service + indexed data.
        """
        if not embeddings_available:
            pytest.skip("Embeddings service is not available in this stack configuration.")
        if not any_document_id:
            pytest.skip("No indexed documents — semantic results cannot be verified.")

        resp = requests.get(
            f"{api_url}{SEARCH_ENDPOINT}",
            params={"q": "book", "mode": "semantic", "limit": "5"},
            timeout=30,
        )
        body = resp.json()
        assert isinstance(body.get("results"), list), (
            f"'results' must be a list in semantic response: {body}"
        )


# ---------------------------------------------------------------------------
# Hybrid search (gated on embeddings service)
# ---------------------------------------------------------------------------


class TestHybridSearch:
    """Hybrid (BM25 + kNN RRF) search mode — requires embeddings service."""

    def test_hybrid_empty_query_returns_400(self, api_url: str, api_available: None) -> None:
        """GET /v1/search with mode=hybrid and an empty query must return HTTP 400.

        This is deterministic — the validation happens before the embeddings
        service is called.
        """
        resp = requests.get(
            f"{api_url}{SEARCH_ENDPOINT}",
            params={"q": "", "mode": "hybrid"},
            timeout=10,
        )
        assert resp.status_code == 400, (
            f"Expected 400 for empty hybrid query, got {resp.status_code}: {resp.text}"
        )

    def test_hybrid_search_returns_200_when_embeddings_available(
        self,
        api_url: str,
        api_available: None,
        embeddings_available: bool,
        any_document_id: str | None,
    ) -> None:
        """GET /v1/search?mode=hybrid must return HTTP 200 when embeddings service is up.

        Gated: requires embeddings service + at least one indexed document with an embedding.
        """
        if not embeddings_available:
            pytest.skip("Embeddings service is not available in this stack configuration.")
        if not any_document_id:
            pytest.skip("No indexed documents — hybrid search cannot be verified.")

        resp = requests.get(
            f"{api_url}{SEARCH_ENDPOINT}",
            params={"q": "book", "mode": "hybrid", "limit": "5"},
            timeout=30,
        )
        assert resp.status_code == 200, (
            f"Expected 200 for hybrid search, got {resp.status_code}: {resp.text}"
        )

    def test_hybrid_search_mode_field_in_response(
        self,
        api_url: str,
        api_available: None,
        embeddings_available: bool,
        any_document_id: str | None,
    ) -> None:
        """Hybrid search response must include mode='hybrid'.

        Gated: requires embeddings service + indexed data.
        """
        if not embeddings_available:
            pytest.skip("Embeddings service is not available in this stack configuration.")
        if not any_document_id:
            pytest.skip("No indexed documents — hybrid mode field cannot be verified.")

        resp = requests.get(
            f"{api_url}{SEARCH_ENDPOINT}",
            params={"q": "book", "mode": "hybrid", "limit": "5"},
            timeout=30,
        )
        body = resp.json()
        assert body.get("mode") == "hybrid", (
            f"Expected mode='hybrid', got {body.get('mode')!r}"
        )

    def test_hybrid_search_results_have_required_fields(
        self,
        api_url: str,
        api_available: None,
        embeddings_available: bool,
        any_document_id: str | None,
    ) -> None:
        """Each hybrid result must include 'id' and 'title' fields.

        Gated: requires embeddings service + indexed data with results.
        """
        if not embeddings_available:
            pytest.skip("Embeddings service is not available in this stack configuration.")
        if not any_document_id:
            pytest.skip("No indexed documents — hybrid result fields cannot be verified.")

        resp = requests.get(
            f"{api_url}{SEARCH_ENDPOINT}",
            params={"q": "book", "mode": "hybrid", "limit": "5"},
            timeout=30,
        )
        results = resp.json().get("results", [])
        for doc in results:
            assert "id" in doc, f"Hybrid result missing 'id': {doc}"
            assert "title" in doc, f"Hybrid result missing 'title': {doc}"


# ---------------------------------------------------------------------------
# Similar-books endpoint
# ---------------------------------------------------------------------------


class TestSimilarBooks:
    """Similar-books endpoint behavior — /v1/books/{id}/similar."""

    def test_similar_unknown_id_returns_404(self, api_url: str, api_available: None) -> None:
        """GET /v1/books/{id}/similar with a non-existent ID must return HTTP 404.

        This is deterministic — no indexed data or embeddings required.
        """
        resp = requests.get(
            f"{api_url}/v1/books/nonexistent-document-id-e2e/similar",
            params={"limit": "5"},
            timeout=10,
        )
        assert resp.status_code == 404, (
            f"Expected 404 for unknown document ID, got {resp.status_code}: {resp.text}"
        )

    def test_similar_returns_list_for_indexed_doc(
        self,
        api_url: str,
        api_available: None,
        embeddings_available: bool,
        any_embedded_document_id: str | None,
    ) -> None:
        """GET /v1/books/{id}/similar must return a list of similar books.

        Gated: requires embeddings service + at least one indexed document with a
        stored embedding vector (verified by ``any_embedded_document_id``).
        """
        if not embeddings_available:
            pytest.skip("Embeddings service is not available in this stack configuration.")
        if not any_embedded_document_id:
            pytest.skip("No document with a stored embedding found — similar-books cannot be verified.")

        resp = requests.get(
            f"{api_url}{_similar_endpoint(any_embedded_document_id)}",
            params={"limit": "5"},
            timeout=30,
        )
        assert resp.status_code == 200, (
            f"Expected 200 for similar-books, got {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        assert "results" in body, f"'results' missing from similar-books response: {body}"
        assert isinstance(body["results"], list), "'results' must be a list."

    def test_similar_excludes_source_document(
        self,
        api_url: str,
        api_available: None,
        embeddings_available: bool,
        any_embedded_document_id: str | None,
    ) -> None:
        """Similar-books results must not include the source document itself.

        Gated: requires embeddings service + indexed document with a stored embedding.
        """
        if not embeddings_available:
            pytest.skip("Embeddings service is not available in this stack configuration.")
        if not any_embedded_document_id:
            pytest.skip("No document with a stored embedding found — exclusion check cannot be performed.")

        resp = requests.get(
            f"{api_url}{_similar_endpoint(any_embedded_document_id)}",
            params={"limit": "5"},
            timeout=30,
        )
        assert resp.status_code == 200, (
            f"Expected 200 for similar-books, got {resp.status_code}: {resp.text}"
        )

        results = resp.json().get("results", [])
        returned_ids = [doc.get("id") for doc in results]
        assert any_embedded_document_id not in returned_ids, (
            f"Source document {any_embedded_document_id!r} must not appear in its own similar-books list. "
            f"Got IDs: {returned_ids}"
        )

    def test_similar_result_fields_are_present(
        self,
        api_url: str,
        api_available: None,
        embeddings_available: bool,
        any_embedded_document_id: str | None,
    ) -> None:
        """Each similar-books result entry must include 'id' and 'title'.

        Gated: requires embeddings service + indexed documents with stored embeddings.
        """
        if not embeddings_available:
            pytest.skip("Embeddings service is not available in this stack configuration.")
        if not any_embedded_document_id:
            pytest.skip("No document with a stored embedding found — result field check cannot be performed.")

        resp = requests.get(
            f"{api_url}{_similar_endpoint(any_embedded_document_id)}",
            params={"limit": "5"},
            timeout=30,
        )
        assert resp.status_code == 200, (
            f"Expected 200 for similar-books, got {resp.status_code}: {resp.text}"
        )

        results = resp.json().get("results", [])
        for doc in results:
            assert "id" in doc, f"Similar result missing 'id': {doc}"
            assert "title" in doc, f"Similar result missing 'title': {doc}"

    def test_v1_similar_alias_is_registered(self, api_url: str, api_available: None) -> None:
        """GET /v1/books/{id}/similar must be reachable (404 for unknown id, not 405/501).

        This is deterministic — just verifies the route is registered.
        """
        resp = requests.get(
            f"{api_url}/v1/books/probe-id-e2e-test/similar",
            params={"limit": "1"},
            timeout=10,
        )
        # 404 = route registered but document not found (expected)
        # 422 = route registered, validation issue (also acceptable)
        # 405/501 would mean the route does not exist
        assert resp.status_code in (404, 422), (
            f"Expected 404 or 422 for probe ID, got {resp.status_code} — "
            "route may not be registered."
        )
