from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from search_service import (  # noqa: E402
    build_filter_queries,
    build_inline_content_disposition,
    build_pagination,
    build_solr_params,
    decode_document_token,
    encode_document_token,
    normalize_book,
    normalize_search_query,
    parse_facet_counts,
    resolve_document_path,
    solr_escape,
)


def test_build_solr_params_adds_pagination_sort_facets_and_highlights() -> None:
    params = build_solr_params(
        query="catalan folklore",
        page=3,
        page_size=25,
        sort_by="year",
        sort_order="asc",
        facet_limit=10,
    )

    assert params["q"] == "catalan folklore"
    assert params["start"] == 50
    assert params["rows"] == 25
    assert params["sort"] == "year_i asc"
    assert params["defType"] == "edismax"
    assert params["facet.field"] == [
        "author_s",
        "category_s",
        "year_i",
        "language_detected_s",
        "language_s",
    ]
    assert params["hl.fl"] == "content,_text_"


def test_parse_facet_counts_prefers_detected_language_buckets() -> None:
    payload = {
        "facet_counts": {
            "facet_fields": {
                "author_s": ["Author One", 2],
                "category_s": ["Folklore", 4],
                "year_i": [1901, 1],
                "language_detected_s": ["ca", 3],
                "language_s": ["en", 2],
            }
        }
    }

    facets = parse_facet_counts(payload)

    assert facets["author"] == [{"value": "Author One", "count": 2}]
    assert facets["category"] == [{"value": "Folklore", "count": 4}]
    assert facets["year"] == [{"value": 1901, "count": 1}]
    assert facets["language"] == [{"value": "ca", "count": 3}]


def test_build_filter_queries_supports_language_fallback_and_exact_matches() -> None:
    filters = build_filter_queries({"author": "Joan Amades", "language": "ca", "year": "1950"})

    assert filters == [
        r"author_s:Joan\ Amades",
        "(language_detected_s:ca OR language_s:ca)",
        "year_i:1950",
    ]


def test_normalize_book_collects_fields_and_highlights() -> None:
    book = normalize_book(
        {
            "id": "abc123",
            "title_s": "Rondalles",
            "author_s": "Amades",
            "year_i": 1950,
            "category_s": "Folklore",
            "language_s": "ca",
            "file_path_s": "amades/rondalles.pdf",
            "folder_path_s": "amades",
            "page_count_i": 320,
            "file_size_l": 4096,
            "score": 12.5,
        },
        {
            "abc123": {
                "content": ["<em>folk</em> story"],
                "_text_": ["<em>folk</em> story", "second snippet"],
            }
        },
        "/documents/token",
    )

    assert book == {
        "id": "abc123",
        "title": "Rondalles",
        "author": "Amades",
        "year": 1950,
        "category": "Folklore",
        "language": "ca",
        "file_path": "amades/rondalles.pdf",
        "folder_path": "amades",
        "page_count": 320,
        "file_size": 4096,
        "pages": None,
        "score": 12.5,
        "highlights": ["<em>folk</em> story", "second snippet"],
        "document_url": "/documents/token",
    }


def test_normalize_book_includes_page_range_for_chunk_hit() -> None:
    book = normalize_book(
        {
            "id": "chunk123",
            "title_s": "Rondalles",
            "author_s": "Amades",
            "year_i": 1950,
            "file_path_s": "amades/rondalles.pdf",
            "page_start_i": 5,
            "page_end_i": 6,
            "score": 8.0,
        },
        {},
        "/documents/token",
    )

    assert book["pages"] == [5, 6]


def test_normalize_book_pages_null_for_full_doc_hit() -> None:
    book = normalize_book(
        {
            "id": "doc1",
            "title_s": "Full Book",
            "file_path_s": "books/full.pdf",
            "score": 5.0,
        },
        {},
        "/documents/token",
    )

    assert book["pages"] is None


def test_normalize_book_single_page_chunk() -> None:
    book = normalize_book(
        {
            "id": "chunk_single",
            "title_s": "Single Page Chunk",
            "file_path_s": "books/doc.pdf",
            "page_start_i": 7,
            "page_end_i": 7,
            "score": 3.0,
        },
        {},
        None,
    )

    assert book["pages"] == [7, 7]


