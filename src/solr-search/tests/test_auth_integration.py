"""Integration tests for auth/user-management API endpoints.

Tests cross-endpoint flows and edge cases for the User CRUD API (#549).
Complements test_user_crud.py (unit tests) with integration scenarios
that exercise multiple endpoints in sequence.

Closes #558
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pytest

os.environ.setdefault("AUTH_DB_PATH", "/tmp/test-auth.db")  # noqa: S108
os.environ.setdefault("AUTH_JWT_SECRET", "test-auth-secret")  # noqa: S105
os.environ.setdefault("AUTH_JWT_TTL", "24h")
os.environ.setdefault("AUTH_COOKIE_NAME", "aithena_auth")

sys.path.append(str(Path(__file__).resolve().parents[1]))

from auth import AuthenticatedUser, create_access_token, hash_password, init_auth_db  # noqa: E402
from config import settings  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

REGISTER_URL = "/v1/auth/register"
USERS_URL = "/v1/auth/users"
LOGIN_URL = "/v1/auth/login"

VALID_PASSWORD = "secure-password-123"  # noqa: S105


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_rate_limiter():
    """Reset login rate limiter between tests to prevent 429 interference."""
    from main import login_rate_limiter

    login_rate_limiter.requests.clear()
    yield
    login_rate_limiter.requests.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_db(tmp_path: Path) -> Path:
    """Isolated SQLite database for each test."""
    original_db_path = settings.auth_db_path
    db_path = tmp_path / "auth.db"
    object.__setattr__(settings, "auth_db_path", db_path)
    init_auth_db(db_path)
    yield db_path
    object.__setattr__(settings, "auth_db_path", original_db_path)


def _seed_user(
    db_path: Path, username: str = "admin", role: str = "admin", password: str = "correct-horse-battery-staple"
) -> AuthenticatedUser:
    """Insert a user directly into the DB and return an AuthenticatedUser."""
    pw_hash = hash_password(password)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, pw_hash, role),
        )
        user_id = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()[0]
        conn.commit()
    return AuthenticatedUser(id=user_id, username=username, role=role)


def _bearer(user: AuthenticatedUser) -> dict[str, str]:
    """Create Authorization header for a user."""
    token = create_access_token(user, settings.auth_jwt_secret, settings.auth_jwt_ttl_seconds)
    return {"Authorization": f"Bearer {token}"}


def _register(
    client: TestClient, headers: dict, *, username: str, password: str = VALID_PASSWORD, role: str = "viewer"
) -> Any:
    """Helper to call the register endpoint."""
    return client.post(REGISTER_URL, json={"username": username, "password": password, "role": role}, headers=headers)


# ===========================================================================
# POST /v1/auth/register — Integration scenarios
# ===========================================================================


class TestRegisterIntegration:
    """Integration tests for user registration endpoint."""

    def test_admin_creates_user_with_admin_role(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        resp = _register(client, _bearer(admin), username="new-admin", role="admin")
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "admin"
        assert data["username"] == "new-admin"

    def test_admin_creates_user_with_user_role(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        resp = _register(client, _bearer(admin), username="new-user", role="user")
        assert resp.status_code == 200
        assert resp.json()["role"] == "user"

    def test_admin_creates_user_with_viewer_role(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        resp = _register(client, _bearer(admin), username="new-viewer", role="viewer")
        assert resp.status_code == 200
        assert resp.json()["role"] == "viewer"

    @pytest.mark.parametrize("role", ["admin", "user", "viewer"])
    def test_all_three_roles_accepted(self, client: TestClient, auth_db: Path, role: str) -> None:
        admin = _seed_user(auth_db)
        resp = _register(client, _bearer(admin), username=f"role-{role}", role=role)
        assert resp.status_code == 200
        assert resp.json()["role"] == role

    def test_non_admin_user_role_gets_403(self, client: TestClient, auth_db: Path) -> None:
        _seed_user(auth_db)
        regular = _seed_user(auth_db, username="regular", role="user")
        resp = _register(client, _bearer(regular), username="attempt")
        assert resp.status_code == 403

    def test_non_admin_viewer_role_gets_403(self, client: TestClient, auth_db: Path) -> None:
        _seed_user(auth_db)
        viewer = _seed_user(auth_db, username="viewer1", role="viewer")
        resp = _register(client, _bearer(viewer), username="attempt")
        assert resp.status_code == 403

    def test_unauthenticated_gets_401(self, client: TestClient, auth_db: Path) -> None:
        resp = client.post(REGISTER_URL, json={"username": "anon", "password": VALID_PASSWORD})
        assert resp.status_code == 401

    def test_duplicate_username_returns_409(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        headers = _bearer(admin)
        _register(client, headers, username="taken")
        resp = _register(client, headers, username="taken")
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"].lower()

    def test_duplicate_username_different_case_returns_409(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        headers = _bearer(admin)
        _register(client, headers, username="Alice")
        resp = _register(client, headers, username="alice")
        assert resp.status_code == 409

    def test_password_too_short_returns_422(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        resp = _register(client, _bearer(admin), username="shortpw", password="1234567")
        assert resp.status_code == 422
        assert "at least" in resp.json()["detail"].lower()

    def test_password_too_long_returns_422(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        resp = _register(client, _bearer(admin), username="longpw", password="x" * 129)
        assert resp.status_code == 422
        assert "at most" in resp.json()["detail"].lower()

    def test_missing_username_returns_422(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        resp = client.post(
            REGISTER_URL,
            json={"password": VALID_PASSWORD},
            headers=_bearer(admin),
        )
        assert resp.status_code == 422

    def test_missing_password_returns_422(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        resp = client.post(
            REGISTER_URL,
            json={"username": "nopw"},
            headers=_bearer(admin),
        )
        assert resp.status_code == 422

    def test_empty_body_returns_422(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        resp = client.post(REGISTER_URL, json={}, headers=_bearer(admin))
        assert resp.status_code == 422

    def test_register_response_never_includes_password(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        resp = _register(client, _bearer(admin), username="check-pw")
        assert resp.status_code == 200
        data = resp.json()
        assert "password" not in data
        assert "password_hash" not in data

    def test_registered_user_can_login(self, client: TestClient, auth_db: Path) -> None:
        """Cross-endpoint: register then login with the new credentials."""
        admin = _seed_user(auth_db)
        _register(client, _bearer(admin), username="logintest", password="my-secure-pw-99")
        login_resp = client.post(LOGIN_URL, json={"username": "logintest", "password": "my-secure-pw-99"})
        assert login_resp.status_code == 200
        assert login_resp.json()["user"]["username"] == "logintest"
        assert login_resp.json()["user"]["role"] == "viewer"

    def test_role_case_normalization(self, client: TestClient, auth_db: Path) -> None:
        """Roles should be normalized to lowercase."""
        admin = _seed_user(auth_db)
        resp = _register(client, _bearer(admin), username="casecheck", role="Admin")
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"


# ===========================================================================
# GET /v1/auth/users — Integration scenarios
# ===========================================================================


class TestListUsersIntegration:
    """Integration tests for user listing endpoint."""

    def test_admin_can_list_all_users(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        _seed_user(auth_db, username="alice", role="viewer")
        _seed_user(auth_db, username="bob", role="user")
        resp = client.get(USERS_URL, headers=_bearer(admin))
        assert resp.status_code == 200
        usernames = {u["username"] for u in resp.json()}
        assert usernames == {"admin", "alice", "bob"}

    def test_non_admin_user_gets_403(self, client: TestClient, auth_db: Path) -> None:
        _seed_user(auth_db)
        regular = _seed_user(auth_db, username="regular", role="user")
        resp = client.get(USERS_URL, headers=_bearer(regular))
        assert resp.status_code == 403

    def test_non_admin_viewer_gets_403(self, client: TestClient, auth_db: Path) -> None:
        _seed_user(auth_db)
        viewer = _seed_user(auth_db, username="viewer1", role="viewer")
        resp = client.get(USERS_URL, headers=_bearer(viewer))
        assert resp.status_code == 403

    def test_unauthenticated_gets_401(self, client: TestClient, auth_db: Path) -> None:
        resp = client.get(USERS_URL)
        assert resp.status_code == 401

    def test_response_never_includes_password_hash(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        _seed_user(auth_db, username="hasher", role="viewer")
        resp = client.get(USERS_URL, headers=_bearer(admin))
        for user in resp.json():
            assert "password_hash" not in user
            assert "password" not in user

    def test_newly_registered_user_appears_in_list(self, client: TestClient, auth_db: Path) -> None:
        """Cross-endpoint: register a user, then verify they appear in the list."""
        admin = _seed_user(auth_db)
        headers = _bearer(admin)
        _register(client, headers, username="fresh-user", role="user")
        resp = client.get(USERS_URL, headers=headers)
        assert resp.status_code == 200
        usernames = {u["username"] for u in resp.json()}
        assert "fresh-user" in usernames

    def test_multiple_registrations_all_appear_in_list(self, client: TestClient, auth_db: Path) -> None:
        """Register 3 users, confirm all appear."""
        admin = _seed_user(auth_db)
        headers = _bearer(admin)
        for name in ("user-a", "user-b", "user-c"):
            _register(client, headers, username=name)
        resp = client.get(USERS_URL, headers=headers)
        usernames = {u["username"] for u in resp.json()}
        assert {"user-a", "user-b", "user-c"}.issubset(usernames)

    def test_list_includes_correct_fields(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        resp = client.get(USERS_URL, headers=_bearer(admin))
        assert resp.status_code == 200
        for user in resp.json():
            assert "id" in user
            assert "username" in user
            assert "role" in user
            assert "created_at" in user


# ===========================================================================
# PUT /v1/auth/users/{id} — Integration scenarios
# ===========================================================================


class TestUpdateUserIntegration:
    """Integration tests for user update endpoint."""

    def test_admin_can_update_any_user_username(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        target = _seed_user(auth_db, username="oldname", role="viewer")
        resp = client.put(
            f"{USERS_URL}/{target.id}",
            json={"username": "newname"},
            headers=_bearer(admin),
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == "newname"

    def test_admin_can_change_user_role(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        target = _seed_user(auth_db, username="promote-me", role="viewer")
        resp = client.put(
            f"{USERS_URL}/{target.id}",
            json={"role": "admin"},
            headers=_bearer(admin),
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    def test_non_admin_can_update_own_username(self, client: TestClient, auth_db: Path) -> None:
        _seed_user(auth_db)
        user = _seed_user(auth_db, username="self-editor", role="user")
        resp = client.put(
            f"{USERS_URL}/{user.id}",
            json={"username": "self-edited"},
            headers=_bearer(user),
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == "self-edited"

    def test_non_admin_cannot_change_own_role(self, client: TestClient, auth_db: Path) -> None:
        _seed_user(auth_db)
        user = _seed_user(auth_db, username="escalator", role="user")
        resp = client.put(
            f"{USERS_URL}/{user.id}",
            json={"role": "admin"},
            headers=_bearer(user),
        )
        assert resp.status_code == 403
        assert "admin" in resp.json()["detail"].lower()

    def test_non_admin_cannot_update_other_users(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        user = _seed_user(auth_db, username="nosy", role="user")
        resp = client.put(
            f"{USERS_URL}/{admin.id}",
            json={"username": "hacked"},
            headers=_bearer(user),
        )
        assert resp.status_code == 403

    def test_viewer_cannot_update_other_users(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        viewer = _seed_user(auth_db, username="peeker", role="viewer")
        resp = client.put(
            f"{USERS_URL}/{admin.id}",
            json={"username": "hacked"},
            headers=_bearer(viewer),
        )
        assert resp.status_code == 403

    def test_nonexistent_user_returns_404(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        resp = client.put(
            f"{USERS_URL}/99999",
            json={"username": "ghost"},
            headers=_bearer(admin),
        )
        assert resp.status_code == 404

    def test_unauthenticated_update_returns_401(self, client: TestClient, auth_db: Path) -> None:
        resp = client.put(f"{USERS_URL}/1", json={"username": "anon"})
        assert resp.status_code == 401

    def test_updated_username_reflects_in_list(self, client: TestClient, auth_db: Path) -> None:
        """Cross-endpoint: update a username, verify it shows in user list."""
        admin = _seed_user(auth_db)
        target = _seed_user(auth_db, username="before", role="viewer")
        headers = _bearer(admin)
        client.put(f"{USERS_URL}/{target.id}", json={"username": "after"}, headers=headers)
        resp = client.get(USERS_URL, headers=headers)
        usernames = {u["username"] for u in resp.json()}
        assert "after" in usernames
        assert "before" not in usernames

    def test_updated_role_reflects_in_list(self, client: TestClient, auth_db: Path) -> None:
        """Cross-endpoint: change a role, verify it shows in user list."""
        admin = _seed_user(auth_db)
        target = _seed_user(auth_db, username="role-target", role="viewer")
        headers = _bearer(admin)
        client.put(f"{USERS_URL}/{target.id}", json={"role": "admin"}, headers=headers)
        resp = client.get(USERS_URL, headers=headers)
        target_user = next(u for u in resp.json() if u["username"] == "role-target")
        assert target_user["role"] == "admin"

    def test_duplicate_username_on_update_returns_409(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        _seed_user(auth_db, username="taken-name", role="viewer")
        target = _seed_user(auth_db, username="want-rename", role="user")
        resp = client.put(
            f"{USERS_URL}/{target.id}",
            json={"username": "taken-name"},
            headers=_bearer(admin),
        )
        assert resp.status_code == 409

    def test_invalid_role_on_update_returns_422(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        target = _seed_user(auth_db, username="bad-role-target", role="viewer")
        resp = client.put(
            f"{USERS_URL}/{target.id}",
            json={"role": "superadmin"},
            headers=_bearer(admin),
        )
        assert resp.status_code == 422


# ===========================================================================
# DELETE /v1/auth/users/{id} — Integration scenarios
# ===========================================================================


class TestDeleteUserIntegration:
    """Integration tests for user deletion endpoint."""

    def test_admin_can_delete_user(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        victim = _seed_user(auth_db, username="goner", role="viewer")
        resp = client.delete(f"{USERS_URL}/{victim.id}", headers=_bearer(admin))
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_admin_cannot_delete_self(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        resp = client.delete(f"{USERS_URL}/{admin.id}", headers=_bearer(admin))
        assert resp.status_code == 400
        assert "yourself" in resp.json()["detail"].lower()

    def test_non_admin_user_gets_403(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        regular = _seed_user(auth_db, username="non-admin", role="user")
        resp = client.delete(f"{USERS_URL}/{admin.id}", headers=_bearer(regular))
        assert resp.status_code == 403

    def test_non_admin_viewer_gets_403(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        viewer = _seed_user(auth_db, username="viewer1", role="viewer")
        resp = client.delete(f"{USERS_URL}/{admin.id}", headers=_bearer(viewer))
        assert resp.status_code == 403

    def test_unauthenticated_gets_401(self, client: TestClient, auth_db: Path) -> None:
        resp = client.delete(f"{USERS_URL}/1")
        assert resp.status_code == 401

    def test_nonexistent_user_returns_404(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        resp = client.delete(f"{USERS_URL}/99999", headers=_bearer(admin))
        assert resp.status_code == 404

    def test_deleted_user_disappears_from_list(self, client: TestClient, auth_db: Path) -> None:
        """Cross-endpoint: delete then verify list no longer includes user."""
        admin = _seed_user(auth_db)
        victim = _seed_user(auth_db, username="vanish", role="viewer")
        headers = _bearer(admin)
        client.delete(f"{USERS_URL}/{victim.id}", headers=headers)
        resp = client.get(USERS_URL, headers=headers)
        usernames = {u["username"] for u in resp.json()}
        assert "vanish" not in usernames

    def test_deleted_user_cannot_login(self, client: TestClient, auth_db: Path) -> None:
        """Cross-endpoint: register, delete, then verify login fails."""
        admin = _seed_user(auth_db)
        headers = _bearer(admin)
        _register(client, headers, username="doomed", password="valid-password-123")
        # Find the user's ID
        users_resp = client.get(USERS_URL, headers=headers)
        doomed = next(u for u in users_resp.json() if u["username"] == "doomed")
        # Delete the user
        client.delete(f"{USERS_URL}/{doomed['id']}", headers=headers)
        # Try to login as deleted user
        login_resp = client.post(LOGIN_URL, json={"username": "doomed", "password": "valid-password-123"})
        assert login_resp.status_code == 401

    def test_double_delete_returns_404(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        victim = _seed_user(auth_db, username="twice", role="viewer")
        headers = _bearer(admin)
        resp1 = client.delete(f"{USERS_URL}/{victim.id}", headers=headers)
        assert resp1.status_code == 200
        resp2 = client.delete(f"{USERS_URL}/{victim.id}", headers=headers)
        assert resp2.status_code == 404


# ===========================================================================
# Cross-endpoint lifecycle flows
# ===========================================================================


class TestUserLifecycleFlows:
    """End-to-end integration flows across multiple endpoints."""

    def test_full_lifecycle_register_list_update_delete(self, client: TestClient, auth_db: Path) -> None:
        """Complete user lifecycle: create → verify in list → update → verify → delete → verify gone."""
        admin = _seed_user(auth_db)
        headers = _bearer(admin)

        # 1. Register
        reg_resp = _register(client, headers, username="lifecycle", role="viewer")
        assert reg_resp.status_code == 200
        user_id = reg_resp.json()["id"]

        # 2. Verify appears in list
        list_resp = client.get(USERS_URL, headers=headers)
        assert any(u["username"] == "lifecycle" for u in list_resp.json())

        # 3. Update username
        upd_resp = client.put(f"{USERS_URL}/{user_id}", json={"username": "lifecycle-v2"}, headers=headers)
        assert upd_resp.status_code == 200
        assert upd_resp.json()["username"] == "lifecycle-v2"

        # 4. Verify updated in list
        list_resp2 = client.get(USERS_URL, headers=headers)
        usernames = {u["username"] for u in list_resp2.json()}
        assert "lifecycle-v2" in usernames
        assert "lifecycle" not in usernames

        # 5. Delete
        del_resp = client.delete(f"{USERS_URL}/{user_id}", headers=headers)
        assert del_resp.status_code == 200

        # 6. Verify gone from list
        list_resp3 = client.get(USERS_URL, headers=headers)
        assert all(u["id"] != user_id for u in list_resp3.json())

    def test_register_login_me_logout_flow(self, client: TestClient, auth_db: Path) -> None:
        """Register → login → /me → logout flow."""
        admin = _seed_user(auth_db)
        _register(client, _bearer(admin), username="flow-user", password="my-test-pw-123", role="user")

        # Login as new user
        login_resp = client.post(LOGIN_URL, json={"username": "flow-user", "password": "my-test-pw-123"})
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

        # Check /me
        me_resp = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        assert me_resp.json()["username"] == "flow-user"
        assert me_resp.json()["role"] == "user"

        # Logout
        logout_resp = client.post("/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert logout_resp.status_code == 200

    def test_role_promotion_reflected_in_login(self, client: TestClient, auth_db: Path) -> None:
        """Register as viewer, promote to admin, verify new login token has admin role."""
        admin = _seed_user(auth_db)
        headers = _bearer(admin)

        # Register viewer
        reg_resp = _register(client, headers, username="promotee", password="good-password-99", role="viewer")
        user_id = reg_resp.json()["id"]

        # Promote to admin
        client.put(f"{USERS_URL}/{user_id}", json={"role": "admin"}, headers=headers)

        # Login and check role in token
        login_resp = client.post(LOGIN_URL, json={"username": "promotee", "password": "good-password-99"})
        assert login_resp.status_code == 200
        assert login_resp.json()["user"]["role"] == "admin"

    def test_role_demotion_restricts_access(self, client: TestClient, auth_db: Path) -> None:
        """Demote an admin to viewer, verify they can't list users with a fresh login."""
        admin = _seed_user(auth_db)
        target = _seed_user(auth_db, username="demotee", role="admin", password="demotee-pw-123")
        headers = _bearer(admin)

        # Demote to viewer
        client.put(f"{USERS_URL}/{target.id}", json={"role": "viewer"}, headers=headers)

        # Login as demoted user to get fresh token with updated role
        login_resp = client.post(LOGIN_URL, json={"username": "demotee", "password": "demotee-pw-123"})
        assert login_resp.status_code == 200
        new_token = login_resp.json()["access_token"]

        # Try admin-only endpoint with new token
        list_resp = client.get(USERS_URL, headers={"Authorization": f"Bearer {new_token}"})
        assert list_resp.status_code == 403

    def test_self_edit_username_then_login_with_new_name(self, client: TestClient, auth_db: Path) -> None:
        """Non-admin updates own username, then logs in with the new name."""
        _seed_user(auth_db)
        user = _seed_user(auth_db, username="old-me", role="user", password="user-pw-12345")

        # Self-update username
        resp = client.put(
            f"{USERS_URL}/{user.id}",
            json={"username": "new-me"},
            headers=_bearer(user),
        )
        assert resp.status_code == 200

        # Login with new username
        login_resp = client.post(LOGIN_URL, json={"username": "new-me", "password": "user-pw-12345"})
        assert login_resp.status_code == 200
        assert login_resp.json()["user"]["username"] == "new-me"

        # Old username no longer works
        old_login = client.post(LOGIN_URL, json={"username": "old-me", "password": "user-pw-12345"})
        assert old_login.status_code == 401

    def test_bulk_register_and_list_count(self, client: TestClient, auth_db: Path) -> None:
        """Register multiple users and verify list count matches."""
        admin = _seed_user(auth_db)
        headers = _bearer(admin)
        for i in range(5):
            _register(client, headers, username=f"bulk-{i}")
        resp = client.get(USERS_URL, headers=headers)
        # 1 seeded admin + 5 registered = 6
        assert len(resp.json()) == 6
