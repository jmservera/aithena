from __future__ import annotations

import json
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

import redis as redis_lib
import requests
from config import settings
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from search_service import (
    build_filter_queries,
    build_inline_content_disposition,
    build_knn_params,
    build_pagination,
    build_solr_params,
    decode_document_token,
    encode_document_token,
    get_query_embedding,
    normalize_book,
    parse_facet_counts,
    parse_stats_response,
    reciprocal_rank_fusion,
    resolve_document_path,
    solr_escape,
)

SortBy = Literal["score", "title", "author", "year", "category", "language"]
SortOrder = Literal["asc", "desc"]

VALID_SEARCH_MODES: frozenset[str] = frozenset({"keyword", "semantic", "hybrid"})

app = FastAPI(title=settings.title, version=settings.version)


def build_params_or_400(**kwargs: Any) -> dict[str, Any]:
    try:
        return build_solr_params(**kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def query_solr(params: dict[str, Any]) -> dict[str, Any]:
    try:
        response = requests.get(settings.select_url, params=params, timeout=settings.request_timeout)
        response.raise_for_status()
        return response.json()
    except requests.Timeout as exc:
        raise HTTPException(status_code=504, detail="Timed out waiting for Solr") from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Solr search request failed") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Solr returned invalid JSON") from exc


def _fetch_embedding(text: str) -> list[float]:
    """Call the embeddings server; wrap errors as HTTP 502."""
    try:
        return get_query_embedding(settings.embeddings_url, text, settings.embeddings_timeout)
    except requests.Timeout as exc:
        raise HTTPException(status_code=504, detail="Timed out waiting for embeddings server") from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Embeddings server request failed") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def build_document_url(request: Request, file_path: str | None) -> str | None:
    if not file_path:
        return None

    document_id = encode_document_token(file_path)
    if settings.document_url_base:
        return f"{settings.document_url_base}/{document_id}"
    return str(request.url_for("get_document", document_id=document_id))


def resolve_page_size(limit: int | None, page_size: int) -> int:
    return limit or page_size


def collect_search_filters(**filters: str | None) -> dict[str, str]:
    return {name: value.strip() for name, value in filters.items() if value and value.strip()}


@app.get("/v1/health", include_in_schema=False, name="health_v1")
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.title, "version": settings.version}


@app.get("/v1/info", include_in_schema=False, name="info_v1")
@app.get("/info")
def info() -> dict[str, str]:
    return {"title": settings.title, "version": settings.version}


@app.get("/v1/search/", include_in_schema=False, name="search_v1")
@app.get("/v1/search", include_in_schema=False, name="search_v1_no_slash")
@app.get("/search")
def search(
    request: Request,
    q: str = Query("", description="Keyword search. Empty values return all indexed books."),
    page: int = Query(1, ge=1),
    limit: int | None = Query(None, ge=1, le=settings.max_page_size),
    page_size: int = Query(settings.default_page_size, ge=1, le=settings.max_page_size),
    sort: str | None = Query(None, description="Combined sort clause like `score desc` or `year_i asc`."),
    sort_by: Annotated[SortBy, Query()] = "score",
    sort_order: Annotated[SortOrder, Query()] = "desc",
    fq_author: str | None = Query(None),
    fq_category: str | None = Query(None),
    fq_language: str | None = Query(None),
    fq_year: str | None = Query(None),
    mode: str = Query(
        settings.default_search_mode,
        description="Search mode: keyword (BM25), semantic (Solr kNN), or hybrid (RRF fusion).",
    ),
) -> dict[str, Any]:
    """Search for books.

    - **keyword** (default): BM25 full-text search via Solr edismax.
    - **semantic**: Dense vector kNN search using Solr HNSW (``book_embedding`` field).
    - **hybrid**: Reciprocal Rank Fusion of the BM25 and kNN legs.

    Supports both the Phase 2 UI contract (`limit`, `sort`, `fq_*`) and the
    newer FastAPI query parameters (`page_size`, `sort_by`, `sort_order`).
    """
    if mode not in VALID_SEARCH_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid search mode: {mode!r}. Must be one of: keyword, semantic, hybrid.",
        )

    resolved_page_size = resolve_page_size(limit, page_size)
    filters = collect_search_filters(
        author=fq_author,
        category=fq_category,
        language=fq_language,
        year=fq_year,
    )

    if mode == "keyword":
        return _search_keyword(request, q, page, resolved_page_size, sort_by, sort_order, sort, filters)
    if mode == "semantic":
        return _search_semantic(request, q, resolved_page_size, filters)
    # hybrid
    return _search_hybrid(request, q, resolved_page_size, sort_by, sort_order, sort, filters)


