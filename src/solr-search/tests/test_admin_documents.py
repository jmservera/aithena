"""Tests for the /v1/admin/documents endpoints (document triage and recovery)."""

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
from config import settings  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import _decode_admin_key, _encode_admin_key  # noqa: E402

from tests.auth_helpers import create_authenticated_client  # noqa: E402

_TEST_ADMIN_KEY = "test-admin-documents-key"


def get_client() -> TestClient:
    client = create_authenticated_client()
    client.headers["X-API-Key"] = _TEST_ADMIN_KEY
    return client


@pytest.fixture(autouse=True)
def _enable_admin_api_key():
    """Patch ADMIN_API_KEY so admin endpoints are accessible in these tests."""
    with patch("admin_auth.ADMIN_API_KEY", _TEST_ADMIN_KEY):
        yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

QUEUE = settings.redis_queue_name
KEY_QUEUED = f"/{QUEUE}//data/docs/queued.pdf"
KEY_PROCESSED = f"/{QUEUE}//data/docs/processed.pdf"
KEY_FAILED = f"/{QUEUE}//data/docs/failed.pdf"

STATE_QUEUED = {
    "path": "/data/docs/queued.pdf",
    "timestamp": "2024-03-01T10:00:00",
    "last_modified": 1709283600.0,
    "processed": False,
}

STATE_PROCESSED = {
    "path": "/data/docs/processed.pdf",
    "timestamp": "2024-03-01T11:00:00",
    "last_modified": 1709287200.0,
    "processed": True,
    "title": "My Book",
    "author": "Author Name",
    "year": 2024,
    "category": "Fiction",
    "page_count": 42,
}

STATE_FAILED = {
    "path": "/data/docs/failed.pdf",
    "timestamp": "2024-03-01T12:00:00",
    "last_modified": 1709290800.0,
    "processed": False,
    "failed": True,
    "error": "PDF parsing error",
}


def _make_redis_mock(entries: dict[str, dict]) -> MagicMock:
    """Return a mock Redis client with the given key→state mapping."""
    mock = MagicMock()
    mock.scan_iter.return_value = iter(list(entries.keys()))

    def _get(key: str):
        val = entries.get(key)
        return json.dumps(val) if val is not None else None

    mock.get.side_effect = _get
    mock.delete.return_value = 1
    return mock


def _all_entries() -> dict[str, dict]:
    return {
        KEY_QUEUED: STATE_QUEUED,
        KEY_PROCESSED: STATE_PROCESSED,
        KEY_FAILED: STATE_FAILED,
    }


# ---------------------------------------------------------------------------
# _encode_admin_key / _decode_admin_key unit tests
# ---------------------------------------------------------------------------


def test_encode_decode_admin_key_roundtrip() -> None:
    key = f"/{QUEUE}//data/docs/book.pdf"
    assert _decode_admin_key(_encode_admin_key(key)) == key


def test_decode_invalid_token_raises() -> None:
    import pytest

    with pytest.raises(ValueError):
        _decode_admin_key("not-valid-base64!!!")


# ---------------------------------------------------------------------------
# GET /v1/admin/documents — list all
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
def test_admin_list_documents_returns_all(mock_pool: MagicMock) -> None:
    """GET /v1/admin/documents returns counts and all documents."""
    redis_mock = _make_redis_mock(_all_entries())
    mock_pool.return_value = MagicMock()
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.get("/v1/admin/documents")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert data["queued"] == 1
    assert data["processed"] == 1
    assert data["failed"] == 1
    assert len(data["documents"]) == 3


@patch("main._get_redis_pool")
def test_admin_list_documents_filter_queued(mock_pool: MagicMock) -> None:
    """?status=queued returns only queued documents."""
    redis_mock = _make_redis_mock(_all_entries())
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.get("/v1/admin/documents", params={"status": "queued"})

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert data["queued"] == 1
    assert len(data["documents"]) == 1
    doc = data["documents"][0]
    assert doc["status"] == "queued"
    assert doc["path"] == "/data/docs/queued.pdf"
    assert "timestamp" in doc
    assert "last_modified" in doc
    assert "id" in doc


@patch("main._get_redis_pool")
def test_admin_list_documents_filter_processed(mock_pool: MagicMock) -> None:
    """?status=processed returns only processed documents."""
    redis_mock = _make_redis_mock(_all_entries())
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.get("/v1/admin/documents", params={"status": "processed"})

    data = response.json()
    assert len(data["documents"]) == 1
    doc = data["documents"][0]
    assert doc["status"] == "processed"
    assert doc["path"] == "/data/docs/processed.pdf"
    assert doc["title"] == "My Book"
    assert doc["author"] == "Author Name"
    assert doc["year"] == 2024
    assert doc["category"] == "Fiction"
    assert doc["page_count"] == 42


