"""Tests for PATCH /v1/admin/documents/{doc_id}/metadata (single document metadata edit)."""

from __future__ import annotations

import json
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

_TEST_ADMIN_KEY = "test-metadata-edit-key"
DOC_ID = "test-doc-001"
ENDPOINT = f"/v1/admin/documents/{DOC_ID}/metadata"


def get_client() -> TestClient:
    client = create_authenticated_client()
    client.headers["X-API-Key"] = _TEST_ADMIN_KEY
    return client


@pytest.fixture(autouse=True)
def _enable_admin_api_key():
    """Patch ADMIN_API_KEY so admin endpoints are accessible in these tests."""
    with patch("admin_auth._get_admin_api_key", return_value=_TEST_ADMIN_KEY):
        yield


def _solr_exists_response(num_found: int = 1) -> dict:
    return {"response": {"numFound": num_found, "docs": []}}


# ---------------------------------------------------------------------------
# Successful metadata edits
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
@patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}})
@patch("main.requests.post")
def test_patch_title_only(mock_post: MagicMock, mock_solr_query: MagicMock, mock_pool: MagicMock) -> None:
    """PATCH with only title updates Solr and Redis."""
    mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
    redis_mock = MagicMock()
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.patch(ENDPOINT, json={"title": "New Title"})

    assert response.status_code == 200  # noqa: S101
    data = response.json()
    assert data["id"] == DOC_ID  # noqa: S101
    assert data["updated_fields"] == ["title"]  # noqa: S101
    assert data["status"] == "ok"  # noqa: S101

    # Verify Solr atomic update was called
    mock_post.assert_called_once()
    solr_payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
    assert solr_payload is not None  # noqa: S101
    assert solr_payload[0]["title_s"] == {"set": "New Title"}  # noqa: S101
    assert solr_payload[0]["title_t"] == {"set": "New Title"}  # noqa: S101

    # Verify Redis override was stored
    redis_mock.set.assert_called_once()
    redis_key = redis_mock.set.call_args[0][0]
    redis_value = json.loads(redis_mock.set.call_args[0][1])
    assert redis_key == f"aithena:metadata-override:{DOC_ID}"  # noqa: S101
    assert redis_value["title_s"] == "New Title"  # noqa: S101
    assert redis_value["title_t"] == "New Title"  # noqa: S101
    assert "edited_by" in redis_value  # noqa: S101
    assert "edited_at" in redis_value  # noqa: S101


@patch("main._get_redis_pool")
@patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}})
@patch("main.requests.post")
def test_patch_multiple_fields(mock_post: MagicMock, mock_solr_query: MagicMock, mock_pool: MagicMock) -> None:
    """PATCH with multiple fields updates all of them."""
    mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
    redis_mock = MagicMock()
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.patch(ENDPOINT, json={"title": "Book", "author": "Author", "year": 2020})

    assert response.status_code == 200  # noqa: S101
    data = response.json()
    assert sorted(data["updated_fields"]) == ["author", "title", "year"]  # noqa: S101


@patch("main._get_redis_pool")
@patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}})
@patch("main.requests.post")
def test_patch_year_only(mock_post: MagicMock, mock_solr_query: MagicMock, mock_pool: MagicMock) -> None:
    """PATCH with only year field."""
    mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
    redis_mock = MagicMock()
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.patch(ENDPOINT, json={"year": 1984})

    assert response.status_code == 200  # noqa: S101
    data = response.json()
    assert data["updated_fields"] == ["year"]  # noqa: S101

    solr_payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
    assert solr_payload[0]["year_i"] == {"set": 1984}  # noqa: S101


@patch("main._get_redis_pool")
@patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}})
@patch("main.requests.post")
def test_patch_series_field(mock_post: MagicMock, mock_solr_query: MagicMock, mock_pool: MagicMock) -> None:
    """PATCH with series field."""
    mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
    redis_mock = MagicMock()
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.patch(ENDPOINT, json={"series": "Discworld"})

    assert response.status_code == 200  # noqa: S101
    data = response.json()
    assert data["updated_fields"] == ["series"]  # noqa: S101

    solr_payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
    assert solr_payload[0]["series_s"] == {"set": "Discworld"}  # noqa: S101


