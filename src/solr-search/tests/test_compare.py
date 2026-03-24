"""Tests for the /v1/search/compare endpoint (P2-3: side-by-side comparison)."""

from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("AUTH_DB_PATH", "/tmp/test-auth.db")  # noqa: S108
os.environ.setdefault("AUTH_JWT_SECRET", "test-auth-secret")
os.environ.setdefault("AUTH_JWT_TTL", "24h")
os.environ.setdefault("AUTH_COOKIE_NAME", "aithena_auth")

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from config import settings  # noqa: E402
from main import _compute_overlap_metrics  # noqa: E402
from tests.auth_helpers import create_authenticated_client  # noqa: E402


def get_client() -> TestClient:
    return create_authenticated_client()


def _solr_payload(docs: list[dict] | None = None) -> dict:
    return {
        "response": {"numFound": len(docs or []), "docs": docs or []},
        "highlighting": {},
        "facet_counts": {"facet_fields": {}},
    }


def _make_doc(doc_id: str = "doc1", title: str = "Test Book", score: float = 5.0) -> dict:
    return {
        "id": doc_id,
        "title_s": title,
        "author_s": "Author",
        "year_i": 2024,
        "category_s": "Test",
        "language_detected_s": "en",
        "file_path_s": "test/book.pdf",
        "folder_path_s": "test",
        "page_count_i": 100,
        "file_size_l": 1024,
        "score": score,
    }


def _copy_settings(mock_settings):
    """Copy real settings attributes onto a mock, silently skipping failures."""
    for attr in dir(settings):
        if not attr.startswith("_"):
            with contextlib.suppress(AttributeError, TypeError):
                object.__setattr__(mock_settings, attr, getattr(settings, attr))


# ---------------------------------------------------------------------------
# _compute_overlap_metrics unit tests
# ---------------------------------------------------------------------------


class TestComputeOverlapMetrics:
    def test_full_overlap(self) -> None:
        results = [{"id": f"doc{i}"} for i in range(10)]
        metrics = _compute_overlap_metrics(results, results)
        assert metrics["overlap_at_10"] == 1.0
        assert metrics["baseline_only"] == []
        assert metrics["candidate_only"] == []

    def test_no_overlap(self) -> None:
        baseline = [{"id": f"base{i}"} for i in range(10)]
        candidate = [{"id": f"cand{i}"} for i in range(10)]
        metrics = _compute_overlap_metrics(baseline, candidate)
        assert metrics["overlap_at_10"] == 0.0
        assert len(metrics["baseline_only"]) == 10
        assert len(metrics["candidate_only"]) == 10

    def test_partial_overlap(self) -> None:
        baseline = [{"id": f"doc{i}"} for i in range(10)]
        candidate = [{"id": f"doc{i}"} for i in range(5, 15)]
        metrics = _compute_overlap_metrics(baseline, candidate)
        assert metrics["overlap_at_10"] == 0.5
        assert metrics["baseline_only"] == [f"doc{i}" for i in range(5)]
        assert metrics["candidate_only"] == [f"doc{i}" for i in range(10, 15)]

    def test_respects_top_n(self) -> None:
        baseline = [{"id": f"doc{i}"} for i in range(20)]
        candidate = [{"id": f"doc{i}"} for i in range(20)]
        metrics = _compute_overlap_metrics(baseline, candidate, top_n=5)
        assert metrics["overlap_at_10"] == 1.0

    def test_empty_results(self) -> None:
        metrics = _compute_overlap_metrics([], [])
        assert metrics["overlap_at_10"] == 0.0
        assert metrics["baseline_only"] == []
        assert metrics["candidate_only"] == []

    def test_one_side_empty(self) -> None:
        results = [{"id": f"doc{i}"} for i in range(5)]
        metrics = _compute_overlap_metrics(results, [])
        assert metrics["overlap_at_10"] == 0.0
        assert len(metrics["baseline_only"]) == 5
        assert metrics["candidate_only"] == []

    def test_fewer_than_10_results(self) -> None:
        baseline = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        candidate = [{"id": "b"}, {"id": "c"}, {"id": "d"}]
        metrics = _compute_overlap_metrics(baseline, candidate)
        assert metrics["overlap_at_10"] == round(2 / 3, 4)
        assert metrics["baseline_only"] == ["a"]
        assert metrics["candidate_only"] == ["d"]

    def test_preserves_order_in_only_lists(self) -> None:
        baseline = [{"id": "x1"}, {"id": "shared"}, {"id": "x2"}]
        candidate = [{"id": "y1"}, {"id": "shared"}, {"id": "y2"}]
        metrics = _compute_overlap_metrics(baseline, candidate)
        assert metrics["baseline_only"] == ["x1", "x2"]
        assert metrics["candidate_only"] == ["y1", "y2"]


