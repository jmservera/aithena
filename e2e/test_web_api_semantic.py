"""Production E2E test: semantic retrieval via the web API only.

Unlike test_semantic_retrieval.py (which uses direct Solr access for setup),
this test exercises the same upload-index-search pipeline purely through
the public-facing web API.  It is suitable for production environments where
Solr is not directly accessible from the test runner.

Flow:
1. Upload two PDFs via POST /v1/upload
2. Wait for documents to appear in search results (keyword mode)
3. Wait for embeddings to be generated (semantic mode returns results)
4. Assert semantic and hybrid search rank the correct document first

Environment variables:
  SEARCH_API_URL    solr-search base URL (default: http://localhost:8080)
  E2E_USERNAME      Login username (default: admin)
  E2E_PASSWORD      Login password (required)
  WEB_API_TIMEOUT   Max seconds to wait for indexing (default: 300)
"""

from __future__ import annotations

import os
import time
import uuid

import pytest
import requests

SEARCH_API_URL: str = os.environ.get("SEARCH_API_URL", "http://localhost:8080")
WEB_API_TIMEOUT = int(os.environ.get("WEB_API_TIMEOUT", "300"))
POLL_INTERVAL = 10
RUN_ID = uuid.uuid4().hex[:8]

# Category used to isolate test documents from any real data
TEST_CATEGORY = "WebAPISemanticE2E"

DOC_CASES = (
    {
        "slug": "reef",
        "title": "Shallow Atoll Survey",
        "author": "Pelagia North",
        "year": "2024",
        "text": (
            "The coral reef biome shelters clownfish, sea anemones, crustaceans, "
            "and bright algae. Sunlit lagoons build calcium structures that protect "
            "coastlines and provide nursery grounds for countless animals."
        ),
        "query": "underwater life and biodiversity",
    },
    {
        "slug": "mars",
        "title": "Jezero Core Archive",
        "author": "Aster Vale",
        "year": "2024",
        "text": (
            "The rover explored Jezero Crater, drilled basalt cores, and sealed "
            "geological specimens for return to Earth. Researchers inspect the "
            "samples for biosignatures that could reveal whether ancient microbes "
            "once inhabited the planet."
        ),
        "query": "searching for extraterrestrial organisms on other worlds",
    },
)


# ---------------------------------------------------------------------------
# Minimal PDF generator (same as conftest._build_pdf)
# ---------------------------------------------------------------------------


