from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
import requests

import document_indexer.__main__ as indexer_module
from document_indexer.__main__ import (
    build_chunk_doc,
    build_literal_params,
    get_queue,
    index_chunks,
    index_document,
    mark_failure,
    save_state,
    wait_for_solr_collection,
)

# ---------------------------------------------------------------------------
# Shared fixtures
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
def metadata_stub(pdf_file: Path, base_path: str):
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

    def test_optional_language_included_when_present(self, metadata_stub):
        metadata_stub["language"] = "ca"
        doc = build_chunk_doc("pid", 0, "text", FAKE_EMBEDDING, metadata_stub)
        assert doc["language_s"] == "ca"

    def test_optional_language_absent_when_none(self, metadata_stub):
        metadata_stub["language"] = None
        doc = build_chunk_doc("pid", 0, "text", FAKE_EMBEDDING, metadata_stub)
        assert "language_s" not in doc

    def test_page_fields_included_when_provided(self, metadata_stub):
        doc = build_chunk_doc("pid", 0, "text", FAKE_EMBEDDING, metadata_stub, page_start=3, page_end=5)
        assert doc["page_start_i"] == 3
        assert doc["page_end_i"] == 5

    def test_page_fields_absent_when_not_provided(self, metadata_stub):
        doc = build_chunk_doc("pid", 0, "text", FAKE_EMBEDDING, metadata_stub)
        assert "page_start_i" not in doc
        assert "page_end_i" not in doc

    def test_page_start_equals_page_end_for_single_page_chunk(self, metadata_stub):
        doc = build_chunk_doc("pid", 0, "text", FAKE_EMBEDDING, metadata_stub, page_start=2, page_end=2)
        assert doc["page_start_i"] == 2
        assert doc["page_end_i"] == 2


# ---------------------------------------------------------------------------
# index_chunks
# ---------------------------------------------------------------------------


