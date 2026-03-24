"""
E2E tests for protected endpoints: stats, admin login, and similar documents.

These tests run against the live solr-search API and verify that authenticated
endpoints return the expected response shapes and types.  They exercise the
full production code path — no mocks.

Prerequisites:
  • The stack is running and solr-search is reachable at SEARCH_API_URL.
  • E2E_PASSWORD (or CI_ADMIN_PASSWORD) must be set for authenticated tests.
  • A fixture document must be indexed for the similar-documents test.

Coverage matrix
~~~~~~~~~~~~~~~

+-------------------------------------------+--------+---------------------------+
| Scenario                                  | Auth   | Note                      |
+===========================================+========+===========================+
| Stats endpoint returns valid JSON         | Bearer | response shape check      |
| Stats returns numeric types               | Bearer | regression for v1.14.1    |
| Admin login flow + token reuse            | POST   | end-to-end auth round-trip|
| Similar documents for fixture doc         | Bearer | 200 or 404, never 422    |
+-------------------------------------------+--------+---------------------------+
"""

from __future__ import annotations

import os

import pytest
import requests

SEARCH_API_URL: str = os.environ.get("SEARCH_API_URL", "http://localhost:8080")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Stats endpoint
# ---------------------------------------------------------------------------


class TestStatsEndpoint:
    """GET /v1/stats returns expected response shape and numeric types."""

    def test_stats_endpoint(
        self, api_url: str, api_available: None, auth_headers: dict[str, str]
    ) -> None:
        """GET /v1/stats must return HTTP 200 with total_books (int) and
        page_stats containing numeric avg."""
        resp = requests.get(
            f"{api_url}/v1/stats", headers=auth_headers, timeout=10
        )
        assert resp.status_code == 200, (
            f"Expected 200 from /v1/stats, got {resp.status_code}: {resp.text}"
        )
        body = resp.json()

        # total_books must be an integer
        assert "total_books" in body, (
            f"'total_books' missing from /v1/stats: {body}"
        )
        assert isinstance(body["total_books"], int), (
            f"'total_books' must be int, got {type(body['total_books'])}: "
            f"{body['total_books']!r}"
        )

        # page_stats.avg must be numeric
        page_stats = body.get("page_stats", {})
        assert "avg" in page_stats, (
            f"'avg' missing from page_stats: {page_stats}"
        )
        assert isinstance(page_stats["avg"], (int, float)), (
            f"page_stats.avg must be numeric, got "
            f"{type(page_stats['avg'])}: {page_stats['avg']!r}"
        )

    def test_stats_returns_numeric_types(
        self, api_url: str, api_available: None, auth_headers: dict[str, str]
    ) -> None:
        """GET /v1/stats — all stat values must be int or float.

        Regression test for the TypeError bug introduced in v1.14.1 where
        certain stat fields were returned as strings instead of numbers.
        """
        resp = requests.get(
            f"{api_url}/v1/stats", headers=auth_headers, timeout=10
        )
        assert resp.status_code == 200, (
            f"Expected 200 from /v1/stats, got {resp.status_code}: {resp.text}"
        )
        body = resp.json()

        # Top-level numeric fields
        for key in ("total_books", "total_pages"):
            if key in body:
                assert isinstance(body[key], (int, float)), (
                    f"Top-level stat '{key}' must be numeric, got "
                    f"{type(body[key])}: {body[key]!r}"
                )

        # Nested stat blocks (e.g. page_stats) — every value must be numeric
        for section_key in ("page_stats",):
            section = body.get(section_key, {})
            if not isinstance(section, dict):
                continue
            for stat_name, stat_value in section.items():
                assert isinstance(stat_value, (int, float)), (
                    f"{section_key}.{stat_name} must be numeric, got "
                    f"{type(stat_value)}: {stat_value!r}"
                )


# ---------------------------------------------------------------------------
# Admin login flow
# ---------------------------------------------------------------------------


class TestAdminLoginFlow:
    """POST /v1/auth/login and token reuse for protected endpoints."""

    def test_admin_login_flow(
        self, api_url: str, api_available: None
    ) -> None:
        """POST /v1/auth/login with valid credentials must return 200 with
        an access_token, and that token must grant access to GET /v1/stats."""
        username = os.environ.get(
            "E2E_USERNAME", os.environ.get("CI_ADMIN_USERNAME", "admin")
        )
        password = os.environ.get("E2E_PASSWORD") or os.environ.get(
            "CI_ADMIN_PASSWORD"
        )
        if not password:
            pytest.skip(
                "E2E_PASSWORD environment variable must be set for login test"
            )

        # Step 1: authenticate
        login_resp = requests.post(
            f"{api_url}/v1/auth/login",
            json={"username": username, "password": password},
            timeout=10,
        )
        assert login_resp.status_code == 200, (
            f"Login failed with {login_resp.status_code}: {login_resp.text}"
        )
        token = login_resp.json().get("access_token")
        assert isinstance(token, str) and token, (
            f"Login response missing access_token: {login_resp.text}"
        )

        # Step 2: use the token to call a protected endpoint
        headers = {"Authorization": f"Bearer {token}"}
        stats_resp = requests.get(
            f"{api_url}/v1/stats", headers=headers, timeout=10
        )
        assert stats_resp.status_code == 200, (
            f"GET /v1/stats with fresh token failed: "
            f"{stats_resp.status_code}: {stats_resp.text}"
        )


# ---------------------------------------------------------------------------
# Similar documents endpoint
# ---------------------------------------------------------------------------


class TestSimilarDocumentsEndpoint:
    """GET /v1/books/{id}/similar returns a valid response."""

    def test_similar_documents_endpoint(
        self,
        api_url: str,
        api_available: None,
        auth_headers: dict[str, str],
        fixture_solr_id: str,
    ) -> None:
        """GET /v1/books/{fixture_solr_id}/similar?limit=5 must return
        200 (with results) or 404 (document not indexed yet), but never
        422 (which would indicate a schema/validation bug)."""
        resp = requests.get(
            f"{api_url}/v1/books/{fixture_solr_id}/similar",
            params={"limit": 5},
            headers=auth_headers,
            timeout=15,
        )
        assert resp.status_code in (200, 404), (
            f"Expected 200 or 404 from /v1/books/{{id}}/similar, "
            f"got {resp.status_code}: {resp.text}"
        )

        if resp.status_code == 200:
            body = resp.json()
            # Response should be a list or contain a results key
            if isinstance(body, list):
                assert len(body) <= 5, (
                    f"Requested limit=5 but got {len(body)} results"
                )
            elif isinstance(body, dict) and "results" in body:
                assert len(body["results"]) <= 5, (
                    f"Requested limit=5 but got {len(body['results'])} results"
                )
