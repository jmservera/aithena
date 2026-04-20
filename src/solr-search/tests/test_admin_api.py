"""Tests for the new admin API endpoints (queue-status, indexing-status, logs, infrastructure)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("AUTH_DB_PATH", "/tmp/test-auth.db")  # noqa: S108
os.environ.setdefault("AUTH_JWT_SECRET", "test-auth-secret")
os.environ.setdefault("AUTH_JWT_TTL", "24h")
os.environ.setdefault("AUTH_COOKIE_NAME", "aithena_auth")

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from config import settings  # noqa: E402
from tests.auth_helpers import create_authenticated_client  # noqa: E402

_TEST_ADMIN_KEY = "test-admin-api-key"

QUEUE = settings.redis_queue_name


def get_client() -> TestClient:
    client = create_authenticated_client()
    client.headers["X-API-Key"] = _TEST_ADMIN_KEY
    return client


@pytest.fixture(autouse=True)
def _enable_admin_api_key():
    """Patch ADMIN_API_KEY so admin endpoints are accessible in these tests."""
    with patch("admin_auth._get_admin_api_key", return_value=_TEST_ADMIN_KEY):
        yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STATE_QUEUED = {
    "path": "/data/docs/queued.pdf",
    "timestamp": "2024-03-01T10:00:00",
    "last_modified": 1709283600.0,
    "processed": False,
}

STATE_PROCESSING = {
    "path": "/data/docs/processing.pdf",
    "timestamp": "2024-03-01T10:30:00",
    "last_modified": 1709285400.0,
    "processed": False,
    "processing": True,
    "text_indexed": True,
    "page_count": 50,
    "chunk_count": 200,
}

STATE_PROCESSED = {
    "path": "/data/docs/processed.pdf",
    "timestamp": "2024-03-01T11:00:00",
    "last_modified": 1709287200.0,
    "processed": True,
    "title": "My Book",
    "author": "Author Name",
    "page_count": 42,
    "chunk_count": 100,
}

STATE_FAILED = {
    "path": "/data/docs/failed.pdf",
    "timestamp": "2024-03-01T12:00:00",
    "last_modified": 1709290800.0,
    "processed": False,
    "failed": True,
    "error": "PDF parsing error",
    "error_stage": "extraction",
}


def _make_redis_mock(entries: dict[str, dict]) -> MagicMock:
    """Return a mock Redis client with the given key→state mapping."""
    mock = MagicMock()
    mock.scan_iter.return_value = iter(entries.keys())
    mock.get.side_effect = lambda key: json.dumps(entries[key]) if key in entries else None
    return mock


# ---------------------------------------------------------------------------
# GET /v1/admin/queue-status
# ---------------------------------------------------------------------------


class TestQueueStatus:
    def test_queue_status_ok(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "messages_ready": 5,
            "messages_unacknowledged": 2,
            "messages": 7,
            "consumers": 1,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("main.requests.get", return_value=mock_response):
            client = get_client()
            resp = client.get("/v1/admin/queue-status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["queue_name"] == QUEUE
        assert data["messages_ready"] == 5
        assert data["messages_unacknowledged"] == 2
        assert data["messages_total"] == 7
        assert data["consumers"] == 1
        assert data["status"] == "ok"

    def test_queue_status_queue_not_found(self):
        import requests as req_lib

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = req_lib.HTTPError(response=mock_response)

        with patch("main.requests.get", return_value=mock_response):
            client = get_client()
            resp = client.get("/v1/admin/queue-status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "queue_not_found"
        assert data["messages_total"] == 0

    def test_queue_status_api_unreachable(self):
        import requests as req_lib

        with patch("main.requests.get", side_effect=req_lib.ConnectionError("refused")):
            client = get_client()
            resp = client.get("/v1/admin/queue-status")

        assert resp.status_code == 502

    def test_queue_status_trailing_slash(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "messages_ready": 0,
            "messages_unacknowledged": 0,
            "messages": 0,
            "consumers": 0,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("main.requests.get", return_value=mock_response):
            client = get_client()
            resp = client.get("/v1/admin/queue-status/")

        assert resp.status_code == 200

    def test_queue_status_requires_auth(self):
        """Verify the endpoint is not accessible without admin auth."""
        from main import app

        unauthed = TestClient(app)
        resp = unauthed.get("/v1/admin/queue-status")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /v1/admin/indexing-status
# ---------------------------------------------------------------------------


class TestIndexingStatus:
    def _patch_redis(self, entries: dict[str, dict]):
        mock = _make_redis_mock(entries)
        return patch("main._get_admin_redis_client", return_value=mock)

    def test_indexing_status_empty(self):
        with self._patch_redis({}):
            client = get_client()
            resp = client.get("/v1/admin/indexing-status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total"] == 0
        assert data["documents"] == []
        assert data["page"] == 1

    def test_indexing_status_mixed(self):
        entries = {
            f"/{QUEUE}//data/docs/queued.pdf": STATE_QUEUED,
            f"/{QUEUE}//data/docs/processing.pdf": STATE_PROCESSING,
            f"/{QUEUE}//data/docs/processed.pdf": STATE_PROCESSED,
            f"/{QUEUE}//data/docs/failed.pdf": STATE_FAILED,
        }
        with self._patch_redis(entries):
            client = get_client()
            resp = client.get("/v1/admin/indexing-status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total"] == 4
        assert data["summary"]["queued"] == 1
        assert data["summary"]["processing"] == 1
        assert data["summary"]["processed"] == 1
        assert data["summary"]["failed"] == 1
        assert data["summary"]["total_doc_pages"] == 92  # 50 + 42
        assert data["summary"]["total_doc_chunks"] == 300  # 200 + 100
        assert len(data["documents"]) == 4

    def test_indexing_status_filter_failed(self):
        entries = {
            f"/{QUEUE}//data/docs/queued.pdf": STATE_QUEUED,
            f"/{QUEUE}//data/docs/failed.pdf": STATE_FAILED,
        }
        with self._patch_redis(entries):
            client = get_client()
            resp = client.get("/v1/admin/indexing-status?status=failed")

        data = resp.json()
        assert data["summary"]["total"] == 2  # summary always reflects all
        assert len(data["documents"]) == 1
        assert data["documents"][0]["status"] == "failed"
        assert data["documents"][0]["error"] == "PDF parsing error"
        assert data["documents"][0]["error_stage"] == "extraction"

    def test_indexing_status_pagination(self):
        entries = {
            f"/{QUEUE}//data/docs/doc{i}.pdf": {**STATE_QUEUED, "path": f"/data/docs/doc{i}.pdf"} for i in range(5)
        }
        with self._patch_redis(entries):
            client = get_client()
            resp = client.get("/v1/admin/indexing-status?page=1&per_page=2")

        data = resp.json()
        assert data["total_documents"] == 5
        assert len(data["documents"]) == 2
        assert data["page"] == 1
        assert data["per_page"] == 2
        assert data["total_pages"] == 3

    def test_indexing_status_requires_auth(self):
        from main import app

        unauthed = TestClient(app)
        resp = unauthed.get("/v1/admin/indexing-status")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /v1/admin/logs/{service_name}
# ---------------------------------------------------------------------------


class TestLogs:
    def test_logs_invalid_service(self):
        client = get_client()
        resp = client.get("/v1/admin/logs/malicious-service")
        assert resp.status_code == 400
        assert "Unknown service" in resp.json()["detail"]

    def test_logs_valid_service(self):
        mock_lines = ["2025-07-18T10:00:01Z INFO Starting...", "2025-07-18T10:00:02Z INFO Done."]
        with patch("main._fetch_docker_logs", return_value=mock_lines):
            client = get_client()
            resp = client.get("/v1/admin/logs/document-indexer")

        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "document-indexer"
        assert data["lines"] == mock_lines
        assert data["total_lines"] == 2
        assert "document-indexer" in data["available_services"]

    def test_logs_docker_unreachable(self):
        exc = HTTPException(status_code=502, detail="Cannot reach Docker API: refused")
        with patch("main._fetch_docker_logs", side_effect=exc):
            client = get_client()
            resp = client.get("/v1/admin/logs/solr-search")

        assert resp.status_code == 502

    def test_logs_tail_capped(self):
        with patch("main._fetch_docker_logs", return_value=[]) as mock_fetch:
            client = get_client()
            resp = client.get("/v1/admin/logs/solr-search?tail=99999")

        assert resp.status_code == 200
        call_args = mock_fetch.call_args
        called_tail = (
            call_args.kwargs.get("tail")
            or call_args[1].get("tail")
            or (call_args[0][1] if len(call_args[0]) > 1 else None)
        )
        assert called_tail is not None
        assert called_tail <= settings.log_tail_max

    def test_logs_since_param(self):
        with patch("main._fetch_docker_logs", return_value=[]) as mock_fetch:
            client = get_client()
            resp = client.get("/v1/admin/logs/solr-search?since=2025-07-18T00:00:00Z")

        assert resp.status_code == 200
        called_since = mock_fetch.call_args.kwargs.get("since") or mock_fetch.call_args[1].get("since")
        assert called_since == "2025-07-18T00:00:00Z"

    def test_logs_trailing_slash(self):
        with patch("main._fetch_docker_logs", return_value=[]):
            client = get_client()
            resp = client.get("/v1/admin/logs/solr-search/")

        assert resp.status_code == 200

    def test_logs_requires_auth(self):
        from main import app

        unauthed = TestClient(app)
        resp = unauthed.get("/v1/admin/logs/solr-search")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /v1/admin/infrastructure
# ---------------------------------------------------------------------------


class TestInfrastructure:
    def test_infrastructure_all_up(self):
        with (
            patch("main._tcp_check", return_value=True),
            patch("main._rabbitmq_management_check", return_value=True),
            patch("main._embeddings_available", return_value=True),
        ):
            client = get_client()
            resp = client.get("/v1/admin/infrastructure")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["services"], list)
        service_names = [s["name"] for s in data["services"]]
        assert "solr" in service_names
        assert "rabbitmq" in service_names
        assert "redis-commander" in service_names
        assert "embeddings-server" in service_names

        for svc in data["services"]:
            assert svc["status"] == "up"

        assert "solr" in data["connections"]
        assert "redis" in data["connections"]
        assert "rabbitmq_amqp" in data["connections"]
        assert "rabbitmq_mgmt" in data["connections"]
        assert "embeddings" in data["connections"]

    def test_infrastructure_some_down(self):
        def selective_tcp(host, port, timeout=2.0):
            return host != settings.redis_host

        with (
            patch("main._tcp_check", side_effect=selective_tcp),
            patch("main._rabbitmq_management_check", return_value=False),
            patch("main._embeddings_available", return_value=True),
        ):
            client = get_client()
            resp = client.get("/v1/admin/infrastructure")

        data = resp.json()
        statuses = {s["name"]: s["status"] for s in data["services"]}
        assert statuses["solr"] == "up"
        assert statuses["redis-commander"] == "down"
        assert statuses["rabbitmq"] == "down"
        assert statuses["embeddings-server"] == "up"

    def test_infrastructure_trailing_slash(self):
        with (
            patch("main._tcp_check", return_value=True),
            patch("main._rabbitmq_management_check", return_value=True),
            patch("main._embeddings_available", return_value=True),
        ):
            client = get_client()
            resp = client.get("/v1/admin/infrastructure/")

        assert resp.status_code == 200

    def test_infrastructure_requires_auth(self):
        from main import app

        unauthed = TestClient(app)
        resp = unauthed.get("/v1/admin/infrastructure")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Pagination on GET /v1/admin/documents
# ---------------------------------------------------------------------------


class TestDocumentsPagination:
    def _patch_redis(self, entries: dict[str, dict]):
        mock = _make_redis_mock(entries)
        return patch("main._get_admin_redis_client", return_value=mock)

    def test_documents_pagination_defaults(self):
        entries = {
            f"/{QUEUE}//data/docs/queued.pdf": STATE_QUEUED,
            f"/{QUEUE}//data/docs/processed.pdf": STATE_PROCESSED,
        }
        with self._patch_redis(entries):
            client = get_client()
            resp = client.get("/v1/admin/documents")

        data = resp.json()
        assert data["page"] == 1
        assert data["per_page"] == 100
        assert data["total_documents"] == 2
        assert data["total_pages"] == 1

    def test_documents_pagination_limits(self):
        entries = {
            f"/{QUEUE}//data/docs/doc{i}.pdf": {**STATE_QUEUED, "path": f"/data/docs/doc{i}.pdf"} for i in range(5)
        }
        with self._patch_redis(entries):
            client = get_client()
            resp = client.get("/v1/admin/documents?page=2&per_page=2")

        data = resp.json()
        assert data["page"] == 2
        assert data["per_page"] == 2
        assert len(data["documents"]) == 2
        assert data["total_documents"] == 5
        assert data["total_pages"] == 3


# Import HTTPException for test use
from fastapi import HTTPException  # noqa: E402
