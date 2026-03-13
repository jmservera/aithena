"""
Tests for the qdrant-search service search modes.

Covers:
- Keyword (Solr BM25) as the default search mode
- Semantic-only (Qdrant vector) search
- Hybrid Reciprocal Rank Fusion combining both legs
- Normalised SearchResult / SearchResponse payload shapes
"""
import sys
import os
import types
import pytest

# ---------------------------------------------------------------------------
# Stub out heavy dependencies before importing main
# ---------------------------------------------------------------------------

# Stub qdrant_client so no real Qdrant connection is attempted at import time
qdrant_stub = types.ModuleType("qdrant_client")
qdrant_stub.models = types.ModuleType("qdrant_client.models")


class _FakeQdrantClient:
    def __init__(self, *args, **kwargs):
        pass

    def search(self, *args, **kwargs):
        return []


qdrant_stub.QdrantClient = _FakeQdrantClient
sys.modules.setdefault("qdrant_client", qdrant_stub)
sys.modules.setdefault("qdrant_client.models", qdrant_stub.models)

# Stub fastapi.staticfiles so the static directory does not need to exist
import fastapi.staticfiles as _sm


class _DummyStaticFiles:
    def __init__(self, *args, **kwargs):
        pass


_sm.StaticFiles = _DummyStaticFiles  # type: ignore[assignment]

# Set minimal env vars so config does not require real services
os.environ.setdefault("SOLR_HOST", "localhost")
os.environ.setdefault("SOLR_PORT", "8983")
os.environ.setdefault("SOLR_COLLECTION", "books")
os.environ.setdefault("QDRANT_HOST", "localhost")
os.environ.setdefault("QDRANT_PORT", "6333")
os.environ.setdefault("EMBEDDINGS_HOST", "localhost")
os.environ.setdefault("EMBEDDINGS_PORT", "8085")

