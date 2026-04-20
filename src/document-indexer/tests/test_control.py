"""Unit tests for the pause/resume control state machine and HTTP API."""

from __future__ import annotations

import json
import threading
from http.client import HTTPConnection
from unittest.mock import MagicMock

import pytest

from document_indexer.control import (
    REDIS_CONTROL_KEY,
    IndexerControl,
    start_control_server,
)

# ---------------------------------------------------------------------------
# IndexerControl state machine tests
# ---------------------------------------------------------------------------


class TestIndexerControlStateMachine:
    def test_initial_state_is_running(self):
        ctrl = IndexerControl(redis_client=None)
        assert ctrl.status()["state"] == "running"
        assert not ctrl.is_paused

    def test_pause_from_running(self):
        ctrl = IndexerControl(redis_client=None)
        result = ctrl.pause()
        assert result["status"] == "paused"
        assert ctrl.status()["state"] == "paused"
        assert ctrl.is_paused

    def test_pause_when_already_paused(self):
        ctrl = IndexerControl(redis_client=None)
        ctrl.pause()
        result = ctrl.pause()
        assert result["status"] == "already_paused"

    def test_resume_from_paused(self):
        ctrl = IndexerControl(redis_client=None)
        ctrl.pause()
        result = ctrl.resume()
        assert result["status"] == "resumed"
        assert ctrl.status()["state"] == "running"
        assert not ctrl.is_paused

    def test_resume_when_already_running(self):
        ctrl = IndexerControl(redis_client=None)
        result = ctrl.resume()
        assert result["status"] == "already_running"

    def test_pause_during_processing(self):
        ctrl = IndexerControl(redis_client=None)
        ctrl.begin_processing("/data/test.pdf")
        assert ctrl.status()["state"] == "processing"
        assert ctrl.status()["current_document"] == "/data/test.pdf"

        result = ctrl.pause()
        assert result["status"] == "pause_pending"
        assert result["current_document"] == "/data/test.pdf"
        # Still processing
        assert ctrl.status()["state"] == "processing"
        assert ctrl.status().get("pause_pending") is True

    def test_end_processing_transitions_to_paused_when_pending(self):
        ctrl = IndexerControl(redis_client=None)
        ctrl.begin_processing("/data/test.pdf")
        ctrl.pause()
        ctrl.end_processing()
        assert ctrl.status()["state"] == "paused"
        assert ctrl.status()["current_document"] is None

    def test_end_processing_transitions_to_running_normally(self):
        ctrl = IndexerControl(redis_client=None)
        ctrl.begin_processing("/data/test.pdf")
        ctrl.end_processing()
        assert ctrl.status()["state"] == "running"

    def test_resume_cancels_pending_pause(self):
        ctrl = IndexerControl(redis_client=None)
        ctrl.begin_processing("/data/test.pdf")
        ctrl.pause()
        ctrl.resume()
        assert not ctrl.is_paused
        ctrl.end_processing()
        assert ctrl.status()["state"] == "running"

    def test_shutdown_flag(self):
        ctrl = IndexerControl(redis_client=None)
        assert not ctrl.is_shutting_down
        ctrl.request_shutdown()
        assert ctrl.is_shutting_down

    def test_pause_sets_paused_at(self):
        ctrl = IndexerControl(redis_client=None)
        ctrl.pause()
        status = ctrl.status()
        assert "paused_at" in status

    def test_resume_clears_paused_at(self):
        ctrl = IndexerControl(redis_client=None)
        ctrl.pause()
        ctrl.resume()
        assert "paused_at" not in ctrl.status()

    def test_wait_while_paused_returns_on_shutdown(self):
        ctrl = IndexerControl(redis_client=None)
        ctrl.pause()

        def _shutdown():
            ctrl.request_shutdown()

        t = threading.Thread(target=_shutdown)
        t.start()
        ctrl.wait_while_paused(timeout=0.1)
        t.join(timeout=2)
        assert ctrl.is_shutting_down


# ---------------------------------------------------------------------------
# Redis persistence tests
# ---------------------------------------------------------------------------


class TestRedisStatePersistence:
    def test_pause_persists_to_redis(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        ctrl = IndexerControl(redis_client=mock_redis)
        ctrl.pause()
        mock_redis.set.assert_called()
        call_args = mock_redis.set.call_args
        key = call_args[0][0]
        payload = json.loads(call_args[0][1])
        assert key == REDIS_CONTROL_KEY
        assert payload["paused"] is True
        assert payload["paused_at"] is not None

    def test_resume_persists_to_redis(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        ctrl = IndexerControl(redis_client=mock_redis)
        ctrl.pause()
        mock_redis.reset_mock()
        ctrl.resume()
        mock_redis.set.assert_called()
        payload = json.loads(mock_redis.set.call_args[0][1])
        assert payload["paused"] is False

    def test_restore_paused_state_from_redis(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps({"paused": True, "paused_at": "2024-01-01T00:00:00"})
        ctrl = IndexerControl(redis_client=mock_redis)
        assert ctrl.is_paused
        assert ctrl.status()["state"] == "paused"
        assert ctrl.status()["paused_at"] == "2024-01-01T00:00:00"

    def test_restore_running_state_from_redis(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps({"paused": False, "paused_at": None})
        ctrl = IndexerControl(redis_client=mock_redis)
        assert not ctrl.is_paused

    def test_restore_handles_redis_error(self):
        mock_redis = MagicMock()
        mock_redis.get.side_effect = Exception("connection refused")
        ctrl = IndexerControl(redis_client=mock_redis)
        # Should default to running state
        assert not ctrl.is_paused

    def test_persist_handles_redis_error(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_redis.set.side_effect = Exception("connection refused")
        ctrl = IndexerControl(redis_client=mock_redis)
        # Should not raise
        ctrl.pause()
        assert ctrl.is_paused

    def test_end_processing_persists_paused(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        ctrl = IndexerControl(redis_client=mock_redis)
        ctrl.begin_processing("/data/test.pdf")
        ctrl.pause()
        mock_redis.reset_mock()
        ctrl.end_processing()
        mock_redis.set.assert_called()
        payload = json.loads(mock_redis.set.call_args[0][1])
        assert payload["paused"] is True


# ---------------------------------------------------------------------------
# HTTP control API tests
# ---------------------------------------------------------------------------


class TestControlHTTPAPI:
    @pytest.fixture(autouse=True)
    def _start_server(self):
        self.ctrl = IndexerControl(redis_client=None)
        self.server = start_control_server(self.ctrl, port=0)
        self.port = self.server.server_address[1]
        yield
        self.server.shutdown()

    def _request(self, method: str, path: str) -> tuple[int, dict]:
        conn = HTTPConnection("127.0.0.1", self.port)
        conn.request(method, path)
        resp = conn.getresponse()
        body = json.loads(resp.read())
        status = resp.status
        conn.close()
        return status, body

    def test_get_status(self):
        status, body = self._request("GET", "/control/status")
        assert status == 200
        assert body["state"] == "running"

    def test_post_pause(self):
        status, body = self._request("POST", "/control/pause")
        assert status == 200
        assert body["status"] == "paused"
        # Verify status endpoint reflects change
        status, body = self._request("GET", "/control/status")
        assert body["state"] == "paused"

    def test_post_resume(self):
        self._request("POST", "/control/pause")
        status, body = self._request("POST", "/control/resume")
        assert status == 200
        assert body["status"] == "resumed"

    def test_unknown_get_path(self):
        status, body = self._request("GET", "/unknown")
        assert status == 404

    def test_unknown_post_path(self):
        status, body = self._request("POST", "/unknown")
        assert status == 404
