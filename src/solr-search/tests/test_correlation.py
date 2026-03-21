"""Tests for correlation ID tracking across service boundaries."""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("AUTH_DB_PATH", "/tmp/test-auth.db")  # noqa: S108
os.environ.setdefault("AUTH_JWT_SECRET", "test-auth-secret")
os.environ.setdefault("AUTH_JWT_TTL", "24h")
os.environ.setdefault("AUTH_COOKIE_NAME", "aithena_auth")

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from correlation import (  # noqa: E402
    CORRELATION_ID_HEADER,
    CorrelationIdFilter,
    correlation_id_var,
    generate_correlation_id,
    get_correlation_id,
    set_correlation_id,
)
from fastapi.testclient import TestClient  # noqa: E402, F401
from main import app  # noqa: E402, F401

from tests.auth_helpers import create_authenticated_client  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_correlation_id():
    """Reset the correlation ID ContextVar between tests."""
    token = correlation_id_var.set("")
    yield
    correlation_id_var.reset(token)


# ---------------------------------------------------------------------------
# Unit tests for correlation.py primitives
# ---------------------------------------------------------------------------


class TestGenerateCorrelationId:
    def test_returns_valid_uuid4(self):
        cid = generate_correlation_id()
        parsed = uuid.UUID(cid, version=4)
        assert str(parsed) == cid

    def test_unique_on_each_call(self):
        ids = {generate_correlation_id() for _ in range(100)}
        assert len(ids) == 100


class TestContextVarAccessors:
    def test_default_is_empty_string(self):
        assert get_correlation_id() == ""

    def test_set_and_get_round_trip(self):
        set_correlation_id("abc-123")
        assert get_correlation_id() == "abc-123"

    def test_set_overwrites_previous(self):
        set_correlation_id("first")
        set_correlation_id("second")
        assert get_correlation_id() == "second"


class TestCorrelationIdFilter:
    def test_adds_correlation_id_to_log_record(self):
        set_correlation_id("test-cid-42")
        log_filter = CorrelationIdFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        result = log_filter.filter(record)
        assert result is True
        assert record.correlation_id == "test-cid-42"  # type: ignore[attr-defined]

    def test_no_attribute_when_unset(self):
        log_filter = CorrelationIdFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        log_filter.filter(record)
        assert not hasattr(record, "correlation_id")


# ---------------------------------------------------------------------------
# Integration tests for CorrelationIdMiddleware via FastAPI TestClient
# ---------------------------------------------------------------------------


class TestCorrelationIdMiddleware:
    """Test the middleware through the real FastAPI app."""

    def _get_client(self) -> TestClient:
        return create_authenticated_client()

    def test_generates_correlation_id_when_none_provided(self):
        client = self._get_client()
        response = client.get("/health")
        assert response.status_code == 200
        cid = response.headers.get(CORRELATION_ID_HEADER)
        assert cid is not None
        uuid.UUID(cid, version=4)

    def test_propagates_incoming_correlation_id(self):
        client = self._get_client()
        incoming_cid = "incoming-test-id-12345"
        response = client.get(
            "/health",
            headers={CORRELATION_ID_HEADER: incoming_cid},
        )
        assert response.status_code == 200
        assert response.headers.get(CORRELATION_ID_HEADER) == incoming_cid

    def test_strips_whitespace_from_incoming_header(self):
        client = self._get_client()
        response = client.get(
            "/health",
            headers={CORRELATION_ID_HEADER: "  spaced-id  "},
        )
        assert response.status_code == 200
        assert response.headers.get(CORRELATION_ID_HEADER) == "spaced-id"

    def test_generates_new_id_for_empty_header(self):
        client = self._get_client()
        response = client.get(
            "/health",
            headers={CORRELATION_ID_HEADER: ""},
        )
        assert response.status_code == 200
        cid = response.headers.get(CORRELATION_ID_HEADER)
        assert cid is not None
        assert cid != ""
        uuid.UUID(cid, version=4)

    def test_generates_new_id_for_whitespace_only_header(self):
        client = self._get_client()
        response = client.get(
            "/health",
            headers={CORRELATION_ID_HEADER: "   "},
        )
        assert response.status_code == 200
        cid = response.headers.get(CORRELATION_ID_HEADER)
        assert cid is not None
        uuid.UUID(cid, version=4)

    def test_different_requests_get_different_ids(self):
        client = self._get_client()
        r1 = client.get("/health")
        r2 = client.get("/health")
        cid1 = r1.headers.get(CORRELATION_ID_HEADER)
        cid2 = r2.headers.get(CORRELATION_ID_HEADER)
        assert cid1 != cid2

    def test_correlation_id_on_authenticated_endpoint(self):
        """Verify correlation ID is returned even for auth-protected endpoints."""
        client = self._get_client()
        with patch("main.requests.post") as mock_solr:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "response": {"numFound": 0, "docs": []},
                "facet_counts": {"facet_fields": {}},
                "highlighting": {},
            }
            mock_solr.return_value = mock_response
            response = client.get("/v1/search?q=test")
        cid = response.headers.get(CORRELATION_ID_HEADER)
        assert cid is not None
        uuid.UUID(cid, version=4)


