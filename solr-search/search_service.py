from __future__ import annotations

import base64
import binascii
import math
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote

FACET_FIELDS: dict[str, tuple[str, ...]] = {
    "author": ("author_s",),
    "category": ("category_s",),
    "year": ("year_i",),
    "language": ("language_detected_s", "language_s"),
}

SOLR_FIELD_LIST = [
    "id",
    "title_s",
    "author_s",
    "year_i",
    "category_s",
    "language_detected_s",
    "language_s",
    "file_path_s",
    "folder_path_s",
    "page_count_i",
    "file_size_l",
    "score",
]

SORT_FIELDS = {
    "score": "score",
    "title": "title_s",
    "author": "author_s",
    "year": "year_i",
    "category": "category_s",
    "language": "language_s",
}

HIGHLIGHT_FIELDS = ("content", "_text_")


def build_sort_clause(sort_by: str, sort_order: str) -> str:
    field_name = SORT_FIELDS.get(sort_by)
    if field_name is None:
        raise ValueError(f"Unsupported sort_by value: {sort_by}")

    normalized_order = sort_order.lower()
    if normalized_order not in {"asc", "desc"}:
        raise ValueError(f"Unsupported sort_order value: {sort_order}")

    return f"{field_name} {normalized_order}"


def normalize_search_query(query: str) -> str:
    search_query = query.strip() or "*:*"
    if "{!" in search_query:
        raise ValueError("Local-parameter syntax is not allowed in search queries")
    return search_query


def build_solr_params(
    query: str,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str,
    facet_limit: int,
    *,
    rows: int | None = None,
) -> dict[str, Any]:
    search_query = normalize_search_query(query)
    start = max(page - 1, 0) * page_size
    params: dict[str, Any] = {
        "q": search_query,
        "start": start,
        "rows": page_size if rows is None else rows,
        "sort": build_sort_clause(sort_by, sort_order),
        "defType": "edismax",
        "wt": "json",
        "fl": ",".join(SOLR_FIELD_LIST),
        "facet": "true",
        "facet.limit": facet_limit,
        "facet.mincount": 1,
        "facet.field": [field for fields in FACET_FIELDS.values() for field in fields],
        "hl": "true",
        "hl.method": "unified",
        "hl.fl": ",".join(HIGHLIGHT_FIELDS),
        "hl.requireFieldMatch": "false",
        "hl.snippets": 3,
        "hl.fragsize": 160,
        "f._text_.hl.alternateField": "content",
        "f._text_.hl.maxAlternateFieldLength": 300,
    }
    return params


def parse_facet_counts(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    facet_fields = payload.get("facet_counts", {}).get("facet_fields", {})
    normalized: dict[str, list[dict[str, Any]]] = {}

    for facet_name, solr_fields in FACET_FIELDS.items():
        buckets: list[dict[str, Any]] = []
        for solr_field in solr_fields:
            raw_values = facet_fields.get(solr_field) or []
            if raw_values:
                buckets = [
                    {"value": raw_values[index], "count": raw_values[index + 1]}
                    for index in range(0, len(raw_values), 2)
                ]
                break
        normalized[facet_name] = buckets

    return normalized


def collect_highlights(document_id: str, highlighting: dict[str, Any]) -> list[str]:
    document_highlighting = highlighting.get(document_id, {})
    snippets: list[str] = []

    for field_name in HIGHLIGHT_FIELDS:
        for snippet in document_highlighting.get(field_name, []):
            if snippet not in snippets:
                snippets.append(snippet)

    return snippets


def encode_document_token(file_path: str) -> str:
    return base64.urlsafe_b64encode(file_path.encode("utf-8")).decode("ascii")


def decode_document_token(token: str) -> str:
    try:
        return base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise ValueError("Invalid document token") from exc


def resolve_document_path(base_path: Path, relative_path: str) -> Path:
    normalized = PurePosixPath(relative_path.replace("\\", "/"))
    if not normalized.parts or normalized.is_absolute() or ".." in normalized.parts:
        raise ValueError("Invalid document path")

    resolved_base = base_path.resolve()
    candidate = (resolved_base.joinpath(*normalized.parts)).resolve()

    try:
        candidate.relative_to(resolved_base)
    except ValueError as exc:
        raise ValueError("Document path escapes base path") from exc

    return candidate


def build_inline_content_disposition(filename: str) -> str:
    sanitized = filename.replace("\r", "").replace("\n", "")
    return f"inline; filename*=UTF-8''{quote(sanitized, safe='')}"


def normalize_book(
    document: dict[str, Any],
    highlighting: dict[str, Any],
    document_url: str | None,
) -> dict[str, Any]:
    document_id = document.get("id", "")
    return {
        "id": document_id,
        "title": document.get("title_s") or Path(document.get("file_path_s", "")).stem,
        "author": document.get("author_s") or "Unknown",
        "year": document.get("year_i"),
        "category": document.get("category_s"),
        "language": document.get("language_detected_s") or document.get("language_s"),
        "file_path": document.get("file_path_s"),
        "folder_path": document.get("folder_path_s"),
        "page_count": document.get("page_count_i"),
        "file_size": document.get("file_size_l"),
        "score": document.get("score"),
        "highlights": collect_highlights(document_id, highlighting),
        "document_url": document_url,
    }


def build_pagination(num_found: int, page: int, page_size: int) -> dict[str, int]:
    return {
        "page": page,
        "page_size": page_size,
        "total_results": num_found,
        "total_pages": math.ceil(num_found / page_size) if num_found else 0,
    }
