"""App-side cosine reranking for hybrid-rerank search architecture.

When SEARCH_ARCHITECTURE=hybrid-rerank, there is no HNSW index. Instead,
BM25 retrieves candidate documents, stored vectors are fetched from Solr,
and this module computes cosine similarity for RRF fusion.
"""

from __future__ import annotations

import math
from typing import Any


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Returns 0.0 if vectors differ in length or either is zero-norm.
    """
    if len(a) != len(b):
        return 0.0
    norm_a = _norm(a)
    norm_b = _norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return _dot(a, b) / (norm_a * norm_b)


def cosine_rerank(
    query_vector: list[float],
    doc_vectors: list[tuple[str, list[float]]],
) -> list[tuple[str, float]]:
    """Rank documents by cosine similarity to the query vector.

    Args:
        query_vector: The query embedding.
        doc_vectors: List of (doc_id, embedding) pairs.

    Returns:
        List of (doc_id, similarity_score) sorted by descending similarity.
    """
    query_norm = _norm(query_vector)
    if query_norm == 0.0:
        return [(doc_id, 0.0) for doc_id, _ in doc_vectors]

    scored = []
    for doc_id, vec in doc_vectors:
        if len(vec) != len(query_vector):
            scored.append((doc_id, 0.0))
            continue
        doc_norm = _norm(vec)
        if doc_norm == 0.0:
            scored.append((doc_id, 0.0))
            continue
        score = _dot(query_vector, vec) / (query_norm * doc_norm)
        scored.append((doc_id, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def build_chunk_vector_params(
    parent_ids: list[str],
    embedding_field: str,
) -> dict[str, Any]:
    """Build Solr params to fetch the first chunk embedding for each parent book.

    Uses Solr grouping to get one chunk per parent, sorted by chunk_index
    so we always get the first chunk's embedding as the representative vector.
    """
    from search_service import solr_escape

    id_filter = " OR ".join('"' + solr_escape(pid) + '"' for pid in parent_ids)
    return {
        "q": f"parent_id_s:({id_filter})",
        "fl": f"parent_id_s,{embedding_field}",
        "rows": len(parent_ids),
        "sort": "chunk_index_i asc",
        "group": "true",
        "group.field": "parent_id_s",
        "group.limit": "1",
        "group.sort": "chunk_index_i asc",
        "wt": "json",
    }


def extract_grouped_vectors(
    solr_response: dict[str, Any],
    embedding_field: str,
) -> dict[str, list[float]]:
    """Extract parent_id → embedding from a grouped Solr response.

    Returns a dict mapping parent_id to the first chunk's embedding vector.
    """
    vectors: dict[str, list[float]] = {}
    grouped = solr_response.get("grouped", {}).get("parent_id_s", {})
    for group in grouped.get("groups", []):
        parent_id = group.get("groupValue")
        docs = group.get("doclist", {}).get("docs", [])
        if parent_id and docs:
            vec = docs[0].get(embedding_field)
            if vec and isinstance(vec, list):
                vectors[parent_id] = vec
    return vectors
