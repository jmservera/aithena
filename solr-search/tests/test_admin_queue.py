"""Tests for admin queue management endpoints."""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("UPLOAD_DIR", "/tmp/test_uploads_admin")
# QUEUE_NAME drives admin_queue_name; RABBITMQ_QUEUE_NAME is the upload queue name
os.environ.setdefault("RABBITMQ_QUEUE_NAME", "shortembeddings")
os.environ.setdefault("QUEUE_NAME", "shortembeddings")

from fastapi.testclient import TestClient  # noqa: E402
from main import _decode_queue_key, _encode_queue_key, app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _make_redis_entry(path: str, processed: bool = False, failed: bool = False, error: str | None = None) -> str:
    """Build a JSON entry matching the format written by document-lister."""
    entry: dict = {
        "path": path,
        "last_modified": 1700000000.0,
        "processed": processed,
        "timestamp": "2024-01-15T10:00:00",
    }
    if failed:
        entry["failed"] = True
    if error:
        entry["error"] = error
    return json.dumps(entry)


def _encode(key: str) -> str:
    """URL-safe base64 encode without padding."""
    return base64.urlsafe_b64encode(key.encode()).decode().rstrip("=")


# ---------------------------------------------------------------------------
# Key encoding helpers
# ---------------------------------------------------------------------------


def test_encode_decode_round_trip():
    key = "/shortembeddings//data/documents/my_book.pdf"
    encoded = _encode_queue_key(key)
    assert _decode_queue_key(encoded) == key


def test_decode_invalid_key_raises_400(client: TestClient):
    response = client.post("/v1/admin/documents/!!!invalid!!!/requeue")
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /v1/admin/queue
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
def test_admin_queue_empty(mock_pool: MagicMock, client: TestClient):
    """Returns zeros when Redis has no documents."""
    mock_client = MagicMock()
    mock_client.scan_iter.return_value = iter([])
    mock_pool.return_value.connection_class = None
    mock_pool.return_value = MagicMock()

    with patch("redis.Redis", return_value=mock_client):
        response = client.get("/v1/admin/queue")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["queued"] == 0
    assert data["processed"] == 0
    assert data["failed"] == 0
    assert data["queued_documents"] == []
    assert data["processed_documents"] == []
    assert data["failed_documents"] == []


@patch("main._get_redis_pool")
def test_admin_queue_with_documents(mock_pool: MagicMock, client: TestClient):
    """Returns counts and document lists split by state."""
    queue_key = "/shortembeddings//data/documents/queued.pdf"
    processed_key = "/shortembeddings//data/documents/processed.pdf"
    failed_key = "/shortembeddings//data/documents/failed.pdf"

    mock_client = MagicMock()
    mock_client.scan_iter.return_value = iter([queue_key, processed_key, failed_key])
    mock_client.mget.return_value = [
        _make_redis_entry(queue_key),
        _make_redis_entry(processed_key, processed=True),
        _make_redis_entry(failed_key, failed=True, error="Extraction failed"),
    ]

    with patch("redis.Redis", return_value=mock_client):
        response = client.get("/v1/admin/queue")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert data["queued"] == 1
    assert data["processed"] == 1
    assert data["failed"] == 1
    assert len(data["queued_documents"]) == 1
    assert len(data["processed_documents"]) == 1
    assert len(data["failed_documents"]) == 1

    # Verify id field is present and is a non-empty string
    assert data["failed_documents"][0]["id"]
    assert data["failed_documents"][0]["error"] == "Extraction failed"


@patch("main._get_redis_pool")
def test_admin_queue_redis_unavailable(mock_pool: MagicMock, client: TestClient):
    """Returns 503 when Redis is down."""
    import redis as redis_lib

    mock_client = MagicMock()
    mock_client.scan_iter.side_effect = redis_lib.exceptions.ConnectionError("down")

    with patch("redis.Redis", return_value=mock_client):
        response = client.get("/v1/admin/queue")

    assert response.status_code == 503


