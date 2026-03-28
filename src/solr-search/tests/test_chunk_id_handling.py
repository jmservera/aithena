"""Tests for chunk ID handling in normalize_book and similar_books endpoint.

Tests cover Parker's changes:
1. normalize_book now includes parent_id field
2. similar_books endpoint resolves chunk IDs to parent IDs
"""

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

from fastapi.testclient import TestClient  # noqa: E402

from search_service import normalize_book  # noqa: E402
from tests.auth_helpers import create_authenticated_client  # noqa: E402


def get_client() -> TestClient:
    return create_authenticated_client()


# ---------------------------------------------------------------------------
# Tests for normalize_book parent_id field
# ---------------------------------------------------------------------------


def test_normalize_book_parent_id_is_none_for_parent_documents() -> None:
    """Parent documents have no parent_id_s field, so parent_id should be None."""
    parent_doc = {
        "id": "9a75196dfb66d2755d9cdfbe7785ac9e9c4b73dc1e7365926e36e01d4337ba2a",
        "title_s": "Parent Book",
        "author_s": "Test Author",
        "file_path_s": "books/parent.pdf",
        "score": 5.0,
    }

    book = normalize_book(parent_doc, {}, None)

    assert book["parent_id"] is None
    assert book["is_chunk"] is False


def test_normalize_book_parent_id_equals_parent_id_s_for_chunk_documents() -> None:
    """Chunk documents have parent_id_s field, which should be included in the result."""
    parent_id = "9a75196dfb66d2755d9cdfbe7785ac9e9c4b73dc1e7365926e36e01d4337ba2a"
    chunk_doc = {
        "id": f"{parent_id}_chunk_0042",
        "title_s": "Parent Book",
        "author_s": "Test Author",
        "file_path_s": "books/parent.pdf",
        "parent_id_s": parent_id,
        "page_start_i": 42,
        "page_end_i": 43,
        "chunk_text_t": "This is chunk text from pages 42-43.",
        "score": 8.5,
    }

    book = normalize_book(chunk_doc, {}, None)

    assert book["parent_id"] == parent_id
    assert book["is_chunk"] is True
    assert book["chunk_text"] == "This is chunk text from pages 42-43."


def test_normalize_book_parent_id_preserved_with_all_fields() -> None:
    """Verify parent_id is included along with all other fields."""
    parent_id = "abc123def456"
    chunk_doc = {
        "id": f"{parent_id}_chunk_0001",
        "title_s": "Catalan Folklore",
        "author_s": "Joan Amades",
        "year_i": 1950,
        "category_s": "Folklore",
        "language_detected_s": "ca",
        "series_s": "Catalan Tales",
        "file_path_s": "folklore/amades.pdf",
        "folder_path_s": "folklore",
        "page_count_i": 500,
        "file_size_l": 8192,
        "parent_id_s": parent_id,
        "page_start_i": 10,
        "page_end_i": 12,
        "chunk_text_t": "Chunk content here.",
        "score": 7.2,
    }

    book = normalize_book(chunk_doc, {"chunk-id": {"content": ["<em>highlight</em>"]}}, "/doc/token")

    # Verify all fields including parent_id
    assert book["id"] == f"{parent_id}_chunk_0001"
    assert book["parent_id"] == parent_id
    assert book["is_chunk"] is True
    assert book["chunk_text"] == "Chunk content here."
    assert book["pages"] == [10, 12]
    assert book["title"] == "Catalan Folklore"
    assert book["author"] == "Joan Amades"
    assert book["year"] == 1950


# ---------------------------------------------------------------------------
# Tests for similar_books chunk ID resolution
# ---------------------------------------------------------------------------

DUMMY_VECTOR = [round(0.002 * i, 4) for i in range(512)]
PARENT_HASH = "9a75196dfb66d2755d9cdfbe7785ac9e9c4b73dc1e7365926e36e01d4337ba2a"
CHUNK_ID = f"{PARENT_HASH}_chunk_0005"


def _make_mock_response(docs: list[dict], num_found: int | None = None) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {
        "response": {
            "numFound": num_found if num_found is not None else len(docs),
            "start": 0,
            "docs": docs,
        }
    }
    return mock_resp


@patch("main.requests.post")
def test_similar_books_works_with_parent_id_no_regression(mock_solr_post: MagicMock) -> None:
    """Passing a parent ID should work exactly as before (no regression)."""
    client = get_client()

    # No chunk lookup needed — parent ID goes straight to fetching chunks
    source_chunk = {"parent_id_s": PARENT_HASH, "embedding_v": DUMMY_VECTOR}
    knn_hits = [
        {"id": "other_chunk_1", "parent_id_s": "other-parent-1", "score": 0.92},
        {"id": "other_chunk_2", "parent_id_s": "other-parent-2", "score": 0.88},
    ]
    parent_docs = [
        {
            "id": "other-parent-1",
            "title_s": "Similar Book One",
            "author_s": "Author A",
            "year_i": 2020,
            "category_s": "Fiction",
            "file_path_s": "fiction/book1.pdf",
        },
        {
            "id": "other-parent-2",
            "title_s": "Similar Book Two",
            "author_s": "Author B",
            "year_i": 2021,
            "category_s": "Fiction",
            "file_path_s": "fiction/book2.pdf",
        },
    ]

    mock_solr_post.side_effect = [
        _make_mock_response([source_chunk]),  # 1. fetch embedding from first chunk
        _make_mock_response(knn_hits),  # 2. kNN search
        _make_mock_response(parent_docs),  # 3. fetch parent metadata
    ]

    response = client.get(f"/books/{PARENT_HASH}/similar")

    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 2
    assert body["results"][0]["id"] == "other-parent-1"
    assert body["results"][1]["id"] == "other-parent-2"
    # Should be 3 calls: fetch chunk embedding, kNN, fetch parent metadata
    assert mock_solr_post.call_count == 3


