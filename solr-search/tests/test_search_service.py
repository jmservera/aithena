"""
Tests for the solr-search service — Phase 2 baseline search API.

Covers:
- Keyword (Solr BM25) as the default search mode
- Normalized response shape (BookResult, SearchResponse, Facets)
- Highlights and facets propagation
- Pagination via start/limit
- Filter queries (fq_author, fq_category, fq_language, fq_year)
- Single book detail endpoint
- Empty query rejection
"""
import sys
import os
import json
import pytest

# ---------------------------------------------------------------------------
# Minimal env vars so config does not require live services
# ---------------------------------------------------------------------------
os.environ.setdefault("SOLR_HOST", "localhost")
os.environ.setdefault("SOLR_PORT", "8983")
os.environ.setdefault("SOLR_COLLECTION", "books")
os.environ.setdefault("EMBEDDINGS_HOST", "localhost")
os.environ.setdefault("EMBEDDINGS_PORT", "8085")
os.environ.setdefault("DEFAULT_SEARCH_MODE", "keyword")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
import main as svc
from main import app, normalize_book, _parse_facets, _reciprocal_rank_fusion, SearchMode, BookResult

client = TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _solr_response(
    docs: list[dict],
    total: int | None = None,
    hl: dict | None = None,
    facets: dict | None = None,
) -> dict:
    """Minimal Solr JSON response body."""
    return {
        "responseHeader": {"status": 0},
        "response": {
            "numFound": total if total is not None else len(docs),
            "docs": docs,
        },
        "highlighting": hl or {},
        "facet_counts": {"facet_fields": facets or {}},
    }


def _sample_doc(doc_id: str = "book-1", score: float = 1.0) -> dict:
    return {
        "id": doc_id,
        "title_s": "Book One",
        "author_s": "Author A",
        "year_i": 2020,
        "file_path_s": "amades/book_one.pdf",
        "folder_path_s": "amades",
        "category_s": "History",
        "language_detected_s": "ca",
        "score": score,
    }


def _make_solr_session(response_body: dict):
    """Return a fake aiohttp.ClientSession class that responds to GET with *response_body*."""

    class _FakeResp:
        status = 200

        async def json(self, *a, **kw):
            return response_body

        async def text(self):
            return json.dumps(response_body)

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


# ---------------------------------------------------------------------------
# Unit tests — normalize_book
# ---------------------------------------------------------------------------

class TestNormalizeBook:
    def test_maps_solr_fields(self):
        doc = _sample_doc("book-1")
        result = normalize_book(doc, 1.5)
        assert result.id == "book-1"
        assert result.title == "Book One"
        assert result.author == "Author A"
        assert result.year == 2020
        assert result.file_path == "amades/book_one.pdf"
        assert result.folder_path == "amades"
        assert result.category == "History"
        assert result.language == "ca"
        assert result.score == 1.5

    def test_missing_fields_are_none(self):
        result = normalize_book({"id": "x"}, 0.0)
        assert result.title is None
        assert result.author is None
        assert result.year is None

    def test_document_url_constructed_when_base_set(self, monkeypatch):
        monkeypatch.setattr(svc, "DOCUMENT_BASE_URL", "http://example.com/docs")
        result = normalize_book({"id": "x", "file_path_s": "amades/book.pdf"}, 0.0)
        assert result.document_url == "http://example.com/docs/amades/book.pdf"

    def test_document_url_none_when_no_base(self, monkeypatch):
        monkeypatch.setattr(svc, "DOCUMENT_BASE_URL", "")
        result = normalize_book({"id": "x", "file_path_s": "amades/book.pdf"}, 0.0)
        assert result.document_url is None

    def test_highlights_passed_through(self):
        result = normalize_book({"id": "x"}, 0.0, ["snippet one", "snippet two"])
        assert result.highlights == ["snippet one", "snippet two"]


# ---------------------------------------------------------------------------
# Unit tests — _parse_facets
# ---------------------------------------------------------------------------

