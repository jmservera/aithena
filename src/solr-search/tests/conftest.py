"""Shared test configuration — loaded by pytest before any test modules.

Sets environment variables that the Settings dataclass needs so the
module-level ``settings`` singleton can be created without requiring
real infrastructure paths (like /data) that don't exist on CI runners.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

# Paths that default to /data/* in production — redirect to /tmp for tests
os.environ.setdefault("BASE_PATH", "/tmp/test_data")  # noqa: S108
os.environ.setdefault("UPLOAD_DIR", "/tmp/test_uploads")  # noqa: S108
os.environ.setdefault("COLLECTIONS_DB_PATH", "/tmp/test-collections.db")  # noqa: S108
os.environ.setdefault("AUTH_DB_PATH", "/tmp/test-auth.db")  # noqa: S108

# Auth defaults
os.environ.setdefault("AUTH_JWT_SECRET", "test-secret-key-for-testing-only")
os.environ.setdefault("AUTH_JWT_TTL", "24h")
os.environ.setdefault("AUTH_COOKIE_NAME", "aithena_auth")

# Service hosts — use localhost to avoid DNS failures on CI
os.environ.setdefault("RABBITMQ_HOST", "localhost")
os.environ.setdefault("RABBITMQ_QUEUE_NAME", "shortembeddings")


@pytest.fixture(autouse=True)
def _mock_pika_globally(monkeypatch):
    """Prevent real RabbitMQ connections during all tests.

    Individual tests can still override with their own mock_rabbitmq fixture.
    """
    import pika  # noqa: E402

    mock_conn = MagicMock()
    mock_conn.return_value.channel.return_value = MagicMock()
    mock_conn.return_value.is_closed = False
    monkeypatch.setattr(pika, "BlockingConnection", mock_conn)
