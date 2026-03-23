"""Tests for the collection query parameter (P1-5: A/B test collection routing)."""

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

from config import settings  # noqa: E402
from main import resolve_collection  # noqa: E402
from tests.auth_helpers import create_authenticated_client  # noqa: E402


def get_client() -> TestClient:
    return create_authenticated_client()


def _solr_payload(docs: list[dict] | None = None) -> dict:
    return {
        "response": {"numFound": len(docs or []), "docs": docs or []},
        "highlighting": {},
        "facet_counts": {"facet_fields": {}},
    }


def _make_doc(doc_id: str = "doc1") -> dict:
    return {
        "id": doc_id,
        "title_s": "Test Book",
        "author_s": "Author",
        "year_i": 2024,
        "category_s": "Test",
        "language_detected_s": "en",
        "file_path_s": "test/book.pdf",
        "folder_path_s": "test",
        "page_count_i": 100,
        "file_size_l": 1024,
        "score": 5.0,
    }


# ---------------------------------------------------------------------------
# resolve_collection unit tests
# ---------------------------------------------------------------------------


def test_resolve_collection_returns_default_when_none() -> None:
    result = resolve_collection(None)
    assert result == settings.default_collection


def test_resolve_collection_accepts_allowed_collection() -> None:
    # The default allowlist contains "books"
    result = resolve_collection("books")
    assert result == "books"


def test_resolve_collection_rejects_unknown_collection() -> None:
    import pytest
    from fastapi import HTTPException  # noqa: E402

    with pytest.raises(HTTPException) as exc_info:
        resolve_collection("nonexistent_collection")
    assert exc_info.value.status_code == 400
    assert "Invalid collection" in exc_info.value.detail


# ---------------------------------------------------------------------------
# Config: allowed_collections / default_collection / e5_collections
# ---------------------------------------------------------------------------


def test_config_allowed_collections_is_frozenset() -> None:
    assert isinstance(settings.allowed_collections, frozenset)
    assert "books" in settings.allowed_collections


def test_config_default_collection() -> None:
    assert settings.default_collection == "books"


def test_config_select_url_for() -> None:
    url = settings.select_url_for("books_e5base")
    assert url.endswith("/books_e5base/select")
    assert settings.solr_url in url


def test_config_embeddings_url_for_defaults_to_main() -> None:
    url = settings.embeddings_url_for("books")
    assert url == settings.embeddings_url


def test_config_is_e5_collection_returns_true_for_books() -> None:
    assert settings.is_e5_collection("books") is True


# ---------------------------------------------------------------------------
# Config with env vars (e5 collections)
# ---------------------------------------------------------------------------


@patch.dict(os.environ, {
    "ALLOWED_COLLECTIONS": "books,books_e5base",
    "DEFAULT_COLLECTION": "books",
    "E5_COLLECTIONS": "books_e5base",
    "EMBEDDINGS_URL_BOOKS_E5BASE": "http://embeddings-server-e5:8085/v1/embeddings/",
})
def test_config_e5_collection_parsing() -> None:
    from config import _parse_collection_set, _parse_embeddings_url_overrides

    allowed = _parse_collection_set("books,books_e5base")
    assert allowed == frozenset({"books", "books_e5base"})

    e5 = _parse_collection_set("books_e5base")
    assert e5 == frozenset({"books_e5base"})

    overrides = _parse_embeddings_url_overrides(allowed)
    overrides_dict = dict(overrides)
    assert "books_e5base" in overrides_dict
    assert "8085" in overrides_dict["books_e5base"]


# ---------------------------------------------------------------------------
# Search endpoint: collection parameter
# ---------------------------------------------------------------------------


