"""Tests for the /v1/books endpoint (library browsing)."""

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
from config import settings  # noqa: E402

from tests.auth_helpers import create_authenticated_client  # noqa: E402


def get_client():
    return create_authenticated_client()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_book_doc(
    idx: int = 0,
    *,
    title: str | None = None,
    author: str | None = None,
    year: int | None = None,
    category: str | None = None,
    language: str | None = None,
) -> dict:
    return {
        "id": f"book{idx}",
        "title_s": title or f"Book {idx}",
        "author_s": author or f"Author {idx}",
        "year_i": year or 2000 + idx,
        "category_s": category or "Fiction",
        "language_detected_s": language or "en",
        "file_path_s": f"library/book{idx}.pdf",
        "folder_path_s": "library",
        "page_count_i": 100 + idx * 10,
        "file_size_l": 1024 * (idx + 1),
        "score": 1.0,
    }


def _solr_response(docs: list[dict], num_found: int | None = None, facets: dict | None = None) -> dict:
    return {
        "response": {
            "numFound": num_found if num_found is not None else len(docs),
            "docs": docs,
        },
        "highlighting": {},
        "facet_counts": {
            "facet_fields": facets or {
                "author_s": [],
                "category_s": [],
                "year_i": [],
                "language_detected_s": [],
                "language_s": [],
            }
        },
    }


def _mock_solr_ok(mock_get: MagicMock, payload: dict) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = payload
    mock_get.return_value = mock_response


# ---------------------------------------------------------------------------
# Basic listing
# ---------------------------------------------------------------------------


@patch("main.requests.get")
def test_books_returns_results(mock_get: MagicMock) -> None:
    docs = [_make_book_doc(i) for i in range(3)]
    _mock_solr_ok(mock_get, _solr_response(docs))

    client = get_client()
    response = client.get("/v1/books")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert data["total_results"] == 3
    assert len(data["results"]) == 3
    assert data["results"][0]["id"] == "book0"
    assert data["results"][0]["title"] == "Book 0"
    assert data["results"][0]["author"] == "Author 0"


@patch("main.requests.get")
def test_books_trailing_slash_alias(mock_get: MagicMock) -> None:
    _mock_solr_ok(mock_get, _solr_response([]))

    client = get_client()
    response = client.get("/v1/books/")

    assert response.status_code == 200
    assert response.json()["total"] == 0


@patch("main.requests.get")
def test_books_canonical_endpoint(mock_get: MagicMock) -> None:
    _mock_solr_ok(mock_get, _solr_response([_make_book_doc(0)]))

    client = get_client()
    response = client.get("/books")

    assert response.status_code == 200
    assert len(response.json()["results"]) == 1


# ---------------------------------------------------------------------------
# Response structure
# ---------------------------------------------------------------------------


@patch("main.requests.get")
def test_books_response_structure(mock_get: MagicMock) -> None:
    docs = [_make_book_doc(0)]
    _mock_solr_ok(mock_get, _solr_response(docs))

    client = get_client()
    data = client.get("/v1/books").json()

    assert "sort" in data
    assert data["sort"] == {"by": "title", "order": "asc"}
    assert "page" in data
    assert "limit" in data
    assert "page_size" in data
    assert "total" in data
    assert "total_results" in data
    assert "total_pages" in data
    assert "results" in data
    assert "facets" in data


@patch("main.requests.get")
def test_books_result_fields(mock_get: MagicMock) -> None:
    docs = [_make_book_doc(0)]
    _mock_solr_ok(mock_get, _solr_response(docs))

    client = get_client()
    result = client.get("/v1/books").json()["results"][0]

    assert result["id"] == "book0"
    assert result["title"] == "Book 0"
    assert result["author"] == "Author 0"
    assert result["year"] == 2000
    assert result["category"] == "Fiction"
    assert result["language"] == "en"
    assert result["file_path"] == "library/book0.pdf"
    assert result["folder_path"] == "library"
    assert result["page_count"] == 100
    assert result["file_size"] == 1024
    assert result["document_url"] is not None


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


