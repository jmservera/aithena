#!/usr/bin/env python
# encoding: utf-8
"""Aithena Solr-backed search API.

Exposes two main endpoints:
  GET /search/      — full-text keyword search via Solr /select
  GET /similar/     — kNN semantic similarity via Solr DenseVectorField
"""
import json

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import (
    PORT,
    SOLR_COLLECTION,
    SOLR_HOST,
    SOLR_PORT,
    SOLR_TIMEOUT,
    SOLR_VECTOR_FIELD,
    TITLE,
    VERSION,
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title=TITLE + " (root)", version=VERSION)
api_app = FastAPI(title=TITLE, version=VERSION)

origins = ["http://localhost:5173"]

app.mount("/v1", api_app)

api_app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SOLR_BASE_URL = f"http://{SOLR_HOST}:{SOLR_PORT}/solr/{SOLR_COLLECTION}"


def _solr_select(params: dict) -> dict:
    """Execute a Solr /select request and return the decoded JSON body."""
    try:
        resp = requests.get(
            f"{SOLR_BASE_URL}/select",
            params=params,
            timeout=SOLR_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Solr error: {exc}")


def _normalize_book(doc: dict) -> dict:
    """Map a raw Solr document to the public API shape."""
    return {
        "id": doc.get("id"),
        "title": doc.get("title_s") or doc.get("title_t"),
        "author": doc.get("author_s") or doc.get("author_t"),
        "year": doc.get("year_i"),
        "category": doc.get("category_s"),
        "document_url": doc.get("file_path_s"),
        "language": doc.get("language_detected_s"),
        "page_count": doc.get("page_count_i"),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@api_app.get("/health")
async def health():
    """Liveness probe — returns OK when the service is running."""
    return {"status": "ok", "version": VERSION}


@api_app.get("/search/")
async def search(q: str, limit: int = 10, page: int = 1):
    """Full-text keyword search backed by Solr /select.

    Returns matching books with title, author, year, category, and document_url.
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' must not be empty.")

    start = (page - 1) * limit
    data = _solr_select(
        {
            "q": q,
            "defType": "edismax",
            "qf": "title_t author_t _text_",
            "fl": "id,title_s,title_t,author_s,author_t,year_i,category_s,file_path_s,language_detected_s,page_count_i,score",
            "rows": limit,
            "start": start,
            "wt": "json",
        }
    )

    response = data.get("response", {})
    docs = response.get("docs", [])
    total = response.get("numFound", 0)

    return {
        "results": [_normalize_book(d) for d in docs],
        "total": total,
        "query": q,
        "page": page,
        "limit": limit,
    }


@api_app.get("/similar/")
async def similar(id: str, limit: int = 5, min_score: float = 0.0):
    """Return books semantically similar to the document identified by *id*.

    *id* is the Solr document ID (SHA-256 of the file path) returned by
    ``/search/``.  The source document is always excluded from results.

    ``limit`` controls the maximum number of books returned.
    ``min_score`` filters out results whose cosine similarity is below the
    given threshold (0.0 = no threshold).

    The endpoint uses Solr's ``{!knn}`` query parser against the
    ``embedding_v`` dense-vector field populated by the indexing pipeline.
    """
    # ------------------------------------------------------------------
    # Step 1: Fetch the source document and its vector from Solr.
    # ------------------------------------------------------------------
    source_data = _solr_select(
        {
            "q": f"id:{_solr_escape(id)}",
            "fl": f"id,file_path_s,{SOLR_VECTOR_FIELD}",
            "rows": 1,
            "wt": "json",
        }
    )

    source_docs = source_data.get("response", {}).get("docs", [])
    if not source_docs:
        raise HTTPException(status_code=404, detail=f"No document found with id: {id!r}")

    source_doc = source_docs[0]
    vector = source_doc.get(SOLR_VECTOR_FIELD)
    if not vector:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Document {id!r} has no embedding yet. "
                "Embeddings are populated by the Phase 3 indexing pipeline."
            ),
        )

    # ------------------------------------------------------------------
    # Step 2: Run kNN query against Solr, excluding the source document.
    # Request limit + 1 candidates so exclusion doesn't leave us short.
    # ------------------------------------------------------------------
    top_k = limit + 1
    vector_str = json.dumps(vector)

    params: dict = {
        "q": f"{{!knn f={SOLR_VECTOR_FIELD} topK={top_k}}}{vector_str}",
        "fq": f"-id:{_solr_escape(id)}",
        "fl": "id,title_s,title_t,author_s,author_t,year_i,category_s,file_path_s,score",
        "rows": limit,
        "wt": "json",
    }

    knn_data = _solr_select(params)
    docs = knn_data.get("response", {}).get("docs", [])

    results = []
    for doc in docs:
        score = doc.get("score", 0.0)
        if min_score > 0.0 and score < min_score:
            continue
        results.append(
            {
                "id": doc.get("id"),
                "title": doc.get("title_s") or doc.get("title_t"),
                "author": doc.get("author_s") or doc.get("author_t"),
                "year": doc.get("year_i"),
                "category": doc.get("category_s"),
                "document_url": doc.get("file_path_s"),
                "score": score,
            }
        )

    return {"results": results}


def _solr_escape(value: str) -> str:
    """Escape special Lucene/Solr query characters in a literal value."""
    special = r'\+-&|!(){}[]^"~*?:/'
    return "".join(f"\\{c}" if c in special else c for c in value)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)
