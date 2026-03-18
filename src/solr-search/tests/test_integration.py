from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

os.environ.setdefault("AUTH_DB_PATH", "/tmp/test-auth.db")  # noqa: S108
os.environ.setdefault("AUTH_JWT_SECRET", "test-auth-secret")
os.environ.setdefault("AUTH_JWT_TTL", "24h")
os.environ.setdefault("AUTH_COOKIE_NAME", "aithena_auth")

sys.path.append(str(Path(__file__).resolve().parents[1]))

from config import settings  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

from tests.auth_helpers import create_authenticated_client  # noqa: E402


def get_client() -> TestClient:
    return create_authenticated_client()


@patch("main.requests.get")
def test_search_returns_results_with_mocked_solr(mock_solr_get: MagicMock) -> None:
    client = get_client()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": {
            "numFound": 2,
            "docs": [
                {
                    "id": "doc1",
                    "title_s": "Catalan Folklore",
                    "author_s": "Joan Amades",
                    "year_i": 1950,
                    "category_s": "Folklore",
                    "language_detected_s": "ca",
                    "file_path_s": "amades/catalan_folklore.pdf",
                    "folder_path_s": "amades",
                    "page_count_i": 250,
                    "file_size_l": 5242880,
                    "score": 12.5,
                },
                {
                    "id": "doc2",
                    "title_s": "Rondalles Populars",
                    "author_s": "Joan Amades",
                    "year_i": 1952,
                    "category_s": "Folklore",
                    "language_s": "ca",
                    "file_path_s": "amades/rondalles.pdf",
                    "folder_path_s": "amades",
                    "page_count_i": 320,
                    "file_size_l": 6291456,
                    "score": 10.2,
                },
            ],
        },
        "highlighting": {
            "doc1": {
                "content": ["<em>folklore</em> traditions"],
            },
            "doc2": {
                "_text_": ["popular <em>tales</em>"],
            },
        },
        "facet_counts": {
            "facet_fields": {
                "author_s": ["Joan Amades", 2],
                "category_s": ["Folklore", 2],
                "year_i": [1950, 1, 1952, 1],
                "language_detected_s": ["ca", 2],
                "language_s": [],
            }
        },
    }
    mock_solr_get.return_value = mock_response

    response = client.get("/search", params={"q": "folklore", "page": 1, "page_size": 10})

    assert response.status_code == 200
    data = response.json()

    assert data["query"] == "folklore"
    assert data["total"] == 2
    assert data["total_results"] == 2
    assert data["page"] == 1
    assert data["limit"] == 10
    assert data["page_size"] == 10
    assert len(data["results"]) == 2

    first_result = data["results"][0]
    assert first_result["id"] == "doc1"
    assert first_result["title"] == "Catalan Folklore"
    assert first_result["author"] == "Joan Amades"
    assert first_result["year"] == 1950
    assert first_result["highlights"] == ["<em>folklore</em> traditions"]

    facets = data["facets"]
    assert facets["author"] == [{"value": "Joan Amades", "count": 2}]
    assert facets["category"] == [{"value": "Folklore", "count": 2}]
    assert len(facets["year"]) == 2


@patch("main.requests.get")
def test_v1_search_alias_supports_ui_contract_params(mock_solr_get: MagicMock) -> None:
    client = get_client()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": {"numFound": 2, "docs": []},
        "highlighting": {},
        "facet_counts": {"facet_fields": {}},
    }
    mock_solr_get.return_value = mock_response

    response = client.get(
        "/v1/search/",
        params={
            "q": "folklore",
            "page": 2,
            "limit": 10,
            "sort": "year_i asc",
            "fq_author": "Joan Amades",
            "fq_language": "ca",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 2
    assert data["limit"] == 10
    assert data["total"] == 2

    params = mock_solr_get.call_args[1]["params"]
    assert params["start"] == 10
    assert params["rows"] == 10
    assert params["sort"] == "year_i asc"
    assert params["fq"] == [
        r"author_s:Joan\ Amades",
        "(language_detected_s:ca OR language_s:ca)",
    ]


@patch("main.requests.get")
def test_search_handles_empty_query(mock_solr_get: MagicMock) -> None:
    client = get_client()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": {"numFound": 0, "docs": []},
        "highlighting": {},
        "facet_counts": {"facet_fields": {}},
    }
    mock_solr_get.return_value = mock_response

    response = client.get("/search", params={"q": ""})

    assert response.status_code == 200
    data = response.json()
    assert data["total_results"] == 0
    assert data["results"] == []

    mock_solr_get.assert_called_once()
    call_args = mock_solr_get.call_args
    assert call_args[1]["params"]["q"] == "*:*"


@patch("main.requests.get")
def test_facets_endpoint_returns_facet_counts(mock_solr_get: MagicMock) -> None:
    client = get_client()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": {"numFound": 5, "docs": []},
        "highlighting": {},
        "facet_counts": {
            "facet_fields": {
                "author_s": ["Author A", 3, "Author B", 2],
                "category_s": ["History", 4, "Science", 1],
                "year_i": [2020, 2, 2019, 3],
                "language_detected_s": ["en", 3, "ca", 2],
                "language_s": [],
            }
        },
    }
    mock_solr_get.return_value = mock_response

    response = client.get("/facets", params={"q": "test"})

    assert response.status_code == 200
    data = response.json()

    assert data["query"] == "test"
    assert "facets" in data
    assert data["facets"]["author"] == [
        {"value": "Author A", "count": 3},
        {"value": "Author B", "count": 2},
    ]
    assert data["facets"]["category"] == [
        {"value": "History", "count": 4},
        {"value": "Science", "count": 1},
    ]