# ---------------------------------------------------------------------------
# Test correlation ID appears in structured JSON log output
# ---------------------------------------------------------------------------


class TestCorrelationIdInLogs:
    """Verify that the correlation ID appears in structured log output."""

    def test_correlation_id_in_json_log(self, capfd):
        """When a request has a correlation ID, it should appear in JSON logs."""
        from logging_config import setup_logging

        root = logging.getLogger()
        original_handlers = root.handlers[:]
        original_level = root.level
        root.handlers.clear()

        try:
            os.environ.pop("LOG_FORMAT", None)
            setup_logging(service_name="test-correlation")
            test_logger = logging.getLogger("test.correlation_json")

            set_correlation_id("log-test-cid-999")
            test_logger.info("request processed", extra={"status": 200})

            captured = capfd.readouterr()
            lines = [ln for ln in captured.out.strip().split("\n") if ln.strip()]
            record = None
            for line in lines:
                try:
                    parsed = json.loads(line)
                    if parsed.get("message") == "request processed":
                        record = parsed
                        break
                except json.JSONDecodeError:
                    continue

            assert record is not None, f"Could not find log line in: {captured.out}"
            assert record["correlation_id"] == "log-test-cid-999"
            assert record["service"] == "test-correlation"
        finally:
            root.handlers = original_handlers
            root.level = original_level

    def test_no_correlation_id_when_empty(self, capfd):
        """When correlation ID is empty, it should not appear in JSON output."""
        from logging_config import setup_logging

        root = logging.getLogger()
        original_handlers = root.handlers[:]
        original_level = root.level
        root.handlers.clear()

        try:
            os.environ.pop("LOG_FORMAT", None)
            setup_logging(service_name="test-no-cid")
            test_logger = logging.getLogger("test.no_cid")
            test_logger.info("no correlation")

            captured = capfd.readouterr()
            lines = [ln for ln in captured.out.strip().split("\n") if ln.strip()]
            record = None
            for line in lines:
                try:
                    parsed = json.loads(line)
                    if parsed.get("message") == "no correlation":
                        record = parsed
                        break
                except json.JSONDecodeError:
                    continue

            assert record is not None
            assert "correlation_id" not in record
        finally:
            root.handlers = original_handlers
            root.level = original_level

    def test_correlation_id_in_pretty_log(self, capfd):
        """Pretty formatter should include cid= when set."""
        from logging_config import setup_logging

        root = logging.getLogger()
        original_handlers = root.handlers[:]
        original_level = root.level
        root.handlers.clear()

        try:
            os.environ["LOG_FORMAT"] = "pretty"
            setup_logging(service_name="test-pretty-cid")
            test_logger = logging.getLogger("test.pretty_cid")

            set_correlation_id("pretty-cid-abc")
            test_logger.info("pretty with cid")

            captured = capfd.readouterr()
            lines = [ln for ln in captured.out.strip().split("\n") if "pretty with cid" in ln]
            assert len(lines) >= 1, f"Expected 'pretty with cid' in: {captured.out}"
            line = lines[0]
            assert "cid=pretty-cid-abc" in line
        finally:
            os.environ.pop("LOG_FORMAT", None)
            root.handlers = original_handlers
            root.level = original_level
