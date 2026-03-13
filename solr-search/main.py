#!/usr/bin/env python
# encoding: utf-8
"""FastAPI service that exposes keyword search against the Solr `books` collection."""

from __future__ import annotations

import urllib.parse
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import (
    DOCUMENTS_BASE_URL,
    PORT,
    SOLR_COLLECTION,
    SOLR_HOST,
    SOLR_PORT,
    TITLE,
    VERSION,
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="api " + TITLE, version=VERSION)
api_app = FastAPI(title=TITLE, version=VERSION)

app.mount("/v1", api_app)

try:
    app.mount("/", StaticFiles(directory="static", html=True), name="assets")
except RuntimeError:
    pass  # static directory may be absent during development / tests

api_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Solr helpers
# ---------------------------------------------------------------------------

SOLR_BASE_URL = f"http://{SOLR_HOST}:{SOLR_PORT}/solr/{SOLR_COLLECTION}"

def _make_document_url(file_path_s: str | None) -> str | None:
    """Return a client-safe URL for opening a PDF from its stored relative path."""
    if not file_path_s:
        return None
    encoded = urllib.parse.quote(file_path_s, safe="/")
    base = DOCUMENTS_BASE_URL.rstrip("/")
    return f"{base}/{encoded}"


def _normalize_doc(
    doc: dict[str, Any],
    highlighting: dict[str, list[str]],
) -> dict[str, Any]:
    """Flatten a Solr document into the API result shape."""
    doc_id = doc.get("id", "")
    file_path = doc.get("file_path_s")

    hl_snippets: list[str] = []
    if doc_id in highlighting:
        for field_snippets in highlighting[doc_id].values():
            hl_snippets.extend(field_snippets)

    return {
        "id": doc_id,
        "title": doc.get("title_s"),
        "author": doc.get("author_s"),
        "year": doc.get("year_i"),
        "category": doc.get("category_s"),
        "language": doc.get("language_detected_s"),
        "file_path": file_path,
        "score": doc.get("score"),
        "highlights": hl_snippets,
        "document_url": _make_document_url(file_path),
    }


def _parse_facets(
    facet_counts: dict[str, Any] | None,
) -> dict[str, list[dict[str, Any]]]:
    """Convert Solr facet_counts into a tidy {field: [{value, count}]} mapping."""
    result: dict[str, list[dict[str, Any]]] = {}
    if not facet_counts:
        return result
    fields: dict[str, list] = facet_counts.get("facet_fields", {})
    for field, flat_list in fields.items():
        buckets: list[dict[str, Any]] = []
        # Solr returns [value, count, value, count, ...]
        it = iter(flat_list)
        for value, count in zip(it, it):
            if count > 0:
                buckets.append({"value": value, "count": count})
        result[field] = buckets
    return result


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class BookResult(BaseModel):
    id: str
    title: str | None = None
    author: str | None = None
    year: int | None = None
    category: str | None = None
    language: str | None = None
    file_path: str | None = None
    score: float | None = None
    highlights: list[str] = []
    document_url: str | None = None


class FacetBucket(BaseModel):
    value: str
    count: int


class SearchResponse(BaseModel):
    query: str
    total: int
    start: int
    rows: int
    results: list[BookResult]
    facets: dict[str, list[FacetBucket]] = {}


# Resolve any forward references in nested generic types (Pydantic v2)
SearchResponse.model_rebuild()


class InfoResponse(BaseModel):
    title: str
    version: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@api_app.get("/info", response_model=InfoResponse)
async def info() -> InfoResponse:
    return InfoResponse(title=TITLE, version=VERSION)


@api_app.get("/search/", response_model=SearchResponse)
async def search(
    q: str = Query(default="*:*", description="Search query (Solr syntax or free text)"),
    start: int = Query(default=0, ge=0, description="Pagination offset"),
    rows: int = Query(default=10, ge=1, le=100, description="Results per page"),
    sort: str = Query(default="score desc", description="Sort expression (e.g. 'year_i desc')"),
) -> SearchResponse:
    """Keyword search against the Solr books collection.

    Supports free-text queries, pagination, custom sort, facets, and highlights.
    """
    solr_params: dict[str, Any] = {
        "q": q,
        "defType": "edismax",
        "qf": "title_t^10 author_t^5 _text_^1",
        "start": start,
        "rows": rows,
        "sort": sort,
        "fl": "id,title_s,author_s,year_i,category_s,language_detected_s,file_path_s,score",
        "wt": "json",
        # Highlighting
        "hl": "true",
        "hl.method": "unified",
        "hl.fl": "content,_text_",
        "hl.snippets": 3,
        "hl.fragsize": 160,
        "f._text_.hl.alternateField": "content",
        "f._text_.hl.maxAlternateFieldLength": 300,
        # Faceting
        "facet": "true",
        "facet.field": [
            "author_s",
            "category_s",
            "language_detected_s",
        ],
        "facet.mincount": 1,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{SOLR_BASE_URL}/select",
                params=solr_params,
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Solr returned an error: {exc.response.status_code}",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not reach Solr: {exc}",
        ) from exc

    data = resp.json()
    response_data = data.get("response", {})
    highlighting = data.get("highlighting", {})
    facet_counts = data.get("facet_counts")

    docs = response_data.get("docs", [])
    total = response_data.get("numFound", 0)

    results = [_normalize_doc(doc, highlighting) for doc in docs]
    raw_facets = _parse_facets(facet_counts)
    facets: dict[str, list[FacetBucket]] = {
        field: [FacetBucket(**b) for b in buckets]
        for field, buckets in raw_facets.items()
    }

    return SearchResponse(
        query=q,
        total=total,
        start=start,
        rows=rows,
        results=[BookResult(**r) for r in results],
        facets=facets,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)