class TestIndexChunks:
    def _mock_response(self, status_code=200, text="OK"):
        resp = MagicMock()
        resp.status_code = status_code
        resp.text = text
        resp.raise_for_status = MagicMock(side_effect=None if status_code < 400 else Exception("HTTP error"))
        return resp

    @patch("document_indexer.__main__.requests.post")
    @patch("document_indexer.__main__.get_embeddings")
    @patch("document_indexer.__main__.extract_pdf_text")
    def test_returns_chunk_count(self, mock_extract_text, mock_get_embeddings, mock_post, pdf_file, metadata_stub):
        mock_extract_text.return_value = FAKE_PAGES
        mock_get_embeddings.return_value = [FAKE_EMBEDDING, FAKE_EMBEDDING]
        mock_post.return_value = self._mock_response()

        with patch("document_indexer.__main__.chunk_text_with_pages", return_value=FAKE_PAGE_CHUNKS):
            count = index_chunks(pdf_file, "parent_id", metadata_stub)

        assert count == 2

    @patch("document_indexer.__main__.requests.post")
    @patch("document_indexer.__main__.get_embeddings")
    @patch("document_indexer.__main__.extract_pdf_text")
    def test_posts_json_docs_to_solr(self, mock_extract_text, mock_get_embeddings, mock_post, pdf_file, metadata_stub):
        mock_extract_text.return_value = FAKE_PAGES
        page_chunks = [("chunk one", 1, 1), ("chunk two", 1, 2)]
        embeddings = [[0.1] * 512, [0.2] * 512]
        mock_get_embeddings.return_value = embeddings
        mock_post.return_value = self._mock_response()

        with patch("document_indexer.__main__.chunk_text_with_pages", return_value=page_chunks):
            index_chunks(pdf_file, "pid", metadata_stub)

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        docs = kwargs["json"]
        assert len(docs) == 2
        assert docs[0]["id"] == "pid_chunk_0000"
        assert docs[1]["id"] == "pid_chunk_0001"

    @patch("document_indexer.__main__.extract_pdf_text")
    def test_empty_text_returns_zero_without_calling_embeddings(self, mock_extract_text, pdf_file, metadata_stub):
        mock_extract_text.return_value = []
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
        mock_extract_text.return_value = FAKE_PAGES
        mock_get_embeddings.side_effect = RuntimeError("embedding server down")

        with (
            patch("document_indexer.__main__.chunk_text_with_pages", return_value=[("chunk", 1, 1)]),
            pytest.raises(RuntimeError, match="embedding server down"),
        ):
            index_chunks(pdf_file, "pid", metadata_stub)

        mock_post.assert_not_called()

    @patch("document_indexer.__main__.requests.post")
    @patch("document_indexer.__main__.get_embeddings")
    @patch("document_indexer.__main__.extract_pdf_text")
    def test_propagates_solr_error(self, mock_extract_text, mock_get_embeddings, mock_post, pdf_file, metadata_stub):
        mock_extract_text.return_value = FAKE_PAGES
        mock_get_embeddings.return_value = [FAKE_EMBEDDING]
        mock_post.return_value = self._mock_response(500, "Solr error")
        mock_post.return_value.raise_for_status.side_effect = requests.HTTPError("500 Server Error")

        with (
            patch("document_indexer.__main__.chunk_text_with_pages", return_value=[("chunk", 1, 1)]),
            pytest.raises(requests.HTTPError, match="500 Server Error"),
        ):
            index_chunks(pdf_file, "pid", metadata_stub)

    @patch("document_indexer.__main__.requests.post")
    @patch("document_indexer.__main__.get_embeddings")
    @patch("document_indexer.__main__.extract_pdf_text")
    def test_page_numbers_propagated_to_solr_docs(
        self, mock_extract_text, mock_get_embeddings, mock_post, pdf_file, metadata_stub
    ):
        mock_extract_text.return_value = FAKE_PAGES
        page_chunks = [("chunk one", 2, 3), ("chunk two", 3, 5)]
        mock_get_embeddings.return_value = [[0.1] * 512, [0.2] * 512]
        mock_post.return_value = self._mock_response()

        with patch("document_indexer.__main__.chunk_text_with_pages", return_value=page_chunks):
            index_chunks(pdf_file, "pid", metadata_stub)

        _, kwargs = mock_post.call_args
        docs = kwargs["json"]
        assert docs[0]["page_start_i"] == 2
        assert docs[0]["page_end_i"] == 3
        assert docs[1]["page_start_i"] == 3
        assert docs[1]["page_end_i"] == 5


# ---------------------------------------------------------------------------
# Solr startup gating
# ---------------------------------------------------------------------------


class TestWaitForSolrCollection:
    def _mock_response(self, *, json_data=None, text="", error=None):
        response = MagicMock()
        response.text = text
        response.raise_for_status = MagicMock(side_effect=error)
        if json_data is None:
            response.json.side_effect = ValueError("invalid json")
        else:
            response.json.return_value = json_data
        return response

    @patch("document_indexer.__main__.requests.get")
    def test_returns_when_collection_and_extract_handler_are_ready(self, mock_get):
        mock_get.side_effect = [
            self._mock_response(json_data={"collections": ["books"]}),
            self._mock_response(text='{"config":{"requestHandler":{"/update/extract":{}}}}'),
        ]

        wait_for_solr_collection(max_attempts=1, delay=0)

        assert mock_get.call_args_list == [
            call(
                "http://solr:8983/solr/admin/collections",
                params={"action": "LIST", "wt": "json"},
                timeout=indexer_module.SOLR_STARTUP_TIMEOUT,
            ),
            call(
                "http://solr:8983/api/collections/books/config",
                timeout=indexer_module.SOLR_STARTUP_TIMEOUT,
            ),
        ]

    @patch("document_indexer.__main__.time.sleep")
    @patch("document_indexer.__main__.requests.get")
    def test_retries_until_extract_handler_exists(self, mock_get, mock_sleep):
        mock_get.side_effect = [
            self._mock_response(json_data={"collections": ["books"]}),
            self._mock_response(text='{"config":{"requestHandler":{}}}'),
            self._mock_response(json_data={"collections": ["books"]}),
            self._mock_response(text='{"config":{"requestHandler":{"/update/extract":{}}}}'),
        ]

        wait_for_solr_collection(max_attempts=2, delay=0)

        mock_sleep.assert_called_once_with(0)

    @patch("document_indexer.__main__.time.sleep")
    @patch("document_indexer.__main__.requests.get")
    def test_raises_after_exhausting_attempts(self, mock_get, mock_sleep):
        mock_get.return_value = self._mock_response(json_data={"collections": []})

        with pytest.raises(RuntimeError, match="did not become ready"):
            wait_for_solr_collection(max_attempts=2, delay=0)

        mock_sleep.assert_called_once_with(0)


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
        resp.raise_for_status.side_effect = requests.HTTPError(message)
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

        with patch("document_indexer.__main__.BASE_PATH", base_path), pytest.raises(requests.HTTPError):
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

        with patch("document_indexer.__main__.BASE_PATH", base_path), pytest.raises(RuntimeError):
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

        with patch("document_indexer.__main__.BASE_PATH", base_path), pytest.raises(requests.HTTPError):
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


