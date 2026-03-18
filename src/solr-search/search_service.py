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
    "page_start_i",
    "page_end_i",
    "score",
]

SORT_FIELDS = {
    "score": "score",
    "title": "title_s",
    "title_s": "title_s",
    "author": "author_s",
    "author_s": "author_s",
    "year": "year_i",
    "year_i": "year_i",
    "category": "category_s",
    "category_s": "category_s",
    "language": "language_s",
    "language_s": "language_s",
    "language_detected_s": "language_detected_s",
}

HIGHLIGHT_FIELDS = ("content", "_text_")


def build_sort_clause(
    sort_by: str = "score",
    sort_order: str = "desc",
    sort: str | None = None,
) -> str:
    if sort is not None:
        parts = sort.split()
        if len(parts) != 2:
            raise ValueError(f"Unsupported sort value: {sort}")
        sort_by, sort_order = parts

    field_name = SORT_FIELDS.get(sort_by)
    if field_name is None:
        raise ValueError(f"Unsupported sort_by value: {sort_by}")

    normalized_order = sort_order.lower()
    if normalized_order not in {"asc", "desc"}:
        raise ValueError(f"Unsupported sort_order value: {sort_order}")

    return f"{field_name} {normalized_order}"


def build_filter_queries(filters: dict[str, str] | None) -> list[str]:
    queries: list[str] = []
    for filter_name, raw_value in (filters or {}).items():
        value = raw_value.strip()
        if not value:
            continue

        fields = FACET_FIELDS.get(filter_name)
        if fields is None:
            raise ValueError(f"Unsupported filter field: {filter_name}")

        escaped_value = solr_escape(value)
        if len(fields) == 1:
            queries.append(f"{fields[0]}:{escaped_value}")
            continue

        joined_fields = " OR ".join(f"{field}:{escaped_value}" for field in fields)
        queries.append(f"({joined_fields})")

    return queries


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
    sort: str | None = None,
    filters: dict[str, str] | None = None,
) -> dict[str, Any]:
    search_query = normalize_search_query(query)
    start = max(page - 1, 0) * page_size
    params: dict[str, Any] = {
        "q": search_query,
        "start": start,
        "rows": page_size if rows is None else rows,
        "sort": build_sort_clause(sort_by, sort_order, sort),
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
    filter_queries = build_filter_queries(filters)
    if filter_queries:
        params["fq"] = filter_queries
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
    page_start = document.get("page_start_i")
    page_end = document.get("page_end_i")
    pages: list[int] | None = None
    if page_start is not None or page_end is not None:
        start = page_start if page_start is not None else page_end
        end = page_end if page_end is not None else page_start
        pages = [start, end]
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
        "pages": pages,
        "score": document.get("score"),
        "highlights": collect_highlights(document_id, highlighting),
        "document_url": document_url,
    }


def build_pagination(num_found: int, page: int, page_size: int) -> dict[str, int]:
    return {
        "page": page,
        "limit": page_size,
        "page_size": page_size,
        "total": num_found,
        "total_results": num_found,
        "total_pages": math.ceil(num_found / page_size) if num_found else 0,
    }


# ---------------------------------------------------------------------------
# Phase 3 — Semantic / Hybrid search helpers
# ---------------------------------------------------------------------------


def build_knn_params(
    vector: list[float],
    top_k: int,
    knn_field: str,
    filters: list[str] | None = None,
) -> dict[str, Any]:
    """Build Solr parameters for a kNN (dense vector) query.

    Uses the Solr ``{!knn}`` local-parameter syntax with the pre-existing
    ``book_embedding`` DenseVectorField (HNSW, cosine similarity, 512-dim).
    """
    vector_str = "[" + ",".join(str(v) for v in vector) + "]"
    params = {
        "q": f"{{!knn f={knn_field} topK={top_k}}}{vector_str}",
        "rows": top_k,
        "fl": ",".join(SOLR_FIELD_LIST),
        "wt": "json",
    }
    if filters:
        params["fq"] = filters
    return params