def test_normalize_book_page_start_only() -> None:
    book = normalize_book(
        {
            "id": "chunk_start_only",
            "title_s": "Partial Chunk",
            "file_path_s": "books/doc.pdf",
            "page_start_i": 10,
            "score": 2.0,
        },
        {},
        None,
    )

    assert book["pages"] == [10, 10]


def test_normalize_book_page_end_only() -> None:
    book = normalize_book(
        {
            "id": "chunk_end_only",
            "title_s": "Partial Chunk",
            "file_path_s": "books/doc.pdf",
            "page_end_i": 15,
            "score": 2.0,
        },
        {},
        None,
    )

    assert book["pages"] == [15, 15]


def test_document_tokens_round_trip_and_stay_under_base_path(tmp_path: Path) -> None:
    relative_path = "amades/rondalles.pdf"
    token = encode_document_token(relative_path)

    assert decode_document_token(token) == relative_path
    assert resolve_document_path(tmp_path, relative_path) == tmp_path / "amades" / "rondalles.pdf"


def test_resolve_document_path_rejects_traversal(tmp_path: Path) -> None:
    try:
        resolve_document_path(tmp_path, "../secret.pdf")
    except ValueError as exc:
        assert "Invalid document path" in str(exc)
    else:
        raise AssertionError("expected traversal path to be rejected")


def test_normalize_search_query_rejects_local_params() -> None:
    try:
        normalize_search_query("{!func}sum(1,1)")
    except ValueError as exc:
        assert "Local-parameter syntax" in str(exc)
    else:
        raise AssertionError("expected local params to be rejected")


def test_build_inline_content_disposition_sanitizes_newlines() -> None:
    header = build_inline_content_disposition("safe\nname.pdf")

    assert "\n" not in header
    assert header.startswith("inline; filename*=UTF-8''")


def test_build_pagination_handles_empty_results() -> None:
    assert build_pagination(0, page=1, page_size=20) == {
        "page": 1,
        "limit": 20,
        "page_size": 20,
        "total": 0,
        "total_results": 0,
        "total_pages": 0,
    }


# ---------------------------------------------------------------------------
# Phase 3 — Hybrid search helpers
# ---------------------------------------------------------------------------

from search_service import (  # noqa: E402
    build_knn_params,
    parse_stats_response,
    reciprocal_rank_fusion,
)


def test_build_knn_params_produces_correct_solr_query() -> None:
    vector = [0.1, 0.2, 0.3]
    params = build_knn_params(vector, top_k=5, knn_field="book_embedding")

    assert params["rows"] == 5
    assert params["q"] == "{!knn f=book_embedding topK=5}[0.1,0.2,0.3]"
    assert "id" in params["fl"]


def test_build_knn_params_custom_field() -> None:
    params = build_knn_params([0.5], top_k=3, knn_field="embedding_v", filters=["author_s:Amades"])
    assert "f=embedding_v" in params["q"]
    assert params["fq"] == ["author_s:Amades"]


def test_reciprocal_rank_fusion_empty_inputs() -> None:
    assert reciprocal_rank_fusion([], []) == []


def test_reciprocal_rank_fusion_keyword_only() -> None:
    docs = [{"id": "a", "score": 1.0}, {"id": "b", "score": 0.5}]
    fused = reciprocal_rank_fusion(docs, [])
    assert [d["id"] for d in fused] == ["a", "b"]


def test_reciprocal_rank_fusion_semantic_only() -> None:
    docs = [{"id": "x", "score": 0.9}, {"id": "y", "score": 0.7}]
    fused = reciprocal_rank_fusion([], docs)
    assert [d["id"] for d in fused] == ["x", "y"]


def test_reciprocal_rank_fusion_shared_doc_ranks_first() -> None:
    kw = [{"id": "shared", "score": 1.0}, {"id": "kw_only", "score": 0.5}]
    sem = [{"id": "shared", "score": 0.9}, {"id": "sem_only", "score": 0.7}]
    fused = reciprocal_rank_fusion(kw, sem)
    assert fused[0]["id"] == "shared"


def test_reciprocal_rank_fusion_scores_descending() -> None:
    kw = [{"id": f"k{i}", "score": 1.0} for i in range(5)]
    sem = [{"id": f"s{i}", "score": 0.9} for i in range(5)]
    fused = reciprocal_rank_fusion(kw, sem)
    scores = [d["score"] for d in fused]
    assert scores == sorted(scores, reverse=True)