def _search_keyword(
    request: Request,
    q: str,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str,
    sort: str | None,
    filters: dict[str, str],
) -> dict[str, Any]:
    payload = query_solr(
        build_params_or_400(
            query=q,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            sort=sort,
            filters=filters,
            facet_limit=settings.facet_limit,
        )
    )

    response = payload.get("response", {})
    highlighting = payload.get("highlighting", {})
    results = [
        normalize_book(
            document,
            highlighting,
            build_document_url(request, document.get("file_path_s")),
        )
        for document in response.get("docs", [])
    ]

    return {
        "query": q,
        "mode": "keyword",
        "sort": {"by": sort_by, "order": sort_order},
        **build_pagination(response.get("numFound", 0), page, page_size),
        "results": results,
        "facets": parse_facet_counts(payload),
    }


def _search_semantic(
    request: Request,
    q: str,
    top_k: int,
    filters: dict[str, str],
) -> dict[str, Any]:
    """Execute a Solr kNN semantic search using the ``book_embedding`` field.

    Facets and highlights degrade to empty because the kNN query path does not
    produce Solr facet counts or highlight snippets.
    """
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty for semantic search")

    vector = _fetch_embedding(q)
    payload = query_solr(build_knn_params(vector, top_k, settings.knn_field, build_filter_queries(filters)))

    response = payload.get("response", {})
    results = [
        normalize_book(
            document,
            {},
            build_document_url(request, document.get("file_path_s")),
        )
        for document in response.get("docs", [])
    ]

    return {
        "query": q,
        "mode": "semantic",
        "sort": {"by": "score", "order": "desc"},
        **build_pagination(response.get("numFound", len(results)), 1, top_k),
        "results": results,
        "facets": {"author": [], "category": [], "year": [], "language": []},
    }


def _search_hybrid(
    request: Request,
    q: str,
    page_size: int,
    sort_by: str,
    sort_order: str,
    sort: str | None,
    filters: dict[str, str],
) -> dict[str, Any]:
    """Execute BM25 and kNN searches in parallel, then fuse with RRF.

    Facets and highlights are sourced from the BM25 (keyword) leg.
    Documents that appear only in the kNN leg will have empty highlights.
    The RRF k constant is configurable via the ``RRF_K`` environment variable
    (default 60, per the original RRF paper).
    """
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty for hybrid search")

    candidate_limit = max(page_size * 2, 20)

    kw_params = build_params_or_400(
        query=q,
        page=1,
        page_size=candidate_limit,
        sort_by=sort_by,
        sort_order=sort_order,
        sort=sort,
        filters=filters,
        facet_limit=settings.facet_limit,
    )

    # Run BM25 query and embedding fetch concurrently
    with ThreadPoolExecutor(max_workers=2) as pool:
        kw_future = pool.submit(query_solr, kw_params)
        emb_future = pool.submit(_fetch_embedding, q)

        kw_payload = kw_future.result()
        vector = emb_future.result()

    knn_payload = query_solr(
        build_knn_params(vector, candidate_limit, settings.knn_field, build_filter_queries(filters))
    )

    kw_response = kw_payload.get("response", {})
    kw_highlighting = kw_payload.get("highlighting", {})

    kw_results = [
        normalize_book(
            document,
            kw_highlighting,
            build_document_url(request, document.get("file_path_s")),
        )
        for document in kw_response.get("docs", [])
    ]

    sem_results = [
        normalize_book(
            document,
            {},
            build_document_url(request, document.get("file_path_s")),
        )
        for document in knn_payload.get("response", {}).get("docs", [])
    ]

    fused = reciprocal_rank_fusion(kw_results, sem_results, k=settings.rrf_k)[:page_size]

    return {
        "query": q,
        "mode": "hybrid",
        "sort": {"by": "score", "order": "desc"},
        **build_pagination(len(fused), 1, page_size),
        "results": fused,
        "facets": parse_facet_counts(kw_payload),
    }


