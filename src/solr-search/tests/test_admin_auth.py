"""Tests for admin endpoint API-key authentication (admin_auth.py)."""

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

import admin_auth  # noqa: E402, F401
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from tests.auth_helpers import create_authenticated_client  # noqa: E402

# Representative admin endpoint used for auth tests.
ADMIN_ENDPOINT = "/v1/admin/documents"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _client_with_admin_key(api_key: str | None, *, header: str = "x-api-key") -> TestClient:
    """Return a TestClient authenticated with JWT and optionally an admin API key."""
    client = create_authenticated_client()
    if api_key is not None:
        client.headers[header] = api_key
    return client


# ---------------------------------------------------------------------------
# ADMIN_API_KEY not configured -> 403 (admin disabled)
# ---------------------------------------------------------------------------


def test_admin_returns_403_when_api_key_not_configured() -> None:
    """When ADMIN_API_KEY is unset, admin endpoints respond with 403."""
    with patch("admin_auth.ADMIN_API_KEY", None):
        client = create_authenticated_client()
        response = client.get(ADMIN_ENDPOINT)
    assert response.status_code == 403
    assert "disabled" in response.json()["detail"].lower()


def test_admin_returns_403_even_with_key_header_when_not_configured() -> None:
    """Sending an X-API-Key when ADMIN_API_KEY is unset still returns 403."""
    with patch("admin_auth.ADMIN_API_KEY", None):
        client = _client_with_admin_key("some-key")
        response = client.get(ADMIN_ENDPOINT)
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# ADMIN_API_KEY configured but request missing/wrong key -> 401
# ---------------------------------------------------------------------------

TEST_KEY = "test-admin-secret-key-12345"


def test_admin_returns_401_when_key_missing() -> None:
    """When ADMIN_API_KEY is set but request has no matching key header -> 401."""
    with patch("admin_auth.ADMIN_API_KEY", TEST_KEY):
        client = create_authenticated_client()
        response = client.get(ADMIN_ENDPOINT)
    assert response.status_code == 401


def test_admin_returns_401_when_wrong_key() -> None:
    """When request sends a wrong API key -> 401."""
    with patch("admin_auth.ADMIN_API_KEY", TEST_KEY):
        client = _client_with_admin_key("wrong-key")
        response = client.get(ADMIN_ENDPOINT)
    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Correct API key -> request proceeds (mocked Redis)
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
def test_admin_succeeds_with_correct_x_api_key(mock_pool) -> None:
    """Correct X-API-Key allows the admin request through."""
    redis_mock = MagicMock()
    redis_mock.scan_iter.return_value = iter([])
    with patch("admin_auth.ADMIN_API_KEY", TEST_KEY), patch(
        "main._get_admin_redis_client", return_value=redis_mock
    ):
        client = _client_with_admin_key(TEST_KEY)
        response = client.get(ADMIN_ENDPOINT)
    assert response.status_code == 200


@patch("main._get_redis_pool")
def test_admin_succeeds_with_correct_bearer_key(mock_pool) -> None:
    """Correct key via X-API-Key header works (recommended approach)."""
    redis_mock = MagicMock()
    redis_mock.scan_iter.return_value = iter([])
    with patch("admin_auth.ADMIN_API_KEY", TEST_KEY), patch(
        "main._get_admin_redis_client", return_value=redis_mock
    ):
        client = _client_with_admin_key(TEST_KEY, header="x-api-key")
        response = client.get(ADMIN_ENDPOINT)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# All admin endpoints are protected
# ---------------------------------------------------------------------------

ADMIN_ENDPOINTS = [
    ("GET", "/v1/admin/containers"),
    ("GET", "/v1/admin/documents"),
    ("POST", "/v1/admin/documents/requeue-failed"),
    ("DELETE", "/v1/admin/documents/processed"),
    ("POST", "/v1/admin/documents/placeholder-id/requeue"),
]


@pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS, ids=[p for _, p in ADMIN_ENDPOINTS])
def test_all_admin_endpoints_require_api_key(method: str, path: str) -> None:
    """Every /v1/admin/* endpoint returns 401 when key is set but not provided."""
    with patch("admin_auth.ADMIN_API_KEY", TEST_KEY):
        client = create_authenticated_client()
        response = client.request(method, path)
    assert response.status_code == 401, f"{method} {path} should require API key"


@pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS, ids=[p for _, p in ADMIN_ENDPOINTS])
def test_all_admin_endpoints_disabled_without_config(method: str, path: str) -> None:
    """Every /v1/admin/* endpoint returns 403 when ADMIN_API_KEY is not set."""
    with patch("admin_auth.ADMIN_API_KEY", None):
        client = create_authenticated_client()
        response = client.request(method, path)
    assert response.status_code == 403, f"{method} {path} should be disabled"
