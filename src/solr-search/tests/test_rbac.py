"""Comprehensive parametrized RBAC test suite for all protected endpoints (#559).

Tests role-based access control across every protected endpoint with a full
matrix covering admin, user, viewer, and unauthenticated access.

Test matrix (9 endpoints × 4 roles = 36 parametrized cases + edge-case tests):
┌────────────────────────────────┬───────┬──────┬────────┬────────┐
│ Endpoint                       │ admin │ user │ viewer │ unauth │
├────────────────────────────────┼───────┼──────┼────────┼────────┤
│ POST /v1/auth/register         │  200  │ 403  │  403   │  401   │
│ GET  /v1/auth/users            │  200  │ 403  │  403   │  401   │
│ PUT  /v1/auth/users/{id}       │  200  │ 403  │  403   │  401   │
│ DELETE /v1/auth/users/{id}     │  200  │ 403  │  403   │  401   │
│ PUT  /v1/auth/change-password  │  200  │ 200  │  200   │  401   │
│ GET  /v1/auth/me               │  200  │ 200  │  200   │  401   │
│ POST /v1/auth/logout           │  200  │ 200  │  200   │  401   │
│ GET  /v1/search                │  200  │ 200  │  200   │  401   │
│ POST /v1/upload                │  200  │ 200  │  403   │  401   │
└────────────────────────────────┴───────┴──────┴────────┴────────┘
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

os.environ.setdefault("AUTH_DB_PATH", "/tmp/test-auth.db")  # noqa: S108
os.environ.setdefault("AUTH_JWT_SECRET", "test-auth-secret")  # noqa: S105
os.environ.setdefault("AUTH_JWT_TTL", "24h")
os.environ.setdefault("AUTH_COOKIE_NAME", "aithena_auth")

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from auth import AuthenticatedUser, create_access_token, hash_password, init_auth_db  # noqa: E402
from config import settings  # noqa: E402
from main import app  # noqa: E402

# Password compliant with policy: uppercase + lowercase + digit, 8-128 chars
VALID_PASSWORD = "TestPass123"  # noqa: S105
NEW_PASSWORD = "NewPass456"  # noqa: S105


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_rate_limiters():
    """Reset all rate limiters between tests to prevent 429 interference."""
    from main import login_rate_limiter, upload_rate_limiter

    login_rate_limiter.requests.clear()
    upload_rate_limiter.requests.clear()
    yield
    login_rate_limiter.requests.clear()
    upload_rate_limiter.requests.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_db(tmp_path: Path):
    """Isolated auth database for each test."""
    original = settings.auth_db_path
    db_path = tmp_path / "rbac_test.db"
    object.__setattr__(settings, "auth_db_path", db_path)
    init_auth_db(db_path)
    yield db_path
    object.__setattr__(settings, "auth_db_path", original)


@pytest.fixture
def seeded_users(auth_db: Path) -> dict[str, AuthenticatedUser]:
    """Seed admin, user, viewer, and a target user in the auth DB.

    Returns dict mapping role name (and 'target') to AuthenticatedUser
    with ids matching the DB rows.
    """
    users: dict[str, AuthenticatedUser] = {}
    for role in ("admin", "user", "viewer"):
        pw_hash = hash_password(VALID_PASSWORD)
        with sqlite3.connect(auth_db) as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (f"rbac-{role}", pw_hash, role),
            )
            user_id = cursor.lastrowid
            conn.commit()
        users[role] = AuthenticatedUser(id=user_id, username=f"rbac-{role}", role=role)

    # Target user for update/delete tests (distinct from any requester)
    pw_hash = hash_password(VALID_PASSWORD)
    with sqlite3.connect(auth_db) as conn:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ("target-user", pw_hash, "viewer"),
        )
        target_id = cursor.lastrowid
        conn.commit()
    users["target"] = AuthenticatedUser(id=target_id, username="target-user", role="viewer")

    return users


def _auth_header(user: AuthenticatedUser) -> dict[str, str]:
    token = create_access_token(user, settings.auth_jwt_secret, settings.auth_jwt_ttl_seconds)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Request helpers — one per endpoint
# ---------------------------------------------------------------------------


def _request_register(client: TestClient, headers: dict[str, str], **_: Any) -> Any:
    return client.post(
        "/v1/auth/register",
        json={"username": "new-rbac-user", "password": VALID_PASSWORD, "role": "viewer"},
        headers=headers,
    )


def _request_list_users(client: TestClient, headers: dict[str, str], **_: Any) -> Any:
    return client.get("/v1/auth/users", headers=headers)


def _request_update_user(
    client: TestClient, headers: dict[str, str], *, target_id: int, **_: Any
) -> Any:
    return client.put(
        f"/v1/auth/users/{target_id}",
        json={"username": "updated-target"},
        headers=headers,
    )


def _request_delete_user(
    client: TestClient, headers: dict[str, str], *, target_id: int, **_: Any
) -> Any:
    return client.delete(f"/v1/auth/users/{target_id}", headers=headers)


def _request_change_password(client: TestClient, headers: dict[str, str], **_: Any) -> Any:
    return client.put(
        "/v1/auth/change-password",
        json={"current_password": VALID_PASSWORD, "new_password": NEW_PASSWORD},
        headers=headers,
    )


def _request_me(client: TestClient, headers: dict[str, str], **_: Any) -> Any:
    return client.get("/v1/auth/me", headers=headers)


def _request_logout(client: TestClient, headers: dict[str, str], **_: Any) -> Any:
    return client.post("/v1/auth/logout", headers=headers)


def _request_search(client: TestClient, headers: dict[str, str], **_: Any) -> Any:
    return client.get("/v1/search?q=test", headers=headers)


def _request_upload(client: TestClient, headers: dict[str, str], **_: Any) -> Any:
    return client.post(
        "/v1/upload",
        files={"file": ("test.pdf", b"%PDF-1.4 test content", "application/pdf")},
        headers=headers,
    )


_REQUEST_FN = {
    "register": _request_register,
    "list_users": _request_list_users,
    "update_user": _request_update_user,
    "delete_user": _request_delete_user,
    "change_password": _request_change_password,
    "me": _request_me,
    "logout": _request_logout,
    "search": _request_search,
    "upload": _request_upload,
}

# Endpoints needing external service mocks for successful (2xx) requests
_NEEDS_SOLR_MOCK = frozenset({"search"})
_NEEDS_UPLOAD_MOCK = frozenset({"upload"})


# ---------------------------------------------------------------------------
# Parametrized RBAC matrix — 36 test cases
# ---------------------------------------------------------------------------

RBAC_MATRIX = [
    # POST /v1/auth/register — admin only
    ("register", "admin", 200),
    ("register", "user", 403),
    ("register", "viewer", 403),
    ("register", None, 401),
    # GET /v1/auth/users — admin only
    ("list_users", "admin", 200),
    ("list_users", "user", 403),
    ("list_users", "viewer", 403),
    ("list_users", None, 401),
    # PUT /v1/auth/users/{id} — admin or self (tested with *other* user → non-admin = 403)
    ("update_user", "admin", 200),
    ("update_user", "user", 403),
    ("update_user", "viewer", 403),
    ("update_user", None, 401),
    # DELETE /v1/auth/users/{id} — admin only
    ("delete_user", "admin", 200),
    ("delete_user", "user", 403),
    ("delete_user", "viewer", 403),
    ("delete_user", None, 401),
    # PUT /v1/auth/change-password — any authenticated user
    ("change_password", "admin", 200),
    ("change_password", "user", 200),
    ("change_password", "viewer", 200),
    ("change_password", None, 401),
    # GET /v1/auth/me — any authenticated user
    ("me", "admin", 200),
    ("me", "user", 200),
    ("me", "viewer", 200),
    ("me", None, 401),
    # POST /v1/auth/logout — any authenticated user
    ("logout", "admin", 200),
    ("logout", "user", 200),
    ("logout", "viewer", 200),
    ("logout", None, 401),
    # GET /v1/search — any authenticated user
    ("search", "admin", 200),
    ("search", "user", 200),
    ("search", "viewer", 200),
    ("search", None, 401),
    # POST /v1/upload — admin and user only, viewer denied
    ("upload", "admin", 200),
    ("upload", "user", 200),
    ("upload", "viewer", 403),
    ("upload", None, 401),
]


@pytest.mark.parametrize(
    "endpoint_id,role,expected_status",
    RBAC_MATRIX,
    ids=[f"{eid}-{role or 'unauth'}-expects-{status}" for eid, role, status in RBAC_MATRIX],
)
def test_rbac_access_control(
    endpoint_id: str,
    role: str | None,
    expected_status: int,
    client: TestClient,
    seeded_users: dict[str, AuthenticatedUser],
    tmp_path: Path,
) -> None:
    """Verify each endpoint enforces the correct access control per role."""
    headers = _auth_header(seeded_users[role]) if role else {}
    target_id = seeded_users["target"].id

    patches: list[Any] = []
    original_upload_dir = settings.upload_dir

    # Apply mocks only for successful requests that reach business logic
    if endpoint_id in _NEEDS_SOLR_MOCK and expected_status == 200:
        patches.append(
            patch("main.query_solr", return_value={"response": {"docs": [], "numFound": 0, "start": 0}})
        )
    if endpoint_id in _NEEDS_UPLOAD_MOCK and expected_status == 200:
        object.__setattr__(settings, "upload_dir", tmp_path / "uploads")
        patches.append(patch("main._publish_to_queue"))

    for p in patches:
        p.start()
    try:
        resp = _REQUEST_FN[endpoint_id](client, headers, target_id=target_id)

        assert resp.status_code == expected_status, (
            f"{endpoint_id} with role={role!r}: expected {expected_status}, "
            f"got {resp.status_code}. Body: {resp.text}"
        )

        if expected_status == 403:
            detail = resp.json()["detail"].lower()
            assert "permission" in detail or "insufficient" in detail

        if expected_status == 401:
            assert "www-authenticate" in {k.lower() for k in resp.headers}
    finally:
        for p in patches:
            p.stop()
        if endpoint_id in _NEEDS_UPLOAD_MOCK and expected_status == 200:
            object.__setattr__(settings, "upload_dir", original_upload_dir)


# ---------------------------------------------------------------------------
# Edge-case tests beyond the matrix
# ---------------------------------------------------------------------------


class TestUpdateUserSelfEdit:
    """PUT /v1/auth/users/{id}: non-admin users CAN update their own profile."""

    def test_user_can_update_own_username(
        self, client: TestClient, seeded_users: dict[str, AuthenticatedUser]
    ) -> None:
        user = seeded_users["user"]
        headers = _auth_header(user)
        resp = client.put(
            f"/v1/auth/users/{user.id}",
            json={"username": "my-new-name"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == "my-new-name"

    def test_viewer_can_update_own_username(
        self, client: TestClient, seeded_users: dict[str, AuthenticatedUser]
    ) -> None:
        viewer = seeded_users["viewer"]
        headers = _auth_header(viewer)
        resp = client.put(
            f"/v1/auth/users/{viewer.id}",
            json={"username": "viewer-new-name"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == "viewer-new-name"

    def test_user_cannot_change_own_role(
        self, client: TestClient, seeded_users: dict[str, AuthenticatedUser]
    ) -> None:
        user = seeded_users["user"]
        headers = _auth_header(user)
        resp = client.put(
            f"/v1/auth/users/{user.id}",
            json={"role": "admin"},
            headers=headers,
        )
        assert resp.status_code == 403
        assert "role" in resp.json()["detail"].lower() or "admin" in resp.json()["detail"].lower()


class TestDeleteUserEdgeCases:
    """DELETE /v1/auth/users/{id}: admin cannot self-delete."""

    def test_admin_cannot_delete_self(
        self, client: TestClient, seeded_users: dict[str, AuthenticatedUser]
    ) -> None:
        admin = seeded_users["admin"]
        headers = _auth_header(admin)
        resp = client.delete(f"/v1/auth/users/{admin.id}", headers=headers)
        assert resp.status_code == 400
        assert "yourself" in resp.json()["detail"].lower()


class TestRbacResponseShape:
    """Verify 403 and 401 responses have correct structure."""

    def test_403_returns_json_with_detail(
        self, client: TestClient, seeded_users: dict[str, AuthenticatedUser]
    ) -> None:
        viewer = seeded_users["viewer"]
        headers = _auth_header(viewer)
        resp = client.post(
            "/v1/upload",
            files={"file": ("test.pdf", b"%PDF-1.4 test", "application/pdf")},
            headers=headers,
        )
        assert resp.status_code == 403
        body = resp.json()
        assert "detail" in body

    def test_401_returns_json_with_www_authenticate(self, client: TestClient) -> None:
        resp = client.get("/v1/auth/me")
        assert resp.status_code == 401
        assert "www-authenticate" in {k.lower() for k in resp.headers}
        body = resp.json()
        assert "detail" in body

    def test_403_not_401_for_authenticated_insufficient_role(
        self, client: TestClient, seeded_users: dict[str, AuthenticatedUser]
    ) -> None:
        """Viewers are authenticated but lack the role → must get 403, never 401."""
        viewer = seeded_users["viewer"]
        headers = _auth_header(viewer)

        # Try admin-only endpoints
        resp_register = client.post(
            "/v1/auth/register",
            json={"username": "x", "password": VALID_PASSWORD, "role": "viewer"},
            headers=headers,
        )
        resp_list = client.get("/v1/auth/users", headers=headers)
        resp_delete = client.delete(
            f"/v1/auth/users/{seeded_users['target'].id}", headers=headers
        )

        for resp, name in [
            (resp_register, "register"),
            (resp_list, "list_users"),
            (resp_delete, "delete_user"),
        ]:
            assert resp.status_code == 403, f"{name}: expected 403, got {resp.status_code}"


class TestAdminApiKeyBackwardCompat:
    """Admin endpoints accept both X-API-Key and admin JWT sessions."""

    def test_admin_containers_rejects_non_admin_jwt(
        self, client: TestClient, seeded_users: dict[str, AuthenticatedUser]
    ) -> None:
        user = seeded_users["user"]
        headers = _auth_header(user)
        resp = client.get("/v1/admin/containers", headers=headers)
        assert resp.status_code in (401, 403)