@patch("main._get_redis_pool")
def test_admin_list_documents_filter_failed(mock_pool: MagicMock) -> None:
    """?status=failed returns only failed documents."""
    redis_mock = _make_redis_mock(_all_entries())
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.get("/v1/admin/documents", params={"status": "failed"})

    data = response.json()
    assert len(data["documents"]) == 1
    doc = data["documents"][0]
    assert doc["status"] == "failed"
    assert doc["path"] == "/data/docs/failed.pdf"
    assert doc["error"] == "PDF parsing error"


@patch("main._get_redis_pool")
def test_admin_list_documents_invalid_status(mock_pool: MagicMock) -> None:
    """?status=unknown must be rejected with 422."""
    redis_mock = _make_redis_mock(_all_entries())
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.get("/v1/admin/documents", params={"status": "unknown"})

    assert response.status_code == 422


@patch("main._get_redis_pool")
def test_admin_list_documents_empty_redis(mock_pool: MagicMock) -> None:
    """Empty Redis returns zero counts and empty list."""
    redis_mock = _make_redis_mock({})
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.get("/v1/admin/documents")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["queued"] == 0
    assert data["processed"] == 0
    assert data["failed"] == 0
    assert data["documents"] == []


@patch("main._get_redis_pool")
def test_admin_list_documents_skips_invalid_json(mock_pool: MagicMock) -> None:
    """Corrupt Redis values are silently skipped."""
    mock_redis = MagicMock()
    mock_redis.scan_iter.return_value = iter([KEY_QUEUED, "bad_key"])
    mock_redis.get.side_effect = lambda k: (
        json.dumps(STATE_QUEUED) if k == KEY_QUEUED else "not-json"
    )
    with patch("main._get_admin_redis_client", return_value=mock_redis):
        client = get_client()
        response = client.get("/v1/admin/documents")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1


@patch("main._get_redis_pool")
def test_admin_list_documents_redis_unavailable(mock_pool: MagicMock) -> None:
    """Redis connection failure returns 503."""
    mock_redis = MagicMock()
    mock_redis.scan_iter.side_effect = Exception("connection refused")
    with patch("main._get_admin_redis_client", return_value=mock_redis):
        client = get_client()
        response = client.get("/v1/admin/documents")

    assert response.status_code == 503


@patch("main._get_redis_pool")
def test_admin_list_documents_slash_alias(mock_pool: MagicMock) -> None:
    """GET /v1/admin/documents/ (trailing slash) returns 200."""
    redis_mock = _make_redis_mock({})
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.get("/v1/admin/documents/", follow_redirects=True)

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# POST /v1/admin/documents/requeue-failed
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
def test_admin_requeue_failed_deletes_failed_keys(mock_pool: MagicMock) -> None:
    """Requeue-failed deletes exactly the failed entries."""
    redis_mock = _make_redis_mock(_all_entries())
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.post("/v1/admin/documents/requeue-failed")

    assert response.status_code == 200
    data = response.json()
    assert data["requeued"] == 1
    assert len(data["ids"]) == 1
    assert _decode_admin_key(data["ids"][0]) == KEY_FAILED


@patch("main._get_redis_pool")
def test_admin_requeue_failed_idempotent_no_failed(mock_pool: MagicMock) -> None:
    """Requeue-failed with no failed docs is idempotent (returns 0)."""
    entries = {KEY_QUEUED: STATE_QUEUED, KEY_PROCESSED: STATE_PROCESSED}
    redis_mock = _make_redis_mock(entries)
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.post("/v1/admin/documents/requeue-failed")

    assert response.status_code == 200
    data = response.json()
    assert data["requeued"] == 0
    assert data["ids"] == []


@patch("main._get_redis_pool")
def test_admin_requeue_failed_redis_unavailable(mock_pool: MagicMock) -> None:
    """Redis connection failure returns 503."""
    mock_redis = MagicMock()
    mock_redis.scan_iter.side_effect = Exception("connection refused")
    with patch("main._get_admin_redis_client", return_value=mock_redis):
        client = get_client()
        response = client.post("/v1/admin/documents/requeue-failed")

    assert response.status_code == 503


