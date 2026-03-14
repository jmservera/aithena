"""Tests for document_lister: poll-interval config and re-queue behaviour."""

from __future__ import annotations

import importlib
import json
import os
import time
import unittest.mock as mock
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper: reload __init__ with a custom environment
# ---------------------------------------------------------------------------


def reload_init(env: dict) -> object:
    """Reload the document_lister package with the given environment variables."""
    with patch.dict(os.environ, env, clear=True):
        import document_lister
        importlib.reload(document_lister)
        return document_lister


# ---------------------------------------------------------------------------
# POLL_INTERVAL configuration tests
# ---------------------------------------------------------------------------


class TestPollIntervalConfig:
    def test_default_poll_interval_is_60(self):
        """POLL_INTERVAL defaults to 60 when env var is not set."""
        env = {k: v for k, v in os.environ.items() if k != "POLL_INTERVAL"}
        env.pop("POLL_INTERVAL", None)
        module = reload_init(env)
        assert module.POLL_INTERVAL == 60

    def test_default_document_wildcard_is_pdf_glob(self):
        """The lister defaults to matching PDF files on the local filesystem."""
        env = {k: v for k, v in os.environ.items() if k != "DOCUMENT_WILDCARD"}
        env.pop("DOCUMENT_WILDCARD", None)
        module = reload_init(env)
        assert module.DOCUMENT_WILDCARD == "*.pdf"

    def test_custom_poll_interval_is_respected(self):
        """POLL_INTERVAL is read from the environment variable."""
        module = reload_init({"POLL_INTERVAL": "120"})
        assert module.POLL_INTERVAL == 120

    def test_poll_interval_is_integer(self):
        """POLL_INTERVAL is parsed as an integer."""
        module = reload_init({"POLL_INTERVAL": "30"})
        assert isinstance(module.POLL_INTERVAL, int)

    def test_poll_interval_one_second(self):
        """POLL_INTERVAL accepts 1 second for rapid polling."""
        module = reload_init({"POLL_INTERVAL": "1"})
        assert module.POLL_INTERVAL == 1


# ---------------------------------------------------------------------------
# handle_document re-queue behaviour tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def redis_mock():
    return MagicMock()


@pytest.fixture()
def channel_mock():
    return MagicMock()


def _import_main_module():
    """Import document_lister.__main__."""
    import document_lister.__main__ as main_mod
    importlib.reload(main_mod)
    return main_mod


def _import_handle_document():
    main_mod = _import_main_module()
    return main_mod.handle_document, main_mod.push_file_to_queue


class TestProcessPath:
    def test_only_pdf_files_are_enqueued(self, tmp_path, redis_mock, channel_mock):
        main_mod = _import_main_module()
        (tmp_path / "book.pdf").write_bytes(b"pdf content")
        (tmp_path / "notes.txt").write_text("notes")

        with patch.object(main_mod, "DOCUMENT_WILDCARD", "*"):
            with patch.object(main_mod, "handle_document") as mock_handle:
                main_mod.process_path(str(tmp_path), redis_mock, channel_mock)

        mock_handle.assert_called_once_with(tmp_path / "book.pdf", redis_mock, channel_mock)


class TestHandleDocument:
    def test_new_document_is_queued(self, tmp_path, redis_mock, channel_mock):
        """A document with no Redis entry is pushed to the queue."""
        handle_document, _ = _import_handle_document()
        pdf = tmp_path / "book.pdf"
        pdf.write_bytes(b"pdf content")

        redis_mock.get.return_value = None

        handle_document(pdf, redis_mock, channel_mock)

        channel_mock.basic_publish.assert_called_once()
        redis_mock.set.assert_called_once()

    def test_unchanged_processed_document_is_not_requeued(self, tmp_path, redis_mock, channel_mock):
        """A processed document whose mtime has not changed is not re-queued."""
        handle_document, _ = _import_handle_document()
        pdf = tmp_path / "book.pdf"
        pdf.write_bytes(b"pdf content")

        existing = json.dumps({
            "path": str(pdf),
            "last_modified": pdf.stat().st_mtime,
            "processed": True,
            "timestamp": "2026-01-01T00:00:00",
        })
        redis_mock.get.return_value = existing

        handle_document(pdf, redis_mock, channel_mock)

        channel_mock.basic_publish.assert_not_called()

    def test_modified_processed_document_is_requeued(self, tmp_path, redis_mock, channel_mock):
        """A processed document whose mtime changed is re-queued and marked unprocessed."""
        handle_document, _ = _import_handle_document()
        pdf = tmp_path / "book.pdf"
        pdf.write_bytes(b"pdf content")

        old_mtime = pdf.stat().st_mtime - 10  # simulate older mtime in Redis
        existing = json.dumps({
            "path": str(pdf),
            "last_modified": old_mtime,
            "processed": True,
            "timestamp": "2026-01-01T00:00:00",
        })
        redis_mock.get.return_value = existing

        handle_document(pdf, redis_mock, channel_mock)

        channel_mock.basic_publish.assert_called_once()

        # Verify that the stored value marks the document as unprocessed
        call_args = redis_mock.set.call_args
        stored = json.loads(call_args[0][1])
        assert stored["processed"] is False

    def test_unprocessed_unchanged_document_is_not_requeued(self, tmp_path, redis_mock, channel_mock):
        """A document already in the queue (not yet processed) is not re-queued."""
        handle_document, _ = _import_handle_document()
        pdf = tmp_path / "book.pdf"
        pdf.write_bytes(b"pdf content")

        existing = json.dumps({
            "path": str(pdf),
            "last_modified": pdf.stat().st_mtime,
            "processed": False,
            "timestamp": "2026-01-01T00:00:00",
        })
        redis_mock.get.return_value = existing

        handle_document(pdf, redis_mock, channel_mock)

        channel_mock.basic_publish.assert_not_called()

    def test_modified_unprocessed_document_updates_mtime_but_not_requeued(
        self, tmp_path, redis_mock, channel_mock
    ):
        """A document already in the queue but with changed mtime updates Redis but does not
        push again (it was not yet processed, so the old queue entry is still valid)."""
        handle_document, _ = _import_handle_document()
        pdf = tmp_path / "book.pdf"
        pdf.write_bytes(b"pdf content")

        old_mtime = pdf.stat().st_mtime - 10
        existing = json.dumps({
            "path": str(pdf),
            "last_modified": old_mtime,
            "processed": False,
            "timestamp": "2026-01-01T00:00:00",
        })
        redis_mock.get.return_value = existing

        handle_document(pdf, redis_mock, channel_mock)

        # Still in queue but not yet processed — no second push
        channel_mock.basic_publish.assert_not_called()
        # But Redis entry is updated with new mtime
        redis_mock.set.assert_called_once()
