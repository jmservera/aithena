from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from search_service import (  # noqa: E402
    SOLR_FIELD_LIST,
    build_filter_queries,
    build_inline_content_disposition,
    build_pagination,
    build_solr_params,
    build_sort_clause,
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
        "series_s",
        "folder_path_s",
    ]
    assert params["hl.fl"] == "content,_text_"


def test_build_solr_params_excludes_chunks_by_default() -> None:
    """Even with no user filters, chunk docs must be excluded from keyword search."""
    params = build_solr_params(
        query="test",
        page=1,
        page_size=10,
        sort_by="score",
        sort_order="desc",
        facet_limit=5,
    )
    assert "-parent_id_s:[* TO *]" in params["fq"]


def test_parse_facet_counts_prefers_detected_language_buckets() -> None:
    payload = {
        "facet_counts": {
            "facet_fields": {
                "author_s": ["Author One", 2],
                "category_s": ["Folklore", 4],
                "year_i": [1901, 1],
                "language_detected_s": ["ca", 3],
                "language_s": ["en", 2],
                "series_s": ["Foundation", 5],
            }
        }
    }

    facets = parse_facet_counts(payload)

    assert facets["author"] == [{"value": "Author One", "count": 2}]
    assert facets["category"] == [{"value": "Folklore", "count": 4}]
    assert facets["year"] == [{"value": 1901, "count": 1}]
    assert facets["language"] == [{"value": "ca", "count": 3}]
    assert facets["series"] == [{"value": "Foundation", "count": 5}]


def test_build_filter_queries_supports_language_fallback_and_exact_matches() -> None:
    filters = build_filter_queries({"author": "Joan Amades", "language": "ca", "year": "1950"})

    assert filters == [
        r"author_s:Joan\ Amades",
        "(language_detected_s:ca OR language_s:ca)",
        "year_i:1950",
    ]


def test_build_filter_queries_supports_series_filter() -> None:
    filters = build_filter_queries({"series": "Foundation"})

    assert filters == ["series_s:Foundation"]


def test_build_sort_clause_title_asc() -> None:
    result = build_sort_clause(sort="title asc")
    assert result == "title_s asc"


def test_build_sort_clause_year_desc() -> None:
    result = build_sort_clause(sort="year desc")
    assert result == "year_i desc"


def test_build_sort_clause_invalid_format() -> None:
    import pytest

    with pytest.raises(ValueError, match="Unsupported sort value"):
        build_sort_clause(sort="invalid")


def test_parse_facet_counts_series_empty_bucket() -> None:
    """Series facet returns empty list when Solr returns an empty bucket."""
def test_build_filter_queries_supports_folder_filter() -> None:
    filters = build_filter_queries({"folder": "en/Science Fiction"})

    assert filters == [r"folder_path_s:en\/Science\ Fiction"]


def test_build_filter_queries_folder_with_special_chars() -> None:
    filters = build_filter_queries({"folder": 'es/Ciencia Ficción'})

    assert filters == [r"folder_path_s:es\/Ciencia\ Ficción"]


def test_parse_facet_counts_includes_folder_facet() -> None:
    payload = {
        "facet_counts": {
            "facet_fields": {
                "author_s": ["Author One", 2],
                "category_s": ["Folklore", 4],
                "year_i": [1901, 1],
                "language_detected_s": ["ca", 3],
                "language_s": [],
                "series_s": [],
                "folder_path_s": [
                    "en/Science Fiction", 125,
                    "en/History", 89,
                    "es/Ciencia Ficción", 47,
                ],
            }
        }
    }

    facets = parse_facet_counts(payload)
    assert facets["folder"] == [
        {"value": "en/Science Fiction", "count": 125},
        {"value": "en/History", "count": 89},
        {"value": "es/Ciencia Ficción", "count": 47},
    ]
    assert facets["author"] == [{"value": "Author One", "count": 2}]
    assert facets["series"] == []


def test_parse_facet_counts_series_absent_from_response() -> None:
    """Series facet returns empty list when series_s is absent from the Solr response."""
    payload = {
        "facet_counts": {
            "facet_fields": {
                "author_s": ["Author One", 2],
                "category_s": [],
                "year_i": [],
                "language_detected_s": [],
                "language_s": [],
            }
        }
    }

    facets = parse_facet_counts(payload)
    assert facets["series"] == []


