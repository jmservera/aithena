from __future__ import annotations

from pathlib import Path
import sys

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
        "score": 12.5,
        "highlights": ["<em>folk</em> story", "second snippet"],
        "document_url": "/documents/token",
    }


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
    header = build_inline_content_disposition('safe\nname.pdf')

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
