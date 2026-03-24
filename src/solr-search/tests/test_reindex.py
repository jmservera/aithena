"""Tests for POST /v1/admin/reindex endpoint.

Covers:
- Successful reindex (mock Solr + Redis)
- Auth required (401 without API key)
- Invalid collection returns 400
- Solr failure returns 502
- Redis failure returns 503
- Timeout handling
"""

from __future__ import annotations

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
import requests  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from tests.auth_helpers import create_authenticated_client  # noqa: E402

REINDEX_URL = "/v1/admin/reindex"
TEST_ADMIN_KEY = "test-reindex-admin-key"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _authed_client() -> TestClient:
    """Return a TestClient with both JWT and admin API key."""
    client = create_authenticated_client()
    client.headers["X-API-Key"] = TEST_ADMIN_KEY
    return client


def _mock_redis_client(keys: list[str] | None = None) -> MagicMock:
    """Return a mock Redis client whose scan_iter yields *keys*."""
    mock = MagicMock()
    mock.scan_iter.return_value = iter(keys or [])
    pipe = MagicMock()
    pipe.execute.return_value = []
    mock.pipeline.return_value = pipe
    return mock


def _mock_solr_response(status_code: int = 200) -> MagicMock:
    """Return a mock requests.Response for Solr update."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# Fixture: enable admin API key for all tests in this module
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _enable_admin_api_key():
    with patch("admin_auth._get_admin_api_key", return_value=TEST_ADMIN_KEY):
        yield


# ---------------------------------------------------------------------------
# 1. Successful reindex (mock Solr + Redis)
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
@patch("main.requests.post")
def test_reindex_success_no_redis_keys(mock_post, mock_pool):
    """Reindex clears Solr and reports zero Redis keys when none exist."""
    mock_post.return_value = _mock_solr_response()
    redis_mock = _mock_redis_client(keys=[])
    mock_pool.return_value = MagicMock()

    with patch("main.redis_lib.Redis", return_value=redis_mock):
        client = _authed_client()
        resp = client.post(REINDEX_URL, params={"collection": "books"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["collection"] == "books"
    assert body["solr"] == "cleared"
    assert body["redis_cleared"] == 0
    assert "re-indexed" in body["message"].lower() or "re-index" in body["message"].lower()


@patch("main._get_redis_pool")
@patch("main.requests.post")
def test_reindex_success_with_redis_keys(mock_post, mock_pool):
    """Reindex clears Solr and deletes existing Redis tracking keys."""
    mock_post.return_value = _mock_solr_response()
    keys = ["/shortembeddings//data/docs/a.pdf", "/shortembeddings//data/docs/b.pdf"]
    redis_mock = _mock_redis_client(keys=keys)
    mock_pool.return_value = MagicMock()

    with patch("main.redis_lib.Redis", return_value=redis_mock):
        client = _authed_client()
        resp = client.post(REINDEX_URL)

    assert resp.status_code == 200
    body = resp.json()
    assert body["redis_cleared"] == 2
    assert body["solr"] == "cleared"


@patch("main._get_redis_pool")
@patch("main.requests.post")
def test_reindex_default_collection_is_books(mock_post, mock_pool):
    """Without an explicit collection param the default is 'books'."""
    mock_post.return_value = _mock_solr_response()
    redis_mock = _mock_redis_client()
    mock_pool.return_value = MagicMock()

    with patch("main.redis_lib.Redis", return_value=redis_mock):
        client = _authed_client()
        resp = client.post(REINDEX_URL)

    assert resp.status_code == 200
    assert resp.json()["collection"] == "books"


# ---------------------------------------------------------------------------
# 2. Auth required — 401 without API key or JWT
# ---------------------------------------------------------------------------


def test_reindex_requires_auth_no_credentials():
    """Request without any auth credentials returns 401."""
    from main import app

    client = TestClient(app)
    resp = client.post(REINDEX_URL)
    assert resp.status_code == 401


def test_reindex_requires_auth_wrong_api_key():
    """Request with an incorrect API key returns 401."""
    client = create_authenticated_client()
    client.headers["X-API-Key"] = "wrong-key"
    resp = client.post(REINDEX_URL)
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 3. Invalid collection returns 400
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
def test_reindex_invalid_collection_returns_400(mock_pool):
    """Requesting a collection not in allowed_collections returns 400."""
    client = _authed_client()
    resp = client.post(REINDEX_URL, params={"collection": "nonexistent_collection"})
    assert resp.status_code == 400
    assert "not in ALLOWED_COLLECTIONS" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 4. Solr failure returns 502
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
@patch("main.requests.post")
def test_reindex_solr_failure_returns_502(mock_post, mock_pool):
    """When Solr returns an error, the endpoint returns 502."""
    mock_post.side_effect = requests.RequestException("Solr connection refused")
    client = _authed_client()
    resp = client.post(REINDEX_URL, params={"collection": "books"})
    assert resp.status_code == 502
    assert "Failed to clear Solr" in resp.json()["detail"]


@patch("main._get_redis_pool")
@patch("main.requests.post")
def test_reindex_solr_http_error_returns_502(mock_post, mock_pool):
    """When Solr raises an HTTP error (e.g. 500), the endpoint returns 502."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
    mock_post.return_value = mock_resp
    client = _authed_client()
    resp = client.post(REINDEX_URL, params={"collection": "books"})
    assert resp.status_code == 502