class TestSaveState:
    def test_allows_file_path_metadata_field(self):
        with (
            patch("document_indexer.__main__.load_state", return_value={"path": "abs/path.pdf"}),
            patch.object(indexer_module.redis_client, "set") as mock_set,
        ):
            state = save_state("abs/path.pdf", file_path="relative/path.pdf", processed=True)

        assert state["path"] == "abs/path.pdf"
        assert state["file_path"] == "relative/path.pdf"
        assert state["processed"] is True
        mock_set.assert_called_once()


# ---------------------------------------------------------------------------
# build_literal_params — language metadata
# ---------------------------------------------------------------------------


class TestBuildLiteralParams:
    def _base_metadata(self, file_path: str = "author/title.pdf") -> dict:
        return {
            "title": "Title",
            "author": "Author",
            "year": None,
            "category": None,
            "language": None,
            "file_path": file_path,
            "folder_path": "author",
            "file_size": 1024,
        }

    def test_language_included_in_params_when_set(self):
        meta = self._base_metadata()
        meta["language"] = "ca"
        params = build_literal_params(meta, page_count=None)
        assert params["literal.language_s"] == "ca"

    def test_language_absent_from_params_when_none(self):
        meta = self._base_metadata()
        meta["language"] = None
        params = build_literal_params(meta, page_count=None)
        assert "literal.language_s" not in params

    def test_language_absent_from_params_when_missing(self):
        meta = self._base_metadata()
        del meta["language"]
        params = build_literal_params(meta, page_count=None)
        assert "literal.language_s" not in params

    @pytest.mark.parametrize("lang", ["es", "ca", "fr", "en", "la", "de", "pt", "it", "nl"])
    def test_all_supported_language_codes_are_passed_through(self, lang):
        meta = self._base_metadata()
        meta["language"] = lang
        params = build_literal_params(meta, page_count=None)
        assert params["literal.language_s"] == lang

    def test_thumbnail_url_included_in_params_when_set(self):
        meta = self._base_metadata()
        params = build_literal_params(meta, page_count=None, thumbnail_url="Author/Title.pdf.thumb.jpg")
        assert params["literal.thumbnail_url_s"] == "Author/Title.pdf.thumb.jpg"

    def test_thumbnail_url_absent_from_params_when_none(self):
        meta = self._base_metadata()
        params = build_literal_params(meta, page_count=None, thumbnail_url=None)
        assert "literal.thumbnail_url_s" not in params

    def test_thumbnail_url_absent_from_params_when_empty_string(self):
        meta = self._base_metadata()
        params = build_literal_params(meta, page_count=None, thumbnail_url="")
        assert "literal.thumbnail_url_s" not in params


# ---------------------------------------------------------------------------
# Exchange declaration and queue binding
# ---------------------------------------------------------------------------