def test_parse_facet_counts_folder_empty_when_no_values() -> None:
    payload = {
        "facet_counts": {
            "facet_fields": {
                "author_s": [],
                "category_s": [],
                "year_i": [],
                "language_detected_s": [],
                "language_s": [],
                "series_s": [],
                "folder_path_s": [],
            }
        }
    }

    facets = parse_facet_counts(payload)
    assert facets["folder"] == []
    assert facets["series"] == []


def test_normalize_book_series_none_when_absent() -> None:
    book = normalize_book(
        {
            "id": "doc_no_series",
            "title_s": "Standalone Book",
            "author_s": "Author",
            "file_path_s": "books/standalone.pdf",
            "score": 5.0,
        },
        {},
        None,
    )

    assert book["series"] is None


def test_solr_escape_handles_folder_path_characters() -> None:
    assert solr_escape("en/Science Fiction") == r"en\/Science\ Fiction"
    assert solr_escape('es/Ciencia Ficción') == r"es\/Ciencia\ Ficción"
    assert solr_escape("") == ""
    assert solr_escape('path/with "quotes"') == r'path\/with\ \"quotes\"'


def test_normalize_book_collects_fields_and_highlights() -> None:
    book = normalize_book(
        {
            "id": "abc123",
            "title_s": "Rondalles",
            "author_s": "Amades",
            "year_i": 1950,
            "category_s": "Folklore",
            "language_s": "ca",
            "series_s": "Catalan Tales",
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
        "series": "Catalan Tales",
        "file_path": "amades/rondalles.pdf",
        "folder_path": "amades",
        "page_count": 320,
        "file_size": 4096,
        "pages": None,
        "is_chunk": False,
        "chunk_text": None,
        "page_start": None,
        "page_end": None,
        "score": 12.5,
        "highlights": ["<em>folk</em> story", "second snippet"],
        "document_url": "/documents/token",
        "thumbnail_url": None,
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
    assert "author_s:Amades" in params["fq"]


def test_build_knn_params_does_not_exclude_chunks() -> None:
    """kNN must search chunk docs because that's where embeddings live."""
    params = build_knn_params([0.1], top_k=5, knn_field="embedding_v")
    assert "fq" not in params
    params_with_filter = build_knn_params([0.1], top_k=5, knn_field="embedding_v", filters=["author_s:X"])
    for fq in params_with_filter["fq"]:
        assert "parent_id_s" not in fq


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
        "grouped": {
            "parent_id_s": {
                "matches": 76,
                "ngroups": 3,
                "groups": [],
            }
        },
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

    assert result["total_books"] == 3
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
        "grouped": {"parent_id_s": {"matches": 0, "ngroups": 0, "groups": []}},
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
        "grouped": {"parent_id_s": {"matches": 5, "ngroups": 2, "groups": []}},
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

    assert result["total_books"] == 2
    assert result["by_author"] == [{"value": "Author A", "count": 5}]
    assert result["page_stats"] == {"total": 0, "avg": 0, "min": 0, "max": 0}


def test_parse_stats_response_rounds_average() -> None:
    payload = {
        "grouped": {"parent_id_s": {"matches": 3, "ngroups": 1, "groups": []}},
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


# ---------------------------------------------------------------------------
# Issue #653 — Folder facet edge-case tests
# ---------------------------------------------------------------------------

from search_service import EXCLUDE_CHUNKS_FQ, FACET_FIELDS  # noqa: E402


def test_build_filter_queries_empty_folder_path_skipped() -> None:
    """An empty-string folder filter should be silently skipped."""
    queries = build_filter_queries({"folder": ""})
    assert queries == []


def test_build_filter_queries_whitespace_only_folder_skipped() -> None:
    """A whitespace-only folder filter should be silently skipped."""
    queries = build_filter_queries({"folder": "   "})
    assert queries == []


def test_build_filter_queries_deeply_nested_folder() -> None:
    """Deeply nested paths like a/b/c/d have every slash escaped."""
    queries = build_filter_queries({"folder": "a/b/c/d"})
    assert queries == [r"folder_path_s:a\/b\/c\/d"]


def test_build_filter_queries_folder_with_double_quotes() -> None:
    """Double quotes in folder names must be escaped for Solr."""
    queries = build_filter_queries({"folder": 'books/"special" edition'})
    assert queries == [r'folder_path_s:books\/\"special\"\ edition']


def test_build_filter_queries_folder_with_parentheses_and_colon() -> None:
    """Parentheses and colons are Lucene special chars and must be escaped."""
    queries = build_filter_queries({"folder": "en/Science (2024): Vol 1"})
    assert queries == [r"folder_path_s:en\/Science\ \(2024\)\:\ Vol\ 1"]


def test_build_filter_queries_folder_with_cjk_characters() -> None:
    """CJK (Chinese, Japanese, Korean) characters should pass through unescaped."""
    queries = build_filter_queries({"folder": "日本語/科学"})
    assert queries == [r"folder_path_s:日本語\/科学"]


def test_build_filter_queries_folder_with_arabic_characters() -> None:
    """Arabic characters should pass through unescaped."""
    queries = build_filter_queries({"folder": "كتب/علوم"})
    assert queries == [r"folder_path_s:كتب\/علوم"]


def test_build_filter_queries_folder_combined_with_other_filters() -> None:
    """Folder filter works alongside author and category filters."""
    queries = build_filter_queries({"author": "Amades", "folder": "ca/Folklore", "category": "History"})
    assert "author_s:Amades" in queries
    assert r"folder_path_s:ca\/Folklore" in queries
    assert "category_s:History" in queries
    assert len(queries) == 3


def test_build_filter_queries_unsupported_filter_raises() -> None:
    """An unknown filter name must raise ValueError."""
    import pytest

    with pytest.raises(ValueError, match="Unsupported filter field"):
        build_filter_queries({"unknown_field": "value"})


def test_parse_facet_counts_deeply_nested_folder_paths() -> None:
    """Folders with deeply nested paths (a/b/c/d/e) parse correctly."""
    payload = {
        "facet_counts": {
            "facet_fields": {
                "author_s": [],
                "category_s": [],
                "year_i": [],
                "language_detected_s": [],
                "language_s": [],
                "series_s": [],
                "folder_path_s": [
                    "a/b/c/d/e", 10,
                    "x/y/z", 5,
                ],
            }
        }
    }
    facets = parse_facet_counts(payload)
    assert facets["folder"] == [
        {"value": "a/b/c/d/e", "count": 10},
        {"value": "x/y/z", "count": 5},
    ]


def test_parse_facet_counts_folder_with_utf8_paths() -> None:
    """UTF-8 folder names (CJK, accented, Cyrillic) are preserved as-is."""
    payload = {
        "facet_counts": {
            "facet_fields": {
                "author_s": [],
                "category_s": [],
                "year_i": [],
                "language_detected_s": [],
                "language_s": [],
                "series_s": [],
                "folder_path_s": [
                    "日本語/科学", 8,
                    "Ελληνικά/Ιστορία", 3,
                    "Русский/Наука", 2,
                ],
            }
        }
    }
    facets = parse_facet_counts(payload)
    assert facets["folder"] == [
        {"value": "日本語/科学", "count": 8},
        {"value": "Ελληνικά/Ιστορία", "count": 3},
        {"value": "Русский/Наука", "count": 2},
    ]


def test_parse_facet_counts_folder_path_s_missing_from_response() -> None:
    """When Solr omits folder_path_s entirely, folder facet is an empty list."""
    payload = {
        "facet_counts": {
            "facet_fields": {
                "author_s": ["Author", 1],
                "category_s": [],
                "year_i": [],
                "language_detected_s": [],
                "language_s": [],
                "series_s": [],
            }
        }
    }
    facets = parse_facet_counts(payload)
    assert facets["folder"] == []


def test_parse_facet_counts_single_folder_entry() -> None:
    """A single folder entry parses into a one-element list."""
    payload = {
        "facet_counts": {
            "facet_fields": {
                "author_s": [],
                "category_s": [],
                "year_i": [],
                "language_detected_s": [],
                "language_s": [],
                "series_s": [],
                "folder_path_s": ["root_folder", 42],
            }
        }
    }
    facets = parse_facet_counts(payload)
    assert facets["folder"] == [{"value": "root_folder", "count": 42}]


def test_parse_facet_counts_folder_with_spaces_in_name() -> None:
    """Folder names with spaces are preserved verbatim in facet values."""
    payload = {
        "facet_counts": {
            "facet_fields": {
                "author_s": [],
                "category_s": [],
                "year_i": [],
                "language_detected_s": [],
                "language_s": [],
                "series_s": [],
                "folder_path_s": ["My Books/Science Fiction", 15],
            }
        }
    }
    facets = parse_facet_counts(payload)
    assert facets["folder"] == [{"value": "My Books/Science Fiction", "count": 15}]


def test_solr_escape_deeply_nested_path() -> None:
    assert solr_escape("a/b/c/d/e") == r"a\/b\/c\/d\/e"


def test_solr_escape_path_with_parentheses() -> None:
    assert solr_escape("books (2024)/vol 1") == r"books\ \(2024\)\/vol\ 1"


def test_solr_escape_cjk_characters_unchanged() -> None:
    assert solr_escape("日本語") == "日本語"


def test_solr_escape_mixed_utf8_and_special() -> None:
    """Mix of UTF-8 and Lucene special characters."""
    assert solr_escape("カテゴリ/テスト (1)") == r"カテゴリ\/テスト\ \(1\)"


def test_facet_fields_includes_folder_mapping() -> None:
    """Verify FACET_FIELDS maps 'folder' to 'folder_path_s'."""
    assert "folder" in FACET_FIELDS
    assert FACET_FIELDS["folder"] == ("folder_path_s",)


def test_solr_field_list_includes_chunk_fields() -> None:
    """SOLR_FIELD_LIST must include chunk_text_t and parent_id_s for chunk support."""
    assert "chunk_text_t" in SOLR_FIELD_LIST
    assert "parent_id_s" in SOLR_FIELD_LIST


def test_normalize_book_includes_folder_path() -> None:
    """normalize_book extracts folder_path from folder_path_s."""
    book = normalize_book(
        {
            "id": "doc_with_folder",
            "title_s": "Folder Test",
            "file_path_s": "en/Science Fiction/test.pdf",
            "folder_path_s": "en/Science Fiction",
            "score": 1.0,
        },
        {},
        None,
    )
    assert book["folder_path"] == "en/Science Fiction"


def test_normalize_book_folder_path_none_when_absent() -> None:
    """folder_path is None when folder_path_s is absent from the Solr document."""
    book = normalize_book(
        {
            "id": "doc_no_folder",
            "title_s": "No Folder",
            "file_path_s": "test.pdf",
            "score": 1.0,
        },
        {},
        None,
    )
    assert book["folder_path"] is None


def test_normalize_book_chunk_document_has_is_chunk_and_text() -> None:
    """Chunk documents (with parent_id_s) set is_chunk=True and extract chunk_text."""
    book = normalize_book(
        {
            "id": "chunk_abc",
            "title_s": "My Book",
            "author_s": "Author",
            "file_path_s": "books/my_book.pdf",
            "parent_id_s": "parent_abc",
            "chunk_text_t": "This is the chunk text content from pages 5 to 6.",
            "page_start_i": 5,
            "page_end_i": 6,
            "score": 9.0,
        },
        {},
        "/documents/token",
    )
    assert book["is_chunk"] is True
    assert book["chunk_text"] == "This is the chunk text content from pages 5 to 6."
    assert book["page_start"] == 5
    assert book["page_end"] == 6
    assert book["pages"] == [5, 6]


def test_normalize_book_parent_document_has_is_chunk_false() -> None:
    """Parent documents (no parent_id_s) set is_chunk=False and chunk_text=None."""
    book = normalize_book(
        {
            "id": "parent_doc",
            "title_s": "Full Book",
            "author_s": "Author",
            "file_path_s": "books/full.pdf",
            "page_count_i": 200,
            "score": 5.0,
        },
        {},
        "/documents/token",
    )
    assert book["is_chunk"] is False
    assert book["chunk_text"] is None
    assert book["page_start"] is None
    assert book["page_end"] is None


def test_normalize_book_chunk_without_chunk_text() -> None:
    """Chunk with parent_id_s but missing chunk_text_t still sets is_chunk=True."""
    book = normalize_book(
        {
            "id": "chunk_no_text",
            "title_s": "My Book",
            "file_path_s": "books/my_book.pdf",
            "parent_id_s": "parent_xyz",
            "page_start_i": 10,
            "page_end_i": 11,
            "score": 3.0,
        },
        {},
        None,
    )
    assert book["is_chunk"] is True
    assert book["chunk_text"] is None
    assert book["page_start"] == 10
    assert book["page_end"] == 11


# ---------------------------------------------------------------------------
# Retro Action R5 — Semantic search on chunk embeddings
# ---------------------------------------------------------------------------


def test_keyword_search_excludes_chunks_semantic_does_not() -> None:
    """Keyword queries use EXCLUDE_CHUNKS_FQ; kNN queries must NOT.

    This is the core data model invariant:
    - Parent documents hold metadata (title, author, year, etc.)
    - Chunk documents hold text + embedding_v vectors
    - Keyword search must exclude chunks to avoid duplicates
    - kNN search must include chunks because that's where embeddings live
    """
    kw_params = build_solr_params(
        query="test", page=1, page_size=10, sort_by="score",
        sort_order="desc", facet_limit=5,
    )
    assert EXCLUDE_CHUNKS_FQ in kw_params["fq"], "Keyword search must exclude chunks"

    knn_params = build_knn_params([0.1, 0.2], top_k=5, knn_field="embedding_v")
    assert "fq" not in knn_params, "kNN search must NOT exclude chunks"


def test_knn_params_with_folder_filter_does_not_exclude_chunks() -> None:
    """Even with folder filters, kNN must not add chunk exclusion."""
    folder_fq = build_filter_queries({"folder": "en/Science"})
    params = build_knn_params([0.1], top_k=5, knn_field="embedding_v", filters=folder_fq)
    for fq_clause in params.get("fq", []):
        assert "parent_id_s" not in fq_clause, \
            f"kNN filter query must not reference parent_id_s: {fq_clause}"


def test_rrf_deduplicates_by_document_id() -> None:
    """RRF merges identical docs from keyword and semantic legs by 'id'.

    In the chunk-based model, kNN returns chunk IDs while keyword returns
    parent IDs. The caller (main.py) normalizes both to book-level dicts
    before RRF. This test confirms RRF correctly merges matching IDs.
    """
    kw_results = [
        {"id": "book_A", "title": "Book A", "score": 10.0},
        {"id": "book_B", "title": "Book B", "score": 8.0},
    ]
    sem_results = [
        {"id": "book_A", "title": "Book A", "score": 0.95},
        {"id": "book_C", "title": "Book C", "score": 0.80},
    ]
    fused = reciprocal_rank_fusion(kw_results, sem_results, k=60)

    fused_ids = [d["id"] for d in fused]
    assert len(fused_ids) == len(set(fused_ids)), "RRF must not produce duplicate IDs"
    assert "book_A" in fused_ids
    assert "book_B" in fused_ids
    assert "book_C" in fused_ids
    assert fused[0]["id"] == "book_A", "Shared doc should rank first"


def test_knn_params_include_chunk_relevant_fields() -> None:
    """kNN field list includes parent_id_s-related fields so chunks can be resolved."""

    params = build_knn_params([0.1], top_k=5, knn_field="embedding_v")
    fl_fields = params["fl"].split(",")
    assert "id" in fl_fields
    assert "title_s" in fl_fields
    assert "file_path_s" in fl_fields
    assert "score" in fl_fields


def test_rrf_chunk_dedup_scenario() -> None:
    """Simulate the real-world scenario where kNN returns chunks and keyword
    returns parent docs. After normalize_book() the caller passes book-level
    dicts to RRF. Chunks from the same parent that map to the same book ID
    should not cause duplicates.
    """
    kw_books = [
        {"id": "parent_1", "title": "Rondalles", "score": 12.0, "highlights": ["folk"]},
        {"id": "parent_2", "title": "History", "score": 8.0, "highlights": ["medieval"]},
    ]
    sem_books = [
        {"id": "parent_1", "title": "Rondalles", "score": 0.92, "highlights": []},
        {"id": "parent_3", "title": "Science", "score": 0.85, "highlights": []},
    ]

    fused = reciprocal_rank_fusion(kw_books, sem_books, k=60)

    ids = [d["id"] for d in fused]
    assert ids.count("parent_1") == 1, "Shared parent must appear exactly once"
    assert set(ids) == {"parent_1", "parent_2", "parent_3"}
    # Shared doc gets contributions from both legs → highest score
    assert fused[0]["id"] == "parent_1"
    # Keyword highlights are preserved for shared docs
    assert fused[0]["highlights"] == ["folk"]


# ---------------------------------------------------------------------------
# Wave 1 — Additional chunk text preview edge cases (#813)
# ---------------------------------------------------------------------------


def test_normalize_book_empty_chunk_text_returns_empty_string() -> None:
    """Chunk document where chunk_text_t is an empty string (not missing)."""
    book = normalize_book(
        {
            "id": "chunk_empty",
            "title_s": "My Book",
            "file_path_s": "books/my_book.pdf",
            "parent_id_s": "parent_xyz",
            "chunk_text_t": "",
            "page_start_i": 1,
            "page_end_i": 1,
            "score": 2.0,
        },
        {},
        None,
    )
    assert book["is_chunk"] is True
    assert book["chunk_text"] == ""


def test_normalize_book_very_short_chunk_text() -> None:
    """Chunk with a single-word chunk_text_t."""
    book = normalize_book(
        {
            "id": "chunk_short",
            "title_s": "Tiny Chunk Book",
            "file_path_s": "books/tiny.pdf",
            "parent_id_s": "parent_short",
            "chunk_text_t": "Hello",
            "page_start_i": 3,
            "page_end_i": 3,
            "score": 1.0,
        },
        {},
        "/documents/tok",
    )
    assert book["is_chunk"] is True
    assert book["chunk_text"] == "Hello"
    assert book["pages"] == [3, 3]


def test_normalize_book_minimal_document_no_fields() -> None:
    """Document with only 'id' set — all optional fields fall back to defaults."""
    book = normalize_book({"id": "bare_doc", "score": 0.5}, {}, None)
    assert book["id"] == "bare_doc"
    assert book["title"] == ""  # Path("").stem
    assert book["author"] == "Unknown"
    assert book["year"] is None
    assert book["category"] is None
    assert book["language"] is None
    assert book["series"] is None
    assert book["pages"] is None
    assert book["is_chunk"] is False
    assert book["chunk_text"] is None
    assert book["page_start"] is None
    assert book["page_end"] is None
    assert book["document_url"] is None


def test_normalize_book_thumbnail_url_present() -> None:
    """normalize_book extracts thumbnail_url from thumbnail_url_s."""
    book = normalize_book(
        {
            "id": "thumb1",
            "title_s": "With Thumb",
            "file_path_s": "books/thumb.pdf",
            "thumbnail_url_s": "https://covers.example.com/thumb.jpg",
            "score": 1.0,
        },
        {},
        None,
    )
    assert book["thumbnail_url"] == "https://covers.example.com/thumb.jpg"


def test_normalize_book_thumbnail_url_none_when_absent() -> None:
    """normalize_book returns None for thumbnail_url when field is missing."""
    book = normalize_book(
        {
            "id": "no_thumb",
            "title_s": "No Thumb",
            "file_path_s": "books/nothumb.pdf",
            "score": 1.0,
        },
        {},
        None,
    )
    assert book["thumbnail_url"] is None


def test_normalize_book_parent_id_ignores_chunk_text() -> None:
    """Parent doc with stray chunk_text_t should NOT return chunk_text."""
    book = normalize_book(
        {
            "id": "parent_stray",
            "title_s": "Stray Fields",
            "file_path_s": "books/stray.pdf",
            "chunk_text_t": "should be ignored",
            "score": 1.0,
        },
        {},
        None,
    )
    assert book["is_chunk"] is False
    assert book["chunk_text"] is None


def test_solr_field_list_includes_page_range_fields() -> None:
    """SOLR_FIELD_LIST must include page_start_i and page_end_i for chunk page support."""
    assert "page_start_i" in SOLR_FIELD_LIST
    assert "page_end_i" in SOLR_FIELD_LIST


def test_solr_field_list_includes_score() -> None:
    """SOLR_FIELD_LIST must include 'score' for relevance ranking."""
    assert "score" in SOLR_FIELD_LIST