@patch("main.requests.get")
def test_books_default_pagination(mock_get: MagicMock) -> None:
    docs = [_make_book_doc(i) for i in range(5)]
    _mock_solr_ok(mock_get, _solr_response(docs, num_found=50))

    client = get_client()
    data = client.get("/v1/books").json()

    assert data["page"] == 1
    assert data["page_size"] == settings.default_page_size
    assert data["total"] == 50

    params = mock_get.call_args[1]["params"]
    assert params["start"] == 0
    assert params["rows"] == settings.default_page_size


@patch("main.requests.get")
def test_books_custom_page_and_page_size(mock_get: MagicMock) -> None:
    _mock_solr_ok(mock_get, _solr_response([], num_found=100))

    client = get_client()
    data = client.get("/v1/books", params={"page": 3, "page_size": 25}).json()

    assert data["page"] == 3
    assert data["page_size"] == 25
    assert data["total_pages"] == 4

    params = mock_get.call_args[1]["params"]
    assert params["start"] == 50
    assert params["rows"] == 25


@patch("main.requests.get")
def test_books_page_1_starts_at_zero(mock_get: MagicMock) -> None:
    _mock_solr_ok(mock_get, _solr_response([], num_found=10))

    client = get_client()
    client.get("/v1/books", params={"page": 1, "page_size": 10})

    params = mock_get.call_args[1]["params"]
    assert params["start"] == 0


@patch("main.requests.get")
def test_books_total_pages_calculated(mock_get: MagicMock) -> None:
    _mock_solr_ok(mock_get, _solr_response([], num_found=51))

    client = get_client()
    data = client.get("/v1/books", params={"page_size": 10}).json()

    assert data["total_pages"] == 6  # ceil(51/10)


def test_books_page_zero_returns_422() -> None:
    client = get_client()
    response = client.get("/v1/books", params={"page": 0})
    assert response.status_code == 422


def test_books_negative_page_returns_422() -> None:
    client = get_client()
    response = client.get("/v1/books", params={"page": -1})
    assert response.status_code == 422


def test_books_page_size_zero_returns_422() -> None:
    client = get_client()
    response = client.get("/v1/books", params={"page_size": 0})
    assert response.status_code == 422


def test_books_page_size_exceeds_max_returns_422() -> None:
    client = get_client()
    response = client.get("/v1/books", params={"page_size": settings.max_page_size + 1})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------


@patch("main.requests.get")
def test_books_default_sort_is_title_asc(mock_get: MagicMock) -> None:
    _mock_solr_ok(mock_get, _solr_response([]))

    client = get_client()
    data = client.get("/v1/books").json()

    assert data["sort"] == {"by": "title", "order": "asc"}
    params = mock_get.call_args[1]["params"]
    assert params["sort"] == "title_s asc"


@patch("main.requests.get")
def test_books_sort_by_year_desc(mock_get: MagicMock) -> None:
    _mock_solr_ok(mock_get, _solr_response([]))

    client = get_client()
    data = client.get("/v1/books", params={"sort_by": "year", "sort_order": "desc"}).json()

    assert data["sort"] == {"by": "year", "order": "desc"}
    params = mock_get.call_args[1]["params"]
    assert params["sort"] == "year_i desc"


@patch("main.requests.get")
def test_books_sort_by_author_asc(mock_get: MagicMock) -> None:
    _mock_solr_ok(mock_get, _solr_response([]))

    client = get_client()
    client.get("/v1/books", params={"sort_by": "author", "sort_order": "asc"})

    params = mock_get.call_args[1]["params"]
    assert params["sort"] == "author_s asc"


@patch("main.requests.get")
def test_books_sort_by_category(mock_get: MagicMock) -> None:
    _mock_solr_ok(mock_get, _solr_response([]))

    client = get_client()
    client.get("/v1/books", params={"sort_by": "category"})

    params = mock_get.call_args[1]["params"]
    assert params["sort"] == "category_s asc"


