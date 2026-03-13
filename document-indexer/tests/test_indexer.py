from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

import document_indexer.__main__ as indexer_module
from document_indexer.__main__ import (
    build_chunk_doc,
    build_literal_params,
    index_chunks,
    index_document,
    mark_failure,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

FAKE_TEXT = " ".join(["word"] * 500)
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
def metadata_stub(pdf_file: Path, base_path: str):
    return {
        "title": "Title",
        "author": "Author",
        "year": None,
        "category": None,
        "file_path": pdf_file.relative_to(base_path).as_posix(),
        "folder_path": pdf_file.parent.relative_to(base_path).as_posix(),
        "file_size": pdf_file.stat().st_size,
    }


# ---------------------------------------------------------------------------
# build_chunk_doc
# ---------------------------------------------------------------------------


class TestBuildChunkDoc:
    def test_chunk_id_is_deterministic(self, metadata_stub):
        doc = build_chunk_doc("parent123", 0, "some text", FAKE_EMBEDDING, metadata_stub)
        assert doc["id"] == "parent123_chunk_0000"

    def test_chunk_index_zero_padded(self, metadata_stub):
        doc = build_chunk_doc("pid", 42, "text", FAKE_EMBEDDING, metadata_stub)
        assert doc["id"] == "pid_chunk_0042"

    def test_embedding_stored_in_doc(self, metadata_stub):
        emb = [float(i) for i in range(512)]
        doc = build_chunk_doc("pid", 0, "text", emb, metadata_stub)
        assert doc["embedding_v"] == emb

    def test_parent_id_linked(self, metadata_stub):
        doc = build_chunk_doc("pid", 0, "text", FAKE_EMBEDDING, metadata_stub)
        assert doc["parent_id_s"] == "pid"
        assert doc["chunk_index_i"] == 0

    def test_metadata_propagated(self, metadata_stub):
        doc = build_chunk_doc("pid", 0, "text", FAKE_EMBEDDING, metadata_stub)
        assert doc["title_s"] == metadata_stub["title"]
        assert doc["author_s"] == metadata_stub["author"]
        assert doc["file_path_s"] == metadata_stub["file_path"]

    def test_optional_category_included_when_present(self, metadata_stub):
        metadata_stub["category"] = "Fiction"
        doc = build_chunk_doc("pid", 0, "text", FAKE_EMBEDDING, metadata_stub)
        assert doc["category_s"] == "Fiction"

    def test_optional_category_absent_when_none(self, metadata_stub):
        metadata_stub["category"] = None
        doc = build_chunk_doc("pid", 0, "text", FAKE_EMBEDDING, metadata_stub)
        assert "category_s" not in doc

    def test_optional_year_included_when_present(self, metadata_stub):
        metadata_stub["year"] = 1984
        doc = build_chunk_doc("pid", 0, "text", FAKE_EMBEDDING, metadata_stub)
        assert doc["year_i"] == 1984


# ---------------------------------------------------------------------------
# index_chunks
# ---------------------------------------------------------------------------


class TestIndexChunks:
    def _mock_response(self, status_code=200, text="OK"):
        resp = MagicMock()
        resp.status_code = status_code
        resp.text = text
        resp.raise_for_status = MagicMock(
            side_effect=None if status_code < 400 else Exception("HTTP error")
        )
        return resp

    @patch("document_indexer.__main__.requests.post")
    @patch("document_indexer.__main__.get_embeddings")
    @patch("document_indexer.__main__.extract_pdf_text")
    def test_returns_chunk_count(
        self, mock_extract_text, mock_get_embeddings, mock_post, pdf_file, metadata_stub
    ):
        mock_extract_text.return_value = FAKE_TEXT
        mock_get_embeddings.return_value = [FAKE_EMBEDDING, FAKE_EMBEDDING]
        mock_post.return_value = self._mock_response()

        with patch("document_indexer.__main__.chunk_text", return_value=["chunk1", "chunk2"]):
            count = index_chunks(pdf_file, "parent_id", metadata_stub)

        assert count == 2

    @patch("document_indexer.__main__.requests.post")
    @patch("document_indexer.__main__.get_embeddings")
    @patch("document_indexer.__main__.extract_pdf_text")
    def test_posts_json_docs_to_solr(
        self, mock_extract_text, mock_get_embeddings, mock_post, pdf_file, metadata_stub
    ):
        mock_extract_text.return_value = FAKE_TEXT
        chunks = ["chunk one", "chunk two"]
        embeddings = [[0.1] * 512, [0.2] * 512]
        mock_get_embeddings.return_value = embeddings
        mock_post.return_value = self._mock_response()

        with patch("document_indexer.__main__.chunk_text", return_value=chunks):
            index_chunks(pdf_file, "pid", metadata_stub)

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        docs = kwargs["json"]
        assert len(docs) == 2
        assert docs[0]["id"] == "pid_chunk_0000"
        assert docs[1]["id"] == "pid_chunk_0001"

    @patch("document_indexer.__main__.extract_pdf_text")
    def test_empty_text_returns_zero_without_calling_embeddings(
        self, mock_extract_text, pdf_file, metadata_stub
    ):
        mock_extract_text.return_value = ""
        with patch("document_indexer.__main__.get_embeddings") as mock_emb:
            count = index_chunks(pdf_file, "pid", metadata_stub)
        assert count == 0
        mock_emb.assert_not_called()

    @patch("document_indexer.__main__.requests.post")
    @patch("document_indexer.__main__.get_embeddings")
    @patch("document_indexer.__main__.extract_pdf_text")
    def test_propagates_embedding_error(
        self, mock_extract_text, mock_get_embeddings, mock_post, pdf_file, metadata_stub
    ):
        mock_extract_text.return_value = FAKE_TEXT
        mock_get_embeddings.side_effect = RuntimeError("embedding server down")

        with patch("document_indexer.__main__.chunk_text", return_value=["chunk"]):
            with pytest.raises(RuntimeError, match="embedding server down"):
                index_chunks(pdf_file, "pid", metadata_stub)

        mock_post.assert_not_called()

    @patch("document_indexer.__main__.requests.post")
    @patch("document_indexer.__main__.get_embeddings")
    @patch("document_indexer.__main__.extract_pdf_text")
    def test_propagates_solr_error(
        self, mock_extract_text, mock_get_embeddings, mock_post, pdf_file, metadata_stub
    ):
        mock_extract_text.return_value = FAKE_TEXT
        mock_get_embeddings.return_value = [FAKE_EMBEDDING]
        mock_post.return_value = self._mock_response(500, "Solr error")
        mock_post.return_value.raise_for_status.side_effect = Exception("500 Server Error")

        with patch("document_indexer.__main__.chunk_text", return_value=["chunk"]):
            with pytest.raises(Exception, match="500 Server Error"):
                index_chunks(pdf_file, "pid", metadata_stub)


# ---------------------------------------------------------------------------
# index_document — full orchestration
# ---------------------------------------------------------------------------


class TestIndexDocument:
    def _mock_ok_response(self):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        return resp

    def _mock_error_response(self, message="HTTP 500"):
        resp = MagicMock()
        resp.raise_for_status.side_effect = Exception(message)
        return resp

    @patch("document_indexer.__main__.save_state")
    @patch("document_indexer.__main__.index_chunks")
    @patch("document_indexer.__main__.requests.post")
    @patch("document_indexer.__main__.extract_metadata")
    @patch("document_indexer.__main__.get_page_count")
    def test_successful_indexing_marks_processed_true(
        self,
        mock_page_count,
        mock_extract_meta,
        mock_post,
        mock_index_chunks,
        mock_save_state,
        pdf_file,
        base_path,
        metadata_stub,
    ):
        mock_page_count.return_value = 10
        mock_extract_meta.return_value = metadata_stub
        mock_post.return_value = self._mock_ok_response()
        mock_index_chunks.return_value = 3

        with patch("document_indexer.__main__.BASE_PATH", base_path):
            result = index_document(pdf_file)

        assert result == metadata_stub
        # Last save_state call should mark processed=True and embedding_indexed=True
        last_call_kwargs = mock_save_state.call_args_list[-1][1]
        assert last_call_kwargs["processed"] is True
        assert last_call_kwargs["embedding_indexed"] is True
        assert last_call_kwargs["chunk_count"] == 3

    @patch("document_indexer.__main__.save_state")
    @patch("document_indexer.__main__.index_chunks")
    @patch("document_indexer.__main__.requests.post")
    @patch("document_indexer.__main__.extract_metadata")
    @patch("document_indexer.__main__.get_page_count")
    def test_text_indexing_records_text_indexed_true_before_embeddings(
        self,
        mock_page_count,
        mock_extract_meta,
        mock_post,
        mock_index_chunks,
        mock_save_state,
        pdf_file,
        base_path,
        metadata_stub,
    ):
        mock_page_count.return_value = 5
        mock_extract_meta.return_value = metadata_stub
        mock_post.return_value = self._mock_ok_response()
        mock_index_chunks.return_value = 2

        with patch("document_indexer.__main__.BASE_PATH", base_path):
            index_document(pdf_file)

        # First save_state call (after text indexing) should have text_indexed=True
        first_call_kwargs = mock_save_state.call_args_list[0][1]
        assert first_call_kwargs["text_indexed"] is True
        assert first_call_kwargs["embedding_indexed"] is False
        assert first_call_kwargs["processed"] is False

    @patch("document_indexer.__main__.mark_failure")
    @patch("document_indexer.__main__.requests.post")
    @patch("document_indexer.__main__.extract_metadata")
    @patch("document_indexer.__main__.get_page_count")
    def test_text_indexing_failure_marks_text_indexing_stage(
        self,
        mock_page_count,
        mock_extract_meta,
        mock_post,
        mock_mark_failure,
        pdf_file,
        base_path,
        metadata_stub,
    ):
        mock_page_count.return_value = 5
        mock_extract_meta.return_value = metadata_stub
        mock_post.return_value = self._mock_error_response("Solr down")

        with patch("document_indexer.__main__.BASE_PATH", base_path):
            with pytest.raises(Exception):
                index_document(pdf_file)

        mock_mark_failure.assert_called_once()
        _, kwargs = mock_mark_failure.call_args
        assert kwargs["stage"] == "text_indexing"

    @patch("document_indexer.__main__.save_state")
    @patch("document_indexer.__main__.mark_failure")
    @patch("document_indexer.__main__.index_chunks")
    @patch("document_indexer.__main__.requests.post")
    @patch("document_indexer.__main__.extract_metadata")
    @patch("document_indexer.__main__.get_page_count")
    def test_embedding_indexing_failure_marks_embedding_indexing_stage(
        self,
        mock_page_count,
        mock_extract_meta,
        mock_post,
        mock_index_chunks,
        mock_mark_failure,
        mock_save_state,
        pdf_file,
        base_path,
        metadata_stub,
    ):
        mock_page_count.return_value = 5
        mock_extract_meta.return_value = metadata_stub
        mock_post.return_value = self._mock_ok_response()
        mock_index_chunks.side_effect = RuntimeError("embeddings server unavailable")

        with patch("document_indexer.__main__.BASE_PATH", base_path):
            with pytest.raises(RuntimeError):
                index_document(pdf_file)

        mock_mark_failure.assert_called_once()
        _, kwargs = mock_mark_failure.call_args
        assert kwargs["stage"] == "embedding_indexing"

    @patch("document_indexer.__main__.save_state")
    @patch("document_indexer.__main__.mark_failure")
    @patch("document_indexer.__main__.index_chunks")
    @patch("document_indexer.__main__.requests.post")
    @patch("document_indexer.__main__.extract_metadata")
    @patch("document_indexer.__main__.get_page_count")
    def test_text_indexing_failure_does_not_attempt_embedding_indexing(
        self,
        mock_page_count,
        mock_extract_meta,
        mock_post,
        mock_index_chunks,
        mock_mark_failure,
        mock_save_state,
        pdf_file,
        base_path,
        metadata_stub,
    ):
        mock_page_count.return_value = 5
        mock_extract_meta.return_value = metadata_stub
        mock_post.return_value = self._mock_error_response()

        with patch("document_indexer.__main__.BASE_PATH", base_path):
            with pytest.raises(Exception):
                index_document(pdf_file)

        mock_index_chunks.assert_not_called()

    def test_non_pdf_raises_value_error(self, tmp_path: Path):
        p = tmp_path / "file.txt"
        p.write_bytes(b"text")
        with pytest.raises(ValueError, match="Unsupported file type"):
            index_document(p)

    def test_missing_file_raises_file_not_found(self, tmp_path: Path):
        p = tmp_path / "missing.pdf"
        with pytest.raises(FileNotFoundError):
            index_document(p)


# ---------------------------------------------------------------------------
# mark_failure — Redis state
# ---------------------------------------------------------------------------


class TestMarkFailure:
    @patch("document_indexer.__main__.save_state")
    def test_records_stage_in_redis_state(self, mock_save_state, pdf_file):
        mark_failure(pdf_file, "boom", stage="text_indexing")
        _, kwargs = mock_save_state.call_args
        assert kwargs["error_stage"] == "text_indexing"
        assert kwargs["failed"] is True
        assert kwargs["processed"] is False

    @patch("document_indexer.__main__.save_state")
    def test_embedding_stage_recorded_correctly(self, mock_save_state, pdf_file):
        mark_failure(pdf_file, "embedding error", stage="embedding_indexing")
        _, kwargs = mock_save_state.call_args
        assert kwargs["error_stage"] == "embedding_indexing"
