#!/usr/bin/env python
# encoding: utf-8
"""Aithena Solr Search API — FastAPI service wrapping Solr /select."""

import os
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

SOLR_HOST = os.getenv("SOLR_HOST", "solr1")
SOLR_PORT = os.getenv("SOLR_PORT", "8983")
SOLR_COLLECTION = os.getenv("SOLR_COLLECTION", "books")
DOCUMENT_BASE_URL = os.getenv("DOCUMENT_BASE_URL", "/api/documents")
PORT = int(os.getenv("PORT", "8080"))

SOLR_SELECT_URL = (
    f"http://{SOLR_HOST}:{SOLR_PORT}/solr/{SOLR_COLLECTION}/select"
)

app = FastAPI(title="Aithena Solr Search API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _normalize_doc(doc: dict) -> dict:
    """Normalize a raw Solr document into the canonical API shape."""
    file_path = doc.get("file_path_s", "")
    document_url = (
        f"{DOCUMENT_BASE_URL}/{file_path}" if file_path else None
    )
    return {
        "id": doc.get("id", ""),
        "title": doc.get("title_s") or doc.get("title_t") or "",
        "author": doc.get("author_s") or doc.get("author_t") or "",
        "year": doc.get("year_i"),
        "category": doc.get("category_s"),
        "language": doc.get("language_detected_s"),
        "file_path": file_path,
        "document_url": document_url,
    }


def _extract_facets(facet_counts: dict) -> dict:
    """Convert Solr facet_counts.facet_fields into {field: {value: count}}."""
    result: dict = {}
    for field, flat_list in facet_counts.get("facet_fields", {}).items():
        pairs: dict = {}
        it = iter(flat_list)
        for value, count in zip(it, it):
            if count > 0:
                pairs[value] = count
        result[field] = pairs
    return result


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/search")
async def search(
    q: str = Query(..., min_length=1, description="Full-text search query"),
    rows: int = Query(default=10, ge=1, le=100, description="Results per page"),
    start: int = Query(default=0, ge=0, description="Pagination offset"),
    facet: bool = Query(default=True, description="Include facet counts"),
) -> dict:
    """Search books in the Solr index and return normalised results."""
    params: dict = {
        "q": q,
        "rows": rows,
        "start": start,
        "wt": "json",
        "hl": "true",
        "hl.fl": "content,_text_",
        "hl.snippets": 3,
        "hl.fragsize": 150,
    }
    if facet:
        params["facet"] = "true"
        params["facet.field"] = ["category_s", "author_s", "language_detected_s"]
        params["facet.mincount"] = 1

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(SOLR_SELECT_URL, params=params, timeout=10.0)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Solr unreachable: {exc}")

    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Solr returned unexpected status {resp.status_code}",
        )

    data = resp.json()
    response_section = data.get("response", {})
    docs = response_section.get("docs", [])
    num_found = response_section.get("numFound", 0)

    results = [_normalize_doc(doc) for doc in docs]
    facets = _extract_facets(data.get("facet_counts", {})) if facet else {}
    highlights = data.get("highlighting", {})

    return {
        "query": q,
        "pagination": {
            "total": num_found,
            "rows": rows,
            "start": start,
        },
        "results": results,
        "facets": facets,
        "highlights": highlights,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)
