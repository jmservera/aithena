"""Tests for ASCII folding configuration and Solr schema validation.

Issue #919 — validates diacritic-insensitive search feature.

Tests verify:
1. SOLR_ASCII_FOLDING environment variable is correctly parsed
2. Solr managed schemas have asciifolding filters in the correct field types
3. Filter ordering is correct (asciifolding after lowercase, before stemmers)
4. Both books and books_e5base schemas are consistent
"""

from __future__ import annotations

import importlib
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure config module is importable
sys.path.append(str(Path(__file__).resolve().parents[1]))

# Required env vars for config import
os.environ.setdefault("AUTH_DB_PATH", "/tmp/test-auth.db")  # noqa: S108
os.environ.setdefault("AUTH_JWT_SECRET", "test-secret-key-for-testing-only")
os.environ.setdefault("AUTH_JWT_TTL", "24h")
os.environ.setdefault("AUTH_COOKIE_NAME", "aithena_auth")

# Schema paths (relative to repo root)
REPO_ROOT = Path(__file__).resolve().parents[3]
BOOKS_SCHEMA = REPO_ROOT / "src" / "solr" / "books" / "managed-schema.xml"
E5BASE_SCHEMA = REPO_ROOT / "src" / "solr" / "books_e5base" / "managed-schema.xml"


# ---------------------------------------------------------------------------
# Schema parsing helpers
# ---------------------------------------------------------------------------


def _get_field_type_filters(schema_path: Path, field_type_name: str) -> list[tuple[str, list[str]]]:
    """Return list of (analyzer_type, [filter_names]) for a field type.

    For field types with a single <analyzer> (no type attr), returns [("default", [...])].
    For field types with index/query analyzers, returns [("index", [...]), ("query", [...])].
    For non-TextField types (e.g. StrField), returns [].
    """
    tree = ET.parse(schema_path)
    root = tree.getroot()

    for ft in root.findall(".//fieldType"):
        if ft.get("name") == field_type_name:
            analyzers = ft.findall("analyzer")
            if not analyzers:
                return []
            results = []
            for analyzer in analyzers:
                atype = analyzer.get("type", "default")
                filters = [f.get("name") for f in analyzer.findall("filter")]
                results.append((atype, filters))
            return results
    return []


def _has_asciifolding(schema_path: Path, field_type_name: str) -> bool:
    """Check if any analyzer in the field type has an asciifolding filter."""
    analyzers = _get_field_type_filters(schema_path, field_type_name)
    return any("asciifolding" in filters for _, filters in analyzers)


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


class TestASCIIFoldingConfig:
    """Test SOLR_ASCII_FOLDING configuration setting."""

    def _reload_config(self):
        """Reload config module to pick up env changes."""
        import config

        importlib.reload(config)
        return config

    def test_ascii_folding_enabled_by_default(self):
        """Unset SOLR_ASCII_FOLDING defaults to True."""
        env = os.environ.copy()
        env.pop("SOLR_ASCII_FOLDING", None)
        with patch.dict(os.environ, env, clear=True):
            config = self._reload_config()
            assert config.settings.ascii_folding is True

    def test_ascii_folding_true(self):
        """SOLR_ASCII_FOLDING=true sets ascii_folding to True."""
        with patch.dict(os.environ, {"SOLR_ASCII_FOLDING": "true"}, clear=False):
            config = self._reload_config()
            assert config.settings.ascii_folding is True

    def test_ascii_folding_false(self):
        """SOLR_ASCII_FOLDING=false sets ascii_folding to False."""
        with patch.dict(os.environ, {"SOLR_ASCII_FOLDING": "false"}, clear=False):
            config = self._reload_config()
            assert config.settings.ascii_folding is False

    def test_ascii_folding_case_insensitive_TRUE(self):
        """SOLR_ASCII_FOLDING=TRUE sets ascii_folding to True (case insensitive)."""
        with patch.dict(os.environ, {"SOLR_ASCII_FOLDING": "TRUE"}, clear=False):
            config = self._reload_config()
            assert config.settings.ascii_folding is True

    def test_ascii_folding_case_insensitive_False(self):
        """SOLR_ASCII_FOLDING=False sets ascii_folding to False (case insensitive)."""
        with patch.dict(os.environ, {"SOLR_ASCII_FOLDING": "False"}, clear=False):
            config = self._reload_config()
            assert config.settings.ascii_folding is False

    def test_ascii_folding_case_insensitive_mixed(self):
        """SOLR_ASCII_FOLDING=True sets ascii_folding to True (mixed case)."""
        with patch.dict(os.environ, {"SOLR_ASCII_FOLDING": "True"}, clear=False):
            config = self._reload_config()
            assert config.settings.ascii_folding is True


# ---------------------------------------------------------------------------
# Schema validation tests — books configset
# ---------------------------------------------------------------------------


