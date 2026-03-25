"""Tests for the GET /v1/books/{book_id} endpoint (single book detail)."""

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

import requests as req_lib  # noqa: E402

from tests.auth_helpers import create_authenticated_client  # noqa: E402

VALID_SHA256 = "a" * 64


def get_client():
    return create_authenticated_client()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_book_doc(book_id: str = VALID_SHA256) -> dict:
    return {
        "id": book_id,
        "title_s": "Test Book",
        "author_s": "Test Author",
        "year_i": 2024,
        "category_s": "Science",
        "language_detected_s": "en",
        "language_s": "en",
        "series_s": "Test Series",
        "file_path_s": "library/test-book.pdf",
        "folder_path_s": "library",
        "page_count_i": 350,
        "file_size_l": 2048000,
        "score": 1.0,
    }


def _solr_response(docs: list[dict]) -> dict:
    return {
        "response": {
            "numFound": len(docs),
            "docs": docs,
        },
        "highlighting": {},
    }


def _mock_solr_ok(mock_post: MagicMock, payload: dict) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = payload
    mock_post.return_value = mock_response


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@patch("main.requests.post")
def test_book_detail_returns_book(mock_post: MagicMock) -> None:
    doc = _make_book_doc()
    _mock_solr_ok(mock_post, _solr_response([doc]))

    client = get_client()
    response = client.get(f"/v1/books/{VALID_SHA256}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == VALID_SHA256
    assert data["title"] == "Test Book"
    assert data["author"] == "Test Author"
    assert data["year"] == 2024
    assert data["category"] == "Science"
    assert data["language"] == "en"
    assert data["series"] == "Test Series"
    assert data["page_count"] == 350
    assert data["file_size"] == 2048000
    assert data["file_path"] == "library/test-book.pdf"
    assert data["folder_path"] == "library"
    assert data["document_url"] is not None


@patch("main.requests.post")
def test_book_detail_queries_solr_by_id(mock_post: MagicMock) -> None:
    """Verify the Solr query uses the book ID and excludes chunks."""
    _mock_solr_ok(mock_post, _solr_response([_make_book_doc()]))

    client = get_client()
    client.get(f"/v1/books/{VALID_SHA256}")

    params = mock_post.call_args[1]["data"]
    assert params["q"] == f"id:{VALID_SHA256}"
    assert params["rows"] == 1
    assert "-parent_id_s:[* TO *]" in params["fq"]


@patch("main.requests.post")
def test_book_detail_includes_document_url(mock_post: MagicMock) -> None:
    _mock_solr_ok(mock_post, _solr_response([_make_book_doc()]))

    client = get_client()
    data = client.get(f"/v1/books/{VALID_SHA256}").json()

    assert data["document_url"] is not None
    assert isinstance(data["document_url"], str)


@patch("main.requests.post")
def test_book_detail_missing_file_path_returns_null_url(mock_post: MagicMock) -> None:
    doc = _make_book_doc()
    doc["file_path_s"] = None
    _mock_solr_ok(mock_post, _solr_response([doc]))

    client = get_client()
    data = client.get(f"/v1/books/{VALID_SHA256}").json()

    assert data["document_url"] is None


@patch("main.requests.post")
def test_book_detail_missing_title_falls_back_to_filename(mock_post: MagicMock) -> None:
    doc = _make_book_doc()
    doc["title_s"] = None
    _mock_solr_ok(mock_post, _solr_response([doc]))

    client = get_client()
    data = client.get(f"/v1/books/{VALID_SHA256}").json()

    assert data["title"] == "test-book"


@patch("main.requests.post")
def test_book_detail_missing_author_falls_back_to_unknown(mock_post: MagicMock) -> None:
    doc = _make_book_doc()
    doc["author_s"] = None
    _mock_solr_ok(mock_post, _solr_response([doc]))

    client = get_client()
    data = client.get(f"/v1/books/{VALID_SHA256}").json()

    assert data["author"] == "Unknown"


@patch("main.requests.post")
def test_book_detail_highlights_empty(mock_post: MagicMock) -> None:
    _mock_solr_ok(mock_post, _solr_response([_make_book_doc()]))

    client = get_client()
    data = client.get(f"/v1/books/{VALID_SHA256}").json()

    assert data["highlights"] == []


@patch("main.requests.post")
def test_book_detail_is_not_chunk(mock_post: MagicMock) -> None:
    _mock_solr_ok(mock_post, _solr_response([_make_book_doc()]))

    client = get_client()
    data = client.get(f"/v1/books/{VALID_SHA256}").json()

    assert data["is_chunk"] is False
    assert data["chunk_text"] is None


@patch("main.requests.post")
def test_book_detail_uppercase_sha256(mock_post: MagicMock) -> None:
    """SHA256 IDs with uppercase hex characters should be accepted."""
    upper_id = "A" * 64
    doc = _make_book_doc(upper_id)
    _mock_solr_ok(mock_post, _solr_response([doc]))

    client = get_client()
    response = client.get(f"/v1/books/{upper_id}")

    assert response.status_code == 200
    assert response.json()["id"] == upper_id


# ---------------------------------------------------------------------------
# 404 — Not found
# ---------------------------------------------------------------------------


@patch("main.requests.post")
def test_book_detail_not_found_returns_404(mock_post: MagicMock) -> None:
    _mock_solr_ok(mock_post, _solr_response([]))

    client = get_client()
    response = client.get(f"/v1/books/{VALID_SHA256}")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 422 — Invalid ID format
# ---------------------------------------------------------------------------


def test_book_detail_short_id_returns_422() -> None:
    client = get_client()
    response = client.get("/v1/books/abc123")
    assert response.status_code == 422
    assert "SHA256" in response.json()["detail"]


def test_book_detail_too_long_id_returns_422() -> None:
    client = get_client()
    response = client.get(f"/v1/books/{'a' * 65}")
    assert response.status_code == 422


def test_book_detail_non_hex_id_returns_422() -> None:
    client = get_client()
    bad_id = "g" * 64  # 'g' is not a hex char
    response = client.get(f"/v1/books/{bad_id}")
    assert response.status_code == 422


def test_book_detail_empty_id_returns_422() -> None:
    """An empty book_id should not match the detail endpoint."""
    client = get_client()
    # /v1/books/ with trailing slash routes to the list endpoint, not detail
    response = client.get("/v1/books/not-a-hash")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Error handling — Solr failures
# ---------------------------------------------------------------------------


@patch("main.requests.post")
def test_book_detail_solr_timeout_returns_504(mock_post: MagicMock) -> None:
    mock_post.side_effect = req_lib.Timeout("Connection timeout")

    client = get_client()
    response = client.get(f"/v1/books/{VALID_SHA256}")

    assert response.status_code == 504
    assert "Timed out" in response.json()["detail"]


@patch("main.requests.post")
def test_book_detail_solr_connection_error_returns_502(mock_post: MagicMock) -> None:
    mock_post.side_effect = req_lib.ConnectionError("Cannot connect to Solr")

    client = get_client()
    response = client.get(f"/v1/books/{VALID_SHA256}")

    assert response.status_code == 502
    assert "failed" in response.json()["detail"]


@patch("main.requests.post")
def test_book_detail_solr_invalid_json_returns_502(mock_post: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_post.return_value = mock_response

    client = get_client()
    response = client.get(f"/v1/books/{VALID_SHA256}")

    assert response.status_code == 502
    assert "invalid JSON" in response.json()["detail"]


# ---------------------------------------------------------------------------
# OpenAPI schema visibility
# ---------------------------------------------------------------------------


def test_book_detail_in_openapi_schema() -> None:
    """The endpoint must be visible in the OpenAPI schema."""
    client = get_client()
    schema = client.get("/openapi.json").json()
    assert "/v1/books/{book_id}" in schema["paths"]
    path_item = schema["paths"]["/v1/books/{book_id}"]
    assert "get" in path_item


# ---------------------------------------------------------------------------
# Gap-fill: mixed-case IDs, response contract, circuit breaker, Solr HTTP error
# ---------------------------------------------------------------------------


@patch("main.requests.post")
def test_book_detail_mixed_case_sha256_accepted(mock_post: MagicMock) -> None:
    """SHA256 IDs with mixed-case hex characters should be accepted."""
    mixed_id = "aAbBcCdD" * 8  # 64 chars, mixed case
    doc = _make_book_doc(mixed_id)
    _mock_solr_ok(mock_post, _solr_response([doc]))

    client = get_client()
    response = client.get(f"/v1/books/{mixed_id}")

    assert response.status_code == 200
    assert response.json()["id"] == mixed_id


@patch("main.requests.post")
def test_book_detail_response_contains_all_expected_keys(mock_post: MagicMock) -> None:
    """The response JSON must include every key defined by normalize_book."""
    _mock_solr_ok(mock_post, _solr_response([_make_book_doc()]))

    client = get_client()
    data = client.get(f"/v1/books/{VALID_SHA256}").json()

    expected_keys = {
        "id", "title", "author", "year", "category", "language",
        "series", "file_path", "folder_path", "page_count", "file_size",
        "pages", "is_chunk", "chunk_text", "page_start", "page_end",
        "score", "highlights", "document_url", "thumbnail_url",
    }
    assert expected_keys.issubset(data.keys()), f"Missing keys: {expected_keys - data.keys()}"


@patch("main.requests.post")
def test_book_detail_special_chars_preserved(mock_post: MagicMock) -> None:
    """Unicode and special characters in metadata survive normalization."""
    doc = _make_book_doc()
    doc["title_s"] = "L'Étranger — A Novel (2nd ed.)"
    doc["author_s"] = "José García Márquez"
    _mock_solr_ok(mock_post, _solr_response([doc]))

    client = get_client()
    data = client.get(f"/v1/books/{VALID_SHA256}").json()

    assert data["title"] == "L'Étranger — A Novel (2nd ed.)"
    assert data["author"] == "José García Márquez"


@patch("main.query_solr")
def test_book_detail_circuit_breaker_open_returns_503(mock_query: MagicMock) -> None:
    """When the circuit breaker is open, query_solr raises HTTPException 503."""
    from fastapi import HTTPException

    mock_query.side_effect = HTTPException(
        status_code=503,
        detail="Search service temporarily unavailable — Solr circuit breaker is open",
    )

    client = get_client()
    response = client.get(f"/v1/books/{VALID_SHA256}")

    assert response.status_code == 503
    assert "circuit breaker" in response.json()["detail"]


@patch("main.requests.post")
def test_book_detail_solr_http_error_returns_502(mock_post: MagicMock) -> None:
    """A non-200 Solr HTTP response (e.g. 500) should yield 502."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = req_lib.HTTPError("500 Server Error")
    mock_post.return_value = mock_response

    client = get_client()
    response = client.get(f"/v1/books/{VALID_SHA256}")

    assert response.status_code == 502
    assert "failed" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Thumbnail URL in book detail (#829 gap-fill)
# ---------------------------------------------------------------------------


@patch("main.requests.post")
def test_book_detail_includes_thumbnail_url_when_present(mock_post: MagicMock) -> None:
    """Book detail response should include thumbnail_url when Solr doc has it."""
    doc = _make_book_doc()
    doc["thumbnail_url_s"] = "library/test-book.pdf.thumb.jpg"
    _mock_solr_ok(mock_post, _solr_response([doc]))

    client = get_client()
    data = client.get(f"/v1/books/{VALID_SHA256}").json()

    assert data["thumbnail_url"] == "/thumbnails/library/test-book.pdf.thumb.jpg"


@patch("main.requests.post")
def test_book_detail_thumbnail_url_null_when_absent(mock_post: MagicMock) -> None:
    """Book detail response should return null thumbnail_url when field is missing."""
    doc = _make_book_doc()
    assert "thumbnail_url_s" not in doc  # baseline: helper has no thumbnail
    _mock_solr_ok(mock_post, _solr_response([doc]))

    client = get_client()
    data = client.get(f"/v1/books/{VALID_SHA256}").json()

    assert data["thumbnail_url"] is None