@app.get("/v1/facets/", include_in_schema=False, name="facets_v1")
@app.get("/v1/facets", include_in_schema=False, name="facets_v1_no_slash")
@app.get("/facets")
def facets(
    q: str = Query("", description="Optional query to scope facet counts."),
    sort: str | None = Query(None),
    sort_by: Annotated[SortBy, Query()] = "score",
    sort_order: Annotated[SortOrder, Query()] = "desc",
    fq_author: str | None = Query(None),
    fq_category: str | None = Query(None),
    fq_language: str | None = Query(None),
    fq_year: str | None = Query(None),
) -> dict[str, Any]:
    payload = query_solr(
        build_params_or_400(
            query=q,
            page=1,
            page_size=1,
            sort_by=sort_by,
            sort_order=sort_order,
            sort=sort,
            filters=collect_search_filters(
                author=fq_author,
                category=fq_category,
                language=fq_language,
                year=fq_year,
            ),
            facet_limit=settings.facet_limit,
            rows=0,
        )
    )
    return {"query": q, "facets": parse_facet_counts(payload)}


@app.get("/v1/documents/{document_id}", include_in_schema=False, name="get_document_v1")
@app.get("/documents/{document_id}", name="get_document")
def get_document(document_id: str) -> FileResponse:
    try:
        file_path = decode_document_token(document_id)
        document_path = resolve_document_path(settings.base_path, file_path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc

    if document_path.suffix.lower() != ".pdf" or not document_path.is_file():
        raise HTTPException(status_code=404, detail="Document not found")

    return FileResponse(
        document_path,
        media_type="application/pdf",
        filename=document_path.name,
        headers={"Content-Disposition": build_inline_content_disposition(document_path.name)},
    )


@app.get("/v1/books/{document_id}/similar", include_in_schema=False, name="similar_books_v1")
@app.get("/books/{document_id}/similar")
def similar_books(
    request: Request,
    document_id: str,
    limit: int = Query(5, ge=1, le=50, description="Maximum number of similar books to return."),
    min_score: float = Query(0.0, ge=0.0, le=1.0, description="Minimum cosine similarity score threshold."),
) -> dict[str, Any]:
    """Return books semantically similar to the one identified by *document_id*.

    The source document is always excluded from results. Similarity is computed
    using Solr's kNN query against the ``book_embedding`` DenseVectorField.
    """
    embedding_field = settings.book_embedding_field

    source_payload = query_solr(
        {
            "q": f"id:{solr_escape(document_id)}",
            "fl": f"id,{embedding_field}",
            "rows": 1,
            "wt": "json",
        }
    )
    source_docs = source_payload.get("response", {}).get("docs", [])
    if not source_docs:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id!r}")

    vector = source_docs[0].get(embedding_field)
    if not vector:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Document {document_id!r} has no embedding yet. "
                "Embeddings are populated by the Phase 3 indexing pipeline."
            ),
        )

    knn_payload = query_solr(
        {
            "q": f"{{!knn f={embedding_field} topK={limit + 1}}}{json.dumps(vector)}",
            "fq": f"-id:{solr_escape(document_id)}",
            "fl": "id,title_s,author_s,year_i,category_s,file_path_s,score",
            "rows": limit,
            "wt": "json",
        }
    )
    docs = knn_payload.get("response", {}).get("docs", [])

    results = []
    for doc in docs:
        score = doc.get("score", 0.0)
        if min_score > 0.0 and score < min_score:
            continue
        file_path = doc.get("file_path_s")
        results.append(
            {
                "id": doc.get("id"),
                "title": doc.get("title_s") or Path(file_path or "").stem,
                "author": doc.get("author_s") or "Unknown",
                "year": doc.get("year_i"),
                "category": doc.get("category_s"),
                "document_url": build_document_url(request, file_path),
                "score": score,
            }
        )

    return {"results": results}


@app.get("/v1/stats/", include_in_schema=False, name="stats_v1")
@app.get("/v1/stats", include_in_schema=False, name="stats_v1_no_slash")
@app.get("/stats")
def stats() -> dict[str, Any]:
    """Return collection-level statistics from Solr.

    Queries Solr with the stats component and facets to produce an overview of
    the indexed book collection including totals, breakdowns by language,
    author, year, and category, and page-count statistics.
    """
    params: dict[str, Any] = {
        "q": "*:*",
        "rows": 0,
        "wt": "json",
        "stats": "true",
        "stats.field": "page_count_i",
        "facet": "true",
        "facet.field": ["author_s", "category_s", "year_i", "language_detected_s"],
        "facet.limit": settings.facet_limit,
        "facet.mincount": 1,
    }
    payload = query_solr(params)
    return parse_stats_response(payload)


