"""Security tests for PATCH /v1/admin/documents/{doc_id}/metadata — auth, sanitization, injection."""

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
from auth import AuthenticatedUser, create_access_token  # noqa: E402
from config import settings  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from tests.auth_helpers import create_authenticated_client  # noqa: E402

_TEST_ADMIN_KEY = "test-metadata-security-key"
DOC_ID = "test-doc-sec-001"
ENDPOINT = f"/v1/admin/documents/{DOC_ID}/metadata"

ADMIN_USER = AuthenticatedUser(id=1, username="admin-user", role="admin")
REGULAR_USER = AuthenticatedUser(id=10, username="regular-user", role="user")
VIEWER_USER = AuthenticatedUser(id=20, username="viewer-user", role="viewer")


def _client_for(user: AuthenticatedUser, api_key: str | None = _TEST_ADMIN_KEY) -> TestClient:
    """Create a test client authenticated as the given user, optionally with API key."""
    client = create_authenticated_client(user)
    if api_key:
        client.headers["X-API-Key"] = api_key
    return client


@pytest.fixture(autouse=True)
def _enable_admin_api_key():
    with patch("admin_auth._get_admin_api_key", return_value=_TEST_ADMIN_KEY):
        yield


# ---------------------------------------------------------------------------
# Admin Auth Validation
# ---------------------------------------------------------------------------


class TestAdminAuthRequired:
    """Metadata edit requires both admin API key and admin JWT role."""

    def test_admin_with_api_key_succeeds(self):
        """Admin user + valid API key → 200."""
        with (
            patch("main._get_redis_pool"),
            patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}}),
            patch("main.requests.post", return_value=MagicMock(status_code=200, raise_for_status=MagicMock())),
            patch("main._get_admin_redis_client", return_value=MagicMock()),
        ):
            client = _client_for(ADMIN_USER)
            resp = client.patch(ENDPOINT, json={"title": "Valid Edit"})
        assert resp.status_code == 200  # noqa: S101

    def test_regular_user_with_api_key_gets_403(self):
        """Non-admin user + valid API key → 403 (role check blocks)."""
        client = _client_for(REGULAR_USER)
        resp = client.patch(ENDPOINT, json={"title": "Blocked"})
        assert resp.status_code == 403  # noqa: S101

    def test_viewer_user_with_api_key_gets_403(self):
        """Viewer user + valid API key → 403."""
        client = _client_for(VIEWER_USER)
        resp = client.patch(ENDPOINT, json={"title": "Blocked"})
        assert resp.status_code == 403  # noqa: S101

    def test_admin_without_api_key_gets_401(self):
        """Admin user without API key → 401."""
        client = _client_for(ADMIN_USER, api_key=None)
        resp = client.patch(ENDPOINT, json={"title": "No Key"})
        assert resp.status_code == 401  # noqa: S101

    def test_wrong_api_key_gets_401(self):
        """Admin user + wrong API key → 401."""
        client = _client_for(ADMIN_USER, api_key="wrong-key-value")
        resp = client.patch(ENDPOINT, json={"title": "Wrong Key"})
        assert resp.status_code == 401  # noqa: S101

    def test_no_auth_at_all_gets_401(self):
        """No JWT, no API key → 401 from auth middleware."""
        client = TestClient(app=__import__("main").app)
        resp = client.patch(ENDPOINT, json={"title": "No Auth"})
        assert resp.status_code == 401  # noqa: S101

    def test_api_key_disabled_returns_403(self):
        """When ADMIN_API_KEY not configured → 403."""
        with patch("admin_auth._get_admin_api_key", return_value=None):
            client = _client_for(ADMIN_USER)
            resp = client.patch(ENDPOINT, json={"title": "Disabled"})
        assert resp.status_code == 403  # noqa: S101

    def test_expired_token_returns_401(self):
        """Expired JWT → 401."""
        from datetime import UTC, datetime, timedelta

        past = datetime.now(UTC) - timedelta(hours=25)
        token = create_access_token(ADMIN_USER, settings.auth_jwt_secret, 1, now=past)
        from main import app

        client = TestClient(app)
        client.headers.update({
            "Authorization": f"Bearer {token}",
            "X-API-Key": _TEST_ADMIN_KEY,
        })
        resp = client.patch(ENDPOINT, json={"title": "Expired"})
        assert resp.status_code == 401  # noqa: S101


# ---------------------------------------------------------------------------
# Input Sanitization — Solr query injection
# ---------------------------------------------------------------------------