def test_reciprocal_rank_fusion_rrf_score_overwrites_original_score() -> None:
    kw = [{"id": "doc1", "score": 99.9, "title": "My Book"}]
    fused = reciprocal_rank_fusion(kw, [])
    # RRF score is 1/(k+1) = 1/61 ≈ 0.016, not the original 99.9
    assert fused[0]["score"] < 1.0
    assert fused[0]["title"] == "My Book"


def test_reciprocal_rank_fusion_preserves_metadata() -> None:
    kw = [{"id": "doc1", "score": 1.0, "title": "My Book", "author": "Author A", "highlights": ["snippet"]}]
    fused = reciprocal_rank_fusion(kw, [])
    assert fused[0]["title"] == "My Book"
    assert fused[0]["author"] == "Author A"
    assert fused[0]["highlights"] == ["snippet"]


def test_solr_escape_handles_special_characters() -> None:
    assert solr_escape("id:with spaces") == r"id\:with\ spaces"
    assert solr_escape("simple") == "simple"
    assert solr_escape("path/to/file.pdf") == r"path\/to\/file.pdf"


# ---------------------------------------------------------------------------
# Phase 4 — Stats endpoint helpers
# ---------------------------------------------------------------------------


def test_parse_stats_response_extracts_all_fields() -> None:
    payload = {
        "response": {"numFound": 76, "docs": []},
        "stats": {
            "stats_fields": {
                "page_count_i": {
                    "min": 1.0,
                    "max": 800.0,
                    "sum": 12000.0,
                    "mean": 157.89,
                    "count": 76,
                    "missing": 0,
                }
            }
        },
        "facet_counts": {
            "facet_fields": {
                "author_s": ["Joan Amades", 15, "Other Author", 5],
                "category_s": ["Folklore", 40, "History", 10],
                "year_i": [1950, 3, 1960, 10],
                "language_detected_s": ["ca", 40, "es", 20],
            }
        },
    }

    result = parse_stats_response(payload)

    assert result["total_books"] == 76
    assert result["by_author"] == [{"value": "Joan Amades", "count": 15}, {"value": "Other Author", "count": 5}]
    assert result["by_category"] == [{"value": "Folklore", "count": 40}, {"value": "History", "count": 10}]
    assert result["by_year"] == [{"value": 1950, "count": 3}, {"value": 1960, "count": 10}]
    assert result["by_language"] == [{"value": "ca", "count": 40}, {"value": "es", "count": 20}]
    assert result["page_stats"]["total"] == 12000
    assert result["page_stats"]["min"] == 1
    assert result["page_stats"]["max"] == 800
    assert result["page_stats"]["avg"] == 158


def test_parse_stats_response_handles_empty_collection() -> None:
    payload = {
        "response": {"numFound": 0, "docs": []},
        "stats": {"stats_fields": {"page_count_i": None}},
        "facet_counts": {"facet_fields": {}},
    }

    result = parse_stats_response(payload)

    assert result["total_books"] == 0
    assert result["by_author"] == []
    assert result["by_category"] == []
    assert result["by_year"] == []
    assert result["by_language"] == []
    assert result["page_stats"] == {"total": 0, "avg": 0, "min": 0, "max": 0}


def test_parse_stats_response_handles_missing_stats_section() -> None:
    payload = {
        "response": {"numFound": 5, "docs": []},
        "facet_counts": {
            "facet_fields": {
                "author_s": ["Author A", 5],
                "category_s": [],
                "year_i": [],
                "language_detected_s": [],
            }
        },
    }

    result = parse_stats_response(payload)

    assert result["total_books"] == 5
    assert result["by_author"] == [{"value": "Author A", "count": 5}]
    assert result["page_stats"] == {"total": 0, "avg": 0, "min": 0, "max": 0}


def test_parse_stats_response_rounds_average() -> None:
    payload = {
        "response": {"numFound": 3, "docs": []},
        "stats": {
            "stats_fields": {
                "page_count_i": {
                    "min": 10.0,
                    "max": 100.0,
                    "sum": 165.0,
                    "mean": 55.0,
                }
            }
        },
        "facet_counts": {"facet_fields": {}},
    }

    result = parse_stats_response(payload)

    assert result["page_stats"]["avg"] == 55
    assert result["page_stats"]["total"] == 165
    assert result["page_stats"]["min"] == 10
    assert result["page_stats"]["max"] == 100