@patch("main.requests.post")
def test_search_default_collection_uses_default_solr_url(mock_post: MagicMock) -> None:
    """When collection is omitted, search uses the default collection URL."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _solr_payload([_make_doc()])
    mock_post.return_value = mock_resp

    client = get_client()
    response = client.get("/search", params={"q": "test"})

    assert response.status_code == 200
    solr_calls = [c for c in mock_post.call_args_list if "data" in c.kwargs]
    assert len(solr_calls) == 1
    # Should use the default select_url (books collection)
    assert solr_calls[0].args[0] == settings.select_url


@patch("main.requests.post")
def test_search_explicit_default_collection(mock_post: MagicMock) -> None:
    """Explicitly passing collection=books uses the same default URL."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _solr_payload([_make_doc()])
    mock_post.return_value = mock_resp

    client = get_client()
    response = client.get("/search", params={"q": "test", "collection": "books"})

    assert response.status_code == 200
    solr_calls = [c for c in mock_post.call_args_list if "data" in c.kwargs]
    assert len(solr_calls) == 1
    assert "/books/select" in solr_calls[0].args[0]


def test_search_invalid_collection_returns_400() -> None:
    """Unknown collection names are rejected with 400."""
    client = get_client()
    response = client.get("/search", params={"q": "test", "collection": "invalid_collection"})

    assert response.status_code == 400
    data = response.json()
    assert "Invalid collection" in data["detail"]


@patch("main.requests.post")
def test_search_with_allowed_collection_routes_to_correct_url(mock_post: MagicMock) -> None:
    """When an allowed collection is specified, Solr queries hit the correct URL."""
    # Temporarily add books_e5base to allowed collections
    original = settings.allowed_collections
    object.__setattr__(settings, "allowed_collections", frozenset({"books", "books_e5base"}))
    try:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _solr_payload([_make_doc()])
        mock_post.return_value = mock_resp

        client = get_client()
        response = client.get("/search", params={"q": "test", "collection": "books_e5base"})

        assert response.status_code == 200
        solr_calls = [c for c in mock_post.call_args_list if "data" in c.kwargs]
        assert len(solr_calls) == 1
        assert "/books_e5base/select" in solr_calls[0].args[0]
    finally:
        object.__setattr__(settings, "allowed_collections", original)


# ---------------------------------------------------------------------------
# Semantic search: collection routes to correct embeddings URL + input_type
# ---------------------------------------------------------------------------


@patch("main.requests.post")
def test_semantic_search_e5_collection_passes_input_type(mock_post: MagicMock) -> None:
    """When targeting an e5 collection, the embeddings request includes input_type='query'."""
    original_allowed = settings.allowed_collections
    original_e5 = settings.e5_collections
    object.__setattr__(settings, "allowed_collections", frozenset({"books", "books_e5base"}))
    object.__setattr__(settings, "e5_collections", frozenset({"books_e5base"}))

    try:
        mock_emb_resp = MagicMock()
        mock_emb_resp.status_code = 200
        mock_emb_resp.json.return_value = {"data": [{"embedding": [0.1] * 512}]}
        mock_emb_resp.raise_for_status = MagicMock()

        mock_solr_resp = MagicMock()
        mock_solr_resp.status_code = 200
        mock_solr_resp.json.return_value = _solr_payload([_make_doc()])

        def _dispatch(url, **kwargs):
            if "json" in kwargs:
                return mock_emb_resp
            return mock_solr_resp

        mock_post.side_effect = _dispatch

        client = get_client()
        response = client.get(
            "/search",
            params={"q": "catalan history", "mode": "semantic", "collection": "books_e5base"},
        )

        assert response.status_code == 200
        # Find the embeddings call (has json= kwarg)
        emb_calls = [c for c in mock_post.call_args_list if "json" in c.kwargs]
        assert len(emb_calls) == 1
        emb_body = emb_calls[0].kwargs["json"]
        assert emb_body.get("input_type") == "query"
    finally:
        object.__setattr__(settings, "allowed_collections", original_allowed)
        object.__setattr__(settings, "e5_collections", original_e5)


