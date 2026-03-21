"""Tests for metadata override persistence in the document-indexer.

Validates that manual metadata edits stored in Redis (aithena:metadata-override:{doc_id})
are applied during re-indexing, ensuring edits survive the indexing pipeline.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from document_indexer.__main__ import (
    apply_metadata_override,
    load_metadata_override,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

FAKE_PAGES = [(1, " ".join(["word"] * 500))]
FAKE_PAGE_CHUNKS = [("chunk1", 1, 1), ("chunk2", 1, 2)]
FAKE_EMBEDDING = [0.1] * 512


@pytest.fixture
def pdf_file(tmp_path: Path) -> Path:
    """Return a path to a minimal stub PDF-like file."""
    p = tmp_path / "Author" / "Title.pdf"
    p.parent.mkdir(parents=True)
    p.write_bytes(b"%PDF-1.4 fake content")
    return p


@pytest.fixture
def base_path(tmp_path: Path) -> str:
    return str(tmp_path)


@pytest.fixture
def metadata_stub(pdf_file: Path, base_path: str) -> dict:
    return {
        "title": "Title",
        "author": "Author",
        "year": None,
        "category": None,
        "language": None,
        "file_path": pdf_file.relative_to(base_path).as_posix(),
        "folder_path": pdf_file.parent.relative_to(base_path).as_posix(),
        "file_size": pdf_file.stat().st_size,
    }


# ---------------------------------------------------------------------------
# load_metadata_override
# ---------------------------------------------------------------------------


class TestLoadMetadataOverride:
    def test_returns_override_when_exists(self) -> None:
        """Returns parsed JSON when Redis has an override for the doc."""
        override_data = {
            "title_s": "Manual Title",
            "title_t": "Manual Title",
            "year_i": 2020,
            "edited_by": "admin",
            "edited_at": "2026-03-20T10:00:00+00:00",
        }
        with patch("document_indexer.__main__.redis_client") as mock_redis:
            mock_redis.get.return_value = json.dumps(override_data)
            result = load_metadata_override("abc123")

        assert result is not None
        assert result["title_s"] == "Manual Title"
        assert result["year_i"] == 2020
        mock_redis.get.assert_called_once_with("aithena:metadata-override:abc123")

    def test_returns_none_when_no_override(self) -> None:
        """Returns None when no override exists in Redis."""
        with patch("document_indexer.__main__.redis_client") as mock_redis:
            mock_redis.get.return_value = None
            result = load_metadata_override("no-override-id")

        assert result is None

    def test_returns_none_on_redis_error(self) -> None:
        """Returns None and logs warning when Redis is unavailable."""
        with patch("document_indexer.__main__.redis_client") as mock_redis:
            mock_redis.get.side_effect = ConnectionError("Redis down")
            result = load_metadata_override("err-id")

        assert result is None

    def test_returns_none_on_invalid_json(self) -> None:
        """Returns None when Redis value is not valid JSON."""
        with patch("document_indexer.__main__.redis_client") as mock_redis:
            mock_redis.get.return_value = "not-valid-json{{"
            result = load_metadata_override("bad-json-id")

        assert result is None

    def test_redis_timeout_handled_gracefully(self) -> None:
        """Redis timeout returns None (graceful degradation)."""
        import redis

        with patch("document_indexer.__main__.redis_client") as mock_redis:
            mock_redis.get.side_effect = redis.exceptions.TimeoutError("timeout")
            result = load_metadata_override("timeout-id")

        assert result is None


# ---------------------------------------------------------------------------
# apply_metadata_override
# ---------------------------------------------------------------------------


class TestApplyMetadataOverride:
    def test_override_title(self, metadata_stub: dict) -> None:
        """Title override replaces auto-detected title."""
        override = {"title_s": "Manual Title", "title_t": "Manual Title"}
        result = apply_metadata_override(metadata_stub, override)
        assert result["title"] == "Manual Title"

    def test_override_author(self, metadata_stub: dict) -> None:
        """Author override replaces auto-detected author."""
        override = {"author_s": "Manual Author", "author_t": "Manual Author"}
        result = apply_metadata_override(metadata_stub, override)
        assert result["author"] == "Manual Author"

    def test_override_year(self, metadata_stub: dict) -> None:
        """Year override replaces auto-detected year."""
        override = {"year_i": 1984}
        result = apply_metadata_override(metadata_stub, override)
        assert result["year"] == 1984

    def test_override_category(self, metadata_stub: dict) -> None:
        """Category override replaces auto-detected category."""
        override = {"category_s": "Science Fiction"}
        result = apply_metadata_override(metadata_stub, override)
        assert result["category"] == "Science Fiction"

    def test_override_series(self, metadata_stub: dict) -> None:
        """Series override adds new field to metadata."""
        override = {"series_s": "Discworld"}
        result = apply_metadata_override(metadata_stub, override)
        assert result["series"] == "Discworld"

    def test_unknown_fields_ignored(self, metadata_stub: dict) -> None:
        """Unknown fields like edited_by are silently skipped."""
        override = {
            "edited_by": "admin",
            "edited_at": "2026-03-20T10:00:00",
            "title_s": "Real Title",
        }
        result = apply_metadata_override(metadata_stub, override)
        assert result["title"] == "Real Title"
        assert "edited_by" not in result
        assert "edited_at" not in result

    def test_original_metadata_not_mutated(self, metadata_stub: dict) -> None:
        """apply_metadata_override returns a new dict, does not mutate the input."""
        original_title = metadata_stub["title"]
        override = {"title_s": "Changed"}
        result = apply_metadata_override(metadata_stub, override)
        assert result["title"] == "Changed"
        assert metadata_stub["title"] == original_title

    def test_multiple_fields_overridden(self, metadata_stub: dict) -> None:
        """Multiple fields can be overridden at once."""
        override = {
            "title_s": "New Title",
            "author_s": "New Author",
            "year_i": 2000,
            "category_s": "Fantasy",
        }
        result = apply_metadata_override(metadata_stub, override)
        assert result["title"] == "New Title"
        assert result["author"] == "New Author"
        assert result["year"] == 2000
        assert result["category"] == "Fantasy"

    def test_empty_override_returns_unchanged(self, metadata_stub: dict) -> None:
        """Empty override dict returns a copy with no changes."""
        result = apply_metadata_override(metadata_stub, {})
        assert result == metadata_stub


# ---------------------------------------------------------------------------
# Integration: index_document with overrides
# ---------------------------------------------------------------------------


class TestIndexDocumentWithOverrides:
    """Tests that index_document checks for and applies Redis overrides."""

    @patch("document_indexer.__main__.save_state")
    @patch("document_indexer.__main__.index_chunks", return_value=5)
    @patch("document_indexer.__main__.requests.post")
    @patch("document_indexer.__main__.get_page_count", return_value=10)
    @patch("document_indexer.__main__.extract_metadata")
    @patch("document_indexer.__main__.load_metadata_override")
    def test_override_applied_during_indexing(
        self,
        mock_override: MagicMock,
        mock_extract: MagicMock,
        mock_page_count: MagicMock,
        mock_post: MagicMock,
        mock_chunks: MagicMock,
        mock_state: MagicMock,
        pdf_file: Path,
        base_path: str,
        metadata_stub: dict,
    ) -> None:
        """When a Redis override exists, metadata is merged before indexing."""
        mock_extract.return_value = dict(metadata_stub)
        mock_override.return_value = {
            "title_s": "Manual Title",
            "year_i": 2020,
            "edited_by": "admin",
            "edited_at": "2026-03-20T10:00:00",
        }
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())

        from document_indexer.__main__ import index_document

        with patch("document_indexer.__main__.BASE_PATH", base_path):
            result = index_document(pdf_file)

        # Override was loaded using the correct doc_id (SHA256 of file_path)
        doc_id = hashlib.sha256(metadata_stub["file_path"].encode("utf-8")).hexdigest()
        mock_override.assert_called_once_with(doc_id)

        # Merged metadata has override values
        assert result["title"] == "Manual Title"
        assert result["year"] == 2020
        # Original author preserved
        assert result["author"] == "Author"

    @patch("document_indexer.__main__.save_state")
    @patch("document_indexer.__main__.index_chunks", return_value=5)
    @patch("document_indexer.__main__.requests.post")
    @patch("document_indexer.__main__.get_page_count", return_value=10)
    @patch("document_indexer.__main__.extract_metadata")
    @patch("document_indexer.__main__.load_metadata_override")
    def test_no_override_uses_auto_detected(
        self,
        mock_override: MagicMock,
        mock_extract: MagicMock,
        mock_page_count: MagicMock,
        mock_post: MagicMock,
        mock_chunks: MagicMock,
        mock_state: MagicMock,
        pdf_file: Path,
        base_path: str,
        metadata_stub: dict,
    ) -> None:
        """When no override exists, auto-detected metadata is used as-is."""
        mock_extract.return_value = dict(metadata_stub)
        mock_override.return_value = None
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())

        from document_indexer.__main__ import index_document

        with patch("document_indexer.__main__.BASE_PATH", base_path):
            result = index_document(pdf_file)

        assert result["title"] == "Title"
        assert result["author"] == "Author"

    @patch("document_indexer.__main__.save_state")
    @patch("document_indexer.__main__.index_chunks", return_value=5)
    @patch("document_indexer.__main__.requests.post")
    @patch("document_indexer.__main__.get_page_count", return_value=10)
    @patch("document_indexer.__main__.extract_metadata")
    @patch("document_indexer.__main__.redis_client")
    def test_redis_failure_proceeds_with_auto_detected(
        self,
        mock_redis: MagicMock,
        mock_extract: MagicMock,
        mock_page_count: MagicMock,
        mock_post: MagicMock,
        mock_chunks: MagicMock,
        mock_state: MagicMock,
        pdf_file: Path,
        base_path: str,
        metadata_stub: dict,
    ) -> None:
        """When Redis is down, indexing proceeds with auto-detected metadata."""
        mock_extract.return_value = dict(metadata_stub)
        mock_redis.get.side_effect = ConnectionError("Redis down")
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())

        from document_indexer.__main__ import index_document

        with patch("document_indexer.__main__.BASE_PATH", base_path):
            result = index_document(pdf_file)

        # Indexing succeeded despite Redis failure
        assert result["title"] == "Title"
        assert result["author"] == "Author"

    @patch("document_indexer.__main__.save_state")
    @patch("document_indexer.__main__.index_chunks", return_value=3)
    @patch("document_indexer.__main__.requests.post")
    @patch("document_indexer.__main__.get_page_count", return_value=5)
    @patch("document_indexer.__main__.extract_metadata")
    @patch("document_indexer.__main__.load_metadata_override")
    def test_override_reflected_in_solr_params(
        self,
        mock_override: MagicMock,
        mock_extract: MagicMock,
        mock_page_count: MagicMock,
        mock_post: MagicMock,
        mock_chunks: MagicMock,
        mock_state: MagicMock,
        pdf_file: Path,
        base_path: str,
        metadata_stub: dict,
    ) -> None:
        """Overridden metadata values are used in the Solr index request params."""
        mock_extract.return_value = dict(metadata_stub)
        mock_override.return_value = {"author_s": "Manual Author"}
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())

        from document_indexer.__main__ import index_document

        with patch("document_indexer.__main__.BASE_PATH", base_path):
            index_document(pdf_file)

        # The Solr extract POST should use the overridden author
        solr_call = mock_post.call_args_list[0]
        solr_params = solr_call.kwargs.get("params") or solr_call[1].get("params")
        assert solr_params["literal.author_s"] == "Manual Author"
