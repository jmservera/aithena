"""Tests for circuit_breaker.py -- state transitions, thresholds, recovery.

Also tests graceful degradation of Redis and Solr calls through the
circuit breakers integrated in main.py.
"""

from __future__ import annotations

import contextlib
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import redis as redis_lib
import requests

sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("AUTH_DB_PATH", "/tmp/test-auth.db")  # noqa: S108
os.environ.setdefault("AUTH_JWT_SECRET", "test-auth-secret")
os.environ.setdefault("AUTH_JWT_TTL", "24h")
os.environ.setdefault("AUTH_COOKIE_NAME", "aithena_auth")

from circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitState  # noqa: E402

from tests.auth_helpers import create_authenticated_client  # noqa: E402


def _raise_value_error() -> None:
    raise ValueError("boom")


def _raise_type_error() -> None:
    raise TypeError("unexpected")


def _raise_redis_error() -> None:
    raise redis_lib.ConnectionError("Redis connection refused")


def _raise_request_error() -> None:
    raise requests.ConnectionError("Solr connection refused")


def _trip_breaker(breaker: CircuitBreaker, raiser) -> None:
    for _ in range(breaker.failure_threshold):
        with contextlib.suppress(Exception):
            breaker.call(raiser)


def _mock_solr_response() -> MagicMock:
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {
        "response": {"numFound": 0, "docs": []},
        "highlighting": {},
        "facet_counts": {"facet_fields": {}},
    }
    mock.raise_for_status.return_value = None
    return mock


def _get_test_client():
    return create_authenticated_client()


# ---------------------------------------------------------------------------
# Unit tests for CircuitBreaker
# ---------------------------------------------------------------------------


class TestCircuitBreakerStateTransitions:

    def _make_breaker(self, **kwargs) -> CircuitBreaker:
        defaults = {
            "name": "test",
            "failure_threshold": 3,
            "recovery_timeout": 0.2,
            "expected_exceptions": (ValueError,),
            "success_threshold": 1,
        }
        defaults.update(kwargs)
        return CircuitBreaker(**defaults)

    def test_starts_closed(self) -> None:
        cb = self._make_breaker()
        assert cb.state is CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_stays_closed_below_threshold(self) -> None:
        cb = self._make_breaker(failure_threshold=3)
        for _ in range(2):
            with contextlib.suppress(ValueError):
                cb.call(_raise_value_error)
        assert cb.state is CircuitState.CLOSED
        assert cb.failure_count == 2

    def test_opens_at_threshold(self) -> None:
        cb = self._make_breaker(failure_threshold=3)
        for _ in range(3):
            with contextlib.suppress(ValueError):
                cb.call(_raise_value_error)
        assert cb.state is CircuitState.OPEN

    def test_open_circuit_rejects_calls(self) -> None:
        cb = self._make_breaker(failure_threshold=1, recovery_timeout=10.0)
        with contextlib.suppress(ValueError):
            cb.call(_raise_value_error)
        assert cb.state is CircuitState.OPEN

        try:
            cb.call(lambda: "ok")
            raised = False
        except CircuitOpenError as exc:
            raised = True
            assert exc.name == "test"
            assert exc.remaining_seconds > 0
        assert raised

    def test_transitions_to_half_open_after_timeout(self) -> None:
        cb = self._make_breaker(failure_threshold=1, recovery_timeout=0.1)
        with contextlib.suppress(ValueError):
            cb.call(_raise_value_error)
        assert cb.state is CircuitState.OPEN
        time.sleep(0.15)
        assert cb.state is CircuitState.HALF_OPEN

    def test_half_open_success_closes_circuit(self) -> None:
        cb = self._make_breaker(failure_threshold=1, recovery_timeout=0.1)
        with contextlib.suppress(ValueError):
            cb.call(_raise_value_error)
        time.sleep(0.15)
        assert cb.state is CircuitState.HALF_OPEN
        result = cb.call(lambda: "recovered")
        assert result == "recovered"
        assert cb.state is CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_half_open_failure_reopens_circuit(self) -> None:
        cb = self._make_breaker(failure_threshold=1, recovery_timeout=0.1)
        with contextlib.suppress(ValueError):
            cb.call(_raise_value_error)
        time.sleep(0.15)
        assert cb.state is CircuitState.HALF_OPEN
        with contextlib.suppress(ValueError):
            cb.call(_raise_value_error)
        assert cb.state is CircuitState.OPEN

    def test_success_resets_failure_count(self) -> None:
        cb = self._make_breaker(failure_threshold=3)
        for _ in range(2):
            with contextlib.suppress(ValueError):
                cb.call(_raise_value_error)
        assert cb.failure_count == 2
        cb.call(lambda: "ok")
        assert cb.failure_count == 0
        for _ in range(2):
            with contextlib.suppress(ValueError):
                cb.call(_raise_value_error)
        assert cb.state is CircuitState.CLOSED

    def test_unexpected_exception_does_not_affect_state(self) -> None:
        cb = self._make_breaker(failure_threshold=1, expected_exceptions=(ValueError,))
        with contextlib.suppress(TypeError):
            cb.call(_raise_type_error)
        assert cb.state is CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_manual_reset(self) -> None:
        cb = self._make_breaker(failure_threshold=1, recovery_timeout=100.0)
        with contextlib.suppress(ValueError):
            cb.call(_raise_value_error)
        assert cb.state is CircuitState.OPEN
        cb.reset()
        assert cb.state is CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_get_status_returns_dict(self) -> None:
        cb = self._make_breaker()
        status = cb.get_status()
        assert status["name"] == "test"
        assert status["state"] == "closed"
        assert status["failure_count"] == 0
        assert status["failure_threshold"] == 3
        assert status["recovery_timeout_seconds"] == 0.2

    def test_success_threshold_requires_multiple_successes(self) -> None:
        cb = self._make_breaker(failure_threshold=1, recovery_timeout=0.1, success_threshold=2)
        with contextlib.suppress(ValueError):
            cb.call(_raise_value_error)
        time.sleep(0.15)
        assert cb.state is CircuitState.HALF_OPEN
        cb.call(lambda: "ok")
        assert cb.state is CircuitState.HALF_OPEN
        cb.call(lambda: "ok")
        assert cb.state is CircuitState.CLOSED

    def test_call_returns_function_result(self) -> None:
        cb = self._make_breaker()
        assert cb.call(lambda: 42) == 42

    def test_call_passes_args_and_kwargs(self) -> None:
        cb = self._make_breaker()
        assert cb.call(lambda a, b, extra=0: a + b + extra, 1, 2, extra=10) == 13


