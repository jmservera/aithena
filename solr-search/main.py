#!/usr/bin/env python
# encoding: utf-8
"""
solr-search — Aithena Search API (Phase 2 + 3)

Provides a FastAPI service wrapping SolrCloud for the Aithena book library.

Endpoints
---------
GET /v1/search/
    Search with keyword (BM25), semantic (Solr kNN), or hybrid (RRF) mode.
    ?q=<query>
    &mode=keyword|semantic|hybrid  (default: keyword)
    &limit=<int>                   (default: 10)
    &page=<int>                    (default: 1)
    &sort=score|year_i|title_s     (default: score)
    &fq_author=<str>               (filter: author_s)
    &fq_category=<str>             (filter: category_s)
    &fq_language=<str>             (filter: language_detected_s)
    &fq_year=<int>                 (filter: year_i)

GET /v1/books/{book_id}
    Fetch a single book document by Solr id.

GET /v1/books/{book_id}/similar
    Return similar books via Solr kNN on the embedding field.

GET /v1/health
    Liveness check.
"""

import asyncio
from enum import Enum
from typing import Optional

import aiohttp
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import (
    DEFAULT_SEARCH_MODE,
    DOCUMENT_BASE_URL,
    EMBEDDINGS_HOST,
    EMBEDDINGS_PORT,
    EMBEDDINGS_TIMEOUT,
    PORT,
    RRF_K,
    SOLR_COLLECTION,
    SOLR_HOST,
    SOLR_PORT,
    SOLR_VECTOR_FIELD,
    TITLE,
    VERSION,
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title=TITLE, version=VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_SOLR_BASE = f"http://{SOLR_HOST}:{SOLR_PORT}/solr/{SOLR_COLLECTION}"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class SearchMode(str, Enum):
    keyword = "keyword"
    semantic = "semantic"
    hybrid = "hybrid"


class FacetValue(BaseModel):
    value: str
    count: int


class Facets(BaseModel):
    author: list[FacetValue] = Field(default_factory=list)
    category: list[FacetValue] = Field(default_factory=list)
    language: list[FacetValue] = Field(default_factory=list)
    year: list[FacetValue] = Field(default_factory=list)


class BookResult(BaseModel):
    id: str
    score: float = 0.0
    title: Optional[str] = None
    author: Optional[str] = None
    year: Optional[int] = None
    file_path: Optional[str] = None
    folder_path: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = None
    highlights: list[str] = Field(default_factory=list)
    document_url: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    mode: SearchMode
    total: int
    page: int
    limit: int
    results: list[BookResult]
    facets: Facets = Field(default_factory=Facets)


class BookDetail(BookResult):
    page_count: Optional[int] = None
    file_size: Optional[int] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def normalize_book(doc: dict, score: float = 0.0, highlights: list[str] | None = None) -> BookResult:
    """Map a raw Solr document to a normalized BookResult."""
    file_path = doc.get("file_path_s")
    document_url: Optional[str] = None
    if file_path and DOCUMENT_BASE_URL:
        document_url = f"{DOCUMENT_BASE_URL.rstrip('/')}/{file_path}"
    return BookResult(
        id=doc.get("id", ""),
        score=score,
        title=doc.get("title_s"),
        author=doc.get("author_s"),
        year=doc.get("year_i"),
        file_path=file_path,
        folder_path=doc.get("folder_path_s"),
        category=doc.get("category_s"),
        language=doc.get("language_detected_s"),
        highlights=highlights or [],
        document_url=document_url,
    )


def _parse_facets(raw_facets: dict) -> Facets:
    """Convert Solr facet_fields flat list into structured Facets."""

    def _pairs(lst: list) -> list[FacetValue]:
        return [
            FacetValue(value=lst[i], count=lst[i + 1])
            for i in range(0, len(lst) - 1, 2)
            if lst[i + 1] > 0
        ]

    return Facets(
        author=_pairs(raw_facets.get("author_s", [])),
        category=_pairs(raw_facets.get("category_s", [])),
        language=_pairs(raw_facets.get("language_detected_s", [])),
        year=_pairs(raw_facets.get("year_i", [])),
    )


async def _get_embeddings(text: str) -> list[float]:
    """Call the embeddings service and return the embedding vector."""
    client_timeout = aiohttp.ClientTimeout(total=EMBEDDINGS_TIMEOUT)
    async with aiohttp.ClientSession(timeout=client_timeout) as session:
        async with session.post(
            f"http://{EMBEDDINGS_HOST}:{EMBEDDINGS_PORT}/v1/embeddings/",
            json={"input": text},
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise HTTPException(
                    status_code=502,
                    detail=f"Embeddings service error {resp.status}: {body[:200]}",
                )
            data = await resp.json()
    if not data.get("data"):
        raise HTTPException(status_code=502, detail="Embeddings service returned empty data")
    return data["data"][0]["embedding"]


# ---------------------------------------------------------------------------
# Solr queries
# ---------------------------------------------------------------------------


async def _keyword_search(
    q: str,
    limit: int,
    start: int,
    sort: str,
    filter_queries: list[str],
) -> tuple[list[BookResult], int, Facets, dict]:
    """BM25 keyword search via Solr edismax."""
    params = {
        "q": q,
        "defType": "edismax",
        "qf": "title_t^2 author_t^1.5 _text_",
        "rows": limit,
        "start": start,
        "sort": sort,
        "hl": "true",
        "hl.fl": "content",
        "hl.snippets": 2,
        "hl.fragsize": 200,
        "facet": "true",
        "facet.field": ["author_s", "category_s", "language_detected_s", "year_i"],
        "facet.mincount": 1,
        "fl": "id,title_s,author_s,year_i,file_path_s,folder_path_s,category_s,language_detected_s,score",
        "wt": "json",
    }
    if filter_queries:
        params["fq"] = filter_queries

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{_SOLR_BASE}/select", params=params) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise HTTPException(status_code=502, detail=f"Solr error {resp.status}: {body[:200]}")
            data = await resp.json()

    response_body = data.get("response", {})
    raw_docs = response_body.get("docs", [])
    total = response_body.get("numFound", len(raw_docs))
    hl_data: dict = data.get("highlighting", {})
    facets = _parse_facets(data.get("facet_counts", {}).get("facet_fields", {}))

    results = [
        normalize_book(doc, float(doc.get("score", 0.0)), hl_data.get(doc.get("id", ""), {}).get("content", []))
        for doc in raw_docs
    ]
    return results, total, facets, hl_data


async def _knn_search(
    vector: list[float],
    top_k: int,
) -> list[BookResult]:
    """Semantic search via Solr kNN HNSW dense vector query."""
    vector_str = "[" + ",".join(str(v) for v in vector) + "]"
    params = {
        "q": f"{{!knn f={SOLR_VECTOR_FIELD} topK={top_k}}}{vector_str}",
        "rows": top_k,
        "fl": "id,title_s,author_s,year_i,file_path_s,folder_path_s,category_s,language_detected_s,score",
        "wt": "json",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{_SOLR_BASE}/select", params=params) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise HTTPException(status_code=502, detail=f"Solr kNN error {resp.status}: {body[:200]}")
            data = await resp.json()

    raw_docs = data.get("response", {}).get("docs", [])
    return [normalize_book(doc, float(doc.get("score", 0.0))) for doc in raw_docs]


def _reciprocal_rank_fusion(
    keyword_results: list[BookResult],
    semantic_results: list[BookResult],
    k: int = RRF_K,
) -> list[BookResult]:
    """
    Combine keyword and semantic result lists using Reciprocal Rank Fusion (RRF).

    RRF score for a document d across ranked lists is:
        sum_over_lists( 1 / (k + rank(d, list)) )

    where rank is 1-based.  Higher combined score → better rank.
    """
    scores: dict[str, float] = {}
    result_map: dict[str, BookResult] = {}

    for rank, result in enumerate(keyword_results, start=1):
        scores[result.id] = scores.get(result.id, 0.0) + 1.0 / (k + rank)
        result_map[result.id] = result

    for rank, result in enumerate(semantic_results, start=1):
        scores[result.id] = scores.get(result.id, 0.0) + 1.0 / (k + rank)
        if result.id not in result_map:
            result_map[result.id] = result

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [
        BookResult(
            id=result_map[doc_id].id,
            score=rrf_score,
            title=result_map[doc_id].title,
            author=result_map[doc_id].author,
            year=result_map[doc_id].year,
            file_path=result_map[doc_id].file_path,
            folder_path=result_map[doc_id].folder_path,
            category=result_map[doc_id].category,
            language=result_map[doc_id].language,
            highlights=result_map[doc_id].highlights,
            document_url=result_map[doc_id].document_url,
        )
        for doc_id, rrf_score in ranked
    ]


# ---------------------------------------------------------------------------
# Search endpoint
# ---------------------------------------------------------------------------


@app.get("/v1/search/", response_model=SearchResponse)
async def search(
    q: str = Query(..., description="Search query"),
    mode: SearchMode = Query(SearchMode(DEFAULT_SEARCH_MODE), description="Search mode"),
    limit: int = Query(10, ge=1, le=100, description="Results per page"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    sort: str = Query("score desc", description="Sort field and direction"),
    fq_author: Optional[str] = Query(None, description="Filter by author"),
    fq_category: Optional[str] = Query(None, description="Filter by category"),
    fq_language: Optional[str] = Query(None, description="Filter by language"),
    fq_year: Optional[int] = Query(None, description="Filter by publication year"),
):
    """Search for books.

    - **mode=keyword** (default): BM25 full-text search via Solr edismax.
    - **mode=semantic**: Dense vector similarity search via Solr kNN (HNSW).
    - **mode=hybrid**: Reciprocal Rank Fusion of keyword + semantic results.

    Facets and highlights are available in ``keyword`` and ``hybrid`` modes
    (sourced from the Solr BM25 leg).  In ``semantic`` mode facets are empty
    and highlights are empty per-result.  See ``solr/README.md`` for details.
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' must not be empty")

    start = (page - 1) * limit

    # Build filter queries
    filter_queries: list[str] = []
    if fq_author:
        filter_queries.append(f'author_s:"{fq_author}"')
    if fq_category:
        filter_queries.append(f'category_s:"{fq_category}"')
    if fq_language:
        filter_queries.append(f'language_detected_s:"{fq_language}"')
    if fq_year is not None:
        filter_queries.append(f"year_i:{fq_year}")

    if mode == SearchMode.keyword:
        results, total, facets, _ = await _keyword_search(q, limit, start, sort, filter_queries)
        return SearchResponse(
            query=q, mode=mode, total=total, page=page, limit=limit, results=results, facets=facets
        )

    if mode == SearchMode.semantic:
        vector = await _get_embeddings(q)
        results = await _knn_search(vector, limit)
        return SearchResponse(
            query=q, mode=mode, total=len(results), page=1, limit=limit, results=results
        )

    # hybrid: run both in parallel, fuse with RRF
    candidate_limit = max(limit * 2, 20)
    kw_task = asyncio.create_task(_keyword_search(q, candidate_limit, 0, sort, filter_queries))
    emb_task = asyncio.create_task(_get_embeddings(q))
    kw_results, total_kw, facets, _ = await kw_task
    vector = await emb_task
    sem_results = await _knn_search(vector, candidate_limit)

    fused = _reciprocal_rank_fusion(kw_results, sem_results)[:limit]
    return SearchResponse(
        query=q,
        mode=mode,
        total=len(fused),
        page=1,
        limit=limit,
        results=fused,
        # Facets sourced from keyword leg; semantic-only hits have no facet coverage.
        facets=facets,
    )


# ---------------------------------------------------------------------------
# Books endpoints
# ---------------------------------------------------------------------------


@app.get("/v1/books/{book_id}", response_model=BookDetail)
async def get_book(book_id: str):
    """Fetch a single book document by Solr id."""
    params = {
        "q": f'id:"{book_id}"',
        "fl": "id,title_s,author_s,year_i,file_path_s,folder_path_s,category_s,language_detected_s,page_count_i,file_size_l",
        "rows": 1,
        "wt": "json",
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{_SOLR_BASE}/select", params=params) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise HTTPException(status_code=502, detail=f"Solr error {resp.status}: {body[:200]}")
            data = await resp.json()

    docs = data.get("response", {}).get("docs", [])
    if not docs:
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")

    doc = docs[0]
    book = normalize_book(doc)
    return BookDetail(
        **book.model_dump(),
        page_count=doc.get("page_count_i"),
        file_size=doc.get("file_size_l"),
    )


@app.get("/v1/books/{book_id}/similar", response_model=SearchResponse)
async def similar_books(book_id: str, limit: int = Query(5, ge=1, le=20)):
    """Return books similar to the given book using Solr kNN on the embedding field."""
    # Fetch the source book's embedding vector
    params = {
        "q": f'id:"{book_id}"',
        "fl": f"id,{SOLR_VECTOR_FIELD}",
        "rows": 1,
        "wt": "json",
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{_SOLR_BASE}/select", params=params) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise HTTPException(status_code=502, detail=f"Solr error {resp.status}: {body[:200]}")
            data = await resp.json()

    docs = data.get("response", {}).get("docs", [])
    if not docs:
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' not found")

    vector = docs[0].get(SOLR_VECTOR_FIELD)
    if not vector:
        raise HTTPException(status_code=404, detail=f"Book '{book_id}' has no embedding vector")

    # Run kNN excluding the source document
    vector_str = "[" + ",".join(str(v) for v in vector) + "]"
    knn_params = {
        "q": f"{{!knn f={SOLR_VECTOR_FIELD} topK={limit + 1}}}{vector_str}",
        "fq": f'-id:"{book_id}"',
        "rows": limit,
        "fl": "id,title_s,author_s,year_i,file_path_s,folder_path_s,category_s,language_detected_s,score",
        "wt": "json",
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{_SOLR_BASE}/select", params=knn_params) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise HTTPException(status_code=502, detail=f"Solr kNN error {resp.status}: {body[:200]}")
            data = await resp.json()

    raw_docs = data.get("response", {}).get("docs", [])
    results = [normalize_book(doc, float(doc.get("score", 0.0))) for doc in raw_docs]
    return SearchResponse(
        query=f"similar:{book_id}",
        mode=SearchMode.semantic,
        total=len(results),
        page=1,
        limit=limit,
        results=results,
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/v1/health")
async def health():
    """Liveness check."""
    return {"status": "ok", "version": VERSION}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)