@patch("main.requests.post")
def test_similar_books_resolves_chunk_id_to_parent_id(mock_solr_post: MagicMock) -> None:
    """Passing a chunk ID should resolve to parent ID and return similar books."""
    client = get_client()

    # Setup mock responses
    chunk_lookup_doc = {"parent_id_s": PARENT_HASH}  # chunk lookup returns parent_id
    source_chunk = {"parent_id_s": PARENT_HASH, "embedding_v": DUMMY_VECTOR}
    knn_hits = [
        {"id": "other_chunk_1", "parent_id_s": "other-parent-1", "score": 0.95},
    ]
    parent_docs = [
        {
            "id": "other-parent-1",
            "title_s": "Related Book",
            "author_s": "Author C",
            "year_i": 2022,
            "category_s": "Science",
            "file_path_s": "science/related.pdf",
        },
    ]

    mock_solr_post.side_effect = [
        _make_mock_response([chunk_lookup_doc]),  # 0. chunk ID lookup to get parent_id
        _make_mock_response([source_chunk]),  # 1. fetch embedding from parent's first chunk
        _make_mock_response(knn_hits),  # 2. kNN search
        _make_mock_response(parent_docs),  # 3. fetch parent metadata
    ]

    response = client.get(f"/books/{CHUNK_ID}/similar")

    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["id"] == "other-parent-1"
    assert body["results"][0]["title"] == "Related Book"

    # Should be 4 calls: chunk lookup + standard 3
    assert mock_solr_post.call_count == 4

    # First call should be the chunk lookup
    first_call_params = mock_solr_post.call_args_list[0][1]["data"]
    q = first_call_params.get("q", "")
    assert f"id:{CHUNK_ID}" in q or "id:9a75196d" in q  # chunk ID lookup
    fl = first_call_params.get("fl", "")
    assert "parent_id_s" in fl


@patch("main.requests.post")
def test_similar_books_returns_404_for_nonexistent_chunk_id(mock_solr_post: MagicMock) -> None:
    """Passing a non-existent chunk ID should return 404."""
    client = get_client()
    fake_chunk_id = f"{PARENT_HASH}_chunk_9999"

    # Chunk lookup returns empty docs
    mock_solr_post.side_effect = [
        _make_mock_response([]),  # chunk lookup finds nothing
    ]

    response = client.get(f"/books/{fake_chunk_id}/similar")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@patch("main.requests.post")
def test_similar_books_returns_404_when_chunk_has_no_parent_id(mock_solr_post: MagicMock) -> None:
    """Passing a chunk ID that exists but has no parent_id_s should return 404."""
    client = get_client()
    orphan_chunk_id = f"{PARENT_HASH}_chunk_0042"

    # Chunk lookup returns a doc without parent_id_s
    mock_solr_post.side_effect = [
        _make_mock_response([{"id": orphan_chunk_id}]),  # missing parent_id_s
    ]

    response = client.get(f"/books/{orphan_chunk_id}/similar")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@patch("main.requests.post")
def test_similar_books_chunk_id_parent_not_found_returns_404(mock_solr_post: MagicMock) -> None:
    """If chunk resolves to a parent ID that doesn't exist, should return 404."""
    client = get_client()
    ghost_parent_id = "ghost123456789"
    chunk_with_ghost_parent = f"{ghost_parent_id}_chunk_0001"

    # Chunk lookup succeeds with parent_id, but fetching chunks for that parent fails
    mock_solr_post.side_effect = [
        _make_mock_response([{"parent_id_s": ghost_parent_id}]),  # chunk lookup returns ghost parent
        _make_mock_response([]),  # no chunks found for ghost parent
        _make_mock_response([]),  # parent doc check also fails
    ]

    response = client.get(f"/books/{chunk_with_ghost_parent}/similar")

    assert response.status_code == 404
    # Should indicate document not found
    assert "not found" in response.json()["detail"].lower()


@patch("main.requests.post")
def test_similar_books_chunk_resolution_uses_correct_solr_query(mock_solr_post: MagicMock) -> None:
    """Verify the chunk lookup query uses correct Solr params."""
    client = get_client()

    chunk_lookup_doc = {"parent_id_s": PARENT_HASH}
    source_chunk = {"parent_id_s": PARENT_HASH, "embedding_v": DUMMY_VECTOR}
    knn_hits = []
    parent_docs = []

    mock_solr_post.side_effect = [
        _make_mock_response([chunk_lookup_doc]),
        _make_mock_response([source_chunk]),
        _make_mock_response(knn_hits),
        _make_mock_response(parent_docs),
    ]

    client.get(f"/books/{CHUNK_ID}/similar")

    # Verify chunk lookup query structure
    chunk_lookup_params = mock_solr_post.call_args_list[0][1]["data"]
    assert "fl" in chunk_lookup_params
    assert "parent_id_s" in chunk_lookup_params["fl"]
    assert chunk_lookup_params.get("rows") == 1
    assert "wt" in chunk_lookup_params
    assert chunk_lookup_params["wt"] == "json"