@patch("main._get_redis_pool")
@patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}})
@patch("main.requests.post")
def test_patch_category_field(mock_post: MagicMock, mock_solr_query: MagicMock, mock_pool: MagicMock) -> None:
    """PATCH with category field."""
    mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
    redis_mock = MagicMock()
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.patch(ENDPOINT, json={"category": "Science Fiction"})

    assert response.status_code == 200  # noqa: S101
    data = response.json()
    assert data["updated_fields"] == ["category"]  # noqa: S101


# ---------------------------------------------------------------------------
# Whitespace trimming
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
@patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}})
@patch("main.requests.post")
def test_patch_trims_whitespace(mock_post: MagicMock, mock_solr_query: MagicMock, mock_pool: MagicMock) -> None:
    """String fields are trimmed before processing."""
    mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
    redis_mock = MagicMock()
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.patch(ENDPOINT, json={"title": "  Trimmed Title  "})

    assert response.status_code == 200  # noqa: S101
    solr_payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
    assert solr_payload[0]["title_s"] == {"set": "Trimmed Title"}  # noqa: S101


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


def test_patch_empty_body_returns_422() -> None:
    """PATCH with empty body returns 422."""
    client = get_client()
    response = client.patch(ENDPOINT, json={})
    assert response.status_code == 422  # noqa: S101


def test_patch_whitespace_only_title_returns_422() -> None:
    """PATCH with whitespace-only string field returns 422."""
    client = get_client()
    response = client.patch(ENDPOINT, json={"title": "   "})
    assert response.status_code == 422  # noqa: S101


def test_patch_year_below_range_returns_422() -> None:
    """PATCH with year < 1000 returns 422."""
    client = get_client()
    response = client.patch(ENDPOINT, json={"year": 999})
    assert response.status_code == 422  # noqa: S101
    assert "year" in response.json()["detail"].lower()  # noqa: S101


def test_patch_year_above_range_returns_422() -> None:
    """PATCH with year > 2099 returns 422."""
    client = get_client()
    response = client.patch(ENDPOINT, json={"year": 2100})
    assert response.status_code == 422  # noqa: S101


def test_patch_title_too_long_returns_422() -> None:
    """PATCH with title longer than 255 chars returns 422."""
    client = get_client()
    response = client.patch(ENDPOINT, json={"title": "A" * 256})
    assert response.status_code == 422  # noqa: S101
    assert "title" in response.json()["detail"].lower()  # noqa: S101


def test_patch_author_too_long_returns_422() -> None:
    """PATCH with author longer than 255 chars returns 422."""
    client = get_client()
    response = client.patch(ENDPOINT, json={"author": "A" * 256})
    assert response.status_code == 422  # noqa: S101


def test_patch_category_too_long_returns_422() -> None:
    """PATCH with category longer than 100 chars returns 422."""
    client = get_client()
    response = client.patch(ENDPOINT, json={"category": "A" * 101})
    assert response.status_code == 422  # noqa: S101


def test_patch_series_too_long_returns_422() -> None:
    """PATCH with series longer than 100 chars returns 422."""
    client = get_client()
    response = client.patch(ENDPOINT, json={"series": "A" * 101})
    assert response.status_code == 422  # noqa: S101


# ---------------------------------------------------------------------------
# Document not found in Solr
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
@patch("main._raw_solr_query", return_value={"response": {"numFound": 0, "docs": []}})
def test_patch_document_not_found_returns_404(mock_solr_query: MagicMock, mock_pool: MagicMock) -> None:
    """PATCH for a non-existent Solr document returns 404."""
    client = get_client()
    response = client.patch(ENDPOINT, json={"title": "New Title"})
    assert response.status_code == 404  # noqa: S101
    assert "not found" in response.json()["detail"].lower()  # noqa: S101


