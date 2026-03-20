"""Tests for batch metadata edit endpoints (PATCH /v1/admin/documents/batch/*)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("AUTH_DB_PATH", "/tmp/test-auth.db")  # noqa: S108
os.environ.setdefault("AUTH_JWT_SECRET", "test-auth-secret")
os.environ.setdefault("AUTH_JWT_TTL", "24h")
os.environ.setdefault("AUTH_COOKIE_NAME", "aithena_auth")

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from tests.auth_helpers import create_authenticated_client  # noqa: E402

_TEST_ADMIN_KEY = "test-batch-metadata-key"
BATCH_ENDPOINT = "/v1/admin/documents/batch/metadata"
QUERY_ENDPOINT = "/v1/admin/documents/batch/metadata-by-query"


def get_client() -> TestClient:
    client = create_authenticated_client()
    client.headers["X-API-Key"] = _TEST_ADMIN_KEY
    return client


@pytest.fixture(autouse=True)
def _enable_admin_api_key():
    """Patch ADMIN_API_KEY so admin endpoints are accessible in these tests."""
    with patch("admin_auth._get_admin_api_key", return_value=_TEST_ADMIN_KEY):
        yield


def _solr_found_response(num_found: int, doc_ids: list[str] | None = None) -> dict:
    docs = [{"id": did} for did in (doc_ids or [])]
    return {"response": {"numFound": num_found, "docs": docs}}


# ---------------------------------------------------------------------------
# PATCH /v1/admin/documents/batch/metadata — success cases
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
@patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}})
@patch("main.requests.post")
def test_batch_edit_two_documents(mock_post: MagicMock, mock_query: MagicMock, mock_pool: MagicMock) -> None:
    """Batch edit applies updates to all specified documents."""
    mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
    redis_mock = MagicMock()
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.patch(
            BATCH_ENDPOINT,
            json={
                "document_ids": ["doc-1", "doc-2"],
                "updates": {"title": "Batch Title"},
            },
        )

    assert response.status_code == 200  # noqa: S101
    data = response.json()
    assert data["matched"] == 2  # noqa: S101
    assert data["updated"] == 2  # noqa: S101
    assert data["failed"] == 0  # noqa: S101
    assert data["errors"] == []  # noqa: S101
    assert mock_post.call_count == 2  # noqa: S101 — one Solr update per doc
    assert redis_mock.set.call_count == 2  # noqa: S101 — one Redis override per doc


@patch("main._get_redis_pool")
@patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}})
@patch("main.requests.post")
def test_batch_edit_multiple_fields(mock_post: MagicMock, mock_query: MagicMock, mock_pool: MagicMock) -> None:
    """Batch edit can update multiple fields simultaneously."""
    mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
    redis_mock = MagicMock()
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.patch(
            BATCH_ENDPOINT,
            json={
                "document_ids": ["doc-1"],
                "updates": {"title": "New", "author": "Author", "year": 2020},
            },
        )

    assert response.status_code == 200  # noqa: S101
    data = response.json()
    assert data["updated"] == 1  # noqa: S101

    solr_payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
    assert solr_payload[0]["title_s"] == {"set": "New"}  # noqa: S101
    assert solr_payload[0]["author_s"] == {"set": "Author"}  # noqa: S101
    assert solr_payload[0]["year_i"] == {"set": 2020}  # noqa: S101


@patch("main._get_redis_pool")
@patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}})
@patch("main.requests.post")
def test_batch_edit_stores_redis_overrides(mock_post: MagicMock, mock_query: MagicMock, mock_pool: MagicMock) -> None:
    """Each document gets its own Redis override entry."""
    mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
    redis_mock = MagicMock()
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.patch(
            BATCH_ENDPOINT,
            json={
                "document_ids": ["doc-a", "doc-b"],
                "updates": {"series": "Foundation"},
            },
        )

    assert response.status_code == 200  # noqa: S101
    redis_keys = [call[0][0] for call in redis_mock.set.call_args_list]
    assert "aithena:metadata-override:doc-a" in redis_keys  # noqa: S101
    assert "aithena:metadata-override:doc-b" in redis_keys  # noqa: S101


# ---------------------------------------------------------------------------
# Partial failure handling
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
@patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}})
@patch("main.requests.post")
def test_batch_edit_partial_failure(mock_post: MagicMock, mock_query: MagicMock, mock_pool: MagicMock) -> None:
    """If one document fails Solr update, others continue and errors are reported."""
    import requests as req_lib

    call_count = 0

    def solr_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise req_lib.ConnectionError("connection refused")
        return MagicMock(status_code=200, raise_for_status=MagicMock())

    mock_post.side_effect = solr_side_effect
    redis_mock = MagicMock()
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.patch(
            BATCH_ENDPOINT,
            json={
                "document_ids": ["doc-ok-1", "doc-fail", "doc-ok-2"],
                "updates": {"title": "Test"},
            },
        )

    assert response.status_code == 200  # noqa: S101
    data = response.json()
    assert data["matched"] == 3  # noqa: S101
    assert data["updated"] == 2  # noqa: S101
    assert data["failed"] == 1  # noqa: S101
    assert len(data["errors"]) == 1  # noqa: S101
    assert data["errors"][0]["document_id"] == "doc-fail"  # noqa: S101


@patch("main._get_redis_pool")
@patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}})
@patch("main.requests.post")
def test_batch_edit_redis_failure_partial(mock_post: MagicMock, mock_query: MagicMock, mock_pool: MagicMock) -> None:
    """Redis failure on one doc reports it as failed, others succeed."""
    mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())

    call_count = 0

    def redis_set_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Redis error")

    redis_mock = MagicMock()
    redis_mock.set.side_effect = redis_set_side_effect
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.patch(
            BATCH_ENDPOINT,
            json={
                "document_ids": ["doc-redis-fail", "doc-ok"],
                "updates": {"title": "Test"},
            },
        )

    assert response.status_code == 200  # noqa: S101
    data = response.json()
    assert data["failed"] == 1  # noqa: S101
    assert data["updated"] == 1  # noqa: S101


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


def test_batch_edit_empty_document_ids_returns_422() -> None:
    """Empty document_ids list returns 422."""
    client = get_client()
    response = client.patch(
        BATCH_ENDPOINT,
        json={"document_ids": [], "updates": {"title": "Test"}},
    )
    assert response.status_code == 422  # noqa: S101


def test_batch_edit_too_many_ids_returns_422() -> None:
    """More than 1000 document_ids returns 422."""
    client = get_client()
    response = client.patch(
        BATCH_ENDPOINT,
        json={
            "document_ids": [f"doc-{i}" for i in range(1001)],
            "updates": {"title": "Test"},
        },
    )
    assert response.status_code == 422  # noqa: S101
    assert "1000" in response.json()["detail"]  # noqa: S101


def test_batch_edit_no_update_fields_returns_422() -> None:
    """Empty updates returns 422."""
    client = get_client()
    response = client.patch(
        BATCH_ENDPOINT,
        json={"document_ids": ["doc-1"], "updates": {}},
    )
    assert response.status_code == 422  # noqa: S101


def test_batch_edit_year_out_of_range_returns_422() -> None:
    """Year validation applies to batch endpoint too."""
    client = get_client()
    response = client.patch(
        BATCH_ENDPOINT,
        json={"document_ids": ["doc-1"], "updates": {"year": 2100}},
    )
    assert response.status_code == 422  # noqa: S101


def test_batch_edit_title_too_long_returns_422() -> None:
    """Title length validation applies to batch endpoint."""
    client = get_client()
    response = client.patch(
        BATCH_ENDPOINT,
        json={"document_ids": ["doc-1"], "updates": {"title": "A" * 256}},
    )
    assert response.status_code == 422  # noqa: S101


# ---------------------------------------------------------------------------
# Auth / security
# ---------------------------------------------------------------------------


def test_batch_edit_no_api_key_returns_401() -> None:
    """Missing API key returns 401."""
    from tests.auth_helpers import create_authenticated_client

    client = create_authenticated_client()
    response = client.patch(
        BATCH_ENDPOINT,
        json={"document_ids": ["doc-1"], "updates": {"title": "Test"}},
    )
    assert response.status_code == 401  # noqa: S101


def test_batch_edit_non_admin_role_returns_403() -> None:
    """Non-admin role with valid API key returns 403."""
    from auth import AuthenticatedUser

    client = create_authenticated_client(user=AuthenticatedUser(id=2, username="viewer", role="viewer"))
    client.headers["X-API-Key"] = _TEST_ADMIN_KEY
    response = client.patch(
        BATCH_ENDPOINT,
        json={"document_ids": ["doc-1"], "updates": {"title": "Test"}},
    )
    assert response.status_code == 403  # noqa: S101


# ---------------------------------------------------------------------------
# Exactly at limit (1000 documents)
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
@patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}})
@patch("main.requests.post")
def test_batch_edit_exactly_1000_ids_accepted(
    mock_post: MagicMock, mock_query: MagicMock, mock_pool: MagicMock
) -> None:
    """Exactly 1000 document IDs is accepted (boundary test)."""
    mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
    redis_mock = MagicMock()
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.patch(
            BATCH_ENDPOINT,
            json={
                "document_ids": [f"doc-{i}" for i in range(1000)],
                "updates": {"category": "Science"},
            },
        )

    assert response.status_code == 200  # noqa: S101
    assert response.json()["matched"] == 1000  # noqa: S101


# ===========================================================================
# PATCH /v1/admin/documents/batch/metadata-by-query
# ===========================================================================


@patch("main._get_redis_pool")
@patch("main.requests.post")
def test_query_batch_edit_success(mock_post: MagicMock, mock_pool: MagicMock) -> None:
    """Query-based batch edit resolves IDs and applies updates."""
    mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
    redis_mock = MagicMock()

    solr_search_response = {
        "response": {
            "numFound": 2,
            "docs": [{"id": "qid-1"}, {"id": "qid-2"}],
        }
    }

    with (
        patch("main._raw_solr_query", return_value=solr_search_response),
        patch("main._get_admin_redis_client", return_value=redis_mock),
    ):
        client = get_client()
        response = client.patch(
            QUERY_ENDPOINT,
            json={
                "query": "author_s:Asimov",
                "updates": {"series": "Foundation"},
            },
        )

    assert response.status_code == 200  # noqa: S101
    data = response.json()
    assert data["matched"] == 2  # noqa: S101
    assert data["updated"] == 2  # noqa: S101
    assert data["failed"] == 0  # noqa: S101


@patch("main._get_redis_pool")
def test_query_batch_edit_no_matches(mock_pool: MagicMock) -> None:
    """Query returning zero results returns a zero-count response."""
    empty_response = {"response": {"numFound": 0, "docs": []}}
    with patch("main._raw_solr_query", return_value=empty_response):
        client = get_client()
        response = client.patch(
            QUERY_ENDPOINT,
            json={
                "query": "author_s:NonexistentAuthor",
                "updates": {"series": "None"},
            },
        )

    assert response.status_code == 200  # noqa: S101
    data = response.json()
    assert data["matched"] == 0  # noqa: S101
    assert data["updated"] == 0  # noqa: S101


def test_query_batch_edit_empty_query_returns_422() -> None:
    """Empty query string returns 422."""
    client = get_client()
    response = client.patch(
        QUERY_ENDPOINT,
        json={"query": "   ", "updates": {"title": "Test"}},
    )
    assert response.status_code == 422  # noqa: S101
    assert "query" in response.json()["detail"].lower()  # noqa: S101


def test_query_batch_edit_no_update_fields_returns_422() -> None:
    """Empty updates in query-based batch returns 422."""
    client = get_client()
    response = client.patch(
        QUERY_ENDPOINT,
        json={"query": "author_s:Asimov", "updates": {}},
    )
    assert response.status_code == 422  # noqa: S101


def test_query_batch_edit_validation_applies() -> None:
    """Field validation applies to query-based batch endpoint."""
    client = get_client()
    response = client.patch(
        QUERY_ENDPOINT,
        json={"query": "author_s:Asimov", "updates": {"year": 999}},
    )
    assert response.status_code == 422  # noqa: S101


def test_query_batch_edit_no_api_key_returns_401() -> None:
    """Missing API key on query endpoint returns 401."""
    from tests.auth_helpers import create_authenticated_client

    client = create_authenticated_client()
    response = client.patch(
        QUERY_ENDPOINT,
        json={"query": "author_s:Asimov", "updates": {"title": "Test"}},
    )
    assert response.status_code == 401  # noqa: S101


@patch("main._get_redis_pool")
@patch("main.requests.post")
def test_query_batch_edit_pagination(mock_post: MagicMock, mock_pool: MagicMock) -> None:
    """Query-based batch edit paginates through results."""
    mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
    redis_mock = MagicMock()

    page1 = {
        "response": {
            "numFound": 3,
            "docs": [{"id": "p1"}, {"id": "p2"}],
        }
    }
    page2 = {
        "response": {
            "numFound": 3,
            "docs": [{"id": "p3"}],
        }
    }
    page3 = {
        "response": {
            "numFound": 3,
            "docs": [],
        }
    }

    with (
        patch("main._raw_solr_query", side_effect=[page1, page2, page3]),
        patch("main._get_admin_redis_client", return_value=redis_mock),
        patch("main._solr_document_exists", return_value=True),
    ):
        # Temporarily reduce batch page size for pagination test
        import main as main_module

        original_page_size = main_module._BATCH_PAGE_SIZE
        main_module._BATCH_PAGE_SIZE = 2
        try:
            client = get_client()
            response = client.patch(
                QUERY_ENDPOINT,
                json={
                    "query": "category_s:Science",
                    "updates": {"category": "Science"},
                },
            )
        finally:
            main_module._BATCH_PAGE_SIZE = original_page_size

    assert response.status_code == 200  # noqa: S101
    data = response.json()
    assert data["matched"] == 3  # noqa: S101
    assert data["updated"] == 3  # noqa: S101


@patch("main._get_redis_pool")
@patch("main.requests.post")
def test_query_batch_partial_failure(mock_post: MagicMock, mock_pool: MagicMock) -> None:
    """Partial failure in query-based batch edit is reported."""
    import requests as req_lib

    call_count = 0

    def solr_post_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise req_lib.Timeout("timed out")
        return MagicMock(status_code=200, raise_for_status=MagicMock())

    mock_post.side_effect = solr_post_side_effect
    redis_mock = MagicMock()

    solr_response = {
        "response": {
            "numFound": 2,
            "docs": [{"id": "qf-ok"}, {"id": "qf-fail"}],
        }
    }

    with (
        patch("main._raw_solr_query", return_value=solr_response),
        patch("main._get_admin_redis_client", return_value=redis_mock),
    ):
        client = get_client()
        response = client.patch(
            QUERY_ENDPOINT,
            json={
                "query": "author_s:Test",
                "updates": {"title": "Test"},
            },
        )

    assert response.status_code == 200  # noqa: S101
    data = response.json()
    assert data["updated"] == 1  # noqa: S101
    assert data["failed"] == 1  # noqa: S101
    assert data["errors"][0]["document_id"] == "qf-fail"  # noqa: S101
