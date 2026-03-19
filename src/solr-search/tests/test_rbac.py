"""Tests for RBAC middleware — require_role() on endpoints (#553)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ.setdefault("AUTH_DB_PATH", "/tmp/test-auth.db")  # noqa: S108
os.environ.setdefault("AUTH_JWT_SECRET", "test-auth-secret")  # noqa: S105
os.environ.setdefault("AUTH_JWT_TTL", "24h")
os.environ.setdefault("AUTH_COOKIE_NAME", "aithena_auth")

sys.path.append(str(Path(__file__).resolve().parents[1]))

from auth import AuthenticatedUser, create_access_token, init_auth_db  # noqa: E402
from config import settings  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_db(tmp_path: Path):
    original = settings.auth_db_path
    db_path = tmp_path / "rbac.db"
    object.__setattr__(settings, "auth_db_path", db_path)
    init_auth_db(db_path)
    yield db_path
    object.__setattr__(settings, "auth_db_path", original)


def _make_user(role: str) -> AuthenticatedUser:
    return AuthenticatedUser(id=1, username=f"test-{role}", role=role)


def _auth_header(user: AuthenticatedUser) -> dict[str, str]:
    token = create_access_token(user, settings.auth_jwt_secret, settings.auth_jwt_ttl_seconds)
    return {"Authorization": f"Bearer {token}"}


# --- /v1/upload: admin and user allowed, viewer denied ---


@patch("main._publish_to_queue")
def test_upload_allowed_for_admin(mock_queue, client: TestClient, auth_db: Path, tmp_path: Path) -> None:
    original_dir = settings.upload_dir
    object.__setattr__(settings, "upload_dir", tmp_path / "uploads")
    try:
        user = _make_user("admin")
        headers = _auth_header(user)
        pdf_content = b"%PDF-1.4 test content"
        resp = client.post(
            "/v1/upload",
            files={"file": ("test.pdf", pdf_content, "application/pdf")},
            headers=headers,
        )
        assert resp.status_code == 200
    finally:
        object.__setattr__(settings, "upload_dir", original_dir)


@patch("main._publish_to_queue")
def test_upload_allowed_for_user(mock_queue, client: TestClient, auth_db: Path, tmp_path: Path) -> None:
    original_dir = settings.upload_dir
    object.__setattr__(settings, "upload_dir", tmp_path / "uploads")
    try:
        user = _make_user("user")
        headers = _auth_header(user)
        pdf_content = b"%PDF-1.4 test content"
        resp = client.post(
            "/v1/upload",
            files={"file": ("test.pdf", pdf_content, "application/pdf")},
            headers=headers,
        )
        assert resp.status_code == 200
    finally:
        object.__setattr__(settings, "upload_dir", original_dir)


def test_upload_denied_for_viewer(client: TestClient, auth_db: Path) -> None:
    user = _make_user("viewer")
    headers = _auth_header(user)
    pdf_content = b"%PDF-1.4 test content"
    resp = client.post(
        "/v1/upload",
        files={"file": ("test.pdf", pdf_content, "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 403
    assert "permissions" in resp.json()["detail"].lower()


# --- /v1/search: any authenticated role allowed ---


@patch("main.query_solr", return_value={"response": {"docs": [], "numFound": 0, "start": 0}})
def test_search_allowed_for_viewer(mock_solr, client: TestClient) -> None:
    user = _make_user("viewer")
    headers = _auth_header(user)
    resp = client.get("/v1/search?q=test", headers=headers)
    assert resp.status_code == 200


@patch("main.query_solr", return_value={"response": {"docs": [], "numFound": 0, "start": 0}})
def test_search_allowed_for_user(mock_solr, client: TestClient) -> None:
    user = _make_user("user")
    headers = _auth_header(user)
    resp = client.get("/v1/search?q=test", headers=headers)
    assert resp.status_code == 200


@patch("main.query_solr", return_value={"response": {"docs": [], "numFound": 0, "start": 0}})
def test_search_allowed_for_admin(mock_solr, client: TestClient) -> None:
    user = _make_user("admin")
    headers = _auth_header(user)
    resp = client.get("/v1/search?q=test", headers=headers)
    assert resp.status_code == 200


# --- Unauthenticated denied ---


def test_search_denied_unauthenticated(client: TestClient) -> None:
    resp = client.get("/v1/search?q=test")
    assert resp.status_code == 401


def test_upload_denied_unauthenticated(client: TestClient) -> None:
    pdf_content = b"%PDF-1.4 test content"
    resp = client.post(
        "/v1/upload",
        files={"file": ("test.pdf", pdf_content, "application/pdf")},
    )
    assert resp.status_code == 401


# --- RBAC returns 403, not 401 for insufficient role ---


def test_rbac_returns_403_not_401(client: TestClient) -> None:
    """Viewers get 403 (not 401) when attempting upload — they ARE authenticated but lack the role."""
    user = _make_user("viewer")
    headers = _auth_header(user)
    pdf_content = b"%PDF-1.4 test content"
    resp = client.post(
        "/v1/upload",
        files={"file": ("test.pdf", pdf_content, "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 403


# --- Admin endpoints still use X-API-Key (backward compat) ---


def test_admin_containers_uses_api_key_not_rbac(client: TestClient) -> None:
    """Phase 1 RBAC: admin endpoints keep X-API-Key auth for backward compat."""
    user = _make_user("admin")
    headers = _auth_header(user)
    # Even an authenticated admin without API key should get 401 or 403
    resp = client.get("/v1/admin/containers", headers=headers)
    assert resp.status_code in (401, 403)
