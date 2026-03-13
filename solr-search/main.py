from __future__ import annotations

from typing import Any, Literal

import requests
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from config import settings
from search_service import (
    build_inline_content_disposition,
    build_pagination,
    build_solr_params,
    decode_document_token,
    encode_document_token,
    normalize_book,
    parse_facet_counts,
    resolve_document_path,
)

SortBy = Literal["score", "title", "author", "year", "category", "language"]
SortOrder = Literal["asc", "desc"]

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


def build_document_url(request: Request, file_path: str | None) -> str | None:
    if not file_path:
        return None

    document_id = encode_document_token(file_path)
    if settings.document_url_base:
        return f"{settings.document_url_base}/{document_id}"
    return str(request.url_for("get_document", document_id=document_id))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.title, "version": settings.version}


@app.get("/info")
def info() -> dict[str, str]:
    return {"title": settings.title, "version": settings.version}


@app.get("/search")
def search(
    request: Request,
    q: str = Query("", description="Keyword search. Empty values return all indexed books."),
    page: int = Query(1, ge=1),
    page_size: int = Query(settings.default_page_size, ge=1, le=settings.max_page_size),
    sort_by: SortBy = Query("score"),
    sort_order: SortOrder = Query("desc"),
) -> dict[str, Any]:
    payload = query_solr(
        build_params_or_400(
            query=q,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
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
        "sort": {"by": sort_by, "order": sort_order},
        **build_pagination(response.get("numFound", 0), page, page_size),
        "results": results,
        "facets": parse_facet_counts(payload),
    }


@app.get("/facets")
def facets(
    q: str = Query("", description="Optional query to scope facet counts."),
    sort_by: SortBy = Query("score"),
    sort_order: SortOrder = Query("desc"),
) -> dict[str, Any]:
    payload = query_solr(
        build_params_or_400(
            query=q,
            page=1,
            page_size=1,
            sort_by=sort_by,
            sort_order=sort_order,
            facet_limit=settings.facet_limit,
            rows=0,
        )
    )
    return {"query": q, "facets": parse_facet_counts(payload)}


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.port)
