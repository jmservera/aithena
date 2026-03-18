"""Tests for rate limiting on the search endpoint."""

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

import redis as redis_lib  # noqa: E402
from fastapi import Request  # noqa: E402
from main import RedisRateLimiter  # noqa: E402

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
# RedisRateLimiter unit tests
# ---------------------------------------------------------------------------


def test_rate_limiter_extracts_ip_from_x_forwarded_for() -> None:
    """Should extract client IP from X-Forwarded-For header when present."""
    limiter = RedisRateLimiter(requests_per_minute=5)
    mock_request = MagicMock(spec=Request)
    mock_request.headers.get.return_value = "203.0.113.5, 198.51.100.1"
    mock_request.client.host = "192.168.1.1"

    client_ip = limiter._get_client_ip(mock_request)

    assert client_ip == "203.0.113.5"


def test_rate_limiter_uses_client_host_when_no_forwarded_header() -> None:
    """Should use request.client.host when X-Forwarded-For is absent."""
    limiter = RedisRateLimiter(requests_per_minute=5)
    mock_request = MagicMock(spec=Request)
    mock_request.headers.get.return_value = None
    mock_request.client.host = "192.168.1.1"

    client_ip = limiter._get_client_ip(mock_request)

    assert client_ip == "192.168.1.1"


def test_rate_limiter_handles_missing_client() -> None:
    """Should handle case where request.client is None."""
    limiter = RedisRateLimiter(requests_per_minute=5)
    mock_request = MagicMock(spec=Request)
    mock_request.headers.get.return_value = None
    mock_request.client = None

    client_ip = limiter._get_client_ip(mock_request)

    assert client_ip == "unknown"


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


@patch("main.requests.get")
@patch("main.RedisRateLimiter.check_rate_limit")
def test_search_endpoint_allows_requests_within_limit(mock_rate_limit: MagicMock, mock_get: MagicMock) -> None:
    """Search endpoint should allow requests within rate limit."""
    _mock_solr_ok(mock_get)
    mock_rate_limit.return_value = (True, 0)  # Allowed

    client = get_client()
    response = client.get("/v1/search?q=test")

    assert response.status_code == 200
    mock_rate_limit.assert_called_once()


@patch("main.requests.get")
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


@patch("main.requests.get")
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


@patch("main.requests.get")
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
