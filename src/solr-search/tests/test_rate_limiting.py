"""Tests for rate limiting on the search and login endpoints."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("AUTH_DB_PATH", "/tmp/test-auth.db")  # noqa: S108
os.environ.setdefault("AUTH_JWT_SECRET", "test-auth-secret")
os.environ.setdefault("AUTH_JWT_TTL", "24h")
os.environ.setdefault("AUTH_COOKIE_NAME", "aithena_auth")
os.environ.setdefault("RATE_LIMIT_REQUESTS_PER_MINUTE", "5")  # Low limit for testing

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi import Request  # noqa: E402

import redis as redis_lib  # noqa: E402
from main import RedisRateLimiter, get_client_ip  # noqa: E402
from tests.auth_helpers import create_authenticated_client  # noqa: E402


def get_client():
    return create_authenticated_client()


def _solr_response() -> dict:
    """Minimal Solr response for search tests."""
    return {
        "response": {
            "numFound": 0,
            "docs": [],
        },
        "highlighting": {},
        "facet_counts": {
            "facet_fields": {
                "author_s": [],
                "category_s": [],
                "year_i": [],
                "language_detected_s": [],
                "language_s": [],
            }
        },
    }


def _mock_solr_ok(mock_get: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = _solr_response()
    mock_get.return_value = mock_response


# ---------------------------------------------------------------------------
# get_client_ip module-level function tests
# ---------------------------------------------------------------------------


def _make_request(forwarded_for: str | None = None,
                  client_host: str | None = "192.168.1.1") -> MagicMock:
    """Create a mock Request with configurable proxy headers."""
    mock_request = MagicMock(spec=Request)

    def _header_get(name: str, default=None):
        headers = {}
        if forwarded_for is not None:
            headers["X-Forwarded-For"] = forwarded_for
        return headers.get(name, default)

    mock_request.headers.get = _header_get
    if client_host is None:
        mock_request.client = None
    else:
        mock_request.client.host = client_host
    return mock_request


def test_get_client_ip_extracts_first_ip_from_x_forwarded_for() -> None:
    """Should extract only the first (client) IP from X-Forwarded-For chain."""
    req = _make_request(forwarded_for="203.0.113.5, 198.51.100.1", client_host="172.18.0.2")
    assert get_client_ip(req) == "203.0.113.5"


def test_get_client_ip_single_forwarded_for() -> None:
    """Should handle a single IP in X-Forwarded-For."""
    req = _make_request(forwarded_for="203.0.113.5")
    assert get_client_ip(req) == "203.0.113.5"


def test_get_client_ip_falls_back_to_client_host() -> None:
    """Should use request.client.host when no proxy headers are present."""
    req = _make_request(client_host="192.168.1.1")
    assert get_client_ip(req) == "192.168.1.1"


def test_get_client_ip_returns_unknown_when_no_client() -> None:
    """Should return 'unknown' when request.client is None and no proxy headers."""
    req = _make_request(client_host=None)
    assert get_client_ip(req) == "unknown"


def test_get_client_ip_handles_empty_forwarded_for() -> None:
    """Should fall back to client host when X-Forwarded-For is empty or malformed."""
    req = _make_request(forwarded_for=", ", client_host="10.0.0.1")
    assert get_client_ip(req) == "10.0.0.1"


def test_get_client_ip_strips_whitespace() -> None:
    """Should strip whitespace from forwarded IPs."""
    req = _make_request(forwarded_for="  203.0.113.5 , 198.51.100.1 ")
    assert get_client_ip(req) == "203.0.113.5"


# ---------------------------------------------------------------------------
# RedisRateLimiter delegates to get_client_ip
# ---------------------------------------------------------------------------


def test_rate_limiter_extracts_ip_from_x_forwarded_for() -> None:
    """RedisRateLimiter._get_client_ip should delegate to get_client_ip."""
    limiter = RedisRateLimiter(requests_per_minute=5)
    req = _make_request(forwarded_for="203.0.113.5, 198.51.100.1", client_host="192.168.1.1")
    assert limiter._get_client_ip(req) == "203.0.113.5"


def test_rate_limiter_uses_client_host_when_no_forwarded_header() -> None:
    """Should use request.client.host when X-Forwarded-For is absent."""
    limiter = RedisRateLimiter(requests_per_minute=5)
    req = _make_request(client_host="192.168.1.1")
    assert limiter._get_client_ip(req) == "192.168.1.1"


def test_rate_limiter_handles_missing_client() -> None:
    """Should handle case where request.client is None."""
    limiter = RedisRateLimiter(requests_per_minute=5)
    req = _make_request(client_host=None)
    assert limiter._get_client_ip(req) == "unknown"


@patch("main.redis_lib.Redis")
def test_rate_limiter_fails_open_on_redis_error(mock_redis: MagicMock) -> None:
    """Rate limiter should fail open (allow) when Redis is unavailable."""
    # Simulate Redis connection error
    mock_redis.side_effect = redis_lib.RedisError("Connection failed")

    with patch("main._get_redis_pool"):
        limiter = RedisRateLimiter(requests_per_minute=5)
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "192.168.1.1"
        mock_request.headers.get.return_value = None

        allowed, retry_after = limiter.check_rate_limit(mock_request)

        assert allowed is True
        assert retry_after == 0


# ---------------------------------------------------------------------------
# Integration tests with FastAPI endpoint
# ---------------------------------------------------------------------------


@patch("main.requests.post")
@patch("main.RedisRateLimiter.check_rate_limit")
def test_search_endpoint_allows_requests_within_limit(mock_rate_limit: MagicMock, mock_get: MagicMock) -> None:
    """Search endpoint should allow requests within rate limit."""
    _mock_solr_ok(mock_get)
    mock_rate_limit.return_value = (True, 0)  # Allowed

    client = get_client()
    response = client.get("/v1/search?q=test")

    assert response.status_code == 200
    mock_rate_limit.assert_called_once()


@patch("main.requests.post")
@patch("main.RedisRateLimiter.check_rate_limit")
def test_search_endpoint_returns_429_when_limit_exceeded(mock_rate_limit: MagicMock, mock_get: MagicMock) -> None:
    """Search endpoint should return 429 when rate limit is exceeded."""
    _mock_solr_ok(mock_get)
    mock_rate_limit.return_value = (False, 45)  # Not allowed, retry after 45 seconds

    client = get_client()
    response = client.get("/v1/search?q=test")

    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert response.headers["Retry-After"] == "45"
    data = response.json()
    assert "Rate limit exceeded" in data["detail"]
    mock_rate_limit.assert_called_once()


@patch("main.requests.post")
@patch("main.RedisRateLimiter.check_rate_limit")
def test_search_endpoint_works_when_redis_fails(mock_rate_limit: MagicMock, mock_get: MagicMock) -> None:
    """Search endpoint should still work (fail open) when Redis is unavailable."""
    _mock_solr_ok(mock_get)
    mock_rate_limit.return_value = (True, 0)  # Fail open

    client = get_client()
    response = client.get("/v1/search?q=test")

    # Should succeed despite Redis failure (fail open)
    assert response.status_code == 200


@patch("main.requests.get")
def test_rate_limit_only_applies_to_search_endpoint(mock_get: MagicMock) -> None:
    """Rate limiting should only apply to search endpoint, not other endpoints."""
    _mock_solr_ok(mock_get)

    client = get_client()

    # Health endpoint should not be rate limited
    response = client.get("/health")
    assert response.status_code == 200

    # Version endpoint should not be rate limited
    response = client.get("/version")
    assert response.status_code == 200

    # Info endpoint should not be rate limited
    response = client.get("/info")
    assert response.status_code == 200


@patch("main.requests.post")
@patch("main.RedisRateLimiter.check_rate_limit")
def test_rate_limit_dependency_called_for_all_search_routes(mock_rate_limit: MagicMock, mock_get: MagicMock) -> None:
    """Rate limiting should be applied to all search endpoint routes."""
    _mock_solr_ok(mock_get)
    mock_rate_limit.return_value = (True, 0)

    client = get_client()

    # Test /search
    response = client.get("/search?q=test")
    assert response.status_code == 200

    # Test /v1/search
    response = client.get("/v1/search?q=test2")
    assert response.status_code == 200

    # Test /v1/search/
    response = client.get("/v1/search/?q=test3")
    assert response.status_code == 200

    # Should have been called 3 times
    assert mock_rate_limit.call_count == 3


# ---------------------------------------------------------------------------
# Login rate limiter tests – verify it uses get_client_ip (X-Forwarded-For)
# ---------------------------------------------------------------------------


@patch("main.login_rate_limiter")
@patch("main.authenticate_user")
def test_login_rate_limiter_uses_forwarded_ip(mock_auth: MagicMock, mock_limiter: MagicMock) -> None:
    """Login endpoint should rate-limit by the real client IP from X-Forwarded-For."""
    mock_limiter.is_allowed.return_value = True
    mock_auth.return_value = None  # auth will fail, but we only care about rate limiter call

    from fastapi.testclient import TestClient

    from main import app

    client = TestClient(app)
    client.post(
        "/v1/auth/login",
        json={"username": "test", "password": "test"},
        headers={"X-Forwarded-For": "203.0.113.50, 172.18.0.2"},
    )

    # The rate limiter should have been called with the real client IP, not the proxy IP
    mock_limiter.is_allowed.assert_called_once_with("203.0.113.50")


@patch("main.login_rate_limiter")
@patch("main.authenticate_user")
def test_login_rate_limiter_falls_back_to_client_host(mock_auth: MagicMock, mock_limiter: MagicMock) -> None:
    """Login endpoint should fall back to client.host when X-Forwarded-For is absent."""
    mock_limiter.is_allowed.return_value = True
    mock_auth.return_value = None

    from fastapi.testclient import TestClient

    from main import app

    client = TestClient(app)
    client.post(
        "/v1/auth/login",
        json={"username": "test", "password": "test"},
    )

    # Without X-Forwarded-For, should use the direct connection IP (testclient)
    called_ip = mock_limiter.is_allowed.call_args[0][0]
    assert called_ip != "unknown"
    mock_limiter.is_allowed.assert_called_once()


@patch("main.login_rate_limiter")
def test_login_returns_429_when_rate_limited(mock_limiter: MagicMock) -> None:
    """Login endpoint should return 429 when rate limit is exceeded."""
    mock_limiter.is_allowed.return_value = False

    from fastapi.testclient import TestClient

    from main import app

    client = TestClient(app)
    response = client.post(
        "/v1/auth/login",
        json={"username": "test", "password": "test"},
        headers={"X-Forwarded-For": "203.0.113.50"},
    )

    assert response.status_code == 429
    assert "Too many login attempts" in response.json()["detail"]


def test_rate_limiter_disabled_when_zero() -> None:
    """Rate limiter should bypass when requests_per_minute is 0."""
    limiter = RedisRateLimiter(requests_per_minute=0)
    request = MagicMock(spec=Request)
    request.headers = {"x-forwarded-for": "10.0.0.1"}
    request.client = MagicMock()
    request.client.host = "10.0.0.1"
    allowed, retry_after = limiter.check_rate_limit(request)
    assert allowed is True
    assert retry_after == 0


def test_rate_limiter_disabled_when_negative() -> None:
    """Rate limiter should bypass when requests_per_minute is negative."""
    limiter = RedisRateLimiter(requests_per_minute=-1)
    request = MagicMock(spec=Request)
    request.headers = {"x-forwarded-for": "10.0.0.1"}
    request.client = MagicMock()
    request.client.host = "10.0.0.1"
    allowed, retry_after = limiter.check_rate_limit(request)
    assert allowed is True
    assert retry_after == 0