# ---------------------------------------------------------------------------
# Integration tests -- circuit breakers in main.py
# ---------------------------------------------------------------------------


class TestHealthEndpointCircuitBreakers:

    def test_health_reports_circuit_breaker_states(self) -> None:
        client = _get_test_client()
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "circuit_breakers" in data
        assert "redis" in data["circuit_breakers"]
        assert "solr" in data["circuit_breakers"]
        redis_cb = data["circuit_breakers"]["redis"]
        assert redis_cb["state"] == "closed"
        assert "failure_count" in redis_cb

    def test_health_status_ok_when_all_circuits_closed(self) -> None:
        import main
        main.redis_circuit.reset()
        main.solr_circuit.reset()
        client = _get_test_client()
        data = client.get("/health").json()
        assert data["status"] == "ok"

    def test_health_status_degraded_when_redis_circuit_open(self) -> None:
        import main
        main.solr_circuit.reset()
        _trip_breaker(main.redis_circuit, _raise_redis_error)
        try:
            data = _get_test_client().get("/health").json()
            assert data["status"] == "degraded"
            assert data["circuit_breakers"]["redis"]["state"] == "open"
        finally:
            main.redis_circuit.reset()

    def test_health_status_unavailable_when_solr_circuit_open(self) -> None:
        import main
        main.redis_circuit.reset()
        _trip_breaker(main.solr_circuit, _raise_request_error)
        try:
            data = _get_test_client().get("/health").json()
            assert data["status"] == "unavailable"
            assert data["circuit_breakers"]["solr"]["state"] == "open"
        finally:
            main.solr_circuit.reset()

    def test_v1_health_also_has_circuit_breakers(self) -> None:
        data = _get_test_client().get("/v1/health").json()
        assert "circuit_breakers" in data


class TestSolrCircuitBreaker:

    @patch("main.requests.post")
    def test_solr_failure_trips_circuit(self, mock_get: MagicMock) -> None:
        import main
        main.solr_circuit.reset()
        mock_get.side_effect = requests.ConnectionError("Solr down")

        client = _get_test_client()
        for _ in range(main.solr_circuit.failure_threshold):
            resp = client.get("/search", params={"q": "test"})
            assert resp.status_code == 502

        resp = client.get("/search", params={"q": "test"})
        assert resp.status_code == 503
        assert "circuit breaker" in resp.json()["detail"].lower()
        main.solr_circuit.reset()

    @patch("main.requests.post")
    def test_solr_recovers_after_timeout(self, mock_get: MagicMock) -> None:
        import main
        original_timeout = main.solr_circuit.recovery_timeout
        main.solr_circuit.recovery_timeout = 0.1
        main.solr_circuit.reset()

        mock_get.side_effect = requests.ConnectionError("Solr down")
        client = _get_test_client()
        for _ in range(main.solr_circuit.failure_threshold):
            client.get("/search", params={"q": "test"})
        assert main.solr_circuit.state is CircuitState.OPEN

        time.sleep(0.15)
        assert main.solr_circuit.state is CircuitState.HALF_OPEN

        mock_get.side_effect = None
        mock_get.return_value = _mock_solr_response()
        resp = client.get("/search", params={"q": "test"})
        assert resp.status_code == 200
        assert main.solr_circuit.state is CircuitState.CLOSED

        main.solr_circuit.recovery_timeout = original_timeout
        main.solr_circuit.reset()


class TestRedisGracefulDegradation:

    @patch("main.requests.get")
    def test_status_endpoint_degrades_when_redis_circuit_open(self, mock_get: MagicMock) -> None:
        import main
        main.redis_circuit.reset()
        _trip_breaker(main.redis_circuit, _raise_redis_error)
        assert main.redis_circuit.state is CircuitState.OPEN

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"cluster": {"live_nodes": ["n1"], "collections": {}}}
        mock_get.return_value = mock_response

        try:
            data = _get_test_client().get("/v1/status").json()
            assert data["indexing"]["total_discovered"] == 0
        finally:
            main.redis_circuit.reset()

    def test_admin_documents_returns_503_when_redis_circuit_open(self) -> None:
        import main
        main.redis_circuit.reset()
        _trip_breaker(main.redis_circuit, _raise_redis_error)
        try:
            client = _get_test_client()
            client.headers["X-API-Key"] = "circuit-breaker-test-key"
            with patch("admin_auth._get_admin_api_key", return_value="circuit-breaker-test-key"):
                resp = client.get("/v1/admin/documents")
            assert resp.status_code == 503
            assert "circuit breaker" in resp.json()["detail"].lower()
        finally:
            main.redis_circuit.reset()