# ---------------------------------------------------------------------------
# 5. Redis failure returns 503
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
@patch("main.requests.post")
def test_reindex_redis_failure_returns_503(mock_post, mock_pool):
    """When Redis scan_iter raises, the endpoint returns 503."""
    mock_post.return_value = _mock_solr_response()
    redis_mock = MagicMock()
    redis_mock.scan_iter.side_effect = Exception("Redis connection lost")
    mock_pool.return_value = MagicMock()

    with patch("main.redis_lib.Redis", return_value=redis_mock):
        client = _authed_client()
        resp = client.post(REINDEX_URL, params={"collection": "books"})

    assert resp.status_code == 503
    assert "Failed to clear Redis" in resp.json()["detail"]


@patch("main._get_redis_pool")
@patch("main.requests.post")
def test_reindex_redis_pipeline_failure_returns_503(mock_post, mock_pool):
    """When Redis pipeline.execute raises, the endpoint returns 503."""
    mock_post.return_value = _mock_solr_response()
    redis_mock = MagicMock()
    redis_mock.scan_iter.return_value = iter(["/shortembeddings//data/docs/a.pdf"])
    pipe = MagicMock()
    pipe.execute.side_effect = Exception("Redis pipeline broken")
    redis_mock.pipeline.return_value = pipe
    mock_pool.return_value = MagicMock()

    with patch("main.redis_lib.Redis", return_value=redis_mock):
        client = _authed_client()
        resp = client.post(REINDEX_URL, params={"collection": "books"})

    assert resp.status_code == 503
    assert "Failed to clear Redis" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 6. Timeout handling
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
@patch("main.requests.post")
def test_reindex_solr_timeout_returns_502(mock_post, mock_pool):
    """A Solr timeout (ConnectTimeout / ReadTimeout) returns 502."""
    mock_post.side_effect = requests.ConnectionError("Read timed out")
    client = _authed_client()
    resp = client.post(REINDEX_URL, params={"collection": "books"})
    assert resp.status_code == 502
    assert "Failed to clear Solr" in resp.json()["detail"]


@patch("main._get_redis_pool")
@patch("main.requests.post")
def test_reindex_solr_read_timeout_returns_502(mock_post, mock_pool):
    """A Solr ReadTimeout is a RequestException subclass and returns 502."""
    mock_post.side_effect = requests.ReadTimeout("Read timed out (read timeout=120)")
    client = _authed_client()
    resp = client.post(REINDEX_URL, params={"collection": "books"})
    assert resp.status_code == 502
    assert "timed out" in resp.json()["detail"].lower() or "Failed to clear Solr" in resp.json()["detail"]


@patch("main._get_redis_pool")
@patch("main.requests.post")
def test_reindex_uses_generous_timeout(mock_post, mock_pool):
    """The Solr request uses max(request_timeout, 120) as timeout."""
    mock_post.return_value = _mock_solr_response()
    redis_mock = _mock_redis_client()
    mock_pool.return_value = MagicMock()

    with patch("main.redis_lib.Redis", return_value=redis_mock):
        client = _authed_client()
        client.post(REINDEX_URL, params={"collection": "books"})

    # Verify the timeout passed to requests.post
    call_kwargs = mock_post.call_args
    timeout_used = call_kwargs.kwargs.get("timeout") or call_kwargs[1].get("timeout")
    assert timeout_used >= 120