# Add service root to sys.path so `from config import *` works
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import main as svc  # noqa: E402  (import after stubs)
from main import (  # noqa: E402
    SearchMode,
    SearchResult,
    SearchResponse,
    _reciprocal_rank_fusion,
    _solr_keyword_search,
    _qdrant_semantic_search,
    _hybrid_search,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(doc_id: str, score: float, title: str = "") -> SearchResult:
    return SearchResult(id=doc_id, score=score, title=title)


def _solr_response(docs: list[dict], total: int | None = None, hl: dict | None = None):
    """Build a minimal Solr JSON response body."""
    return {
        "responseHeader": {"status": 0},
        "response": {
            "numFound": total if total is not None else len(docs),
            "docs": docs,
        },
        "highlighting": hl or {},
        "facet_counts": {"facet_fields": {}},
    }


def _make_solr_session(response_body: dict):
    """Return a fake aiohttp.ClientSession class that responds to GET with *response_body*."""
    import json as _json

    class _FakeResp:
        status = 200

        async def json(self, *a, **kw):
            return response_body

        async def text(self):
            return _json.dumps(response_body)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

    class _FakeSession:
        def __init__(self, *a, **kw):
            pass

        def get(self, *a, **kw):
            return _FakeResp()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

    return _FakeSession


def _make_embeddings_session():
    """Return a fake aiohttp.ClientSession class that responds to POST with embeddings."""
    embedding_response = {"data": [{"embedding": [0.1] * 512}]}

    class _FakeEmbResp:
        status = 200

        async def json(self, *a, **kw):
            return embedding_response

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

    class _FakeEmbSession:
        def __init__(self, *a, **kw):
            pass

        def post(self, *a, **kw):
            return _FakeEmbResp()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

    return _FakeEmbSession


class _FakeQdrant:
    """Fake Qdrant client that returns two pre-canned hits."""

    class _Hit:
        def __init__(self, id_, score, payload=None):
            self.id = id_
            self.score = score
            self.payload = payload or {}

    def __init__(self, hits=None):
        self._hits = hits or [
            self._Hit("qdrant-hit-1", 0.95, {"title_s": "Semantic Book", "author_s": "Sem Author"}),
            self._Hit("qdrant-hit-2", 0.80, {}),
        ]

    def search(self, *args, **kwargs):
        return self._hits


# ---------------------------------------------------------------------------
# Unit tests — RRF fusion (no I/O)
# ---------------------------------------------------------------------------

class TestReciprocalRankFusion:
    def test_empty_lists_return_empty(self):
        assert _reciprocal_rank_fusion([], []) == []

    def test_keyword_only(self):
        kw = [_make_result("a", 1.0), _make_result("b", 0.5)]
        fused = _reciprocal_rank_fusion(kw, [])
        ids = [r.id for r in fused]
        assert ids == ["a", "b"]

    def test_semantic_only(self):
        sem = [_make_result("x", 0.9), _make_result("y", 0.4)]
        fused = _reciprocal_rank_fusion([], sem)
        ids = [r.id for r in fused]
        assert ids == ["x", "y"]

    def test_overlapping_docs_ranked_higher(self):
        # "common" appears in both lists → gets double RRF contribution
        kw = [_make_result("common", 0.9), _make_result("kw_only", 0.5)]
        sem = [_make_result("common", 0.8), _make_result("sem_only", 0.6)]
        fused = _reciprocal_rank_fusion(kw, sem)
        ids = [r.id for r in fused]
        assert ids[0] == "common", "Doc present in both lists should rank first"

    def test_rrf_scores_sum_contributions(self):
        k = 60
        kw = [_make_result("doc1", 1.0)]
        sem = [_make_result("doc1", 1.0)]
        fused = _reciprocal_rank_fusion(kw, sem, k=k)
        expected = 1 / (k + 1) + 1 / (k + 1)
        assert abs(fused[0].score - expected) < 1e-9

    def test_fused_scores_are_normalised(self):
        kw = [_make_result(f"k{i}", 1.0 - i * 0.1) for i in range(5)]
        sem = [_make_result(f"s{i}", 1.0 - i * 0.1) for i in range(5)]
        fused = _reciprocal_rank_fusion(kw, sem)
        # All fused scores should be positive and in descending order
        scores = [r.score for r in fused]
        assert all(s > 0 for s in scores)
        assert scores == sorted(scores, reverse=True)

    def test_keyword_metadata_preserved(self):
        kw = [SearchResult(id="doc1", score=1.0, title="My Book", author="Author A")]
        fused = _reciprocal_rank_fusion(kw, [])
        assert fused[0].title == "My Book"
        assert fused[0].author == "Author A"

    def test_semantic_metadata_used_when_not_in_keyword(self):
        kw = [_make_result("doc1", 1.0)]
        sem = [
            SearchResult(id="doc2", score=0.9, title="Sem Title", author="Sem Author")
        ]
        fused = _reciprocal_rank_fusion(kw, sem)
        sem_result = next(r for r in fused if r.id == "doc2")
        assert sem_result.title == "Sem Title"

    def test_custom_k_changes_scores(self):
        kw = [_make_result("doc", 1.0)]
        sem = [_make_result("doc", 1.0)]
        fused_k1 = _reciprocal_rank_fusion(kw, sem, k=1)
        fused_k100 = _reciprocal_rank_fusion(kw, sem, k=100)
        # k=1 gives higher RRF scores than k=100
        assert fused_k1[0].score > fused_k100[0].score


# ---------------------------------------------------------------------------
# Integration-style tests — keyword search (mock Solr via aiohttp mock)
# ---------------------------------------------------------------------------

class TestKeywordSearch:
    @pytest.mark.asyncio
    async def test_returns_search_response_shape(self, mock_solr):
        resp = await _solr_keyword_search("catalan history", limit=5)
        assert isinstance(resp, SearchResponse)
        assert resp.mode == SearchMode.keyword
        assert isinstance(resp.results, list)
        assert isinstance(resp.facets, dict)
        assert isinstance(resp.highlights, dict)

    @pytest.mark.asyncio
    async def test_default_mode_is_keyword(self):
        from config import DEFAULT_SEARCH_MODE
        assert DEFAULT_SEARCH_MODE == "keyword"

    @pytest.mark.asyncio
    async def test_result_fields_populated(self, mock_solr):
        resp = await _solr_keyword_search("history", limit=5)
        assert len(resp.results) > 0
        r = resp.results[0]
        assert r.id == "solr-doc-1"
        assert r.title == "Book One"
        assert r.author == "Author A"
        assert r.year == 2020
        assert r.file_path == "amades/book_one.pdf"

    @pytest.mark.asyncio
    async def test_highlights_propagated(self, mock_solr_with_highlights):
        resp = await _solr_keyword_search("history", limit=5)
        assert resp.results[0].highlights == ["...relevant snippet..."]

    @pytest.mark.asyncio
    async def test_total_reflects_numfound(self, mock_solr):
        resp = await _solr_keyword_search("query", limit=5)
        assert resp.total == 42


# ---------------------------------------------------------------------------
# Integration-style tests — semantic search (mock embeddings + Qdrant)
# ---------------------------------------------------------------------------

class TestSemanticSearch:
    @pytest.mark.asyncio
    async def test_returns_search_response_shape(self, mock_semantic):
        resp = await _qdrant_semantic_search("Catalan folklore", limit=5)
        assert isinstance(resp, SearchResponse)
        assert resp.mode == SearchMode.semantic
        assert isinstance(resp.results, list)

    @pytest.mark.asyncio
    async def test_facets_and_highlights_empty(self, mock_semantic):
        resp = await _qdrant_semantic_search("test", limit=5)
        assert resp.facets == {}
        assert resp.highlights == {}

    @pytest.mark.asyncio
    async def test_result_score_from_qdrant(self, mock_semantic):
        resp = await _qdrant_semantic_search("test", limit=5)
        assert len(resp.results) > 0
        assert resp.results[0].score == pytest.approx(0.95)

    @pytest.mark.asyncio
    async def test_result_id_is_string(self, mock_semantic):
        resp = await _qdrant_semantic_search("test", limit=5)
        for r in resp.results:
            assert isinstance(r.id, str)


# ---------------------------------------------------------------------------
# Integration-style tests — hybrid search
# ---------------------------------------------------------------------------

class TestHybridSearch:
    @pytest.mark.asyncio
    async def test_returns_search_response_shape(self, mock_hybrid):
        resp = await _hybrid_search("folklore", limit=5)
        assert isinstance(resp, SearchResponse)
        assert resp.mode == SearchMode.hybrid
        assert isinstance(resp.results, list)

    @pytest.mark.asyncio
    async def test_facets_sourced_from_keyword_leg(self, mock_hybrid):
        resp = await _hybrid_search("folklore", limit=5)
        # Facets come from the Solr keyword leg only
        assert isinstance(resp.facets, dict)

    @pytest.mark.asyncio
    async def test_result_count_limited(self, mock_hybrid):
        resp = await _hybrid_search("folklore", limit=3)
        assert len(resp.results) <= 3

    @pytest.mark.asyncio
    async def test_overlapping_doc_ranked_first(self, mock_hybrid_overlap):
        resp = await _hybrid_search("query", limit=10)
        ids = [r.id for r in resp.results]
        assert ids[0] == "shared-doc"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_solr(monkeypatch):
    """Patch aiohttp.ClientSession so Solr calls return a canned response."""
    import aiohttp

    docs = [
        {
            "id": "solr-doc-1",
            "title_s": "Book One",
            "author_s": "Author A",
            "year_i": 2020,
            "file_path_s": "amades/book_one.pdf",
            "folder_path_s": "amades",
            "category_s": "History",
            "language_detected_s": "ca",
            "score": 1.5,
        }
    ]
    body = _solr_response(docs, total=42)
    monkeypatch.setattr(aiohttp, "ClientSession", _make_solr_session(body))
    yield


@pytest.fixture
def mock_solr_with_highlights(monkeypatch):
    import aiohttp

    docs = [
        {
            "id": "solr-doc-1",
            "title_s": "Book One",
            "author_s": "Author A",
            "year_i": 2020,
            "file_path_s": "amades/book_one.pdf",
            "folder_path_s": "amades",
            "score": 1.0,
        }
    ]
    hl = {"solr-doc-1": {"content": ["...relevant snippet..."]}}
    body = _solr_response(docs, total=1, hl=hl)
    monkeypatch.setattr(aiohttp, "ClientSession", _make_solr_session(body))
    yield


@pytest.fixture
def mock_semantic(monkeypatch):
    """Patch embeddings HTTP call and Qdrant client for semantic search."""
    import aiohttp

    monkeypatch.setattr(aiohttp, "ClientSession", _make_embeddings_session())
    monkeypatch.setattr(svc, "qdrant", _FakeQdrant())
    yield


@pytest.fixture
def mock_hybrid(monkeypatch):
    """Patch both Solr and Qdrant for hybrid search by mocking the sub-functions."""
    # For hybrid, patch the two leg functions directly to avoid aiohttp session conflicts
    async def _fake_kw(query, limit):
        return SearchResponse(
            query=query,
            mode=SearchMode.keyword,
            total=1,
            results=[SearchResult(id="kw-doc-1", score=1.0, title="Keyword Book")],
            facets={"author_s": {"Author A": 1}},
            highlights={},
        )

    async def _fake_sem(query, limit):
        return SearchResponse(
            query=query,
            mode=SearchMode.semantic,
            total=2,
            results=[
                SearchResult(id="qdrant-hit-1", score=0.95, title="Semantic Book"),
                SearchResult(id="qdrant-hit-2", score=0.80),
            ],
            facets={},
            highlights={},
        )

    monkeypatch.setattr(svc, "_solr_keyword_search", _fake_kw)
    monkeypatch.setattr(svc, "_qdrant_semantic_search", _fake_sem)
    yield


@pytest.fixture
def mock_hybrid_overlap(monkeypatch):
    """Hybrid fixture where 'shared-doc' appears in both keyword and semantic legs."""
    async def _fake_kw(query, limit):
        return SearchResponse(
            query=query,
            mode=SearchMode.keyword,
            total=2,
            results=[
                SearchResult(id="shared-doc", score=1.0, title="Shared"),
                SearchResult(id="kw-only", score=0.5, title="KW Only"),
            ],
            facets={},
            highlights={},
        )

    async def _fake_sem(query, limit):
        return SearchResponse(
            query=query,
            mode=SearchMode.semantic,
            total=2,
            results=[
                SearchResult(id="shared-doc", score=0.95),
                SearchResult(id="sem-only", score=0.70),
            ],
            facets={},
            highlights={},
        )

    monkeypatch.setattr(svc, "_solr_keyword_search", _fake_kw)
    monkeypatch.setattr(svc, "_qdrant_semantic_search", _fake_sem)
    yield

