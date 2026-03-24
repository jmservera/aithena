"""Tests for the indexing_status page helpers."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock

os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")

from pages.indexing_status import (
    build_status_dataframe,
    classify_document,
    load_all_documents,
)


# ---------------------------------------------------------------------------
# classify_document
# ---------------------------------------------------------------------------
class TestClassifyDocument:
    def test_failed_document(self):
        assert classify_document({"failed": True, "processed": False}) == "failed"

    def test_processed_document(self):
        assert classify_document({"processed": True, "failed": False}) == "processed"

    def test_processing_text_indexed(self):
        state = {"text_indexed": True, "processed": False, "failed": False}
        assert classify_document(state) == "processing"

    def test_processing_has_solr_id(self):
        state = {"solr_id": "abc123", "processed": False, "failed": False}
        assert classify_document(state) == "processing"

    def test_queued_document(self):
        assert classify_document({"processed": False, "failed": False}) == "queued"

    def test_failed_takes_priority(self):
        state = {"failed": True, "processed": True, "text_indexed": True}
        assert classify_document(state) == "failed"


# ---------------------------------------------------------------------------
# build_status_dataframe
# ---------------------------------------------------------------------------
class TestBuildStatusDataframe:
    def _sample_docs(self):
        return [
            {
                "status": "queued",
                "path": "/books/a.pdf",
                "timestamp": "2024-01-01",
            },
            {
                "status": "processing",
                "path": "/books/b.pdf",
                "text_indexed": True,
                "embedding_indexed": False,
                "page_count": 10,
                "chunk_count": 0,
                "timestamp": "2024-01-02",
            },
            {
                "status": "processed",
                "path": "/books/c.pdf",
                "text_indexed": True,
                "embedding_indexed": True,
                "page_count": 50,
                "chunk_count": 120,
                "timestamp": "2024-01-03",
            },
            {
                "status": "failed",
                "path": "/books/d.pdf",
                "error": "timeout",
                "error_stage": "embedding_indexing",
                "timestamp": "2024-01-04",
            },
        ]

    def test_no_filter_returns_all(self):
        df = build_status_dataframe(self._sample_docs())
        assert len(df) == 4

    def test_filter_by_status(self):
        df = build_status_dataframe(self._sample_docs(), status_filter="processed")
        assert len(df) == 1
        assert "Done" in df["status"].iloc[0]

    def test_filter_processing(self):
        df = build_status_dataframe(self._sample_docs(), status_filter="processing")
        assert len(df) == 1

    def test_empty_documents_returns_empty_df(self):
        df = build_status_dataframe([])
        assert df.empty

    def test_boolean_columns_mapped(self):
        df = build_status_dataframe(self._sample_docs())
        if "text_indexed" in df.columns:
            assert df["text_indexed"].iloc[1] == "✅"
            assert df["text_indexed"].iloc[2] == "✅"

    def test_page_and_chunk_counts_are_int(self):
        df = build_status_dataframe(self._sample_docs())
        if "page_count" in df.columns:
            assert df["page_count"].dtype in (int, "int64", "Int64")


# ---------------------------------------------------------------------------
# load_all_documents
# ---------------------------------------------------------------------------
class TestLoadAllDocuments:
    def test_loads_and_classifies(self):
        mock_redis = MagicMock()
        mock_redis.keys.return_value = [
            "/shortembeddings/a.pdf",
            "/shortembeddings/b.pdf",
        ]
        states = {
            "/shortembeddings/a.pdf": json.dumps(
                {"path": "/a.pdf", "processed": False, "failed": False}
            ),
            "/shortembeddings/b.pdf": json.dumps(
                {"path": "/b.pdf", "processed": True, "failed": False, "page_count": 5}
            ),
        }
        mock_redis.get.side_effect = lambda k: states.get(k)

        docs = load_all_documents(mock_redis)
        assert len(docs) == 2
        statuses = {d["status"] for d in docs}
        assert statuses == {"queued", "processed"}

    def test_skips_invalid_json(self):
        mock_redis = MagicMock()
        mock_redis.keys.return_value = ["/shortembeddings/bad.pdf"]
        mock_redis.get.return_value = "not-json{"

        docs = load_all_documents(mock_redis)
        assert len(docs) == 0

    def test_skips_empty_values(self):
        mock_redis = MagicMock()
        mock_redis.keys.return_value = ["/shortembeddings/empty.pdf"]
        mock_redis.get.return_value = None

        docs = load_all_documents(mock_redis)
        assert len(docs) == 0