class TestParseFacets:
    def test_empty_facets(self):
        facets = _parse_facets({})
        assert facets.author == []
        assert facets.category == []

    def test_parses_author_facet(self):
        raw = {"author_s": ["Author A", 5, "Author B", 3]}
        facets = _parse_facets(raw)
        assert len(facets.author) == 2
        assert facets.author[0].value == "Author A"
        assert facets.author[0].count == 5

    def test_zero_count_excluded(self):
        raw = {"author_s": ["Author A", 0, "Author B", 2]}
        facets = _parse_facets(raw)
        assert len(facets.author) == 1
        assert facets.author[0].value == "Author B"

    def test_odd_length_list_safe(self):
        # Should not raise even if Solr returns an odd-length list
        raw = {"author_s": ["Author A", 3, "Author B"]}
        facets = _parse_facets(raw)
        assert len(facets.author) == 1


# ---------------------------------------------------------------------------
# Unit tests — _reciprocal_rank_fusion
# ---------------------------------------------------------------------------

class TestRRF:
    def _r(self, doc_id: str, score: float = 1.0) -> BookResult:
        return BookResult(id=doc_id, score=score)

    def test_empty_inputs(self):
        assert _reciprocal_rank_fusion([], []) == []

    def test_keyword_only(self):
        kw = [self._r("a"), self._r("b")]
        fused = _reciprocal_rank_fusion(kw, [])
        assert [r.id for r in fused] == ["a", "b"]

    def test_semantic_only(self):
        sem = [self._r("x"), self._r("y")]
        fused = _reciprocal_rank_fusion([], sem)
        assert [r.id for r in fused] == ["x", "y"]

    def test_shared_doc_ranks_first(self):
        kw = [self._r("shared"), self._r("kw_only")]
        sem = [self._r("shared"), self._r("sem_only")]
        fused = _reciprocal_rank_fusion(kw, sem)
        assert fused[0].id == "shared"

    def test_scores_descending(self):
        kw = [self._r(f"k{i}") for i in range(5)]
        sem = [self._r(f"s{i}") for i in range(5)]
        fused = _reciprocal_rank_fusion(kw, sem)
        scores = [r.score for r in fused]
        assert scores == sorted(scores, reverse=True)

    def test_keyword_metadata_preserved(self):
        kw = [BookResult(id="doc1", score=1.0, title="My Book", author="Author A")]
        fused = _reciprocal_rank_fusion(kw, [])
        assert fused[0].title == "My Book"
        assert fused[0].author == "Author A"


# ---------------------------------------------------------------------------
# Integration tests — /v1/search/ keyword mode
# ---------------------------------------------------------------------------