def test_books_invalid_sort_by_returns_422() -> None:
    client = get_client()
    response = client.get("/v1/books", params={"sort_by": "invalid_field"})
    assert response.status_code == 422


def test_books_invalid_sort_order_returns_422() -> None:
    client = get_client()
    response = client.get("/v1/books", params={"sort_order": "sideways"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


@patch("main.requests.get")
def test_books_filter_by_author(mock_get: MagicMock) -> None:
    _mock_solr_ok(mock_get, _solr_response([]))

    client = get_client()
    client.get("/v1/books", params={"fq_author": "Joan Amades"})

    params = mock_get.call_args[1]["params"]
    assert any("author_s:" in fq for fq in params["fq"])


@patch("main.requests.get")
def test_books_filter_by_category(mock_get: MagicMock) -> None:
    _mock_solr_ok(mock_get, _solr_response([]))

    client = get_client()
    client.get("/v1/books", params={"fq_category": "Folklore"})

    params = mock_get.call_args[1]["params"]
    assert any("category_s:" in fq for fq in params["fq"])


@patch("main.requests.get")
def test_books_filter_by_language(mock_get: MagicMock) -> None:
    _mock_solr_ok(mock_get, _solr_response([]))

    client = get_client()
    client.get("/v1/books", params={"fq_language": "ca"})

    params = mock_get.call_args[1]["params"]
    fq_list = params["fq"]
    assert any("language_detected_s:ca" in fq or "language_s:ca" in fq for fq in fq_list)


@patch("main.requests.get")
def test_books_filter_by_year(mock_get: MagicMock) -> None:
    _mock_solr_ok(mock_get, _solr_response([]))

    client = get_client()
    client.get("/v1/books", params={"fq_year": "1950"})

    params = mock_get.call_args[1]["params"]
    assert any("year_i:" in fq for fq in params["fq"])


@patch("main.requests.get")
def test_books_multiple_filters(mock_get: MagicMock) -> None:
    _mock_solr_ok(mock_get, _solr_response([]))

    client = get_client()
    client.get("/v1/books", params={"fq_author": "Amades", "fq_category": "Folklore"})

    params = mock_get.call_args[1]["params"]
    fq_list = params["fq"]
    assert len(fq_list) == 2


@patch("main.requests.get")
def test_books_no_filters_sends_no_fq(mock_get: MagicMock) -> None:
    _mock_solr_ok(mock_get, _solr_response([]))

    client = get_client()
    client.get("/v1/books")

    params = mock_get.call_args[1]["params"]
    assert "fq" not in params or params.get("fq") == [] or params.get("fq") is None


@patch("main.requests.get")
def test_books_uses_wildcard_query(mock_get: MagicMock) -> None:
    """The books endpoint must query Solr with *:* to match all documents."""
    _mock_solr_ok(mock_get, _solr_response([]))

    client = get_client()
    client.get("/v1/books")

    params = mock_get.call_args[1]["params"]
    assert params["q"] == "*:*"


# ---------------------------------------------------------------------------
# Facets
# ---------------------------------------------------------------------------


@patch("main.requests.get")
def test_books_returns_facets(mock_get: MagicMock) -> None:
    facets = {
        "author_s": ["Author A", 3, "Author B", 2],
        "category_s": ["Fiction", 4, "History", 1],
        "year_i": [2020, 2, 2021, 3],
        "language_detected_s": ["en", 3, "ca", 2],
        "language_s": [],
    }
    _mock_solr_ok(mock_get, _solr_response([], facets=facets))

    client = get_client()
    data = client.get("/v1/books").json()

    assert "facets" in data
    assert data["facets"]["author"] == [
        {"value": "Author A", "count": 3},
        {"value": "Author B", "count": 2},
    ]
    assert data["facets"]["category"] == [
        {"value": "Fiction", "count": 4},
        {"value": "History", "count": 1},
    ]


# ---------------------------------------------------------------------------
# Error handling — Solr failures
# ---------------------------------------------------------------------------


@patch("main.requests.get")
def test_books_solr_timeout_returns_504(mock_get: MagicMock) -> None:
    mock_get.side_effect = req_lib.Timeout("Connection timeout")

    client = get_client()
    response = client.get("/v1/books")

    assert response.status_code == 504
    assert "Timed out" in response.json()["detail"]


@patch("main.requests.get")
def test_books_solr_connection_error_returns_502(mock_get: MagicMock) -> None:
    mock_get.side_effect = req_lib.ConnectionError("Cannot connect to Solr")

    client = get_client()
    response = client.get("/v1/books")

    assert response.status_code == 502
    assert "failed" in response.json()["detail"]


@patch("main.requests.get")
def test_books_solr_invalid_json_returns_502(mock_get: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_get.return_value = mock_response

    client = get_client()
    response = client.get("/v1/books")

    assert response.status_code == 502
    assert "invalid JSON" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@patch("main.requests.get")
def test_books_empty_results(mock_get: MagicMock) -> None:
    _mock_solr_ok(mock_get, _solr_response([], num_found=0))

    client = get_client()
    data = client.get("/v1/books").json()

    assert data["total"] == 0
    assert data["total_results"] == 0
    assert data["total_pages"] == 0
    assert data["results"] == []


@patch("main.requests.get")
def test_books_single_result(mock_get: MagicMock) -> None:
    docs = [_make_book_doc(0, title="Only Book", author="Solo Author")]
    _mock_solr_ok(mock_get, _solr_response(docs, num_found=1))

    client = get_client()
    data = client.get("/v1/books").json()

    assert data["total"] == 1
    assert data["total_pages"] == 1
    assert len(data["results"]) == 1
    assert data["results"][0]["title"] == "Only Book"
    assert data["results"][0]["author"] == "Solo Author"


@patch("main.requests.get")
def test_books_missing_title_falls_back_to_filename(mock_get: MagicMock) -> None:
    doc = _make_book_doc(0)
    doc["title_s"] = None
    _mock_solr_ok(mock_get, _solr_response([doc]))

    client = get_client()
    result = client.get("/v1/books").json()["results"][0]

    assert result["title"] == "book0"  # stem of file_path_s


@patch("main.requests.get")
def test_books_missing_author_falls_back_to_unknown(mock_get: MagicMock) -> None:
    doc = _make_book_doc(0)
    doc["author_s"] = None
    _mock_solr_ok(mock_get, _solr_response([doc]))

    client = get_client()
    result = client.get("/v1/books").json()["results"][0]

    assert result["author"] == "Unknown"


@patch("main.requests.get")
def test_books_document_url_present(mock_get: MagicMock) -> None:
    docs = [_make_book_doc(0)]
    _mock_solr_ok(mock_get, _solr_response(docs))

    client = get_client()
    result = client.get("/v1/books").json()["results"][0]

    assert result["document_url"] is not None
    assert isinstance(result["document_url"], str)


@patch("main.requests.get")
def test_books_missing_file_path_returns_null_url(mock_get: MagicMock) -> None:
    doc = _make_book_doc(0)
    doc["file_path_s"] = None
    _mock_solr_ok(mock_get, _solr_response([doc]))

    client = get_client()
    result = client.get("/v1/books").json()["results"][0]

    assert result["document_url"] is None


@patch("main.requests.get")
def test_books_large_page_beyond_results(mock_get: MagicMock) -> None:
    """Requesting a page beyond available results returns empty results."""
    _mock_solr_ok(mock_get, _solr_response([], num_found=5))

    client = get_client()
    data = client.get("/v1/books", params={"page": 100, "page_size": 10}).json()

    assert data["total"] == 5
    assert data["results"] == []
    assert data["page"] == 100


@patch("main.requests.get")
def test_books_highlighting_empty_dict(mock_get: MagicMock) -> None:
    """Highlighting should always be an empty list for books (no query)."""
    docs = [_make_book_doc(0)]
    _mock_solr_ok(mock_get, _solr_response(docs))

    client = get_client()
    result = client.get("/v1/books").json()["results"][0]

    assert result["highlights"] == []