@patch("main.requests.get")
def test_search_handles_solr_timeout(mock_solr_get: MagicMock) -> None:
    import requests

    mock_solr_get.side_effect = requests.Timeout("Connection timeout")

    client = get_client()
    response = client.get("/search", params={"q": "test"})

    assert response.status_code == 504
    assert "Timed out" in response.json()["detail"]


@patch("main.requests.get")
def test_search_handles_solr_connection_error(mock_solr_get: MagicMock) -> None:
    import requests

    mock_solr_get.side_effect = requests.ConnectionError("Cannot connect to Solr")

    client = get_client()
    response = client.get("/search", params={"q": "test"})

    assert response.status_code == 502
    assert "failed" in response.json()["detail"]


@patch("main.requests.get")
def test_search_handles_invalid_solr_response(mock_solr_get: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_solr_get.return_value = mock_response

    client = get_client()
    response = client.get("/search", params={"q": "test"})

    assert response.status_code == 502
    assert "invalid JSON" in response.json()["detail"]


def test_health_endpoint_returns_ok() -> None:
    client = get_client()
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "service" in data
    assert "version" in data


def test_info_endpoint_returns_service_info() -> None:
    client = get_client()
    response = client.get("/info")

    assert response.status_code == 200
    data = response.json()
    assert "title" in data
    assert "version" in data


def test_v1_health_and_info_aliases_return_ok() -> None:
    client = get_client()

    health_response = client.get("/v1/health")
    info_response = client.get("/v1/info")

    assert health_response.status_code == 200
    assert info_response.status_code == 200


def test_version_endpoint_returns_build_metadata() -> None:
    client = get_client()
    response = client.get("/version")

    assert response.status_code == 200
    assert response.json() == {
        "service": "solr-search",
        "version": settings.version,
        "commit": settings.commit,
        "built": settings.built,
    }


@patch("main.requests.get")
def test_search_pagination_parameters_passed_correctly(mock_solr_get: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": {"numFound": 100, "docs": []},
        "highlighting": {},
        "facet_counts": {"facet_fields": {}},
    }
    mock_solr_get.return_value = mock_response

    client = get_client()
    response = client.get("/search", params={"q": "test", "page": 3, "page_size": 25})

    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 3
    assert data["page_size"] == 25
    assert data["total_pages"] == 4

    mock_solr_get.assert_called_once()
    call_args = mock_solr_get.call_args
    assert call_args[1]["params"]["start"] == 50
    assert call_args[1]["params"]["rows"] == 25


@patch("main.requests.get")
def test_search_sorting_parameters_applied(mock_solr_get: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": {"numFound": 0, "docs": []},
        "highlighting": {},
        "facet_counts": {"facet_fields": {}},
    }
    mock_solr_get.return_value = mock_response

    client = get_client()
    response = client.get("/search", params={"q": "test", "sort_by": "year", "sort_order": "asc"})

    assert response.status_code == 200

    mock_solr_get.assert_called_once()
    call_args = mock_solr_get.call_args
    assert call_args[1]["params"]["sort"] == "year_i asc"


# ---------------------------------------------------------------------------
# Phase 3 — Hybrid search mode integration tests
# ---------------------------------------------------------------------------


def _make_solr_docs(n: int = 1) -> list[dict]:
    return [
        {
            "id": f"doc{i}",
            "title_s": f"Book {i}",
            "author_s": "Author A",
            "year_i": 2000 + i,
            "category_s": "History",
            "language_detected_s": "ca",
            "file_path_s": f"amades/book{i}.pdf",
            "folder_path_s": "amades",
            "page_count_i": 100,
            "file_size_l": 1024,
            "score": 1.0 - i * 0.1,
        }
        for i in range(n)
    ]


def _solr_payload(docs: list[dict], facets: dict | None = None) -> dict:
    return {
        "response": {"numFound": len(docs), "docs": docs},
        "highlighting": {},
        "facet_counts": {
            "facet_fields": facets
            or {
                "author_s": ["Author A", len(docs)],
                "category_s": ["History", len(docs)],
                "year_i": [],
                "language_detected_s": ["ca", len(docs)],
                "language_s": [],
            }
        },
    }


@patch("main.requests.get")
def test_search_keyword_mode_explicit(mock_solr_get: MagicMock) -> None:
    """?mode=keyword must behave identically to the default search."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = _solr_payload(_make_solr_docs(2))
    mock_solr_get.return_value = mock_response

    client = get_client()
    response = client.get("/search", params={"q": "folklore", "mode": "keyword"})

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "keyword"
    assert len(data["results"]) == 2
    assert "facets" in data


@patch("main.requests.get")
def test_search_default_mode_is_keyword(mock_solr_get: MagicMock) -> None:
    """Default mode (no ?mode param) should be 'keyword'."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = _solr_payload(_make_solr_docs(1))
    mock_solr_get.return_value = mock_response

    client = get_client()
    response = client.get("/search", params={"q": "test"})

    assert response.status_code == 200
    assert response.json()["mode"] == "keyword"


@patch("main.requests.post")
@patch("main.requests.get")
def test_search_semantic_mode_calls_embeddings_and_knn(mock_solr_get: MagicMock, mock_emb_post: MagicMock) -> None:
    """Semantic mode must call embeddings server then Solr kNN."""
    mock_emb_resp = MagicMock()
    mock_emb_resp.status_code = 200
    mock_emb_resp.json.return_value = {"data": [{"embedding": [0.1] * 512}]}
    mock_emb_resp.raise_for_status = MagicMock()
    mock_emb_post.return_value = mock_emb_resp

    mock_solr_resp = MagicMock()
    mock_solr_resp.status_code = 200
    mock_solr_resp.json.return_value = {
        "response": {"numFound": 1, "docs": _make_solr_docs(1)},
        "highlighting": {},
        "facet_counts": {"facet_fields": {}},
    }
    mock_solr_get.return_value = mock_solr_resp

    client = get_client()
    response = client.get("/search", params={"q": "catalan history", "mode": "semantic"})

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "semantic"
    assert len(data["results"]) == 1
    # Facets must be empty in semantic mode
    assert data["facets"]["author"] == []
    assert data["facets"]["category"] == []


@patch("main.requests.post")
@patch("main.requests.get")
def test_search_semantic_empty_query_returns_400(mock_solr_get: MagicMock, mock_emb_post: MagicMock) -> None:
    client = get_client()
    response = client.get("/search", params={"q": "", "mode": "semantic"})
    assert response.status_code == 400


@patch("main.requests.post")
@patch("main.requests.get")
def test_search_semantic_falls_back_to_keyword_when_embeddings_fail(
    mock_solr_get: MagicMock,
    mock_emb_post: MagicMock,
) -> None:
    import requests

    mock_emb_post.side_effect = requests.ConnectionError("embeddings unavailable")

    mock_solr_resp = MagicMock()
    mock_solr_resp.status_code = 200
    mock_solr_resp.json.return_value = _solr_payload(_make_solr_docs(2))
    mock_solr_get.return_value = mock_solr_resp

    client = get_client()
    response = client.get("/search", params={"q": "catalan history", "mode": "semantic"})

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "keyword"
    assert data["requested_mode"] == "semantic"
    assert data["degraded"] is True
    assert data["message"] == "Embeddings unavailable — showing keyword results"
    assert len(data["results"]) == 2

    mock_solr_get.assert_called_once()
    assert mock_solr_get.call_args[1]["params"]["q"] == "catalan history"


@patch("main.requests.post")
@patch("main.requests.get")
def test_search_hybrid_mode_fuses_both_legs(mock_solr_get: MagicMock, mock_emb_post: MagicMock) -> None:
    """Hybrid mode must combine keyword + kNN results using RRF."""
    mock_emb_resp = MagicMock()
    mock_emb_resp.status_code = 200
    mock_emb_resp.json.return_value = {"data": [{"embedding": [0.1] * 512}]}
    mock_emb_resp.raise_for_status = MagicMock()
    mock_emb_post.return_value = mock_emb_resp

    kw_docs = _make_solr_docs(3)
    knn_docs = [
        {
            "id": "sem-only",
            "title_s": "Semantic Book",
            "author_s": "Sem Author",
            "year_i": 2021,
            "category_s": "Science",
            "language_detected_s": "en",
            "file_path_s": "science/sem.pdf",
            "folder_path_s": "science",
            "page_count_i": 50,
            "file_size_l": 512,
            "score": 0.95,
        }
    ] + kw_docs[:1]  # doc0 shared in both

    solr_call_count = [0]

    def _solr_side_effect(url: str, params: dict, timeout: float):
        mock_r = MagicMock()
        mock_r.status_code = 200
        solr_call_count[0] += 1
        if "{!knn" in str(params.get("q", "")):
            mock_r.json.return_value = {
                "response": {"numFound": len(knn_docs), "docs": knn_docs},
                "highlighting": {},
                "facet_counts": {"facet_fields": {}},
            }
        else:
            mock_r.json.return_value = _solr_payload(kw_docs)
        return mock_r

    mock_solr_get.side_effect = _solr_side_effect

    client = get_client()
    response = client.get("/search", params={"q": "folklore", "mode": "hybrid", "page_size": 5})

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "hybrid"
    # doc0 appears in both lists → should rank first (RRF)
    assert data["results"][0]["id"] == "doc0"
    # Facets sourced from keyword leg
    assert len(data["facets"]["author"]) > 0
    # All results capped at page_size
    assert len(data["results"]) <= 5


@patch("main.requests.post")
@patch("main.requests.get")
def test_search_hybrid_empty_query_returns_400(mock_solr_get: MagicMock, mock_emb_post: MagicMock) -> None:
    client = get_client()
    response = client.get("/search", params={"q": "", "mode": "hybrid"})
    assert response.status_code == 400


@patch("main.requests.post")
@patch("main.requests.get")
def test_search_hybrid_falls_back_to_keyword_when_embeddings_fail(
    mock_solr_get: MagicMock,
    mock_emb_post: MagicMock,
) -> None:
    import requests

    mock_emb_post.side_effect = requests.Timeout("embeddings timeout")

    mock_solr_resp = MagicMock()
    mock_solr_resp.status_code = 200
    mock_solr_resp.json.return_value = _solr_payload(_make_solr_docs(3))
    mock_solr_get.return_value = mock_solr_resp

    client = get_client()
    response = client.get("/search", params={"q": "folklore", "mode": "hybrid", "page_size": 2})

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "keyword"
    assert data["requested_mode"] == "hybrid"
    assert data["degraded"] is True
    assert data["message"] == "Embeddings unavailable — showing keyword results"
    assert len(data["results"]) == 3
    assert mock_solr_get.call_count == 2
    assert all("{!knn" not in call[1]["params"]["q"] for call in mock_solr_get.call_args_list)


# ---------------------------------------------------------------------------
# Tests for invalid search mode parameter
# ---------------------------------------------------------------------------


def test_search_invalid_mode_returns_400() -> None:
    """GET /v1/search?q=test&mode=invalid must return 400 with a descriptive message."""
    client = get_client()
    response = client.get("/v1/search", params={"q": "test", "mode": "invalid"})

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Invalid search mode" in detail
    assert "keyword" in detail
    assert "semantic" in detail
    assert "hybrid" in detail


@patch("main.requests.get")
def test_search_keyword_mode_returns_200(mock_solr_get: MagicMock) -> None:
    """GET /v1/search?q=test&mode=keyword must return 200 (control case)."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = _solr_payload(_make_solr_docs(1))
    mock_solr_get.return_value = mock_response

    client = get_client()
    response = client.get("/v1/search", params={"q": "test", "mode": "keyword"})

    assert response.status_code == 200
    assert response.json()["mode"] == "keyword"


# ---------------------------------------------------------------------------
# Tests for GET /books/{document_id}/similar
# ---------------------------------------------------------------------------

DUMMY_VECTOR = [round(0.002 * i, 4) for i in range(512)]

SOURCE_DOC_WITH_EMBEDDING = {
    "id": "source-doc-id",
    "book_embedding": DUMMY_VECTOR,
}

SIMILAR_BOOKS_DOCS = [
    {
        "id": "similar-1",
        "title_s": "Book One",
        "author_s": "Author A",
        "year_i": 2010,
        "category_s": "Fiction",
        "file_path_s": "fiction/Author A/Book One.pdf",
        "score": 0.93,
    },
    {
        "id": "similar-2",
        "title_s": "Book Two",
        "author_s": "Author B",
        "year_i": 2015,
        "category_s": "Fiction",
        "file_path_s": "fiction/Author B/Book Two.pdf",
        "score": 0.85,
    },
]


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


@patch("main.requests.get")
def test_similar_returns_200_with_results(mock_solr_get: MagicMock) -> None:
    client = get_client()
    mock_solr_get.side_effect = [
        _make_mock_response([SOURCE_DOC_WITH_EMBEDDING]),
        _make_mock_response(SIMILAR_BOOKS_DOCS),
    ]

    response = client.get("/books/source-doc-id/similar")

    assert response.status_code == 200
    body = response.json()
    assert "results" in body
    assert len(body["results"]) == 2


@patch("main.requests.get")
def test_v1_similar_alias_returns_results(mock_solr_get: MagicMock) -> None:
    client = get_client()
    mock_solr_get.side_effect = [
        _make_mock_response([SOURCE_DOC_WITH_EMBEDDING]),
        _make_mock_response(SIMILAR_BOOKS_DOCS),
    ]

    response = client.get("/v1/books/source-doc-id/similar")

    assert response.status_code == 200
    assert len(response.json()["results"]) == 2


@patch("main.requests.get")
def test_similar_result_contains_required_fields(mock_solr_get: MagicMock) -> None:
    client = get_client()
    mock_solr_get.side_effect = [
        _make_mock_response([SOURCE_DOC_WITH_EMBEDDING]),
        _make_mock_response(SIMILAR_BOOKS_DOCS),
    ]

    response = client.get("/books/source-doc-id/similar")

    assert response.status_code == 200
    result = response.json()["results"][0]
    for field in ("id", "title", "author", "year", "category", "document_url", "score"):
        assert field in result, f"Missing required field: {field}"


@patch("main.requests.get")
def test_similar_excludes_source_document_via_fq(mock_solr_get: MagicMock) -> None:
    client = get_client()
    mock_solr_get.side_effect = [
        _make_mock_response([SOURCE_DOC_WITH_EMBEDDING]),
        _make_mock_response(SIMILAR_BOOKS_DOCS),
    ]

    client.get("/books/source-doc-id/similar")

    assert mock_solr_get.call_count == 2
    knn_call_params = mock_solr_get.call_args_list[1][1]["params"]
    fq = knn_call_params.get("fq", "")
    assert "source" in fq
    assert fq.startswith("-id:")


@patch("main.requests.get")
def test_similar_uses_knn_query_parser(mock_solr_get: MagicMock) -> None:
    client = get_client()
    mock_solr_get.side_effect = [
        _make_mock_response([SOURCE_DOC_WITH_EMBEDDING]),
        _make_mock_response(SIMILAR_BOOKS_DOCS),
    ]

    client.get("/books/source-doc-id/similar")

    knn_call_params = mock_solr_get.call_args_list[1][1]["params"]
    q = knn_call_params.get("q", "")
    assert "{!knn" in q
    assert "book_embedding" in q


@patch("main.requests.get")
def test_similar_retrieves_embedding_field_from_source(mock_solr_get: MagicMock) -> None:
    client = get_client()
    mock_solr_get.side_effect = [
        _make_mock_response([SOURCE_DOC_WITH_EMBEDDING]),
        _make_mock_response(SIMILAR_BOOKS_DOCS),
    ]

    client.get("/books/source-doc-id/similar")

    source_call_params = mock_solr_get.call_args_list[0][1]["params"]
    fl = source_call_params.get("fl", "")
    assert "book_embedding" in fl


@patch("main.requests.get")
def test_similar_limit_controls_rows_in_knn_query(mock_solr_get: MagicMock) -> None:
    client = get_client()
    mock_solr_get.side_effect = [
        _make_mock_response([SOURCE_DOC_WITH_EMBEDDING]),
        _make_mock_response(SIMILAR_BOOKS_DOCS[:1]),
    ]

    client.get("/books/source-doc-id/similar?limit=3")

    knn_call_params = mock_solr_get.call_args_list[1][1]["params"]
    assert knn_call_params.get("rows") == 3


@patch("main.requests.get")
def test_similar_min_score_filters_results(mock_solr_get: MagicMock) -> None:
    client = get_client()
    low_score_doc = {**SIMILAR_BOOKS_DOCS[1], "score": 0.50}
    mock_solr_get.side_effect = [
        _make_mock_response([SOURCE_DOC_WITH_EMBEDDING]),
        _make_mock_response([SIMILAR_BOOKS_DOCS[0], low_score_doc]),
    ]

    response = client.get("/books/source-doc-id/similar?min_score=0.8")

    assert response.status_code == 200
    scores = [r["score"] for r in response.json()["results"]]
    assert all(s >= 0.8 for s in scores)
    assert len(scores) == 1


@patch("main.requests.get")
def test_similar_returns_404_for_unknown_id(mock_solr_get: MagicMock) -> None:
    client = get_client()
    mock_solr_get.return_value = _make_mock_response([])

    response = client.get("/books/nonexistent-id/similar")

    assert response.status_code == 404


@patch("main.requests.get")
def test_similar_returns_422_when_embedding_missing(mock_solr_get: MagicMock) -> None:
    client = get_client()
    doc_no_embedding = {"id": "source-doc-id"}
    mock_solr_get.return_value = _make_mock_response([doc_no_embedding])

    response = client.get("/books/source-doc-id/similar")

    assert response.status_code == 422


@patch("main.requests.get")
def test_similar_returns_empty_list_when_no_similar_found(mock_solr_get: MagicMock) -> None:
    client = get_client()
    mock_solr_get.side_effect = [
        _make_mock_response([SOURCE_DOC_WITH_EMBEDDING]),
        _make_mock_response([]),
    ]

    response = client.get("/books/source-doc-id/similar")

    assert response.status_code == 200
    assert response.json()["results"] == []


@patch("main.requests.get")
def test_similar_returns_502_on_solr_error(mock_solr_get: MagicMock) -> None:
    import requests as req

    client = get_client()
    mock_solr_get.side_effect = req.ConnectionError("Cannot connect to Solr")

    response = client.get("/books/source-doc-id/similar")

    assert response.status_code == 502


def test_v1_document_alias_is_registered() -> None:
    assert app.url_path_for("get_document_v1", document_id="token") == "/v1/documents/token"


# ---------------------------------------------------------------------------
# Tests for GET /v1/stats/
# ---------------------------------------------------------------------------

_STATS_SOLR_PAYLOAD = {
    "grouped": {
        "parent_id_s": {
            "matches": 76,
            "ngroups": 3,
            "groups": [],
        }
    },
    "stats": {
        "stats_fields": {
            "page_count_i": {
                "min": 1.0,
                "max": 800.0,
                "sum": 12000.0,
                "mean": 157.89,
                "count": 76,
                "missing": 0,
            }
        }
    },
    "facet_counts": {
        "facet_fields": {
            "author_s": ["Joan Amades", 15, "Other Author", 5],
            "category_s": ["amades", 40, "other", 36],
            "year_i": [1950, 3, 1960, 10],
            "language_detected_s": ["ca", 40, "es", 20],
        }
    },
}


@patch("main.requests.get")
def test_stats_returns_200_with_correct_shape(mock_solr_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _STATS_SOLR_PAYLOAD
    mock_solr_get.return_value = mock_resp

    client = get_client()
    response = client.get("/v1/stats/")

    assert response.status_code == 200
    data = response.json()

    assert data["total_books"] == 3
    assert data["by_language"] == [{"value": "ca", "count": 40}, {"value": "es", "count": 20}]
    assert data["by_author"] == [{"value": "Joan Amades", "count": 15}, {"value": "Other Author", "count": 5}]
    assert data["by_year"] == [{"value": 1950, "count": 3}, {"value": 1960, "count": 10}]
    assert data["by_category"] == [{"value": "amades", "count": 40}, {"value": "other", "count": 36}]
    assert data["page_stats"]["total"] == 12000
    assert data["page_stats"]["min"] == 1
    assert data["page_stats"]["max"] == 800
    assert data["page_stats"]["avg"] == 158


@patch("main.requests.get")
def test_stats_no_slash_alias_returns_200(mock_solr_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _STATS_SOLR_PAYLOAD
    mock_solr_get.return_value = mock_resp

    client = get_client()
    response = client.get("/v1/stats")

    assert response.status_code == 200


@patch("main.requests.get")
def test_stats_legacy_path_returns_200(mock_solr_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _STATS_SOLR_PAYLOAD
    mock_solr_get.return_value = mock_resp

    client = get_client()
    response = client.get("/stats")

    assert response.status_code == 200


@patch("main.requests.get")
def test_stats_sends_correct_solr_params(mock_solr_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _STATS_SOLR_PAYLOAD
    mock_solr_get.return_value = mock_resp

    client = get_client()
    client.get("/v1/stats/")

    mock_solr_get.assert_called_once()
    params = mock_solr_get.call_args[1]["params"]
    assert params["q"] == "*:*"
    assert params["rows"] == 0
    assert params["group"] == "true"
    assert params["group.field"] == "parent_id_s"
    assert params["group.limit"] == 0
    assert params["stats"] == "true"
    assert params["stats.field"] == "page_count_i"
    assert params["facet"] == "true"
    assert "author_s" in params["facet.field"]
    assert "category_s" in params["facet.field"]
    assert "year_i" in params["facet.field"]
    assert "language_detected_s" in params["facet.field"]


@patch("main.requests.get")
def test_stats_handles_empty_collection(mock_solr_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "grouped": {"parent_id_s": {"matches": 0, "ngroups": 0, "groups": []}},
        "stats": {"stats_fields": {"page_count_i": None}},
        "facet_counts": {"facet_fields": {}},
    }
    mock_solr_get.return_value = mock_resp

    client = get_client()
    response = client.get("/v1/stats/")

    assert response.status_code == 200
    data = response.json()
    assert data["total_books"] == 0
    assert data["by_language"] == []
    assert data["by_author"] == []
    assert data["page_stats"] == {"total": 0, "avg": 0, "min": 0, "max": 0}


@patch("main.requests.get")
def test_stats_returns_504_on_solr_timeout(mock_solr_get: MagicMock) -> None:
    import requests as req

    mock_solr_get.side_effect = req.Timeout("Connection timeout")

    client = get_client()
    response = client.get("/v1/stats/")

    assert response.status_code == 504


@patch("main.requests.get")
def test_stats_returns_502_on_solr_error(mock_solr_get: MagicMock) -> None:
    import requests as req

    mock_solr_get.side_effect = req.ConnectionError("Cannot connect to Solr")

    client = get_client()
    response = client.get("/v1/stats/")

    assert response.status_code == 502


# ---------------------------------------------------------------------------
# Page range support — chunk-level search hits
# ---------------------------------------------------------------------------


@patch("main.requests.get")
def test_search_chunk_hits_include_page_range(mock_solr_get: MagicMock) -> None:
    """Chunk documents with page_start_i/page_end_i must expose pages in results."""
    client = get_client()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": {
            "numFound": 2,
            "docs": [
                {
                    "id": "chunk-1",
                    "title_s": "Rondalles",
                    "author_s": "Amades",
                    "year_i": 1950,
                    "file_path_s": "amades/rondalles.pdf",
                    "page_start_i": 5,
                    "page_end_i": 6,
                    "score": 9.0,
                },
                {
                    "id": "doc-full",
                    "title_s": "Full Book",
                    "author_s": "Amades",
                    "year_i": 1952,
                    "file_path_s": "amades/full.pdf",
                    "score": 5.0,
                },
            ],
        },
        "highlighting": {},
        "facet_counts": {"facet_fields": {}},
    }
    mock_solr_get.return_value = mock_response

    response = client.get("/search", params={"q": "rondalles"})

    assert response.status_code == 200
    results = response.json()["results"]

    chunk_result = next(r for r in results if r["id"] == "chunk-1")
    assert chunk_result["pages"] == [5, 6]

    full_result = next(r for r in results if r["id"] == "doc-full")
    assert full_result["pages"] is None


@patch("main.requests.get")
def test_search_solr_field_list_includes_page_fields(mock_solr_get: MagicMock) -> None:
    """Solr queries must request page_start_i and page_end_i fields."""
    client = get_client()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": {"numFound": 0, "docs": []},
        "highlighting": {},
        "facet_counts": {"facet_fields": {}},
    }
    mock_solr_get.return_value = mock_response

    client.get("/search", params={"q": "test"})

    params = mock_solr_get.call_args[1]["params"]
    assert "page_start_i" in params["fl"]
    assert "page_end_i" in params["fl"]


# ---------------------------------------------------------------------------
# Phase 4 — /v1/status/ endpoint tests
# ---------------------------------------------------------------------------


@patch("main._embeddings_available")
@patch("main._tcp_check")
@patch("main._get_indexing_status")
@patch("main._get_solr_status")
def test_status_endpoint_returns_expected_shape(
    mock_solr_status: MagicMock,
    mock_indexing: MagicMock,
    mock_tcp: MagicMock,
    mock_embeddings_available: MagicMock,
) -> None:
    """GET /v1/status/ must return solr, indexing, and services keys."""
    mock_solr_status.return_value = {"status": "ok", "nodes": 3, "docs_indexed": 76}
    mock_indexing.return_value = {
        "total_discovered": 169,
        "indexed": 76,
        "failed": 2,
        "pending": 91,
    }
    mock_tcp.return_value = True
    mock_embeddings_available.return_value = True

    client = get_client()
    response = client.get("/v1/status")

    assert response.status_code == 200
    data = response.json()

    assert data["solr"] == {"status": "ok", "nodes": 3, "docs_indexed": 76}
    assert data["indexing"] == {
        "total_discovered": 169,
        "indexed": 76,
        "failed": 2,
        "pending": 91,
    }
    assert data["embeddings_available"] is True
    assert data["services"] == {"solr": "up", "redis": "up", "rabbitmq": "up", "embeddings": "up"}


@patch("main._embeddings_available")
@patch("main._tcp_check")
@patch("main._get_indexing_status")
@patch("main._get_solr_status")
def test_status_endpoint_slash_alias(
    mock_solr_status: MagicMock,
    mock_indexing: MagicMock,
    mock_tcp: MagicMock,
    mock_embeddings_available: MagicMock,
) -> None:
    """/v1/status/ (with trailing slash) must also return 200."""
    mock_solr_status.return_value = {"status": "ok", "nodes": 3, "docs_indexed": 0}
    mock_indexing.return_value = {
        "total_discovered": 0,
        "indexed": 0,
        "failed": 0,
        "pending": 0,
    }
    mock_tcp.return_value = True
    mock_embeddings_available.return_value = True

    client = get_client()
    response = client.get("/v1/status/")

    assert response.status_code == 200


@patch("main._embeddings_available")
@patch("main._tcp_check")
@patch("main._get_indexing_status")
@patch("main._get_solr_status")
def test_status_services_down_when_tcp_fails(
    mock_solr_status: MagicMock,
    mock_indexing: MagicMock,
    mock_tcp: MagicMock,
    mock_embeddings_available: MagicMock,
) -> None:
    """Services must report 'down' when TCP check fails."""
    mock_solr_status.return_value = {"status": "error", "nodes": 0, "docs_indexed": 0}
    mock_indexing.return_value = {
        "total_discovered": 0,
        "indexed": 0,
        "failed": 0,
        "pending": 0,
    }
    mock_tcp.return_value = False
    mock_embeddings_available.return_value = False

    client = get_client()
    response = client.get("/v1/status")

    assert response.status_code == 200
    data = response.json()
    assert data["embeddings_available"] is False
    assert data["services"]["solr"] == "down"
    assert data["services"]["redis"] == "down"
    assert data["services"]["rabbitmq"] == "down"
    assert data["services"]["embeddings"] == "down"


def _container_by_name(containers: list[dict[str, str]], name: str) -> dict[str, str]:
    return next(container for container in containers if container["name"] == name)


@patch("main._tcp_check", return_value=True)
@patch("main.requests.get")
def test_admin_containers_endpoint_happy_path(
    mock_requests_get: MagicMock,
    _mock_tcp: MagicMock,
) -> None:
    """GET /v1/admin/containers returns all services with shared build metadata and health."""

    def side_effect(url: str, *args: object, **kwargs: object) -> MagicMock:
        response = MagicMock()
        response.raise_for_status = MagicMock()
        if url.endswith("/admin/collections"):
            response.json.return_value = {
                "cluster": {
                    "live_nodes": ["node1", "node2", "node3"],
                    "collections": {
                        "books": {
                            "shards": {
                                "shard1": {"replicas": {"replica1": {"index": {"numDocs": 76}}}}
                            }
                        }
                    },
                }
            }
            return response
        if url.endswith("/version") and "embeddings-server" in url:
            response.json.return_value = {
                "service": "embeddings-server",
                "version": "0.7.0",
                "commit": "abc1234",
                "built": "2026-03-15T00:00:00Z",
            }
            return response
        raise AssertionError(f"Unexpected URL {url}")

    mock_requests_get.side_effect = side_effect

    client = get_client()
    response = client.get("/v1/admin/containers")

    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 10
    assert data["healthy"] == 8
    assert data["last_updated"].endswith("Z")

    solr_search = _container_by_name(data["containers"], "solr-search")
    assert solr_search == {
        "name": "solr-search",
        "status": "up",
        "type": "service",
        "version": settings.version,
        "commit": settings.commit,
    }

    embeddings = _container_by_name(data["containers"], "embeddings-server")
    assert embeddings == {
        "name": "embeddings-server",
        "status": "up",
        "type": "service",
        "version": "0.7.0",
        "commit": "abc1234",
    }

    assert _container_by_name(data["containers"], "streamlit-admin") == {
        "name": "streamlit-admin",
        "status": "up",
        "type": "service",
        "version": settings.version,
        "commit": settings.commit,
    }
    assert _container_by_name(data["containers"], "aithena-ui") == {
        "name": "aithena-ui",
        "status": "up",
        "type": "service",
        "version": settings.version,
        "commit": settings.commit,
    }
    assert _container_by_name(data["containers"], "document-indexer") == {
        "name": "document-indexer",
        "status": "unknown",
        "type": "worker",
        "version": settings.version,
        "commit": settings.commit,
    }
    assert _container_by_name(data["containers"], "document-lister") == {
        "name": "document-lister",
        "status": "unknown",
        "type": "worker",
        "version": settings.version,
        "commit": settings.commit,
    }
    assert _container_by_name(data["containers"], "solr") == {
        "name": "solr",
        "status": "up",
        "type": "infrastructure",
        "version": "unknown",
        "commit": "unknown",
    }
    assert _container_by_name(data["containers"], "redis")["status"] == "up"
    assert _container_by_name(data["containers"], "rabbitmq")["status"] == "up"
    assert _container_by_name(data["containers"], "nginx")["status"] == "up"


@patch("main.requests.get")
def test_admin_containers_endpoint_degraded_path(mock_requests_get: MagicMock) -> None:
    """GET /v1/admin/containers marks failed checks down while workers remain unknown."""

    def requests_side_effect(url: str, *args: object, **kwargs: object) -> MagicMock:
        if url.endswith("/admin/collections"):
            raise Exception("solr unavailable")
        if url.endswith("/version") and "embeddings-server" in url:
            raise Exception("embeddings unavailable")
        raise AssertionError(f"Unexpected URL {url}")

    def tcp_side_effect(host: str, port: int, timeout: float = 2.0) -> bool:
        host_statuses = {
            "streamlit-admin": False,
            settings.redis_host: True,
            settings.rabbitmq_host: False,
            "aithena-ui": True,
            "nginx": True,
            urlparse(settings.solr_url).hostname or settings.solr_url: False,
        }
        return host_statuses[host]

    mock_requests_get.side_effect = requests_side_effect

    with patch("main._tcp_check", side_effect=tcp_side_effect):
        client = get_client()
        response = client.get("/v1/admin/containers/")

    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 10
    assert data["healthy"] == 4
    assert _container_by_name(data["containers"], "embeddings-server") == {
        "name": "embeddings-server",
        "status": "down",
        "type": "service",
        "version": "unknown",
        "commit": "unknown",
    }
    assert _container_by_name(data["containers"], "streamlit-admin")["status"] == "down"
    assert _container_by_name(data["containers"], "solr")["status"] == "down"
    assert _container_by_name(data["containers"], "rabbitmq")["status"] == "down"
    assert _container_by_name(data["containers"], "document-indexer")["status"] == "unknown"
    assert _container_by_name(data["containers"], "document-lister")["status"] == "unknown"


def test_get_solr_status_on_connection_error() -> None:
    """_get_solr_status must return error status when Solr is unreachable."""
    from main import _get_solr_status

    with patch("main.requests.get", side_effect=Exception("connection refused")):
        result = _get_solr_status("http://solr:8983/solr")

    assert result["status"] == "error"
    assert result["nodes"] == 0
    assert result["docs_indexed"] == 0


def test_get_solr_status_parses_cluster_response() -> None:
    """_get_solr_status must extract live node count and sum doc counts across shards."""
    from main import _get_solr_status

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "cluster": {
            "live_nodes": ["node1", "node2", "node3"],
            "collections": {
                "books": {
                    "shards": {
                        "shard1": {
                            "replicas": {
                                "replica1": {"index": {"numDocs": 40}},
                                "replica2": {"index": {"numDocs": 40}},
                            }
                        },
                        "shard2": {
                            "replicas": {
                                "replica3": {"index": {"numDocs": 36}},
                            }
                        },
                    }
                }
            },
        }
    }

    with patch("main.requests.get", return_value=mock_response):
        result = _get_solr_status("http://solr:8983/solr")

    assert result["status"] == "ok"
    assert result["nodes"] == 3
    assert result["docs_indexed"] == 76  # 40 (shard1 first replica) + 36 (shard2)


def test_get_solr_status_degraded_with_fewer_nodes() -> None:
    """_get_solr_status must return 'degraded' with fewer than 3 live nodes."""
    from main import _get_solr_status

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "cluster": {
            "live_nodes": ["node1"],
            "collections": {},
        }
    }

    with patch("main.requests.get", return_value=mock_response):
        result = _get_solr_status("http://solr:8983/solr")

    assert result["status"] == "degraded"
    assert result["nodes"] == 1


def test_get_indexing_status_counts_states() -> None:
    """_get_indexing_status must tally text_indexed, failed, and pending states."""
    from main import _get_indexing_status

    mock_redis = MagicMock()
    mock_redis.scan_iter.return_value = ["doc:1", "doc:2", "doc:3", "doc:4", "doc:5"]
    mock_redis.mget.return_value = [
        "text_indexed",
        "text_indexed",
        "failed",
        "processing",
        None,
    ]

    with (
        patch("main.redis_lib.Redis", return_value=mock_redis),
        patch("main._get_redis_pool", return_value=MagicMock()),
    ):
        result = _get_indexing_status("doc:*")

    assert result["total_discovered"] == 5
    assert result["indexed"] == 2
    assert result["failed"] == 1
    assert result["pending"] == 2


def test_get_indexing_status_on_redis_error() -> None:
    """_get_indexing_status must return zeros when Redis is unreachable."""
    from main import _get_indexing_status

    with patch("main._get_redis_pool", side_effect=Exception("connection refused")):
        result = _get_indexing_status("doc:*")

    assert result == {"total_discovered": 0, "indexed": 0, "failed": 0, "pending": 0}


def test_tcp_check_success() -> None:
    """_tcp_check must return True for an open TCP port."""
    from main import _tcp_check

    mock_sock = MagicMock()
    mock_sock.__enter__ = MagicMock(return_value=mock_sock)
    mock_sock.__exit__ = MagicMock(return_value=False)

    with patch("main.socket.create_connection", return_value=mock_sock):
        assert _tcp_check("localhost", 6379) is True


def test_tcp_check_failure() -> None:
    """_tcp_check must return False when connection is refused."""
    from main import _tcp_check

    with patch("main.socket.create_connection", side_effect=OSError("refused")):
        assert _tcp_check("localhost", 6379) is False