# ---------------------------------------------------------------------------
# /v1/search/compare endpoint tests
# ---------------------------------------------------------------------------


class TestSearchCompareEndpoint:
    """Integration tests for GET /v1/search/compare."""

    @patch("main.query_solr")
    @patch("main.settings")
    def test_keyword_compare_returns_both_collections(self, mock_settings, mock_solr) -> None:
        _copy_settings(mock_settings)
        object.__setattr__(mock_settings, "comparison_baseline_collection", "books")
        object.__setattr__(mock_settings, "comparison_candidate_collection", "books_e5base")
        object.__setattr__(mock_settings, "allowed_collections", frozenset({"books", "books_e5base"}))

        baseline_docs = [_make_doc("b1", "Baseline Book")]
        candidate_docs = [_make_doc("c1", "Candidate Book")]

        def solr_side_effect(params, *, collection=None):
            if collection == "books_e5base":
                return _solr_payload(candidate_docs)
            return _solr_payload(baseline_docs)

        mock_solr.side_effect = solr_side_effect

        client = get_client()
        resp = client.get("/v1/search/compare", params={"q": "test", "mode": "keyword"})
        assert resp.status_code == 200

        data = resp.json()
        assert data["query"] == "test"
        assert data["mode"] == "keyword"
        assert data["baseline"]["collection"] == "books"
        assert data["candidate"]["collection"] == "books_e5base"
        assert len(data["baseline"]["results"]) == 1
        assert len(data["candidate"]["results"]) == 1
        assert data["baseline"]["results"][0]["id"] == "b1"
        assert data["candidate"]["results"][0]["id"] == "c1"
        assert "latency_ms" in data["baseline"]
        assert "latency_ms" in data["candidate"]
        assert "metrics" in data
        assert "overlap_at_10" in data["metrics"]

    @patch("main.query_solr")
    @patch("main.settings")
    def test_compare_overlap_metrics_computed(self, mock_settings, mock_solr) -> None:
        _copy_settings(mock_settings)
        object.__setattr__(mock_settings, "comparison_baseline_collection", "books")
        object.__setattr__(mock_settings, "comparison_candidate_collection", "books_e5base")
        object.__setattr__(mock_settings, "allowed_collections", frozenset({"books", "books_e5base"}))

        shared_docs = [_make_doc(f"shared{i}") for i in range(6)]
        baseline_only = [_make_doc(f"base{i}") for i in range(4)]
        candidate_only = [_make_doc(f"cand{i}") for i in range(4)]

        def solr_side_effect(params, *, collection=None):
            if collection == "books_e5base":
                return _solr_payload(shared_docs + candidate_only)
            return _solr_payload(shared_docs + baseline_only)

        mock_solr.side_effect = solr_side_effect

        client = get_client()
        resp = client.get("/v1/search/compare", params={"q": "overlap", "mode": "keyword"})
        assert resp.status_code == 200

        metrics = resp.json()["metrics"]
        assert metrics["overlap_at_10"] == 0.6
        assert len(metrics["baseline_only"]) == 4
        assert len(metrics["candidate_only"]) == 4

    @patch("main.query_solr")
    @patch("main.settings")
    def test_compare_invalid_mode_returns_400(self, mock_settings, mock_solr) -> None:
        _copy_settings(mock_settings)

        client = get_client()
        resp = client.get("/v1/search/compare", params={"q": "test", "mode": "invalid"})
        assert resp.status_code == 400
        assert "Invalid search mode" in resp.json()["detail"]

    @patch("main.query_solr")
    @patch("main.settings")
    def test_compare_with_filters(self, mock_settings, mock_solr) -> None:
        _copy_settings(mock_settings)
        object.__setattr__(mock_settings, "comparison_baseline_collection", "books")
        object.__setattr__(mock_settings, "comparison_candidate_collection", "books_e5base")
        object.__setattr__(mock_settings, "allowed_collections", frozenset({"books", "books_e5base"}))

        mock_solr.return_value = _solr_payload([_make_doc("f1")])

        client = get_client()
        resp = client.get(
            "/v1/search/compare",
            params={"q": "test", "mode": "keyword", "fq_author": "Tolkien", "fq_year": "1954"},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["baseline"]["total"] == 1
        assert data["candidate"]["total"] == 1

    @patch("main.query_solr")
    @patch("main._fetch_embedding")
    @patch("main.settings")
    def test_compare_semantic_mode(self, mock_settings, mock_embed, mock_solr) -> None:
        _copy_settings(mock_settings)
        object.__setattr__(mock_settings, "comparison_baseline_collection", "books")
        object.__setattr__(mock_settings, "comparison_candidate_collection", "books_e5base")
        object.__setattr__(mock_settings, "allowed_collections", frozenset({"books", "books_e5base"}))
        object.__setattr__(mock_settings, "e5_collections", frozenset({"books_e5base"}))

        mock_embed.return_value = [0.1] * 512

        knn_payload = {
            "response": {"numFound": 2, "docs": [_make_doc("s1"), _make_doc("s2")]},
        }
        mock_solr.return_value = knn_payload

        client = get_client()
        resp = client.get("/v1/search/compare", params={"q": "neural search", "mode": "semantic"})
        assert resp.status_code == 200

        data = resp.json()
        assert data["mode"] == "semantic"
        assert len(data["baseline"]["results"]) == 2
        assert len(data["candidate"]["results"]) == 2

    @patch("main.query_solr")
    @patch("main.settings")
    def test_compare_empty_results(self, mock_settings, mock_solr) -> None:
        _copy_settings(mock_settings)
        object.__setattr__(mock_settings, "comparison_baseline_collection", "books")
        object.__setattr__(mock_settings, "comparison_candidate_collection", "books_e5base")
        object.__setattr__(mock_settings, "allowed_collections", frozenset({"books", "books_e5base"}))

        mock_solr.return_value = _solr_payload([])

        client = get_client()
        resp = client.get("/v1/search/compare", params={"q": "nonexistent", "mode": "keyword"})
        assert resp.status_code == 200

        data = resp.json()
        assert data["baseline"]["total"] == 0
        assert data["candidate"]["total"] == 0
        assert data["metrics"]["overlap_at_10"] == 0.0

    @patch("main.query_solr")
    @patch("main.settings")
    def test_compare_respects_limit_parameter(self, mock_settings, mock_solr) -> None:
        _copy_settings(mock_settings)
        object.__setattr__(mock_settings, "comparison_baseline_collection", "books")
        object.__setattr__(mock_settings, "comparison_candidate_collection", "books_e5base")
        object.__setattr__(mock_settings, "allowed_collections", frozenset({"books", "books_e5base"}))

        docs = [_make_doc(f"doc{i}") for i in range(5)]
        mock_solr.return_value = _solr_payload(docs)

        client = get_client()
        resp = client.get("/v1/search/compare", params={"q": "test", "mode": "keyword", "limit": "5"})
        assert resp.status_code == 200

    @patch("main.query_solr")
    @patch("main.settings")
    def test_compare_latency_is_numeric(self, mock_settings, mock_solr) -> None:
        _copy_settings(mock_settings)
        object.__setattr__(mock_settings, "comparison_baseline_collection", "books")
        object.__setattr__(mock_settings, "comparison_candidate_collection", "books_e5base")
        object.__setattr__(mock_settings, "allowed_collections", frozenset({"books", "books_e5base"}))

        mock_solr.return_value = _solr_payload([_make_doc()])

        client = get_client()
        resp = client.get("/v1/search/compare", params={"q": "test", "mode": "keyword"})
        data = resp.json()
        assert isinstance(data["baseline"]["latency_ms"], (int, float))
        assert isinstance(data["candidate"]["latency_ms"], (int, float))
        assert data["baseline"]["latency_ms"] >= 0
        assert data["candidate"]["latency_ms"] >= 0

    @patch("main.query_solr")
    @patch("main.settings")
    def test_compare_not_in_openapi_schema(self, mock_settings, mock_solr) -> None:
        """The compare endpoint should be internal (include_in_schema=False)."""
        from main import app

        openapi = app.openapi()
        paths = openapi.get("paths", {})
        assert "/v1/search/compare" not in paths

    @patch("main.query_solr")
    @patch("main._fetch_embedding")
    @patch("main.settings")
    def test_compare_hybrid_mode(self, mock_settings, mock_embed, mock_solr) -> None:
        _copy_settings(mock_settings)
        object.__setattr__(mock_settings, "comparison_baseline_collection", "books")
        object.__setattr__(mock_settings, "comparison_candidate_collection", "books_e5base")
        object.__setattr__(mock_settings, "allowed_collections", frozenset({"books", "books_e5base"}))
        object.__setattr__(mock_settings, "e5_collections", frozenset({"books_e5base"}))

        mock_embed.return_value = [0.1] * 512

        docs = [_make_doc("h1"), _make_doc("h2")]
        mock_solr.return_value = {
            "response": {"numFound": 2, "docs": docs},
            "highlighting": {},
            "facet_counts": {"facet_fields": {}},
        }

        client = get_client()
        resp = client.get("/v1/search/compare", params={"q": "hybrid test", "mode": "hybrid"})
        assert resp.status_code == 200

        data = resp.json()
        assert data["mode"] == "hybrid"
        assert "baseline" in data
        assert "candidate" in data


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


class TestComparisonConfig:
    def test_default_baseline_collection(self) -> None:
        assert settings.comparison_baseline_collection == "books"

    def test_default_candidate_collection(self) -> None:
        assert settings.comparison_candidate_collection == "books"

    @patch.dict(os.environ, {
        "COMPARISON_BASELINE_COLLECTION": "custom_baseline",
        "COMPARISON_CANDIDATE_COLLECTION": "custom_candidate",
    })
    def test_custom_collections_from_env(self) -> None:
        from config import Settings

        custom = Settings(
            title="test",
            version="test",
            commit="test",
            built="test",
            port=8080,
            solr_url="http://localhost:8983/solr",
            solr_collection="books",
            base_path=Path("/tmp"),  # noqa: S108
            request_timeout=30,
            default_page_size=20,
            max_page_size=100,
            facet_limit=25,
            cors_origins=[],
            allow_credentials=False,
            document_url_base=None,
            embeddings_url="http://localhost:8080/v1/embeddings/",
            embeddings_timeout=120,
            default_search_mode="keyword",
            rrf_k=60,
            knn_field="embedding_v",
            book_embedding_field="embedding_v",
            redis_host="redis",
            redis_port=6379,
            redis_key_pattern="doc:*",
            redis_queue_name="shortembeddings",
            rabbitmq_host="rabbitmq",
            rabbitmq_port=5672,
            rabbitmq_user="",
            rabbitmq_pass="",
            upload_dir=Path("/tmp/uploads"),  # noqa: S108
            max_upload_size_mb=50,
            rabbitmq_queue_name="shortembeddings",
            auth_db_path=Path("/tmp/auth.db"),  # noqa: S108
            auth_jwt_secret="test",
            auth_jwt_ttl_seconds=86400,
            auth_cookie_name="aithena_auth",
            cb_redis_failure_threshold=5,
            cb_redis_recovery_timeout=30,
            cb_solr_failure_threshold=5,
            cb_solr_recovery_timeout=30,
            cb_embeddings_failure_threshold=3,
            cb_embeddings_recovery_timeout=30,
            admin_api_key=None,
            rate_limit_requests_per_minute=100,
            rabbitmq_management_port=15672,
            zookeeper_hosts="zoo1:2181",
            auth_default_admin_username="admin",
            auth_default_admin_password=None,
            collections_db_path=Path("/tmp/collections.db"),  # noqa: S108
            collections_note_max_length=1000,
            allowed_collections=frozenset({"books"}),
            default_collection="books",
            e5_collections=frozenset(),
            collection_embeddings_urls=(),
            comparison_baseline_collection="custom_baseline",
            comparison_candidate_collection="custom_candidate",
        )
        assert custom.comparison_baseline_collection == "custom_baseline"
        assert custom.comparison_candidate_collection == "custom_candidate"


# ---------------------------------------------------------------------------
# Concurrent execution tests
# ---------------------------------------------------------------------------


class TestCompareParallelExecution:
    @patch("main.query_solr")
    @patch("main.settings")
    def test_both_collections_queried(self, mock_settings, mock_solr) -> None:
        """Verify both collections are queried (via the Solr mock call args)."""
        _copy_settings(mock_settings)
        object.__setattr__(mock_settings, "comparison_baseline_collection", "books")
        object.__setattr__(mock_settings, "comparison_candidate_collection", "books_e5base")
        object.__setattr__(mock_settings, "allowed_collections", frozenset({"books", "books_e5base"}))

        mock_solr.return_value = _solr_payload([_make_doc()])

        client = get_client()
        resp = client.get("/v1/search/compare", params={"q": "test", "mode": "keyword"})
        assert resp.status_code == 200

        collections_called = [
            call.kwargs.get("collection") for call in mock_solr.call_args_list
        ]
        assert "books" in collections_called
        assert "books_e5base" in collections_called


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestCompareEdgeCases:
    @patch("main.query_solr")
    @patch("main.settings")
    def test_same_collection_for_both(self, mock_settings, mock_solr) -> None:
        """When both baseline and candidate are the same, results should match."""
        _copy_settings(mock_settings)
        object.__setattr__(mock_settings, "comparison_baseline_collection", "books")
        object.__setattr__(mock_settings, "comparison_candidate_collection", "books")
        object.__setattr__(mock_settings, "allowed_collections", frozenset({"books"}))

        docs = [_make_doc("x1"), _make_doc("x2")]
        mock_solr.return_value = _solr_payload(docs)

        client = get_client()
        resp = client.get("/v1/search/compare", params={"q": "test", "mode": "keyword"})
        assert resp.status_code == 200

        data = resp.json()
        assert data["metrics"]["overlap_at_10"] == 1.0

    @patch("main.query_solr")
    @patch("main.settings")
    def test_compare_with_sort_parameter(self, mock_settings, mock_solr) -> None:
        _copy_settings(mock_settings)
        object.__setattr__(mock_settings, "comparison_baseline_collection", "books")
        object.__setattr__(mock_settings, "comparison_candidate_collection", "books_e5base")
        object.__setattr__(mock_settings, "allowed_collections", frozenset({"books", "books_e5base"}))

        mock_solr.return_value = _solr_payload([_make_doc()])

        client = get_client()
        resp = client.get(
            "/v1/search/compare",
            params={"q": "test", "mode": "keyword", "sort": "year_i desc"},
        )
        assert resp.status_code == 200

    @patch("main.query_solr")
    @patch("main.settings")
    def test_compare_default_query(self, mock_settings, mock_solr) -> None:
        """Empty query should work for keyword mode (defaults to *:*)."""
        _copy_settings(mock_settings)
        object.__setattr__(mock_settings, "comparison_baseline_collection", "books")
        object.__setattr__(mock_settings, "comparison_candidate_collection", "books_e5base")
        object.__setattr__(mock_settings, "allowed_collections", frozenset({"books", "books_e5base"}))

        mock_solr.return_value = _solr_payload([])

        client = get_client()
        resp = client.get("/v1/search/compare", params={"mode": "keyword"})
        assert resp.status_code == 200
        assert resp.json()["query"] == ""