# ---------------------------------------------------------------------------
# POST /v1/admin/documents/{id}/requeue
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
def test_admin_requeue_document_success(mock_pool: MagicMock, client: TestClient):
    """Deletes the Redis key for a given document id."""
    redis_key = "/shortembeddings//data/documents/failed.pdf"
    doc_id = _encode(redis_key)

    mock_client = MagicMock()
    mock_client.delete.return_value = 1  # 1 key deleted

    with patch("redis.Redis", return_value=mock_client):
        response = client.post(f"/v1/admin/documents/{doc_id}/requeue")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "requeued"
    assert data["id"] == doc_id
    mock_client.delete.assert_called_once_with(redis_key)


@patch("main._get_redis_pool")
def test_admin_requeue_document_not_found(mock_pool: MagicMock, client: TestClient):
    """Returns 404 when the document key does not exist."""
    redis_key = "/shortembeddings//data/documents/missing.pdf"
    doc_id = _encode(redis_key)

    mock_client = MagicMock()
    mock_client.delete.return_value = 0  # nothing deleted

    with patch("redis.Redis", return_value=mock_client):
        response = client.post(f"/v1/admin/documents/{doc_id}/requeue")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /v1/admin/documents/requeue-failed
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
def test_admin_requeue_failed_all(mock_pool: MagicMock, client: TestClient):
    """Deletes all failed document keys and returns count."""
    failed_key = "/shortembeddings//data/documents/failed.pdf"

    mock_client = MagicMock()
    mock_client.scan_iter.return_value = iter([failed_key])
    mock_client.mget.return_value = [_make_redis_entry(failed_key, failed=True, error="err")]
    mock_client.delete.return_value = 1

    with patch("redis.Redis", return_value=mock_client):
        response = client.post("/v1/admin/documents/requeue-failed")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["requeued"] == 1


@patch("main._get_redis_pool")
def test_admin_requeue_failed_nothing_to_requeue(mock_pool: MagicMock, client: TestClient):
    """Returns 0 requeued when there are no failed documents."""
    mock_client = MagicMock()
    mock_client.scan_iter.return_value = iter([])

    with patch("redis.Redis", return_value=mock_client):
        response = client.post("/v1/admin/documents/requeue-failed")

    assert response.status_code == 200
    assert response.json()["requeued"] == 0


# ---------------------------------------------------------------------------
# DELETE /v1/admin/documents/processed
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
def test_admin_clear_processed(mock_pool: MagicMock, client: TestClient):
    """Deletes all processed document keys and returns count."""
    processed_key = "/shortembeddings//data/documents/indexed.pdf"

    mock_client = MagicMock()
    mock_client.scan_iter.return_value = iter([processed_key])
    mock_client.mget.return_value = [_make_redis_entry(processed_key, processed=True)]
    mock_client.delete.return_value = 1

    with patch("redis.Redis", return_value=mock_client):
        response = client.delete("/v1/admin/documents/processed")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["cleared"] == 1


@patch("main._get_redis_pool")
def test_admin_clear_processed_nothing_to_clear(mock_pool: MagicMock, client: TestClient):
    """Returns 0 cleared when there are no processed documents."""
    mock_client = MagicMock()
    mock_client.scan_iter.return_value = iter([])

    with patch("redis.Redis", return_value=mock_client):
        response = client.delete("/v1/admin/documents/processed")

    assert response.status_code == 200
    assert response.json()["cleared"] == 0


# ---------------------------------------------------------------------------
# Slash-redirect variant
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
def test_admin_queue_slash_redirect(mock_pool: MagicMock, client: TestClient):
    """GET /v1/admin/queue/ returns the same data as /v1/admin/queue."""
    mock_client = MagicMock()
    mock_client.scan_iter.return_value = iter([])

    with patch("redis.Redis", return_value=mock_client):
        response = client.get("/v1/admin/queue/", follow_redirects=True)

    assert response.status_code == 200
    assert "total" in response.json()
