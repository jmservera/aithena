"""Tests for configurable search architecture (HNSW vs hybrid-rerank).

Tests the /v1/capabilities endpoint, mode gating, hybrid-rerank search path,
and similar_books gating.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from tests.auth_helpers import create_authenticated_client  # noqa: E402


def get_client() -> TestClient:
    return create_authenticated_client()


# -- /v1/capabilities tests --


def test_capabilities_endpoint_returns_search_modes():
    client = get_client()
    resp = client.get("/v1/capabilities")
    assert resp.status_code == 200
    data = resp.json()
    assert "search_modes" in data
    assert "architecture" in data
    assert "vector_dimensions" in data
    assert data["vector_dimensions"] == 768
    assert isinstance(data["search_modes"], list)
    assert "keyword" in data["search_modes"]


def test_capabilities_hnsw_mode():
    """Default architecture is hnsw — semantic should be available."""
    client = get_client()
    resp = client.get("/v1/capabilities")
    data = resp.json()
    assert data["architecture"] == "hnsw"
    assert "semantic" in data["search_modes"]
    assert "hybrid" in data["search_modes"]
    assert data["similar_books"] is True


# -- Mode gating tests --


def test_semantic_mode_allowed_in_hnsw():
    """In HNSW mode, semantic search should be accepted (not 400)."""
    from main import VALID_SEARCH_MODES

    assert "semantic" in VALID_SEARCH_MODES


# -- Search endpoint mode validation --


@patch("main.requests.post")
def test_search_invalid_mode_returns_400_with_architecture(mock_post: MagicMock):
    client = get_client()
    resp = client.get("/v1/search", params={"q": "test", "mode": "invalid_mode"})
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "architecture" in detail


# -- Hybrid-rerank search path tests --


@patch("main.query_solr")
@patch("main._fetch_embedding")
def test_search_hybrid_rerank_path(mock_embedding: MagicMock, mock_solr: MagicMock):
    """Test hybrid search delegates to rerank path when architecture is hybrid-rerank."""
    from main import _search_hybrid_rerank

    # Mock BM25 response with 2 books
    bm25_response = {
        "response": {
            "numFound": 2,
            "docs": [
                {
                    "id": "book1",
                    "title_s": "Test Book 1",
                    "score": 10.0,
                    "file_path_s": "test1.pdf",
                },
                {
                    "id": "book2",
                    "title_s": "Test Book 2",
                    "score": 8.0,
                    "file_path_s": "test2.pdf",
                },
            ],
        },
        "highlighting": {},
        "facet_counts": {"facet_fields": {}},
    }

    # Mock grouped vector response
    grouped_response = {
        "grouped": {
            "parent_id_s": {
                "groups": [
                    {
                        "groupValue": "book1",
                        "doclist": {"docs": [{"parent_id_s": "book1", "embedding_v": [0.9, 0.1, 0.0]}]},
                    },
                    {
                        "groupValue": "book2",
                        "doclist": {"docs": [{"parent_id_s": "book2", "embedding_v": [0.1, 0.9, 0.0]}]},
                    },
                ]
            }
        }
    }

    mock_embedding.return_value = [1.0, 0.0, 0.0]  # query vector
    mock_solr.side_effect = [bm25_response, grouped_response]

    mock_request = MagicMock()
    mock_request.url_for.return_value = "http://test/doc/123"

    result = _search_hybrid_rerank(
        mock_request,
        "test query",
        1,
        10,
        "score",
        "desc",
        None,
        {},
    )

    assert result["mode"] == "hybrid"
    assert result["architecture"] == "hybrid-rerank"
    assert len(result["results"]) == 2
    # book1 should rank higher (more similar to query)
    assert result["results"][0]["id"] == "book1"


@patch("main.query_solr")
@patch("main._fetch_embedding")
def test_search_hybrid_rerank_no_vectors_degrades(mock_embedding: MagicMock, mock_solr: MagicMock):
    """When no vectors are available, hybrid-rerank should degrade gracefully."""
    from main import _search_hybrid_rerank

    bm25_response = {
        "response": {
            "numFound": 1,
            "docs": [
                {"id": "book1", "title_s": "Test Book", "score": 10.0, "file_path_s": "test.pdf"},
            ],
        },
        "highlighting": {},
        "facet_counts": {"facet_fields": {}},
    }

    # Empty grouped response (no vectors)
    grouped_response = {"grouped": {"parent_id_s": {"groups": []}}}

    mock_embedding.return_value = [1.0, 0.0]
    mock_solr.side_effect = [bm25_response, grouped_response]

    mock_request = MagicMock()
    mock_request.url_for.return_value = "http://test/doc/123"

    result = _search_hybrid_rerank(
        mock_request,
        "test query",
        1,
        10,
        "score",
        "desc",
        None,
        {},
    )

    assert result["degraded"] is True
    assert "No vector embeddings" in result["message"]


@patch("main.query_solr")
@patch("main._fetch_embedding")
def test_search_hybrid_rerank_empty_query_raises_400(mock_embedding: MagicMock, mock_solr: MagicMock):
    """Empty query in hybrid-rerank should return 400."""
    import pytest
    from fastapi import HTTPException

    from main import _search_hybrid_rerank

    mock_request = MagicMock()
    with pytest.raises(HTTPException) as exc_info:
        _search_hybrid_rerank(
            mock_request,
            "   ",
            1,
            10,
            "score",
            "desc",
            None,
            {},
        )
    assert exc_info.value.status_code == 400


@patch("main._search_keyword")
def test_search_hybrid_rerank_non_relevance_sort_uses_keyword(mock_keyword: MagicMock):
    """Non-relevance sorts should bypass reranking and use keyword search."""
    from main import _search_hybrid_rerank

    mock_keyword.return_value = {"results": [], "mode": "keyword"}
    mock_request = MagicMock()

    _search_hybrid_rerank(
        mock_request,
        "test",
        1,
        10,
        "title",
        "asc",
        None,
        {},
    )
    mock_keyword.assert_called_once()


@patch("main.query_solr")
@patch("main._fetch_embedding")
def test_search_hybrid_rerank_no_results(mock_embedding: MagicMock, mock_solr: MagicMock):
    """Empty BM25 results should return empty response."""
    from main import _search_hybrid_rerank

    bm25_response = {
        "response": {"numFound": 0, "docs": []},
        "highlighting": {},
        "facet_counts": {"facet_fields": {}},
    }

    mock_embedding.return_value = [1.0, 0.0]
    mock_solr.return_value = bm25_response

    mock_request = MagicMock()
    result = _search_hybrid_rerank(
        mock_request,
        "nonexistent",
        1,
        10,
        "score",
        "desc",
        None,
        {},
    )

    assert result["results"] == []
    assert result["architecture"] == "hybrid-rerank"


# -- Similar books gating tests --


def test_similar_books_blocked_in_hybrid_rerank():
    """Similar books should return 501 when architecture is hybrid-rerank."""
    import main as main_module

    client = get_client()
    with patch.object(
        type(main_module.settings),
        "search_architecture",
        new_callable=property,
        fget=lambda self: "hybrid-rerank",
    ):
        resp = client.get("/v1/books/some-doc-id/similar")
        assert resp.status_code == 501
        assert "hybrid-rerank" in resp.json()["detail"]


@patch("main.query_solr")
def test_similar_books_works_in_hnsw(mock_solr: MagicMock):
    """In HNSW mode, similar books should work (not 501)."""
    from config import settings

    # Settings default is "hnsw", so similar_books should NOT return 501
    assert settings.search_architecture == "hnsw"

    # Mock Solr to return a document with a vector
    mock_solr.return_value = {
        "response": {
            "numFound": 1,
            "docs": [{"id": "chunk1", "parent_id_s": "doc1", "chunk_embedding": [0.1] * 768}],
        }
    }

    client = get_client()
    resp = client.get("/v1/books/some-doc-id/similar")
    # Should not be 501 — may be 200 or 404 depending on Solr mock, but NOT 501
    assert resp.status_code != 501