class TestBooksSchemaASCIIFolding:
    """Validate asciifolding filter in books/managed-schema.xml."""

    @pytest.fixture(autouse=True)
    def _require_schema(self):
        if not BOOKS_SCHEMA.exists():
            pytest.skip(f"Schema not found: {BOOKS_SCHEMA}")

    def test_text_general_has_asciifolding(self):
        """text_general (used by _text_, content, title_t, author_t) has asciifolding."""
        analyzers = _get_field_type_filters(BOOKS_SCHEMA, "text_general")
        assert len(analyzers) == 2, "text_general should have index + query analyzers"
        for atype, filters in analyzers:
            assert "asciifolding" in filters, f"{atype} analyzer missing asciifolding"

    def test_text_en_has_asciifolding(self):
        """text_en has asciifolding in both analyzers."""
        analyzers = _get_field_type_filters(BOOKS_SCHEMA, "text_en")
        assert len(analyzers) == 2
        for atype, filters in analyzers:
            assert "asciifolding" in filters, f"{atype} analyzer missing asciifolding"

    def test_text_es_has_asciifolding(self):
        """text_es has asciifolding."""
        assert _has_asciifolding(BOOKS_SCHEMA, "text_es")

    def test_text_fr_has_asciifolding(self):
        """text_fr has asciifolding."""
        assert _has_asciifolding(BOOKS_SCHEMA, "text_fr")

    def test_text_ca_has_asciifolding(self):
        """text_ca has asciifolding."""
        assert _has_asciifolding(BOOKS_SCHEMA, "text_ca")

    def test_text_gen_sort_has_asciifolding(self):
        """text_gen_sort has asciifolding in both analyzers."""
        analyzers = _get_field_type_filters(BOOKS_SCHEMA, "text_gen_sort")
        assert len(analyzers) == 2
        for atype, filters in analyzers:
            assert "asciifolding" in filters, f"{atype} analyzer missing asciifolding"

    def test_text_general_rev_has_asciifolding(self):
        """text_general_rev has asciifolding in both analyzers."""
        analyzers = _get_field_type_filters(BOOKS_SCHEMA, "text_general_rev")
        assert len(analyzers) == 2
        for atype, filters in analyzers:
            assert "asciifolding" in filters, f"{atype} analyzer missing asciifolding"

    def test_string_does_not_have_asciifolding(self):
        """string (StrField) should NOT have asciifolding — exact match field."""
        assert not _has_asciifolding(BOOKS_SCHEMA, "string")

    def test_knn_vector_does_not_have_asciifolding(self):
        """knn_vector_512 should NOT have asciifolding — dense vector field."""
        assert not _has_asciifolding(BOOKS_SCHEMA, "knn_vector_512")

    def test_text_general_index_filter_ordering(self):
        """In text_general index analyzer: lowercase comes before asciifolding."""
        analyzers = _get_field_type_filters(BOOKS_SCHEMA, "text_general")
        index_filters = [f for atype, f in analyzers if atype == "index"][0]
        lc_idx = index_filters.index("lowercase")
        af_idx = index_filters.index("asciifolding")
        assert lc_idx < af_idx, f"lowercase ({lc_idx}) should precede asciifolding ({af_idx})"

    def test_text_en_index_filter_ordering(self):
        """In text_en index analyzer: lowercase -> asciifolding -> englishPossessive."""
        analyzers = _get_field_type_filters(BOOKS_SCHEMA, "text_en")
        index_filters = [f for atype, f in analyzers if atype == "index"][0]
        lc_idx = index_filters.index("lowercase")
        af_idx = index_filters.index("asciifolding")
        ep_idx = index_filters.index("englishPossessive")
        assert lc_idx < af_idx < ep_idx, (
            f"Expected lowercase({lc_idx}) < asciifolding({af_idx}) < englishPossessive({ep_idx})"
        )

    def test_text_es_filter_ordering(self):
        """In text_es: lowercase -> asciifolding -> stop -> spanishLightStem."""
        analyzers = _get_field_type_filters(BOOKS_SCHEMA, "text_es")
        filters = analyzers[0][1]  # single analyzer
        lc_idx = filters.index("lowercase")
        af_idx = filters.index("asciifolding")
        stem_idx = filters.index("spanishLightStem")
        assert lc_idx < af_idx < stem_idx

    def test_text_fr_filter_ordering(self):
        """In text_fr: elision -> lowercase -> asciifolding -> stop -> frenchLightStem."""
        analyzers = _get_field_type_filters(BOOKS_SCHEMA, "text_fr")
        filters = analyzers[0][1]
        el_idx = filters.index("elision")
        lc_idx = filters.index("lowercase")
        af_idx = filters.index("asciifolding")
        stem_idx = filters.index("frenchLightStem")
        assert el_idx < lc_idx < af_idx < stem_idx

    def test_text_ca_filter_ordering(self):
        """In text_ca: elision -> lowercase -> asciifolding -> stop -> snowballPorter."""
        analyzers = _get_field_type_filters(BOOKS_SCHEMA, "text_ca")
        filters = analyzers[0][1]
        el_idx = filters.index("elision")
        lc_idx = filters.index("lowercase")
        af_idx = filters.index("asciifolding")
        stem_idx = filters.index("snowballPorter")
        assert el_idx < lc_idx < af_idx < stem_idx


# ---------------------------------------------------------------------------
# Cross-configset consistency tests
# ---------------------------------------------------------------------------


class TestSchemaConsistency:
    """Both books and books_e5base should have identical text analyzer chains."""

    @pytest.fixture(autouse=True)
    def _require_schemas(self):
        if not BOOKS_SCHEMA.exists():
            pytest.skip(f"Schema not found: {BOOKS_SCHEMA}")
        if not E5BASE_SCHEMA.exists():
            pytest.skip(f"Schema not found: {E5BASE_SCHEMA}")

    @pytest.mark.parametrize(
        "field_type",
        ["text_general", "text_en", "text_es", "text_fr", "text_ca", "text_gen_sort", "text_general_rev"],
    )
    def test_text_analyzers_match(self, field_type: str):
        """Text analyzer chains should be identical across both configsets."""
        books_analyzers = _get_field_type_filters(BOOKS_SCHEMA, field_type)
        e5base_analyzers = _get_field_type_filters(E5BASE_SCHEMA, field_type)
        assert books_analyzers == e5base_analyzers, (
            f"{field_type} analyzers differ between configsets:\n"
            f"  books:   {books_analyzers}\n"
            f"  e5base:  {e5base_analyzers}"
        )