# ---------------------------------------------------------------------------
# DELETE /v1/admin/documents/processed
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
def test_admin_clear_processed_deletes_processed_keys(mock_pool: MagicMock) -> None:
    """Clear-processed deletes exactly the processed entries."""
    redis_mock = _make_redis_mock(_all_entries())
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.delete("/v1/admin/documents/processed")

    assert response.status_code == 200
    data = response.json()
    assert data["cleared"] == 1


@patch("main._get_redis_pool")
def test_admin_clear_processed_idempotent_no_processed(mock_pool: MagicMock) -> None:
    """Clear-processed with no processed docs returns 0."""
    entries = {KEY_QUEUED: STATE_QUEUED, KEY_FAILED: STATE_FAILED}
    redis_mock = _make_redis_mock(entries)
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.delete("/v1/admin/documents/processed")

    assert response.status_code == 200
    assert response.json()["cleared"] == 0


@patch("main._get_redis_pool")
def test_admin_clear_processed_redis_unavailable(mock_pool: MagicMock) -> None:
    """Redis connection failure returns 503."""
    mock_redis = MagicMock()
    mock_redis.scan_iter.side_effect = Exception("connection refused")
    with patch("main._get_admin_redis_client", return_value=mock_redis):
        client = get_client()
        response = client.delete("/v1/admin/documents/processed")

    assert response.status_code == 503


# ---------------------------------------------------------------------------
# POST /v1/admin/documents/{doc_id}/requeue  — single document
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
def test_admin_requeue_single_document_succeeds(mock_pool: MagicMock) -> None:
    """POST /{doc_id}/requeue deletes the key and returns requeued:1."""
    doc_id = _encode_admin_key(KEY_FAILED)
    redis_mock = _make_redis_mock({KEY_FAILED: STATE_FAILED})
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        response = client.post(f"/v1/admin/documents/{doc_id}/requeue")

    assert response.status_code == 200
    data = response.json()
    assert data["requeued"] == 1
    assert data["id"] == doc_id


@patch("main._get_redis_pool")
def test_admin_requeue_single_document_not_found(mock_pool: MagicMock) -> None:
    """Requeueing a key that does not exist returns 404."""
    doc_id = _encode_admin_key(KEY_FAILED)
    mock_redis = MagicMock()
    mock_redis.delete.return_value = 0  # key did not exist
    with patch("main._get_admin_redis_client", return_value=mock_redis):
        client = get_client()
        response = client.post(f"/v1/admin/documents/{doc_id}/requeue")

    assert response.status_code == 404


def test_admin_requeue_single_document_invalid_token() -> None:
    """An invalid doc_id token returns 400."""
    client = get_client()
    response = client.post("/v1/admin/documents/!!!invalid!!!/requeue")
    assert response.status_code == 400


def test_admin_requeue_single_document_wrong_queue() -> None:
    """A doc_id for a different queue prefix returns 400."""
    wrong_key = "/different-queue//data/docs/book.pdf"
    doc_id = _encode_admin_key(wrong_key)
    client = get_client()
    response = client.post(f"/v1/admin/documents/{doc_id}/requeue")
    assert response.status_code == 400


@patch("main._get_redis_pool")
def test_admin_requeue_single_document_redis_unavailable(mock_pool: MagicMock) -> None:
    """Redis connection failure returns 503."""
    doc_id = _encode_admin_key(KEY_FAILED)
    mock_redis = MagicMock()
    mock_redis.delete.side_effect = Exception("connection refused")
    with patch("main._get_admin_redis_client", return_value=mock_redis):
        client = get_client()
        response = client.post(f"/v1/admin/documents/{doc_id}/requeue")

    assert response.status_code == 503


# ---------------------------------------------------------------------------
# Document id in listing can be used for requeue
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
def test_list_then_requeue_integration(mock_pool: MagicMock) -> None:
    """The id returned from the list endpoint can be used to requeue."""
    redis_mock = _make_redis_mock(_all_entries())
    with patch("main._get_admin_redis_client", return_value=redis_mock):
        client = get_client()
        list_response = client.get("/v1/admin/documents", params={"status": "failed"})

    assert list_response.status_code == 200
    docs = list_response.json()["documents"]
    assert len(docs) == 1
    doc_id = docs[0]["id"]

    redis_mock2 = MagicMock()
    redis_mock2.delete.return_value = 1
    with patch("main._get_admin_redis_client", return_value=redis_mock2):
        requeue_response = client.post(f"/v1/admin/documents/{doc_id}/requeue")

    assert requeue_response.status_code == 200
    assert requeue_response.json()["requeued"] == 1