# ---------------------------------------------------------------------------
# Solr errors
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
@patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}})
@patch("main.requests.post")
def test_patch_solr_timeout_returns_504(
    mock_post: MagicMock, mock_solr_query: MagicMock, mock_pool: MagicMock
) -> None:
    """Solr timeout during atomic update returns 504."""
    import requests as req_lib

    mock_post.side_effect = req_lib.Timeout("connection timed out")
    redis_mock = MagicMock()
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.patch(ENDPOINT, json={"title": "New Title"})

    assert response.status_code == 504  # noqa: S101


@patch("main._get_redis_pool")
@patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}})
@patch("main.requests.post")
def test_patch_solr_error_returns_502(
    mock_post: MagicMock, mock_solr_query: MagicMock, mock_pool: MagicMock
) -> None:
    """Solr connection error during atomic update returns 502."""
    import requests as req_lib

    mock_post.side_effect = req_lib.ConnectionError("connection refused")
    redis_mock = MagicMock()
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.patch(ENDPOINT, json={"title": "New Title"})

    assert response.status_code == 502  # noqa: S101


# ---------------------------------------------------------------------------
# Redis errors
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
@patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}})
@patch("main.requests.post")
def test_patch_redis_failure_returns_503(
    mock_post: MagicMock, mock_solr_query: MagicMock, mock_pool: MagicMock
) -> None:
    """Redis failure during override store returns 503."""
    mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
    redis_mock = MagicMock()
    redis_mock.set.side_effect = Exception("connection refused")
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.patch(ENDPOINT, json={"title": "New Title"})

    assert response.status_code == 503  # noqa: S101


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
@patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}})
@patch("main.requests.post")
def test_patch_year_boundary_1000(mock_post: MagicMock, mock_solr_query: MagicMock, mock_pool: MagicMock) -> None:
    """Year exactly 1000 is valid."""
    mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
    redis_mock = MagicMock()
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.patch(ENDPOINT, json={"year": 1000})

    assert response.status_code == 200  # noqa: S101


@patch("main._get_redis_pool")
@patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}})
@patch("main.requests.post")
def test_patch_year_boundary_2099(mock_post: MagicMock, mock_solr_query: MagicMock, mock_pool: MagicMock) -> None:
    """Year exactly 2099 is valid."""
    mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
    redis_mock = MagicMock()
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.patch(ENDPOINT, json={"year": 2099})

    assert response.status_code == 200  # noqa: S101


@patch("main._get_redis_pool")
@patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}})
@patch("main.requests.post")
def test_patch_all_fields(mock_post: MagicMock, mock_solr_query: MagicMock, mock_pool: MagicMock) -> None:
    """PATCH with all five fields succeeds."""
    mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
    redis_mock = MagicMock()
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.patch(
            ENDPOINT,
            json={
                "title": "The Colour of Magic",
                "author": "Terry Pratchett",
                "year": 1983,
                "category": "Fantasy",
                "series": "Discworld",
            },
        )

    assert response.status_code == 200  # noqa: S101
    data = response.json()
    assert sorted(data["updated_fields"]) == ["author", "category", "series", "title", "year"]  # noqa: S101


def test_patch_null_fields_ignored() -> None:
    """Null-valued fields are ignored; still needs at least one non-null."""
    client = get_client()
    response = client.patch(ENDPOINT, json={"title": None, "author": None})
    assert response.status_code == 422  # noqa: S101


@patch("main._get_redis_pool")
@patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}})
@patch("main.requests.post")
def test_patch_title_max_length_255(mock_post: MagicMock, mock_solr_query: MagicMock, mock_pool: MagicMock) -> None:
    """Title of exactly 255 chars is accepted."""
    mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
    redis_mock = MagicMock()
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.patch(ENDPOINT, json={"title": "A" * 255})

    assert response.status_code == 200  # noqa: S101