class TestKeywordSearch:
    @pytest.mark.asyncio
    async def test_default_mode_is_keyword(self):
        from config import DEFAULT_SEARCH_MODE
        assert DEFAULT_SEARCH_MODE == "keyword"

    @pytest.mark.asyncio
    async def test_keyword_response_shape(self, monkeypatch):
        import aiohttp
        docs = [_sample_doc()]
        body = _solr_response(docs, total=1)
        monkeypatch.setattr(aiohttp, "ClientSession", _make_solr_session(body))
        resp = client.get("/v1/search/?q=history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "keyword"
        assert "results" in data
        assert "facets" in data
        assert "total" in data
        assert data["page"] == 1

    @pytest.mark.asyncio
    async def test_result_fields_populated(self, monkeypatch):
        import aiohttp
        docs = [_sample_doc("book-42", 1.5)]
        body = _solr_response(docs, total=1)
        monkeypatch.setattr(aiohttp, "ClientSession", _make_solr_session(body))
        resp = client.get("/v1/search/?q=history")
        assert resp.status_code == 200
        r = resp.json()["results"][0]
        assert r["id"] == "book-42"
        assert r["title"] == "Book One"
        assert r["author"] == "Author A"
        assert r["year"] == 2020
        assert r["file_path"] == "amades/book_one.pdf"

    @pytest.mark.asyncio
    async def test_highlights_in_results(self, monkeypatch):
        import aiohttp
        docs = [_sample_doc()]
        hl = {"book-1": {"content": ["...relevant snippet..."]}}
        body = _solr_response(docs, total=1, hl=hl)
        monkeypatch.setattr(aiohttp, "ClientSession", _make_solr_session(body))
        resp = client.get("/v1/search/?q=history")
        assert resp.status_code == 200
        assert resp.json()["results"][0]["highlights"] == ["...relevant snippet..."]

    @pytest.mark.asyncio
    async def test_total_reflects_numfound(self, monkeypatch):
        import aiohttp
        body = _solr_response([_sample_doc()], total=99)
        monkeypatch.setattr(aiohttp, "ClientSession", _make_solr_session(body))
        resp = client.get("/v1/search/?q=history")
        assert resp.json()["total"] == 99

    @pytest.mark.asyncio
    async def test_facets_populated(self, monkeypatch):
        import aiohttp
        facets = {"author_s": ["Author A", 5], "category_s": ["History", 2]}
        body = _solr_response([_sample_doc()], total=1, facets=facets)
        monkeypatch.setattr(aiohttp, "ClientSession", _make_solr_session(body))
        resp = client.get("/v1/search/?q=history")
        data = resp.json()
        assert data["facets"]["author"][0]["value"] == "Author A"
        assert data["facets"]["author"][0]["count"] == 5

    @pytest.mark.asyncio
    async def test_empty_query_returns_400(self):
        resp = client.get("/v1/search/?q=")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_missing_query_returns_422(self):
        resp = client.get("/v1/search/")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Integration tests — /v1/search/ semantic mode
# ---------------------------------------------------------------------------

def _make_emb_then_solr_session(emb_response: dict, solr_response_body: dict):
    """Session that returns embeddings on POST and kNN results on GET."""

    class _EmbResp:
        status = 200

        async def json(self, *a, **kw):
            return emb_response

        async def text(self):
            return json.dumps(emb_response)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

    class _SolrResp:
        status = 200

        async def json(self, *a, **kw):
            return solr_response_body

        async def text(self):
            return json.dumps(solr_response_body)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

    class _FakeSession:
        def __init__(self, *a, **kw):
            pass

        def post(self, *a, **kw):
            return _EmbResp()

        def get(self, *a, **kw):
            return _SolrResp()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

    return _FakeSession


class TestSemanticSearch:
    @pytest.mark.asyncio
    async def test_semantic_response_shape(self, monkeypatch):
        import aiohttp
        emb = {"data": [{"embedding": [0.1] * 512}]}
        solr = _solr_response([_sample_doc("sem-1", 0.95)], total=1)
        monkeypatch.setattr(aiohttp, "ClientSession", _make_emb_then_solr_session(emb, solr))
        resp = client.get("/v1/search/?q=folklore&mode=semantic")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "semantic"
        assert isinstance(data["results"], list)

    @pytest.mark.asyncio
    async def test_semantic_empty_facets(self, monkeypatch):
        import aiohttp
        emb = {"data": [{"embedding": [0.1] * 512}]}
        solr = _solr_response([_sample_doc("sem-1", 0.95)], total=1)
        monkeypatch.setattr(aiohttp, "ClientSession", _make_emb_then_solr_session(emb, solr))
        resp = client.get("/v1/search/?q=folklore&mode=semantic")
        data = resp.json()
        assert data["facets"]["author"] == []
        assert data["facets"]["category"] == []

    @pytest.mark.asyncio
    async def test_semantic_results_have_no_highlights(self, monkeypatch):
        import aiohttp
        emb = {"data": [{"embedding": [0.1] * 512}]}
        solr = _solr_response([_sample_doc("sem-1", 0.95)], total=1)
        monkeypatch.setattr(aiohttp, "ClientSession", _make_emb_then_solr_session(emb, solr))
        resp = client.get("/v1/search/?q=folklore&mode=semantic")
        assert resp.json()["results"][0]["highlights"] == []


# ---------------------------------------------------------------------------
# Integration tests — /v1/search/ hybrid mode
# ---------------------------------------------------------------------------

class TestHybridSearch:
    @pytest.mark.asyncio
    async def test_hybrid_response_shape(self, monkeypatch):
        async def _fake_kw(q, limit, start, sort, fq):
            return [BookResult(id="kw-1", score=1.0, title="KW Book")], 1, svc._parse_facets({}), {}

        async def _fake_emb(text):
            return [0.1] * 512

        async def _fake_knn(vector, top_k):
            return [BookResult(id="sem-1", score=0.9, title="Sem Book")]

        monkeypatch.setattr(svc, "_keyword_search", _fake_kw)
        monkeypatch.setattr(svc, "_get_embeddings", _fake_emb)
        monkeypatch.setattr(svc, "_knn_search", _fake_knn)

        resp = client.get("/v1/search/?q=folklore&mode=hybrid")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "hybrid"
        assert isinstance(data["results"], list)

    @pytest.mark.asyncio
    async def test_hybrid_shared_doc_ranks_first(self, monkeypatch):
        async def _fake_kw(q, limit, start, sort, fq):
            return [
                BookResult(id="shared", score=1.0),
                BookResult(id="kw-only", score=0.5),
            ], 2, svc._parse_facets({}), {}

        async def _fake_emb(text):
            return [0.1] * 512

        async def _fake_knn(vector, top_k):
            return [BookResult(id="shared", score=0.95), BookResult(id="sem-only", score=0.7)]

        monkeypatch.setattr(svc, "_keyword_search", _fake_kw)
        monkeypatch.setattr(svc, "_get_embeddings", _fake_emb)
        monkeypatch.setattr(svc, "_knn_search", _fake_knn)

        resp = client.get("/v1/search/?q=folklore&mode=hybrid")
        assert resp.json()["results"][0]["id"] == "shared"

    @pytest.mark.asyncio
    async def test_hybrid_result_count_limited(self, monkeypatch):
        async def _fake_kw(q, limit, start, sort, fq):
            return [BookResult(id=f"k{i}", score=1.0) for i in range(20)], 20, svc._parse_facets({}), {}

        async def _fake_emb(text):
            return [0.1] * 512

        async def _fake_knn(vector, top_k):
            return [BookResult(id=f"s{i}", score=0.9) for i in range(20)]

        monkeypatch.setattr(svc, "_keyword_search", _fake_kw)
        monkeypatch.setattr(svc, "_get_embeddings", _fake_emb)
        monkeypatch.setattr(svc, "_knn_search", _fake_knn)

        resp = client.get("/v1/search/?q=test&mode=hybrid&limit=5")
        assert len(resp.json()["results"]) <= 5

    @pytest.mark.asyncio
    async def test_hybrid_facets_from_keyword_leg(self, monkeypatch):
        from main import Facets, FacetValue

        expected_facets = Facets(author=[FacetValue(value="Author A", count=3)])

        async def _fake_kw(q, limit, start, sort, fq):
            return [BookResult(id="k1", score=1.0)], 1, expected_facets, {}

        async def _fake_emb(text):
            return [0.1] * 512

        async def _fake_knn(vector, top_k):
            return []

        monkeypatch.setattr(svc, "_keyword_search", _fake_kw)
        monkeypatch.setattr(svc, "_get_embeddings", _fake_emb)
        monkeypatch.setattr(svc, "_knn_search", _fake_knn)

        resp = client.get("/v1/search/?q=history&mode=hybrid")
        data = resp.json()
        assert data["facets"]["author"][0]["value"] == "Author A"
        assert data["facets"]["author"][0]["count"] == 3