def get_query_embedding(embeddings_url: str, text: str, timeout: float) -> list[float]:
    """Call the embeddings server and return the query vector.

    Args:
        embeddings_url: Full URL of the embeddings endpoint
                        (e.g. ``http://embeddings-server:8001/v1/embeddings/``).
        text: Query text to embed.
        timeout: HTTP request timeout in seconds.

    Returns:
        A list of floats representing the query embedding.

    Raises:
        requests.HTTPError: If the embeddings server returns a non-2xx status.
        ValueError: If the response payload has no ``data`` entries.
    """
    import requests  # local import to keep search_service import-clean in tests

    response = requests.post(
        embeddings_url,
        json={"input": text},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json().get("data", [])
    if not data:
        raise ValueError("Embeddings server returned empty data")
    return data[0]["embedding"]


def reciprocal_rank_fusion(
    keyword_results: list[dict[str, Any]],
    semantic_results: list[dict[str, Any]],
    k: int = 60,
) -> list[dict[str, Any]]:
    """Merge two ranked result lists using Reciprocal Rank Fusion (RRF).

    For each document, the RRF score is the sum across lists of
    ``1 / (k + rank)`` (1-based rank).  Documents present in both lists
    score higher than documents present in only one.

    Facets and highlights from *keyword_results* are preserved on the merged
    result because the kNN leg does not produce Solr-style facet counts or
    highlights.

    Args:
        keyword_results: Normalised book dicts from the BM25 Solr leg.
        semantic_results: Normalised book dicts from the kNN Solr leg.
        k: RRF damping constant (default 60 per the original RRF paper).

    Returns:
        A new list of book dicts sorted by descending RRF score, with the
        ``score`` field overwritten with the RRF combined score.
    """
    scores: dict[str, float] = {}
    result_map: dict[str, dict[str, Any]] = {}

    for rank, doc in enumerate(keyword_results, start=1):
        doc_id = doc["id"]
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
        result_map[doc_id] = doc

    for rank, doc in enumerate(semantic_results, start=1):
        doc_id = doc["id"]
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
        if doc_id not in result_map:
            result_map[doc_id] = doc

    ranked = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
    fused: list[dict[str, Any]] = []
    for doc_id, rrf_score in ranked:
        merged = dict(result_map[doc_id])
        merged["score"] = rrf_score
        fused.append(merged)
    return fused


def solr_escape(value: str) -> str:
    """Escape special Lucene/Solr query characters in a literal string value."""
    special = r'\+-&|!(){}[]^"~*?:/ '
    return "".join(f"\\{ch}" if ch in special else ch for ch in value)


def parse_stats_response(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract collection statistics from a Solr stats + facets response.

    Args:
        payload: Raw Solr JSON response containing ``grouped``, ``stats``, and
                 ``facet_counts`` sections. Uses Solr grouping to count distinct
                 books by parent_id_s (Phase 1 quick win for issue #404).

    Returns:
        A dict with ``total_books``, ``by_language``, ``by_author``,
        ``by_year``, ``by_category``, and ``page_stats`` keys.
    """
    grouped = payload.get("grouped", {})
    parent_id_groups = grouped.get("parent_id_s", {})
    ngroups = parent_id_groups.get("ngroups")
    total_books: int = ngroups if ngroups is not None else parent_id_groups.get("matches", 0)

    facet_fields: dict[str, list[Any]] = payload.get("facet_counts", {}).get("facet_fields", {})

    def _parse_facet(field: str) -> list[dict[str, Any]]:
        raw = facet_fields.get(field) or []
        return [{"value": raw[i], "count": raw[i + 1]} for i in range(0, len(raw), 2)]

    stats_fields: dict[str, Any] = payload.get("stats", {}).get("stats_fields", {})
    page_count_stats: dict[str, Any] = stats_fields.get("page_count_i") or {}

    page_stats: dict[str, Any] = {
        "total": int(page_count_stats.get("sum") or 0),
        "avg": round(page_count_stats.get("mean") or 0),
        "min": int(page_count_stats.get("min") or 0),
        "max": int(page_count_stats.get("max") or 0),
    }

    return {
        "total_books": total_books,
        "by_language": _parse_facet("language_detected_s"),
        "by_author": _parse_facet("author_s"),
        "by_year": _parse_facet("year_i"),
        "by_category": _parse_facet("category_s"),
        "page_stats": page_stats,
    }