class TestExchangeBinding:
    def test_get_queue_declares_fanout_exchange(self):
        """get_queue declares the fanout exchange on the channel."""
        indexer_module.queue = None
        channel = MagicMock()
        channel.queue_declare.return_value = MagicMock()

        get_queue(channel)

        channel.exchange_declare.assert_called_once_with(
            exchange="documents",
            exchange_type="fanout",
            durable=True,
        )

    def test_get_queue_binds_queue_to_exchange_on_first_call(self):
        """On the first call, the queue is bound to the fanout exchange."""
        indexer_module.queue = None
        channel = MagicMock()
        channel.queue_declare.return_value = MagicMock()

        get_queue(channel)

        channel.queue_bind.assert_called_once_with(
            queue="new_documents",
            exchange="documents",
        )

    def test_get_queue_does_not_rebind_on_subsequent_calls(self):
        """On subsequent calls, the queue is not re-bound (passive check only)."""
        indexer_module.queue = MagicMock()  # simulate prior call
        channel = MagicMock()
        channel.queue_declare.return_value = MagicMock()

        get_queue(channel)

        channel.queue_bind.assert_not_called()
        # Reset for other tests
        indexer_module.queue = None

    def test_get_queue_sets_prefetch_count(self):
        """get_queue sets QoS prefetch_count=1 for backpressure."""
        indexer_module.queue = None
        channel = MagicMock()
        channel.queue_declare.return_value = MagicMock()

        get_queue(channel)

        channel.basic_qos.assert_called_once_with(prefetch_count=1)

    def test_get_queue_declares_durable_queue(self):
        """get_queue declares a durable, non-auto-delete queue."""
        indexer_module.queue = None
        channel = MagicMock()
        channel.queue_declare.return_value = MagicMock()

        get_queue(channel)

        channel.queue_declare.assert_called_once_with(
            queue="new_documents",
            durable=True,
            auto_delete=False,
            passive=False,
        )

    def test_get_queue_uses_passive_on_subsequent_calls(self):
        """On subsequent calls, queue_declare uses passive=True."""
        indexer_module.queue = MagicMock()  # simulate prior call
        channel = MagicMock()
        channel.queue_declare.return_value = MagicMock()

        get_queue(channel)

        channel.queue_declare.assert_called_once_with(
            queue="new_documents",
            durable=True,
            auto_delete=False,
            passive=True,
        )
        # Reset for other tests
        indexer_module.queue = None


# ---------------------------------------------------------------------------
# Queue name and collection configurability
# ---------------------------------------------------------------------------


class TestQueueNameConfig:
    def test_default_queue_name(self):
        """QUEUE_NAME defaults to 'new_documents'."""
        import importlib
        import os

        env = {k: v for k, v in os.environ.items() if k != "QUEUE_NAME"}
        with patch.dict(os.environ, env, clear=True):
            import document_indexer

            importlib.reload(document_indexer)
            assert document_indexer.QUEUE_NAME == "new_documents"

    def test_custom_queue_name(self):
        """QUEUE_NAME can be overridden via env var."""
        import importlib
        import os

        with patch.dict(os.environ, {"QUEUE_NAME": "e5base_chunks"}):
            import document_indexer

            importlib.reload(document_indexer)
            assert document_indexer.QUEUE_NAME == "e5base_chunks"

    def test_default_exchange_name(self):
        """EXCHANGE_NAME defaults to 'documents'."""
        import importlib
        import os

        env = {k: v for k, v in os.environ.items() if k != "EXCHANGE_NAME"}
        with patch.dict(os.environ, env, clear=True):
            import document_indexer

            importlib.reload(document_indexer)
            assert document_indexer.EXCHANGE_NAME == "documents"

    def test_custom_exchange_name(self):
        """EXCHANGE_NAME can be overridden via env var."""
        import importlib
        import os

        with patch.dict(os.environ, {"EXCHANGE_NAME": "custom_exchange"}):
            import document_indexer

            importlib.reload(document_indexer)
            assert document_indexer.EXCHANGE_NAME == "custom_exchange"


