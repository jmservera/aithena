"""Lightweight HTTP control API for pausing/resuming the document-indexer.

Endpoints:
    POST /control/pause   — stop consuming after current document finishes
    POST /control/resume  — restart consuming
    GET  /control/status   — return current state and document info

State is persisted in Redis so a container restart respects it.
"""

from __future__ import annotations

import json
import logging
import signal
import threading
from datetime import UTC, datetime
from enum import Enum
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import redis

from . import INDEXER_CONTROL_PORT

logger = logging.getLogger(__name__)

REDIS_CONTROL_KEY = "aithena:indexer:control"


class IndexerState(str, Enum):  # noqa: UP042
    RUNNING = "running"
    PAUSED = "paused"
    PROCESSING = "processing"


class IndexerControl:
    """Thread-safe state machine for the indexer pause/resume lifecycle."""

    def __init__(self, redis_client: redis.Redis | None = None) -> None:
        self._lock = threading.Lock()
        self._state = IndexerState.RUNNING
        self._current_document: str | None = None
        self._paused_at: str | None = None
        self._redis = redis_client
        self._shutting_down = threading.Event()
        self._pause_requested = threading.Event()
        self._restore_from_redis()

    # ── Redis persistence ─────────────────────────────────────────────────

    def _restore_from_redis(self) -> None:
        if self._redis is None:
            return
        try:
            raw = self._redis.get(REDIS_CONTROL_KEY)
            if raw is None:
                return
            data = json.loads(raw)
            if data.get("paused"):
                self._state = IndexerState.PAUSED
                self._paused_at = data.get("paused_at")
                self._pause_requested.set()
                logger.info("Restored paused state from Redis (paused_at=%s)", self._paused_at)
        except Exception:
            logger.warning("Could not restore control state from Redis", exc_info=True)

    def _persist(self) -> None:
        if self._redis is None:
            return
        payload = {
            "paused": self._state == IndexerState.PAUSED,
            "paused_at": self._paused_at,
        }
        try:
            self._redis.set(REDIS_CONTROL_KEY, json.dumps(payload))
        except Exception:
            logger.warning("Could not persist control state to Redis", exc_info=True)

    # ── Public API ────────────────────────────────────────────────────────

    def pause(self) -> dict[str, Any]:
        with self._lock:
            if self._state == IndexerState.PAUSED:
                return {"status": "already_paused"}
            self._paused_at = datetime.now(UTC).isoformat()
            if self._state == IndexerState.PROCESSING:
                # Will transition to PAUSED once current doc finishes
                self._pause_requested.set()
                self._persist_paused_state()
                return {"status": "pause_pending", "current_document": self._current_document}
            self._state = IndexerState.PAUSED
            self._pause_requested.set()
            self._persist()
            return {"status": "paused"}

    def _persist_paused_state(self) -> None:
        """Persist paused=True even while still processing (pause is pending)."""
        if self._redis is None:
            return
        payload = {"paused": True, "paused_at": self._paused_at}
        try:
            self._redis.set(REDIS_CONTROL_KEY, json.dumps(payload))
        except Exception:
            logger.warning("Could not persist control state to Redis", exc_info=True)

    def resume(self) -> dict[str, Any]:
        with self._lock:
            if (
                self._state == IndexerState.RUNNING or self._state == IndexerState.PROCESSING
            ) and not self._pause_requested.is_set():
                return {"status": "already_running"}
            self._pause_requested.clear()
            if self._state == IndexerState.PAUSED:
                self._state = IndexerState.RUNNING
            self._paused_at = None
            self._persist()
            return {"status": "resumed"}

    def status(self) -> dict[str, Any]:
        with self._lock:
            result: dict[str, Any] = {
                "state": self._state.value,
                "current_document": self._current_document,
            }
            if self._paused_at:
                result["paused_at"] = self._paused_at
            if self._pause_requested.is_set() and self._state == IndexerState.PROCESSING:
                result["pause_pending"] = True
            return result

    def begin_processing(self, document: str) -> None:
        with self._lock:
            self._state = IndexerState.PROCESSING
            self._current_document = document

    def end_processing(self) -> None:
        with self._lock:
            self._current_document = None
            if self._pause_requested.is_set():
                self._state = IndexerState.PAUSED
                self._persist()
            else:
                self._state = IndexerState.RUNNING

    @property
    def is_paused(self) -> bool:
        return self._pause_requested.is_set()

    @property
    def is_shutting_down(self) -> bool:
        return self._shutting_down.is_set()

    def request_shutdown(self) -> None:
        self._shutting_down.set()

    def wait_while_paused(self, timeout: float = 1.0) -> None:
        """Block while paused, checking periodically for shutdown or resume."""
        while self._pause_requested.is_set() and not self._shutting_down.is_set():
            self._shutting_down.wait(timeout=timeout)


# ── HTTP request handler ──────────────────────────────────────────────────


def _make_handler(control: IndexerControl) -> type[BaseHTTPRequestHandler]:
    class ControlHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            logger.debug(format, *args)

        def _send_json(self, status: int, body: dict) -> None:
            payload = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/control/status":
                self._send_json(HTTPStatus.OK, control.status())
            else:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path == "/control/pause":
                result = control.pause()
                self._send_json(HTTPStatus.OK, result)
            elif self.path == "/control/resume":
                result = control.resume()
                self._send_json(HTTPStatus.OK, result)
            else:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    return ControlHandler


def start_control_server(
    control: IndexerControl,
    port: int = INDEXER_CONTROL_PORT,
) -> HTTPServer:
    """Start the control HTTP server in a daemon thread."""
    handler_class = _make_handler(control)
    server = HTTPServer(("0.0.0.0", port), handler_class)  # noqa: S104
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Control API listening on port %d", port)
    return server


def install_signal_handlers(control: IndexerControl) -> None:
    """Install SIGTERM/SIGINT handlers for graceful shutdown."""

    def _handler(signum: int, frame: Any) -> None:
        sig_name = signal.Signals(signum).name
        logger.info("Received %s — requesting graceful shutdown", sig_name)
        control.request_shutdown()

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)