# ---------------------------------------------------------------------------
# Phase 4 — /v1/status/ endpoint
# ---------------------------------------------------------------------------

_redis_pool: redis_lib.ConnectionPool | None = None
_redis_pool_lock = threading.Lock()


def _get_redis_pool() -> redis_lib.ConnectionPool:
    """Return a singleton Redis ConnectionPool (double-checked locking)."""
    global _redis_pool
    if _redis_pool is None:
        with _redis_pool_lock:
            if _redis_pool is None:
                _redis_pool = redis_lib.ConnectionPool(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=5,
                )
    return _redis_pool


def _tcp_check(host: str, port: int, timeout: float = 2.0) -> bool:
    """Return True if a TCP connection to *host*:*port* succeeds within *timeout* seconds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _get_solr_status(solr_url: str, timeout: float = 5.0) -> dict[str, Any]:
    """Query Solr CLUSTERSTATUS and return aggregated node/doc information."""
    cluster_url = f"{solr_url}/admin/collections"
    try:
        resp = requests.get(
            cluster_url,
            params={"action": "CLUSTERSTATUS", "wt": "json"},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return {"status": "error", "nodes": 0, "docs_indexed": 0}

    cluster = data.get("cluster", {})
    live_nodes = cluster.get("live_nodes", [])
    node_count = len(live_nodes)

    docs_indexed = 0
    collections = cluster.get("collections", {})
    for col_data in collections.values():
        for shard_data in col_data.get("shards", {}).values():
            replicas = shard_data.get("replicas", {})
            if replicas:
                first_replica = next(iter(replicas.values()))
                docs_indexed += first_replica.get("index", {}).get("numDocs", 0)

    if node_count == 0:
        solr_status = "error"
    elif node_count < 3:
        solr_status = "degraded"
    else:
        solr_status = "ok"

    return {"status": solr_status, "nodes": node_count, "docs_indexed": docs_indexed}


def _get_indexing_status(key_pattern: str) -> dict[str, int]:
    """Scan Redis for *key_pattern* keys and tally indexing state counts."""
    try:
        pool = _get_redis_pool()
        client = redis_lib.Redis(connection_pool=pool)
        keys = list(client.scan_iter(match=key_pattern, count=100))
        if not keys:
            return {"total_discovered": 0, "indexed": 0, "failed": 0, "pending": 0}

        values = client.mget(keys)
        indexed = 0
        failed = 0
        pending = 0
        for val in values:
            if val is None:
                pending += 1
            elif val == "text_indexed":
                indexed += 1
            elif val == "failed":
                failed += 1
            else:
                pending += 1

        total = len(keys)
        return {
            "total_discovered": total,
            "indexed": indexed,
            "failed": failed,
            "pending": pending,
        }
    except Exception:
        return {"total_discovered": 0, "indexed": 0, "failed": 0, "pending": 0}


@app.get("/v1/status/", include_in_schema=False, name="status_v1_slash")
@app.get("/v1/status", name="status_v1")
def service_status() -> dict[str, Any]:
    """Return aggregated indexing and service health status.

    Aggregates:
    - Solr CLUSTERSTATUS (node health + doc count)
    - Redis ``doc:*`` key scan (indexing state breakdown)
    - TCP reachability checks for Solr, Redis, and RabbitMQ
    """
    parsed = urlparse(settings.solr_url)
    solr_host = parsed.hostname or settings.solr_url
    solr_port = parsed.port or 8983

    solr_info = _get_solr_status(settings.solr_url, timeout=settings.request_timeout)
    indexing_info = _get_indexing_status(settings.redis_key_pattern)

    solr_up = _tcp_check(solr_host, solr_port)
    redis_up = _tcp_check(settings.redis_host, settings.redis_port)
    rabbitmq_up = _tcp_check(settings.rabbitmq_host, settings.rabbitmq_port)

    return {
        "solr": solr_info,
        "indexing": indexing_info,
        "services": {
            "solr": "up" if solr_up else "down",
            "redis": "up" if redis_up else "down",
            "rabbitmq": "up" if rabbitmq_up else "down",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.port)
