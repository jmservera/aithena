"""Tests for the safe_numeric utility and its integration with Solr response parsing."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest
from utils import safe_numeric

# ---------------------------------------------------------------------------
# safe_numeric — unit tests
# ---------------------------------------------------------------------------


class TestSafeNumericFloat:
    """Default type_fn=float behaviour."""

    def test_converts_int(self) -> None:
        assert safe_numeric(42) == 42.0

    def test_converts_float(self) -> None:
        assert safe_numeric(3.14) == 3.14

    def test_converts_string_int(self) -> None:
        assert safe_numeric("42") == 42.0

    def test_converts_string_float(self) -> None:
        assert safe_numeric("3.14") == 3.14

    def test_returns_default_for_none(self) -> None:
        assert safe_numeric(None) == 0

    def test_returns_default_for_empty_string(self) -> None:
        assert safe_numeric("") == 0

    def test_returns_default_for_non_numeric_string(self) -> None:
        assert safe_numeric("not-a-number") == 0

    def test_returns_custom_default(self) -> None:
        assert safe_numeric(None, default=-1) == -1

    def test_returns_default_for_dict(self) -> None:
        assert safe_numeric({"unexpected": True}) == 0

    def test_returns_default_for_list(self) -> None:
        assert safe_numeric([1, 2]) == 0

    def test_handles_negative_string(self) -> None:
        assert safe_numeric("-5.5") == -5.5

    def test_handles_zero_string(self) -> None:
        assert safe_numeric("0") == 0.0

    def test_handles_zero(self) -> None:
        assert safe_numeric(0) == 0.0


class TestSafeNumericInt:
    """type_fn=int behaviour."""

    def test_converts_int(self) -> None:
        assert safe_numeric(42, int) == 42

    def test_converts_float_to_int(self) -> None:
        assert safe_numeric(3.9, int) == 3

    def test_converts_string_int(self) -> None:
        assert safe_numeric("42", int) == 42

    def test_string_float_raises_for_plain_int(self) -> None:
        # int("3.14") raises ValueError — safe_numeric should return default
        assert safe_numeric("3.14", int) == 0

    def test_returns_default_for_none(self) -> None:
        assert safe_numeric(None, int) == 0

    def test_returns_default_for_garbage(self) -> None:
        assert safe_numeric("abc", int) == 0


class TestSafeNumericCustomTypeFn:
    """Custom callables as type_fn (e.g. lambda v: int(float(v)))."""

    def test_int_via_float_on_string(self) -> None:
        assert safe_numeric("3.14", lambda v: int(float(v))) == 3

    def test_round_via_float_on_string(self) -> None:
        assert safe_numeric("42.7", lambda v: round(float(v))) == 43

    def test_custom_fn_returns_default_on_failure(self) -> None:
        assert safe_numeric("bad", lambda v: int(float(v))) == 0


# ---------------------------------------------------------------------------
# Integration: parse_stats_response with various Solr value types
# ---------------------------------------------------------------------------

from search_service import (  # noqa: E402
    build_pagination,
    parse_facet_counts,
    parse_stats_response,
)


class TestParseStatsResponseCoercion:
    """Verify parse_stats_response handles string, int, float, None stats values."""

    @pytest.fixture()
    def base_payload(self) -> dict:
        return {
            "grouped": {"parent_id_s": {"matches": 10, "ngroups": 5, "groups": []}},
            "facet_counts": {"facet_fields": {}},
        }

    def test_native_float_values(self, base_payload: dict) -> None:
        base_payload["stats"] = {
            "stats_fields": {
                "page_count_i": {"min": 1.0, "max": 800.0, "sum": 12000.0, "mean": 157.89}
            }
        }
        result = parse_stats_response(base_payload)
        assert result["page_stats"] == {"total": 12000, "avg": 158, "min": 1, "max": 800}

    def test_native_int_values(self, base_payload: dict) -> None:
        base_payload["stats"] = {
            "stats_fields": {
                "page_count_i": {"min": 1, "max": 800, "sum": 12000, "mean": 158}
            }
        }
        result = parse_stats_response(base_payload)
        assert result["page_stats"] == {"total": 12000, "avg": 158, "min": 1, "max": 800}

    def test_string_values(self, base_payload: dict) -> None:
        base_payload["stats"] = {
            "stats_fields": {
                "page_count_i": {"min": "10", "max": "200", "sum": "500", "mean": "42.5"}
            }
        }
        result = parse_stats_response(base_payload)
        assert result["page_stats"] == {"total": 500, "avg": 42, "min": 10, "max": 200}

    def test_none_values(self, base_payload: dict) -> None:
        base_payload["stats"] = {
            "stats_fields": {
                "page_count_i": {"min": None, "max": None, "sum": None, "mean": None}
            }
        }
        result = parse_stats_response(base_payload)
        assert result["page_stats"] == {"total": 0, "avg": 0, "min": 0, "max": 0}

    def test_missing_stats_fields(self, base_payload: dict) -> None:
        result = parse_stats_response(base_payload)
        assert result["page_stats"] == {"total": 0, "avg": 0, "min": 0, "max": 0}

    def test_null_page_count_stats_block(self, base_payload: dict) -> None:
        base_payload["stats"] = {"stats_fields": {"page_count_i": None}}
        result = parse_stats_response(base_payload)
        assert result["page_stats"] == {"total": 0, "avg": 0, "min": 0, "max": 0}

    def test_string_ngroups(self) -> None:
        payload = {
            "grouped": {"parent_id_s": {"matches": "10", "ngroups": "5", "groups": []}},
            "facet_counts": {"facet_fields": {}},
        }
        result = parse_stats_response(payload)
        assert result["total_books"] == 5

    def test_string_matches_fallback(self) -> None:
        payload = {
            "grouped": {"parent_id_s": {"matches": "7", "groups": []}},
            "facet_counts": {"facet_fields": {}},
        }
        result = parse_stats_response(payload)
        assert result["total_books"] == 7

    def test_non_numeric_ngroups_returns_zero(self) -> None:
        payload = {
            "grouped": {"parent_id_s": {"ngroups": "NaN", "groups": []}},
            "facet_counts": {"facet_fields": {}},
        }
        result = parse_stats_response(payload)
        assert result["total_books"] == 0

    def test_mixed_types_in_stats(self, base_payload: dict) -> None:
        """Some fields string, some float, some int — should all work."""
        base_payload["stats"] = {
            "stats_fields": {
                "page_count_i": {"min": 1, "max": "800", "sum": 12000.0, "mean": "157.89"}
            }
        }
        result = parse_stats_response(base_payload)
        assert result["page_stats"] == {"total": 12000, "avg": 158, "min": 1, "max": 800}


class TestParseFacetCountsCoercion:
    """Verify facet count values are coerced to int."""

    def test_string_facet_counts(self) -> None:
        payload = {
            "facet_counts": {
                "facet_fields": {
                    "author_s": ["Joan Amades", "15", "Other Author", "5"],
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
        assert facets["author"] == [
            {"value": "Joan Amades", "count": 15},
            {"value": "Other Author", "count": 5},
        ]

    def test_int_facet_counts(self) -> None:
        payload = {
            "facet_counts": {
                "facet_fields": {
                    "author_s": ["Author A", 10],
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
        assert facets["author"] == [{"value": "Author A", "count": 10}]


class TestBuildPaginationCoercion:
    """Verify build_pagination handles string numFound values."""

    def test_string_num_found(self) -> None:
        result = build_pagination("100", 1, 20)
        assert result["total"] == 100
        assert result["total_results"] == 100
        assert result["total_pages"] == 5

    def test_none_num_found(self) -> None:
        result = build_pagination(None, 1, 20)
        assert result["total"] == 0
        assert result["total_results"] == 0
        assert result["total_pages"] == 0

    def test_int_num_found(self) -> None:
        result = build_pagination(50, 1, 20)
        assert result["total"] == 50
        assert result["total_pages"] == 3

    def test_float_num_found(self) -> None:
        result = build_pagination(50.0, 1, 20)
        assert result["total"] == 50
        assert result["total_pages"] == 3
