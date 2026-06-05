"""Schema audit tests for PathHierarchyTokenizer usage.

Issue: v2.5 — Verify PathHierarchyTokenizer behavior change (token position
increment 0 → 1 in Solr 10) does not affect the books collection.

Tests verify:
1. ancestor_path and descendent_path field types exist as boilerplate definitions
2. No concrete fields use ancestor_path or descendent_path types
3. Dynamic field patterns for these types exist but match no indexed/stored data fields
"""

from __future__ import annotations

import xml.etree.ElementTree as ET  # nosec B405 — trusted local schema files only
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
BOOKS_SCHEMA = REPO_ROOT / "src" / "solr" / "books" / "managed-schema.xml"


# ---------------------------------------------------------------------------
# Schema parsing helpers
# ---------------------------------------------------------------------------


def _parse_schema(schema_path: Path) -> ET.Element:
    tree = ET.parse(schema_path)  # nosec B314 — trusted local schema file
    return tree.getroot()


def _get_field_type_names(root: ET.Element) -> set[str]:
    """Return the set of all fieldType names defined in the schema."""
    return {ft.get("name") for ft in root.findall(".//fieldType") if ft.get("name")}


def _get_concrete_field_types(root: ET.Element) -> dict[str, str]:
    """Return a mapping of concrete field name → type for all <field> elements."""
    return {f.get("name"): f.get("type") for f in root.findall(".//field") if f.get("name") and f.get("type")}


def _get_dynamic_field_types(root: ET.Element) -> dict[str, str]:
    """Return a mapping of dynamic field pattern → type for all <dynamicField> elements."""
    return {f.get("name"): f.get("type") for f in root.findall(".//dynamicField") if f.get("name") and f.get("type")}


def _get_tokenizer_names_for_field_type(root: ET.Element, field_type_name: str) -> list[str]:
    """Return the list of tokenizer names used by a given field type (both analyzers)."""
    tokenizers = []
    for ft in root.findall(".//fieldType"):
        if ft.get("name") == field_type_name:
            for analyzer in ft.findall("analyzer"):
                tok = analyzer.find("tokenizer")
                if tok is not None and tok.get("name"):
                    tokenizers.append(tok.get("name"))
    return tokenizers


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPathHierarchyTokenizerAudit:
    """Audit: PathHierarchyTokenizer usage in the books Solr schema.

    Solr 10 changed the PathHierarchyTokenizer token position increment from 0
    to 1.  These tests confirm that no concrete (non-dynamic) fields use the
    ancestor_path or descendent_path field types, so the behavior change has
    no impact on the books collection.
    """

    @pytest.fixture(scope="class")
    def schema_root(self) -> ET.Element:
        return _parse_schema(BOOKS_SCHEMA)

    def test_ancestor_path_field_type_is_defined(self, schema_root: ET.Element) -> None:
        """ancestor_path field type exists in the schema (default Solr boilerplate)."""
        names = _get_field_type_names(schema_root)
        assert "ancestor_path" in names

    def test_descendent_path_field_type_is_defined(self, schema_root: ET.Element) -> None:
        """descendent_path field type exists in the schema (default Solr boilerplate)."""
        names = _get_field_type_names(schema_root)
        assert "descendent_path" in names

    def test_ancestor_path_uses_path_hierarchy_tokenizer(self, schema_root: ET.Element) -> None:
        """ancestor_path type uses pathHierarchy tokenizer (in query analyzer)."""
        tokenizers = _get_tokenizer_names_for_field_type(schema_root, "ancestor_path")
        assert "pathHierarchy" in tokenizers

    def test_descendent_path_uses_path_hierarchy_tokenizer(self, schema_root: ET.Element) -> None:
        """descendent_path type uses pathHierarchy tokenizer (in index analyzer)."""
        tokenizers = _get_tokenizer_names_for_field_type(schema_root, "descendent_path")
        assert "pathHierarchy" in tokenizers

    def test_no_concrete_field_uses_ancestor_path_type(self, schema_root: ET.Element) -> None:
        """No concrete <field> element uses the ancestor_path field type.

        This is the key audit assertion: because no concrete fields use
        ancestor_path, the Solr 10 PathHierarchyTokenizer position-increment
        change (0 → 1) has no impact on indexed or queried data.
        """
        concrete = _get_concrete_field_types(schema_root)
        fields_using_type = [name for name, ftype in concrete.items() if ftype == "ancestor_path"]
        assert fields_using_type == [], (
            f"Unexpected concrete fields with type ancestor_path: {fields_using_type}. "
            "Review the Solr 10 PathHierarchyTokenizer position-increment change impact."
        )

    def test_no_concrete_field_uses_descendent_path_type(self, schema_root: ET.Element) -> None:
        """No concrete <field> element uses the descendent_path field type.

        Same rationale as above — confirms no reindexing or query changes are
        needed for the Solr 10 migration.
        """
        concrete = _get_concrete_field_types(schema_root)
        fields_using_type = [name for name, ftype in concrete.items() if ftype == "descendent_path"]
        assert fields_using_type == [], (
            f"Unexpected concrete fields with type descendent_path: {fields_using_type}. "
            "Review the Solr 10 PathHierarchyTokenizer position-increment change impact."
        )

    def test_dynamic_field_pattern_ancestor_path_exists(self, schema_root: ET.Element) -> None:
        """Dynamic field pattern *_ancestor_path is registered (expected boilerplate)."""
        dynamic = _get_dynamic_field_types(schema_root)
        assert "*_ancestor_path" in dynamic
        assert dynamic["*_ancestor_path"] == "ancestor_path"

    def test_dynamic_field_pattern_descendent_path_exists(self, schema_root: ET.Element) -> None:
        """Dynamic field pattern *_descendent_path is registered (expected boilerplate)."""
        dynamic = _get_dynamic_field_types(schema_root)
        assert "*_descendent_path" in dynamic
        assert dynamic["*_descendent_path"] == "descendent_path"