@patch("main.requests.post")
def test_semantic_search_default_collection_sends_input_type(mock_post: MagicMock) -> None:
    """Default (e5) collection should include input_type='query' in embeddings request."""
    mock_emb_resp = MagicMock()
    mock_emb_resp.status_code = 200
    mock_emb_resp.json.return_value = {"data": [{"embedding": [0.1] * 768}]}
    mock_emb_resp.raise_for_status = MagicMock()

    mock_solr_resp = MagicMock()
    mock_solr_resp.status_code = 200
    mock_solr_resp.json.return_value = _solr_payload([_make_doc()])

    def _dispatch(url, **kwargs):
        if "json" in kwargs:
            return mock_emb_resp
        return mock_solr_resp

    mock_post.side_effect = _dispatch

    client = get_client()
    response = client.get("/search", params={"q": "test query", "mode": "semantic"})

    assert response.status_code == 200
    emb_calls = [c for c in mock_post.call_args_list if "json" in c.kwargs]
    assert len(emb_calls) == 1
    emb_body = emb_calls[0].kwargs["json"]
    assert emb_body.get("input_type") == "query"


# ---------------------------------------------------------------------------
# Hybrid search: collection parameter threaded through
# ---------------------------------------------------------------------------


@patch("main.requests.post")
def test_hybrid_search_with_collection_routes_correctly(mock_post: MagicMock) -> None:
    """Hybrid search should route both BM25 and kNN legs to the specified collection."""
    original_allowed = settings.allowed_collections
    object.__setattr__(settings, "allowed_collections", frozenset({"books", "books_e5base"}))

    try:
        mock_emb_resp = MagicMock()
        mock_emb_resp.status_code = 200
        mock_emb_resp.json.return_value = {"data": [{"embedding": [0.1] * 512}]}
        mock_emb_resp.raise_for_status = MagicMock()

        mock_solr_resp = MagicMock()
        mock_solr_resp.status_code = 200
        mock_solr_resp.json.return_value = _solr_payload([_make_doc()])

        def _dispatch(url, **kwargs):
            if "json" in kwargs:
                return mock_emb_resp
            return mock_solr_resp

        mock_post.side_effect = _dispatch

        client = get_client()
        response = client.get(
            "/search",
            params={"q": "test query", "mode": "hybrid", "collection": "books_e5base"},
        )

        assert response.status_code == 200
        # All Solr calls (data= kwarg) should go to books_e5base
        solr_calls = [c for c in mock_post.call_args_list if "data" in c.kwargs]
        for call in solr_calls:
            assert "/books_e5base/select" in call.args[0]
    finally:
        object.__setattr__(settings, "allowed_collections", original_allowed)


# ---------------------------------------------------------------------------
# Facets endpoint: collection parameter
# ---------------------------------------------------------------------------


@patch("main.requests.post")
def test_facets_with_collection_routes_correctly(mock_post: MagicMock) -> None:
    """Facets endpoint should route to the specified collection."""
    original_allowed = settings.allowed_collections
    object.__setattr__(settings, "allowed_collections", frozenset({"books", "books_e5base"}))

    try:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _solr_payload()
        mock_post.return_value = mock_resp

        client = get_client()
        response = client.get("/facets", params={"q": "test", "collection": "books_e5base"})

        assert response.status_code == 200
        solr_calls = [c for c in mock_post.call_args_list if "data" in c.kwargs]
        assert len(solr_calls) == 1
        assert "/books_e5base/select" in solr_calls[0].args[0]
    finally:
        object.__setattr__(settings, "allowed_collections", original_allowed)


def test_facets_invalid_collection_returns_400() -> None:
    client = get_client()
    response = client.get("/facets", params={"q": "test", "collection": "invalid"})
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Books endpoint: collection parameter
# ---------------------------------------------------------------------------


@patch("main.requests.post")
def test_books_with_collection_routes_correctly(mock_post: MagicMock) -> None:
    """Books listing endpoint should route to the specified collection."""
    original_allowed = settings.allowed_collections
    object.__setattr__(settings, "allowed_collections", frozenset({"books", "books_e5base"}))

    try:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _solr_payload([_make_doc()])
        mock_post.return_value = mock_resp

        client = get_client()
        response = client.get("/books", params={"collection": "books_e5base"})

        assert response.status_code == 200
        solr_calls = [c for c in mock_post.call_args_list if "data" in c.kwargs]
        assert len(solr_calls) == 1
        assert "/books_e5base/select" in solr_calls[0].args[0]
    finally:
        object.__setattr__(settings, "allowed_collections", original_allowed)


