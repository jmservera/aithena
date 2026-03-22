"""Tests for admin endpoint authentication (admin_auth.py).

Admin endpoints accept either X-API-Key or a JWT session with admin role.
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

import admin_auth  # noqa: E402, F401
import pytest  # noqa: E402
from auth import AuthenticatedUser  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from tests.auth_helpers import create_authenticated_client  # noqa: E402

# Representative admin endpoint used for auth tests.
ADMIN_ENDPOINT = "/v1/admin/documents"
TEST_KEY = "test-admin-secret-key-12345"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _client_with_admin_key(api_key: str | None, *, header: str = "x-api-key") -> TestClient:
    """Return a TestClient authenticated with JWT and optionally an admin API key."""
    client = create_authenticated_client()
    if api_key is not None:
        client.headers[header] = api_key
    return client


def _mock_redis():
    """Return a patched Redis client that returns no documents."""
    redis_mock = MagicMock()
    redis_mock.scan_iter.return_value = iter([])
    return redis_mock


# ---------------------------------------------------------------------------
# Path 1: API-key authentication
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
def test_admin_succeeds_with_correct_x_api_key(mock_pool) -> None:
    """Correct X-API-Key allows the admin request through."""
    with patch("admin_auth._get_admin_api_key", return_value=TEST_KEY), patch(
        "main._get_admin_redis_client", return_value=_mock_redis()
    ):
        client = _client_with_admin_key(TEST_KEY)
        response = client.get(ADMIN_ENDPOINT)
    assert response.status_code == 200


def test_admin_returns_401_when_wrong_key() -> None:
    """When request sends a wrong API key -> 401."""
    with patch("admin_auth._get_admin_api_key", return_value=TEST_KEY):
        client = _client_with_admin_key("wrong-key")
        response = client.get(ADMIN_ENDPOINT)
    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Path 2: JWT session authentication (browser-based admin access)
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
def test_admin_jwt_admin_user_succeeds_without_api_key(mock_pool) -> None:
    """Admin JWT session grants access even without X-API-Key."""
    with patch("admin_auth._get_admin_api_key", return_value=TEST_KEY), patch(
        "main._get_admin_redis_client", return_value=_mock_redis()
    ):
        client = create_authenticated_client()  # admin role by default
        response = client.get(ADMIN_ENDPOINT)
    assert response.status_code == 200


@patch("main._get_redis_pool")
def test_admin_jwt_admin_user_succeeds_without_api_key_config(mock_pool) -> None:
    """Admin JWT session works even when ADMIN_API_KEY is not configured."""
    with patch("admin_auth._get_admin_api_key", return_value=None), patch(
        "main._get_admin_redis_client", return_value=_mock_redis()
    ):
        client = create_authenticated_client()  # admin role by default
        response = client.get(ADMIN_ENDPOINT)
    assert response.status_code == 200


def test_admin_jwt_non_admin_user_rejected() -> None:
    """Non-admin JWT user cannot access admin endpoints."""
    with patch("admin_auth._get_admin_api_key", return_value=TEST_KEY):
        non_admin = AuthenticatedUser(id=2, username="reader", role="user")
        client = create_authenticated_client(user=non_admin)
        response = client.get(ADMIN_ENDPOINT)
    assert response.status_code == 401


def test_admin_jwt_non_admin_rejected_without_api_key_config() -> None:
    """Non-admin JWT user rejected even when ADMIN_API_KEY is unset."""
    with patch("admin_auth._get_admin_api_key", return_value=None):
        non_admin = AuthenticatedUser(id=2, username="reader", role="user")
        client = create_authenticated_client(user=non_admin)
        response = client.get(ADMIN_ENDPOINT)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@patch("main._get_redis_pool")
def test_admin_api_key_takes_precedence_over_jwt(mock_pool) -> None:
    """When both API key and JWT are present, API key is checked first."""
    with patch("admin_auth._get_admin_api_key", return_value=TEST_KEY), patch(
        "main._get_admin_redis_client", return_value=_mock_redis()
    ):
        client = _client_with_admin_key(TEST_KEY)
        response = client.get(ADMIN_ENDPOINT)
    assert response.status_code == 200


def test_admin_wrong_api_key_rejected_even_with_admin_jwt() -> None:
    """A wrong API key fails fast — JWT fallback is not attempted."""
    with patch("admin_auth._get_admin_api_key", return_value=TEST_KEY):
        client = _client_with_admin_key("wrong-key")
        response = client.get(ADMIN_ENDPOINT)
    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# All admin endpoints are protected
# ---------------------------------------------------------------------------

ADMIN_ENDPOINTS = [
    ("GET", "/v1/admin/containers"),
    ("GET", "/v1/admin/documents"),
    ("POST", "/v1/admin/documents/requeue-failed"),
    ("DELETE", "/v1/admin/documents/processed"),
    ("POST", "/v1/admin/documents/placeholder-id/requeue"),
    ("PATCH", "/v1/admin/documents/placeholder-id/metadata"),
]


@pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS, ids=[p for _, p in ADMIN_ENDPOINTS])
def test_all_admin_endpoints_reject_non_admin_jwt(method: str, path: str) -> None:
    """Every /v1/admin/* endpoint rejects non-admin JWT users."""
    with patch("admin_auth._get_admin_api_key", return_value=None):
        non_admin = AuthenticatedUser(id=2, username="reader", role="user")
        client = create_authenticated_client(user=non_admin)
        response = client.request(method, path)
    assert response.status_code == 401, f"{method} {path} should reject non-admin"