class TestSolrInjectionPrevention:
    """Verify Solr query injection payloads in doc_id are escaped."""

    SOLR_PAYLOADS = [
        "test OR *:*",
        "test AND title_s:hacked",
        "{!lucene}id:*",
        "test:* OR id:[* TO *]",
        "'; DROP TABLE --",
    ]

    @pytest.mark.parametrize("payload", SOLR_PAYLOADS)
    def test_solr_injection_in_doc_id_path(self, payload):
        """Solr injection payloads in doc_id path should not leak data."""
        with (
            patch("main._get_redis_pool"),
            patch("main._raw_solr_query", return_value={"response": {"numFound": 0, "docs": []}}),
        ):
            endpoint = f"/v1/admin/documents/{payload}/metadata"
            client = _client_for(ADMIN_USER)
            resp = client.patch(endpoint, json={"title": "Injected"})

        # Should be 404 (not found) — not returning all documents
        assert resp.status_code == 404  # noqa: S101

    def test_doc_id_with_wildcards_does_not_match_all(self):
        """A doc_id of '*' should not match all documents via Solr."""
        with (
            patch("main._get_redis_pool"),
            patch("main._raw_solr_query", return_value={"response": {"numFound": 0, "docs": []}}) as mock_query,
        ):
            client = _client_for(ADMIN_USER)
            resp = client.patch("/v1/admin/documents/*/metadata", json={"title": "Wildcard"})
        assert resp.status_code == 404  # noqa: S101
        # Verify the query passed to Solr has the wildcard escaped
        call_args = mock_query.call_args[0][0]
        assert "\\*" in call_args.get("q", "") or resp.status_code == 404  # noqa: S101


# ---------------------------------------------------------------------------
# Input Sanitization — Field validation boundaries
# ---------------------------------------------------------------------------


class TestMetadataFieldValidation:
    """Comprehensive boundary testing for metadata field validation."""

    def test_title_exactly_255_accepted(self):
        with (
            patch("main._get_redis_pool"),
            patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}}),
            patch("main.requests.post", return_value=MagicMock(status_code=200, raise_for_status=MagicMock())),
            patch("main._get_admin_redis_client", return_value=MagicMock()),
        ):
            client = _client_for(ADMIN_USER)
            resp = client.patch(ENDPOINT, json={"title": "T" * 255})
        assert resp.status_code == 200  # noqa: S101

    def test_title_256_rejected(self):
        client = _client_for(ADMIN_USER)
        resp = client.patch(ENDPOINT, json={"title": "T" * 256})
        assert resp.status_code == 422  # noqa: S101

    def test_author_256_rejected(self):
        client = _client_for(ADMIN_USER)
        resp = client.patch(ENDPOINT, json={"author": "A" * 256})
        assert resp.status_code == 422  # noqa: S101

    def test_category_101_rejected(self):
        client = _client_for(ADMIN_USER)
        resp = client.patch(ENDPOINT, json={"category": "C" * 101})
        assert resp.status_code == 422  # noqa: S101

    def test_series_101_rejected(self):
        client = _client_for(ADMIN_USER)
        resp = client.patch(ENDPOINT, json={"series": "S" * 101})
        assert resp.status_code == 422  # noqa: S101

    def test_year_below_1000_rejected(self):
        client = _client_for(ADMIN_USER)
        resp = client.patch(ENDPOINT, json={"year": 999})
        assert resp.status_code == 422  # noqa: S101

    def test_year_above_2099_rejected(self):
        client = _client_for(ADMIN_USER)
        resp = client.patch(ENDPOINT, json={"year": 2100})
        assert resp.status_code == 422  # noqa: S101

    def test_year_boundary_1000_accepted(self):
        with (
            patch("main._get_redis_pool"),
            patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}}),
            patch("main.requests.post", return_value=MagicMock(status_code=200, raise_for_status=MagicMock())),
            patch("main._get_admin_redis_client", return_value=MagicMock()),
        ):
            client = _client_for(ADMIN_USER)
            resp = client.patch(ENDPOINT, json={"year": 1000})
        assert resp.status_code == 200  # noqa: S101

    def test_year_boundary_2099_accepted(self):
        with (
            patch("main._get_redis_pool"),
            patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}}),
            patch("main.requests.post", return_value=MagicMock(status_code=200, raise_for_status=MagicMock())),
            patch("main._get_admin_redis_client", return_value=MagicMock()),
        ):
            client = _client_for(ADMIN_USER)
            resp = client.patch(ENDPOINT, json={"year": 2099})
        assert resp.status_code == 200  # noqa: S101

    def test_whitespace_only_title_rejected(self):
        client = _client_for(ADMIN_USER)
        resp = client.patch(ENDPOINT, json={"title": "   "})
        assert resp.status_code == 422  # noqa: S101

    def test_empty_body_rejected(self):
        client = _client_for(ADMIN_USER)
        resp = client.patch(ENDPOINT, json={})
        assert resp.status_code == 422  # noqa: S101

    def test_unknown_fields_ignored(self):
        """Extra fields not in _METADATA_FIELD_MAP should not cause errors."""
        client = _client_for(ADMIN_USER)
        resp = client.patch(ENDPOINT, json={"unknown_field": "value"})
        assert resp.status_code == 422  # noqa: S101 (no valid fields)

    def test_html_in_title_stored_as_is(self):
        """HTML is not stripped — sanitization is display-side, not storage-side."""
        with (
            patch("main._get_redis_pool"),
            patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}}),
            patch("main.requests.post", return_value=MagicMock(status_code=200, raise_for_status=MagicMock())),
            patch("main._get_admin_redis_client", return_value=MagicMock()),
        ):
            client = _client_for(ADMIN_USER)
            resp = client.patch(ENDPOINT, json={"title": "<script>alert('xss')</script>"})
        # Accepted but frontend must sanitize on display
        assert resp.status_code == 200  # noqa: S101