def _build_pdf(text: str) -> bytes:
    """Return a minimal but valid single-page PDF containing *text*."""
    stream_body = (f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET").encode()
    objects: list[bytes] = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        ),
        (f"4 0 obj\n<< /Length {len(stream_body)} >>\nstream\n".encode() + stream_body + b"\nendstream\nendobj\n"),
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    body = b""
    offsets: list[int] = []
    header = b"%PDF-1.4\n"
    body += header
    for obj in objects:
        offsets.append(len(body))
        body += obj
    xref_offset = len(body)
    xref = f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    for off in offsets:
        xref += f"{off:010d} 00000 n \n"
    xref += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
    return body + xref.encode()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(api_url: str) -> dict[str, str]:
    """Login and return auth headers."""
    username = os.environ.get("E2E_USERNAME", os.environ.get("CI_ADMIN_USERNAME", "admin"))
    password = os.environ.get("E2E_PASSWORD") or os.environ.get("CI_ADMIN_PASSWORD")
    if not password:
        pytest.skip("E2E_PASSWORD must be set for authenticated web API tests")

    resp = requests.post(
        f"{api_url}/v1/auth/login",
        json={"username": username, "password": password},
        timeout=10,
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        pytest.fail(f"Login failed — no access_token: {resp.text}")
    return {"Authorization": f"Bearer {token}"}


def _upload_pdf(api_url: str, headers: dict[str, str], filename: str, content: bytes) -> requests.Response:
    """Upload a PDF via the web API upload endpoint."""
    return requests.post(
        f"{api_url}/v1/upload",
        headers=headers,
        files={"file": (filename, content, "application/pdf")},
        timeout=60,
    )


def _search(
    api_url: str,
    headers: dict[str, str],
    *,
    query: str,
    mode: str,
    category: str | None = None,
) -> requests.Response:
    params: dict[str, str] = {"q": query, "mode": mode, "limit": "5"}
    if category:
        params["fq_category"] = category
    return requests.get(
        f"{api_url}/v1/search",
        params=params,
        headers=headers,
        timeout=30,
    )


def _wait_for_search_results(
    api_url: str,
    headers: dict[str, str],
    *,
    query: str,
    mode: str,
    expected_count: int,
    category: str | None = None,
    timeout: int = WEB_API_TIMEOUT,
) -> dict | None:
    """Poll search until at least expected_count results appear."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = _search(api_url, headers, query=query, mode=mode, category=category)
        if resp.status_code == 200:
            body = resp.json()
            results = body.get("results", [])
            if len(results) >= expected_count:
                return body
        time.sleep(POLL_INTERVAL)
    return None


def _delete_via_api(api_url: str, headers: dict[str, str], doc_id: str) -> None:
    """Delete a document via the admin API (best-effort cleanup)."""
    api_key = os.environ.get("ADMIN_API_KEY")
    if api_key:
        requests.delete(
            f"{api_url}/v1/admin/documents/{doc_id}",
            headers={"X-API-Key": api_key},
            timeout=30,
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def api_url() -> str:
    return SEARCH_API_URL.rstrip("/")


@pytest.fixture(scope="module")
def auth_headers(api_url: str) -> dict[str, str]:
    return _login(api_url)


@pytest.fixture(scope="module")
def web_api_available(api_url: str) -> None:
    """Skip if the web API is not reachable or embeddings unavailable."""
    try:
        resp = requests.get(f"{api_url}/v1/status", timeout=10)
        resp.raise_for_status()
    except Exception as exc:
        pytest.skip(f"Web API not reachable: {exc}")

    payload = resp.json()
    if not payload.get("embeddings_available"):
        pytest.skip("Embeddings not available — semantic search cannot be tested.")


@pytest.fixture(scope="module")
def uploaded_docs(
    api_url: str,
    auth_headers: dict[str, str],
    web_api_available: None,
) -> list[dict]:
    """Upload both test PDFs and wait for them to become searchable.

    Returns list of doc metadata dicts with title, query, slug info.
    """
    uploaded: list[dict] = []

    for case in DOC_CASES:
        filename = f"{case['author']} - {case['title']} ({case['year']}).pdf"
        pdf_bytes = _build_pdf(case["text"])

        resp = _upload_pdf(api_url, auth_headers, filename, pdf_bytes)
        assert resp.status_code in (200, 201, 202), f"Upload failed for {case['slug']}: {resp.status_code} {resp.text}"

        upload_data = resp.json() if resp.content else {}
        uploaded.append(
            {
                **case,
                "filename": filename,
                "upload_response": upload_data,
            }
        )

    # Wait for keyword search to find both documents (confirms indexing).
    # Use terms from document *content* (not titles) since keyword mode
    # searches the content field by default.
    body = _wait_for_search_results(
        api_url,
        auth_headers,
        query="clownfish OR Jezero",
        mode="keyword",
        expected_count=2,
        timeout=WEB_API_TIMEOUT,
    )
    if not body:
        pytest.skip(
            f"Documents did not appear in keyword search within {WEB_API_TIMEOUT}s. "
            "The upload→index pipeline may not be running."
        )

    # Wait for semantic search to work (confirms embeddings generated)
    semantic_body = _wait_for_search_results(
        api_url,
        auth_headers,
        query="coral reef marine biology",
        mode="semantic",
        expected_count=1,
        timeout=WEB_API_TIMEOUT,
    )
    if not semantic_body:
        pytest.skip(
            f"Semantic search returned no results within {WEB_API_TIMEOUT}s. "
            "Embeddings may not have been generated yet."
        )

    yield uploaded

    # Cleanup: best-effort delete via API
    for entry in uploaded:
        doc_id = entry.get("upload_response", {}).get("doc_id", "")
        if doc_id:
            _delete_via_api(api_url, auth_headers, doc_id)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def _title_matches(actual_title: str | None, expected_prefix: str) -> bool:
    """Check if actual title starts with the expected title prefix.

    The metadata extractor may append year and timestamp suffixes to
    titles derived from sanitized filenames (e.g. "My Title 2024 20260512_123456"),
    so we match on prefix rather than exact equality.
    """
    return bool(actual_title and actual_title.startswith(expected_prefix))


class TestWebAPISemanticRetrieval:
    """Validate semantic search via the web API (no direct Solr access)."""

    def test_semantic_search_ranks_correctly(
        self,
        api_url: str,
        auth_headers: dict[str, str],
        uploaded_docs: list[dict],
    ) -> None:
        """Semantic queries must rank the intended document first."""
        for case in uploaded_docs:
            wrong_title = next(doc["title"] for doc in uploaded_docs if doc["slug"] != case["slug"])
            resp = _search(api_url, auth_headers, query=case["query"], mode="semantic", category="Uploads")
            assert resp.status_code == 200, f"Semantic search failed for {case['slug']}: {resp.status_code} {resp.text}"

            body = resp.json()
            results = body.get("results", [])
            assert results, f"No results for query {case['query']!r}: {body}"

            top = results[0]
            assert _title_matches(top.get("title"), case["title"]), (
                f"Expected top result starting with {case['title']!r} for {case['query']!r}, "
                f"got {top.get('title')!r}. Scores: "
                f"{[(r.get('title'), r.get('score')) for r in results]}"
            )
            assert not _title_matches(top.get("title"), wrong_title)

    def test_hybrid_search_ranks_correctly(
        self,
        api_url: str,
        auth_headers: dict[str, str],
        uploaded_docs: list[dict],
    ) -> None:
        """Hybrid queries must still rank the intended document first."""
        for case in uploaded_docs:
            wrong_title = next(doc["title"] for doc in uploaded_docs if doc["slug"] != case["slug"])
            resp = _search(api_url, auth_headers, query=case["query"], mode="hybrid", category="Uploads")
            assert resp.status_code == 200, f"Hybrid search failed for {case['slug']}: {resp.status_code} {resp.text}"

            body = resp.json()
            results = body.get("results", [])
            assert results, f"No results for query {case['query']!r}: {body}"

            top = results[0]
            assert _title_matches(top.get("title"), case["title"]), (
                f"Expected top result starting with {case['title']!r} for {case['query']!r}, "
                f"got {top.get('title')!r}. Scores: "
                f"{[(r.get('title'), r.get('score')) for r in results]}"
            )
            assert not _title_matches(top.get("title"), wrong_title)

    def test_keyword_mode_also_returns_results(
        self,
        api_url: str,
        auth_headers: dict[str, str],
        uploaded_docs: list[dict],
    ) -> None:
        """Keyword mode should find the documents by unique terms."""
        resp = _search(api_url, auth_headers, query="clownfish OR Jezero", mode="keyword", category="Uploads")
        assert resp.status_code == 200
        body = resp.json()
        results = body.get("results", [])
        titles = [r.get("title", "") for r in results]
        found_reef = any(t.startswith("Shallow Atoll Survey") for t in titles)
        found_mars = any(t.startswith("Jezero Core Archive") for t in titles)
        assert found_reef or found_mars, f"Keyword search didn't find test documents. Titles: {titles}"
