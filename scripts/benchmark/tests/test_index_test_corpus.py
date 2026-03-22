"""Tests for the index_test_corpus script logic.

All RabbitMQ and Solr calls are mocked — these tests validate document
discovery, publishing logic, and status reporting.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from index_test_corpus import (
    discover_documents,
    get_collection_counts,
    publish_documents,
)

# ---------------------------------------------------------------------------
# discover_documents
# ---------------------------------------------------------------------------


class TestDiscoverDocuments:
    def test_finds_pdfs(self, tmp_path: Path) -> None:
        (tmp_path / "book1.pdf").touch()
        (tmp_path / "book2.pdf").touch()
        (tmp_path / "readme.txt").touch()

        files = discover_documents(str(tmp_path), "*.pdf")
        assert len(files) == 2
        assert all(f.endswith(".pdf") for f in files)

    def test_recursive_discovery(self, tmp_path: Path) -> None:
        subdir = tmp_path / "sub" / "deep"
        subdir.mkdir(parents=True)
        (subdir / "nested.pdf").touch()
        (tmp_path / "top.pdf").touch()

        files = discover_documents(str(tmp_path), "*.pdf")
        assert len(files) == 2

    def test_limit_parameter(self, tmp_path: Path) -> None:
        for i in range(10):
            (tmp_path / f"book{i:02d}.pdf").touch()

        files = discover_documents(str(tmp_path), "*.pdf", limit=3)
        assert len(files) == 3

    def test_empty_directory(self, tmp_path: Path) -> None:
        files = discover_documents(str(tmp_path), "*.pdf")
        assert files == []

    def test_custom_wildcard(self, tmp_path: Path) -> None:
        (tmp_path / "doc.epub").touch()
        (tmp_path / "doc.pdf").touch()

        files = discover_documents(str(tmp_path), "*.epub")
        assert len(files) == 1
        assert files[0].endswith(".epub")

    def test_results_sorted(self, tmp_path: Path) -> None:
        (tmp_path / "c.pdf").touch()
        (tmp_path / "a.pdf").touch()
        (tmp_path / "b.pdf").touch()

        files = discover_documents(str(tmp_path), "*.pdf")
        basenames = [os.path.basename(f) for f in files]
        assert basenames == sorted(basenames)


# ---------------------------------------------------------------------------
# publish_documents (mocked pika)
# ---------------------------------------------------------------------------


class TestPublishDocuments:
    @patch("index_test_corpus.pika")
    def test_publishes_all_files(self, mock_pika: MagicMock) -> None:
        mock_channel = MagicMock()
        mock_connection = MagicMock()
        mock_connection.channel.return_value = mock_channel
        mock_pika.BlockingConnection.return_value = mock_connection

        files = ["/data/doc1.pdf", "/data/doc2.pdf", "/data/doc3.pdf"]
        count = publish_documents(files, exchange="documents")

        assert count == 3
        assert mock_channel.basic_publish.call_count == 3
        mock_connection.close.assert_called_once()

    @patch("index_test_corpus.pika")
    def test_declares_fanout_exchange(self, mock_pika: MagicMock) -> None:
        mock_channel = MagicMock()
        mock_connection = MagicMock()
        mock_connection.channel.return_value = mock_channel
        mock_pika.BlockingConnection.return_value = mock_connection

        publish_documents(["/data/doc.pdf"], exchange="documents")

        mock_channel.exchange_declare.assert_called_once_with(
            exchange="documents", exchange_type="fanout", durable=True,
        )

    @patch("index_test_corpus.pika")
    def test_persistent_delivery_mode(self, mock_pika: MagicMock) -> None:
        mock_channel = MagicMock()
        mock_connection = MagicMock()
        mock_connection.channel.return_value = mock_channel
        mock_pika.BlockingConnection.return_value = mock_connection
        mock_pika.BasicProperties = MagicMock()

        publish_documents(["/data/doc.pdf"], exchange="documents")

        props_call = mock_pika.BasicProperties.call_args
        assert props_call[1]["delivery_mode"] == 2

    @patch("index_test_corpus.pika")
    def test_uses_empty_routing_key(self, mock_pika: MagicMock) -> None:
        mock_channel = MagicMock()
        mock_connection = MagicMock()
        mock_connection.channel.return_value = mock_channel
        mock_pika.BlockingConnection.return_value = mock_connection

        publish_documents(["/data/doc.pdf"], exchange="documents")

        publish_call = mock_channel.basic_publish.call_args
        assert publish_call[1]["routing_key"] == ""
        assert publish_call[1]["exchange"] == "documents"

    @patch("index_test_corpus.pika")
    def test_file_path_as_body(self, mock_pika: MagicMock) -> None:
        mock_channel = MagicMock()
        mock_connection = MagicMock()
        mock_connection.channel.return_value = mock_channel
        mock_pika.BlockingConnection.return_value = mock_connection

        publish_documents(["/data/my-book.pdf"], exchange="documents")

        publish_call = mock_channel.basic_publish.call_args
        assert publish_call[1]["body"] == "/data/my-book.pdf"

    @patch("index_test_corpus.pika")
    def test_empty_list_returns_zero(self, mock_pika: MagicMock) -> None:
        mock_channel = MagicMock()
        mock_connection = MagicMock()
        mock_connection.channel.return_value = mock_channel
        mock_pika.BlockingConnection.return_value = mock_connection

        count = publish_documents([], exchange="documents")

        assert count == 0
        mock_channel.basic_publish.assert_not_called()


# ---------------------------------------------------------------------------
# get_collection_counts (mocked requests)
# ---------------------------------------------------------------------------


class TestGetCollectionCounts:
    @patch("index_test_corpus.requests.get")
    def test_returns_counts(self, mock_get: MagicMock) -> None:
        def side_effect(url, **kwargs):
            mock_resp = MagicMock()
            if "books_e5base" in url:
                mock_resp.json.return_value = {"response": {"numFound": 50}}
            else:
                mock_resp.json.return_value = {"response": {"numFound": 100}}
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        mock_get.side_effect = side_effect

        counts = get_collection_counts(
            solr_host="localhost", solr_port=8983,
            collections=("books", "books_e5base"),
        )
        assert counts["books"] == 100
        assert counts["books_e5base"] == 50

    @patch("index_test_corpus.requests.get")
    def test_handles_connection_error(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = ConnectionError("refused")

        counts = get_collection_counts(
            solr_host="localhost", solr_port=8983,
            collections=("books",),
        )
        assert "error" in str(counts["books"])