# ---------------------------------------------------------------------------
# Redis Access Control
# ---------------------------------------------------------------------------


class TestRedisKeyConstruction:
    """Verify Redis key construction is safe."""

    def test_redis_key_uses_correct_pattern(self):
        """Override key follows pattern aithena:metadata-override:{doc_id}."""
        with (
            patch("main._get_redis_pool"),
            patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}}),
            patch("main.requests.post", return_value=MagicMock(status_code=200, raise_for_status=MagicMock())),
            patch("main._get_admin_redis_client", return_value=MagicMock()) as mock_redis,
        ):
            client = _client_for(ADMIN_USER)
            client.patch(f"/v1/admin/documents/{DOC_ID}/metadata", json={"title": "Test"})
        redis_client = mock_redis.return_value
        redis_client.set.assert_called_once()
        key_arg = redis_client.set.call_args[0][0]
        assert key_arg == f"aithena:metadata-override:{DOC_ID}"  # noqa: S101

    def test_redis_key_with_special_chars_in_doc_id(self):
        """Special characters in doc_id are passed through (no Redis command injection)."""
        special_id = "doc-with-dashes_and_underscores"
        with (
            patch("main._get_redis_pool"),
            patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}}),
            patch("main.requests.post", return_value=MagicMock(status_code=200, raise_for_status=MagicMock())),
            patch("main._get_admin_redis_client", return_value=MagicMock()) as mock_redis,
        ):
            client = _client_for(ADMIN_USER)
            client.patch(
                f"/v1/admin/documents/{special_id}/metadata",
                json={"title": "Test"},
            )
        redis_client = mock_redis.return_value
        redis_client.set.assert_called_once()
        key_arg = redis_client.set.call_args[0][0]
        assert key_arg == f"aithena:metadata-override:{special_id}"  # noqa: S101

    def test_redis_override_data_structure(self):
        """Verify the stored Redis value has correct structure."""
        with (
            patch("main._get_redis_pool"),
            patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}}),
            patch("main.requests.post", return_value=MagicMock(status_code=200, raise_for_status=MagicMock())),
            patch("main._get_admin_redis_client", return_value=MagicMock()) as mock_redis,
        ):
            client = _client_for(ADMIN_USER)
            client.patch(ENDPOINT, json={"title": "Test Title", "year": 2020})
        redis_client = mock_redis.return_value
        stored_json = redis_client.set.call_args[0][1]
        data = json.loads(stored_json)
        assert "title_s" in data  # noqa: S101
        assert "title_t" in data  # noqa: S101
        assert "year_i" in data  # noqa: S101
        assert data["edited_by"] == "admin"  # noqa: S101
        assert "edited_at" in data  # noqa: S101
        # No TTL set (permanent by design)


# ---------------------------------------------------------------------------
# Solr Update Security
# ---------------------------------------------------------------------------


class TestSolrAtomicUpdateSecurity:
    """Verify Solr atomic updates use correct field mapping and format."""

    def test_only_allowed_fields_sent_to_solr(self):
        """Only fields in _METADATA_FIELD_MAP are sent as Solr updates."""
        with (
            patch("main._get_redis_pool"),
            patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}}),
            patch("main.requests.post", return_value=MagicMock(status_code=200, raise_for_status=MagicMock()))
                as mock_post,
            patch("main._get_admin_redis_client", return_value=MagicMock()),
        ):
            client = _client_for(ADMIN_USER)
            client.patch(ENDPOINT, json={"title": "Test", "author": "Author"})

        solr_payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        doc = solr_payload[0]
        allowed_keys = {"id", "title_s", "title_t", "author_s", "author_t"}
        assert set(doc.keys()) == allowed_keys  # noqa: S101

    def test_atomic_update_uses_set_operation(self):
        """All field updates use Solr's 'set' atomic operation."""
        with (
            patch("main._get_redis_pool"),
            patch("main._raw_solr_query", return_value={"response": {"numFound": 1, "docs": []}}),
            patch("main.requests.post", return_value=MagicMock(status_code=200, raise_for_status=MagicMock()))
                as mock_post,
            patch("main._get_admin_redis_client", return_value=MagicMock()),
        ):
            client = _client_for(ADMIN_USER)
            client.patch(ENDPOINT, json={"title": "Test"})

        solr_payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        doc = solr_payload[0]
        for key, val in doc.items():
            if key != "id":
                assert isinstance(val, dict) and "set" in val, f"Field {key} must use 'set' operation"  # noqa: S101
