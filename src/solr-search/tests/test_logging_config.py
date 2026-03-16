"""Tests for structured JSON logging configuration."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from logging_config import setup_logging  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_root_logger():
    """Ensure the root logger is reset before each test."""
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    yield
    root.handlers = original_handlers
    root.level = original_level


class TestAithenaJsonFormatter:
    """Verify JSON formatter produces valid structured log entries."""

    def test_basic_log_is_valid_json(self, capfd):
        setup_logging(service_name="test-service")
        test_logger = logging.getLogger("test.json_format")
        test_logger.info("hello world")
        captured = capfd.readouterr()
        record = json.loads(captured.out.strip())
        assert record["message"] == "hello world"
        assert record["level"] == "INFO"
        assert record["service"] == "test-service"
        assert "timestamp" in record
        assert record["logger"] == "test.json_format"

    def test_extra_fields_included(self, capfd):
        setup_logging(service_name="test-service")
        test_logger = logging.getLogger("test.extra")
        test_logger.info("request done", extra={"http_status": 200, "duration_ms": 42.5})
        captured = capfd.readouterr()
        record = json.loads(captured.out.strip())
        assert record["http_status"] == 200
        assert record["duration_ms"] == 42.5

    def test_timestamp_is_iso8601(self, capfd):
        setup_logging(service_name="test-service")
        test_logger = logging.getLogger("test.timestamp")
        test_logger.info("check timestamp")
        captured = capfd.readouterr()
        record = json.loads(captured.out.strip())
        ts = record["timestamp"]
        assert "T" in ts
        assert ts.endswith("+00:00")

    def test_exception_included_in_json(self, capfd):
        setup_logging(service_name="test-service")
        test_logger = logging.getLogger("test.exception")
        try:
            raise ValueError("boom")
        except ValueError:
            test_logger.exception("something failed")
        captured = capfd.readouterr()
        record = json.loads(captured.out.strip())
        assert record["level"] == "ERROR"
        assert "exc_info" in record
        assert "ValueError: boom" in record["exc_info"]


class TestAithenaPrettyFormatter:
    """Verify pretty formatter for dev mode."""

    def test_pretty_format_is_human_readable(self, capfd):
        os.environ["LOG_FORMAT"] = "pretty"
        try:
            setup_logging(service_name="my-service")
            test_logger = logging.getLogger("test.pretty")
            test_logger.info("hello pretty")
            captured = capfd.readouterr()
            line = captured.out.strip()
            assert "my-service" in line
            assert "hello pretty" in line
            assert "INFO" in line
            with pytest.raises(json.JSONDecodeError):
                json.loads(line)
        finally:
            os.environ.pop("LOG_FORMAT", None)


class TestSetupLogging:
    """Verify setup_logging respects environment variables."""

    def test_default_log_level_is_info(self):
        os.environ.pop("LOG_LEVEL", None)
        os.environ.pop("LOG_FORMAT", None)
        setup_logging(service_name="test")
        root = logging.getLogger()
        assert root.level == logging.INFO

    def test_log_level_from_env(self):
        os.environ["LOG_LEVEL"] = "DEBUG"
        try:
            setup_logging(service_name="test")
            root = logging.getLogger()
            assert root.level == logging.DEBUG
        finally:
            os.environ.pop("LOG_LEVEL", None)

    def test_warning_level_filters_info(self, capfd):
        os.environ["LOG_LEVEL"] = "WARNING"
        os.environ.pop("LOG_FORMAT", None)
        try:
            setup_logging(service_name="test")
            test_logger = logging.getLogger("test.level_filter")
            test_logger.info("should not appear")
            test_logger.warning("should appear")
            captured = capfd.readouterr()
            lines = [line for line in captured.out.strip().split("\n") if line]
            assert len(lines) == 1
            record = json.loads(lines[0])
            assert record["message"] == "should appear"
        finally:
            os.environ.pop("LOG_LEVEL", None)

    def test_json_is_default_format(self, capfd):
        os.environ.pop("LOG_FORMAT", None)
        setup_logging(service_name="test")
        test_logger = logging.getLogger("test.default_format")
        test_logger.info("default format check")
        captured = capfd.readouterr()
        record = json.loads(captured.out.strip())
        assert record["service"] == "test"