class TestCollectionRouting:
    def test_default_solr_collection(self):
        """SOLR_COLLECTION defaults to 'books'."""
        import importlib
        import os

        env = {k: v for k, v in os.environ.items() if k != "SOLR_COLLECTION"}
        with patch.dict(os.environ, env, clear=True):
            import document_indexer

            importlib.reload(document_indexer)
            assert document_indexer.SOLR_COLLECTION == "books"

    def test_custom_solr_collection(self):
        """SOLR_COLLECTION can be overridden for dual-model routing."""
        import importlib
        import os

        with patch.dict(os.environ, {"SOLR_COLLECTION": "books_e5base"}):
            import document_indexer

            importlib.reload(document_indexer)
            assert document_indexer.SOLR_COLLECTION == "books_e5base"

    @patch("document_indexer.__main__.requests.post")
    @patch("document_indexer.__main__.get_embeddings")
    @patch("document_indexer.__main__.extract_pdf_text")
    def test_index_chunks_uses_configured_collection(
        self, mock_extract_text, mock_get_embeddings, mock_post, pdf_file, metadata_stub
    ):
        """index_chunks posts to the correct Solr collection URL."""
        mock_extract_text.return_value = FAKE_PAGES
        mock_get_embeddings.return_value = [FAKE_EMBEDDING, FAKE_EMBEDDING]
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        mock_post.return_value = resp

        with (
            patch("document_indexer.__main__.chunk_text_with_pages", return_value=FAKE_PAGE_CHUNKS),
            patch("document_indexer.__main__.SOLR_COLLECTION", "books_e5base"),
            patch("document_indexer.__main__.SOLR_HOST", "solr"),
            patch("document_indexer.__main__.SOLR_PORT", 8983),
        ):
            index_chunks(pdf_file, "parent_id", metadata_stub)

        solr_url = mock_post.call_args[0][0]
        assert "books_e5base" in solr_url
        assert "/solr/books_e5base/update" in solr_url


# ---------------------------------------------------------------------------
# Chunk size configuration
# ---------------------------------------------------------------------------


class TestChunkSizeConfig:
    def test_default_chunk_size(self):
        """CHUNK_SIZE defaults to 90."""
        import importlib
        import os

        env = {k: v for k, v in os.environ.items() if k != "CHUNK_SIZE"}
        with patch.dict(os.environ, env, clear=True):
            import document_indexer

            importlib.reload(document_indexer)
            assert document_indexer.CHUNK_SIZE == 90

    def test_custom_chunk_size(self):
        """CHUNK_SIZE can be overridden for different models (e.g. e5: 300)."""
        import importlib
        import os

        with patch.dict(os.environ, {"CHUNK_SIZE": "300"}):
            import document_indexer

            importlib.reload(document_indexer)
            assert document_indexer.CHUNK_SIZE == 300

    def test_default_chunk_overlap(self):
        """CHUNK_OVERLAP defaults to 10."""
        import importlib
        import os

        env = {k: v for k, v in os.environ.items() if k != "CHUNK_OVERLAP"}
        with patch.dict(os.environ, env, clear=True):
            import document_indexer

            importlib.reload(document_indexer)
            assert document_indexer.CHUNK_OVERLAP == 10

    def test_custom_chunk_overlap(self):
        """CHUNK_OVERLAP can be overridden for different models (e.g. e5: 50)."""
        import importlib
        import os

        with patch.dict(os.environ, {"CHUNK_OVERLAP": "50"}):
            import document_indexer

            importlib.reload(document_indexer)
            assert document_indexer.CHUNK_OVERLAP == 50

    def test_chunk_size_is_integer(self):
        """CHUNK_SIZE is parsed as an integer."""
        import importlib
        import os

        with patch.dict(os.environ, {"CHUNK_SIZE": "200"}):
            import document_indexer

            importlib.reload(document_indexer)
            assert isinstance(document_indexer.CHUNK_SIZE, int)