def test_books_invalid_collection_returns_400() -> None:
    client = get_client()
    response = client.get("/books", params={"collection": "invalid"})
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Backward compatibility: omitting collection works as before
# ---------------------------------------------------------------------------


@patch("main.requests.post")
def test_search_without_collection_is_backward_compatible(mock_post: MagicMock) -> None:
    """Omitting collection should behave exactly like the existing API."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _solr_payload([_make_doc()])
    mock_post.return_value = mock_resp

    client = get_client()
    response = client.get("/search", params={"q": "folklore"})

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "keyword"
    assert len(data["results"]) == 1


@patch("main.requests.post")
def test_facets_without_collection_is_backward_compatible(mock_post: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _solr_payload()
    mock_post.return_value = mock_resp

    client = get_client()
    response = client.get("/facets", params={"q": ""})
    assert response.status_code == 200


@patch("main.requests.post")
def test_books_without_collection_is_backward_compatible(mock_post: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _solr_payload([_make_doc()])
    mock_post.return_value = mock_resp

    client = get_client()
    response = client.get("/books")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# search_service.get_query_embedding: input_type support
# ---------------------------------------------------------------------------


def test_get_query_embedding_without_input_type() -> None:
    """Default call should not include input_type in request body."""
    from search_service import get_query_embedding

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3]}]}

    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = get_query_embedding("http://example.com/embed", "test", timeout=10.0)

    assert result == [0.1, 0.2, 0.3]
    call_body = mock_post.call_args.kwargs["json"]
    assert "input_type" not in call_body
    assert call_body["input"] == "test"


def test_get_query_embedding_with_input_type_query() -> None:
    """When input_type='query', it should be included in the request body."""
    from search_service import get_query_embedding

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": [{"embedding": [0.4, 0.5, 0.6]}]}

    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = get_query_embedding(
            "http://example.com/embed", "test", timeout=10.0, input_type="query"
        )

    assert result == [0.4, 0.5, 0.6]
    call_body = mock_post.call_args.kwargs["json"]
    assert call_body["input_type"] == "query"
    assert call_body["input"] == "test"


# ---------------------------------------------------------------------------
# E5 collection embeddings URL override
# ---------------------------------------------------------------------------


def test_embeddings_url_for_with_override() -> None:
    """Per-collection embeddings URL override should take precedence."""
    original_urls = settings.collection_embeddings_urls
    override = (("books_e5base", "http://embeddings-e5:8085/v1/embeddings/"),)
    object.__setattr__(settings, "collection_embeddings_urls", override)

    try:
        url = settings.embeddings_url_for("books_e5base")
        assert url == "http://embeddings-e5:8085/v1/embeddings/"

        # Non-overridden collections still use the default
        default_url = settings.embeddings_url_for("books")
        assert default_url == settings.embeddings_url
    finally:
        object.__setattr__(settings, "collection_embeddings_urls", original_urls)


# ---------------------------------------------------------------------------
# Filters work with collection parameter
# ---------------------------------------------------------------------------


@patch("main.requests.post")
def test_search_with_collection_and_filters(mock_post: MagicMock) -> None:
    """Collection parameter should work alongside fq_* filter parameters."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _solr_payload([_make_doc()])
    mock_post.return_value = mock_resp

    client = get_client()
    response = client.get(
        "/search",
        params={"q": "test", "fq_author": "Author", "fq_year": "2024"},
    )

    assert response.status_code == 200
    solr_calls = [c for c in mock_post.call_args_list if "data" in c.kwargs]
    assert len(solr_calls) == 1
    # Verify filter queries are present
    fq = solr_calls[0].kwargs["data"]["fq"]
    fq_str = " ".join(fq) if isinstance(fq, list) else fq
    assert "author_s" in fq_str
    assert "year_i" in fq_str
