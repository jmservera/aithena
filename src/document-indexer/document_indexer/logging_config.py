"""Structured JSON logging configuration for Aithena services.

Usage:
    from logging_config import setup_logging

    setup_logging(service_name="solr-search")

Environment variables:
    LOG_LEVEL  — Python log level name (default: INFO)
    LOG_FORMAT — "json" (default) or "pretty" for human-readable dev output
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import UTC, datetime

from pythonjsonlogger.json import JsonFormatter


class AithenaJsonFormatter(JsonFormatter):
    """JSON formatter that includes service name and ISO 8601 timestamps."""

    def __init__(self, service_name: str = "unknown", **kwargs):
        super().__init__(**kwargs)
        self.service_name = service_name

    def add_fields(self, log_record: dict, record: logging.LogRecord, message_dict: dict) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record["timestamp"] = datetime.now(UTC).isoformat()
        log_record["level"] = record.levelname
        log_record["service"] = self.service_name
        log_record["logger"] = record.name
        if record.exc_info and not log_record.get("exc_info"):
            log_record["exc_info"] = self.formatException(record.exc_info)


class AithenaPrettyFormatter(logging.Formatter):
    """Human-readable formatter for local development."""

    def __init__(self, service_name: str = "unknown"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S")
        base = f"{timestamp} [{record.levelname:<8}] {self.service_name} | {record.name} | {record.getMessage()}"
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            base += f"\n{record.exc_text}"
        return base


def setup_logging(service_name: str = "unknown") -> logging.Logger:
    """Configure the root logger with structured JSON or pretty output.

    Args:
        service_name: Identifier included in every log entry (e.g. "solr-search").

    Returns:
        The root logger, already configured.
    """
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_format = os.environ.get("LOG_FORMAT", "json").lower()

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Remove any existing handlers (e.g. from basicConfig)
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)

    if log_format == "pretty":
        handler.setFormatter(AithenaPrettyFormatter(service_name=service_name))
    else:
        handler.setFormatter(
            AithenaJsonFormatter(
                service_name=service_name,
                fmt="%(timestamp)s %(level)s %(service)s %(name)s %(message)s",
            )
        )

    root_logger.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("pika").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    return root_logger
