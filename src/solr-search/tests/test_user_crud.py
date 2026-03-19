"""Tests for user CRUD API endpoints (POST register, GET users, PUT users/{id}, DELETE users/{id})."""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

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


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_db(tmp_path: Path) -> Path:
    original_db_path = settings.auth_db_path
    db_path = tmp_path / "auth.db"
    object.__setattr__(settings, "auth_db_path", db_path)
    init_auth_db(db_path)
    yield db_path
    object.__setattr__(settings, "auth_db_path", original_db_path)


def _seed_user(auth_db: Path, username: str = "admin", role: str = "admin") -> AuthenticatedUser:
    password_hash = hash_password("correct-horse-battery-staple")
    with sqlite3.connect(auth_db) as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, password_hash, role),
        )
        user_id = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()[0]
        conn.commit()
    return AuthenticatedUser(id=user_id, username=username, role=role)


def _auth_header(user: AuthenticatedUser) -> dict[str, str]:
    token = create_access_token(user, settings.auth_jwt_secret, settings.auth_jwt_ttl_seconds)
    return {"Authorization": f"Bearer {token}"}


# ---- POST /v1/auth/register ----


class TestRegister:
    def test_admin_can_register_user(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        resp = client.post(
            "/v1/auth/register",
            json={"username": "newuser", "password": "secure-password-123", "role": "viewer"},
            headers=_auth_header(admin),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "newuser"
        assert data["role"] == "viewer"
        assert "id" in data
        assert "created_at" in data

    def test_register_default_role_is_viewer(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        resp = client.post(
            "/v1/auth/register",
            json={"username": "default-role", "password": "secure-password-123"},
            headers=_auth_header(admin),
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "viewer"

    def test_register_duplicate_username_returns_409(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        client.post(
            "/v1/auth/register",
            json={"username": "dupuser", "password": "secure-password-123", "role": "viewer"},
            headers=_auth_header(admin),
        )
        resp = client.post(
            "/v1/auth/register",
            json={"username": "dupuser", "password": "another-password1", "role": "user"},
            headers=_auth_header(admin),
        )
        assert resp.status_code == 409

    def test_register_duplicate_username_case_insensitive(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        client.post(
            "/v1/auth/register",
            json={"username": "CaseUser", "password": "secure-password-123", "role": "viewer"},
            headers=_auth_header(admin),
        )
        resp = client.post(
            "/v1/auth/register",
            json={"username": "caseuser", "password": "another-password1", "role": "user"},
            headers=_auth_header(admin),
        )
        assert resp.status_code == 409

    def test_register_short_password_rejected(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        resp = client.post(
            "/v1/auth/register",
            json={"username": "shortpw", "password": "short", "role": "viewer"},
            headers=_auth_header(admin),
        )
        assert resp.status_code == 422
        assert "at least" in resp.json()["detail"]

    def test_register_long_password_rejected(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        resp = client.post(
            "/v1/auth/register",
            json={"username": "longpw", "password": "x" * 129, "role": "viewer"},
            headers=_auth_header(admin),
        )
        assert resp.status_code == 422
        assert "at most" in resp.json()["detail"]

    def test_register_invalid_role_rejected(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        resp = client.post(
            "/v1/auth/register",
            json={"username": "badrole", "password": "secure-password-123", "role": "superadmin"},
            headers=_auth_header(admin),
        )
        assert resp.status_code == 422

    def test_register_empty_username_rejected(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        resp = client.post(
            "/v1/auth/register",
            json={"username": "  ", "password": "secure-password-123", "role": "viewer"},
            headers=_auth_header(admin),
        )
        assert resp.status_code == 422

    def test_non_admin_cannot_register(self, client: TestClient, auth_db: Path) -> None:
        _seed_user(auth_db)
        viewer = _seed_user(auth_db, username="viewer1", role="viewer")
        resp = client.post(
            "/v1/auth/register",
            json={"username": "hack", "password": "secure-password-123", "role": "admin"},
            headers=_auth_header(viewer),
        )
        assert resp.status_code == 403

    def test_unauthenticated_register_rejected(self, client: TestClient, auth_db: Path) -> None:
        resp = client.post(
            "/v1/auth/register",
            json={"username": "anon", "password": "secure-password-123", "role": "viewer"},
        )
        assert resp.status_code == 401

    def test_register_max_length_password_accepted(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        resp = client.post(
            "/v1/auth/register",
            json={"username": "maxpw", "password": "x" * 128, "role": "viewer"},
            headers=_auth_header(admin),
        )
        assert resp.status_code == 200


# ---- GET /v1/auth/users ----


class TestListUsers:
    def test_admin_can_list_users(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        _seed_user(auth_db, username="bob", role="viewer")
        resp = client.get("/v1/auth/users", headers=_auth_header(admin))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert all("password_hash" not in u for u in data)
        usernames = {u["username"] for u in data}
        assert usernames == {"admin", "bob"}

    def test_non_admin_cannot_list_users(self, client: TestClient, auth_db: Path) -> None:
        _seed_user(auth_db)
        viewer = _seed_user(auth_db, username="viewer1", role="viewer")
        resp = client.get("/v1/auth/users", headers=_auth_header(viewer))
        assert resp.status_code == 403

    def test_unauthenticated_list_users_rejected(self, client: TestClient, auth_db: Path) -> None:
        resp = client.get("/v1/auth/users")
        assert resp.status_code == 401

    def test_list_users_returns_ordered_by_id(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        _seed_user(auth_db, username="alice", role="user")
        _seed_user(auth_db, username="bob", role="viewer")
        resp = client.get("/v1/auth/users", headers=_auth_header(admin))
        data = resp.json()
        ids = [u["id"] for u in data]
        assert ids == sorted(ids)


# ---- PUT /v1/auth/users/{id} ----


class TestUpdateUser:
    def test_admin_can_update_any_user_username(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        viewer = _seed_user(auth_db, username="oldname", role="viewer")
        resp = client.put(
            f"/v1/auth/users/{viewer.id}",
            json={"username": "newname"},
            headers=_auth_header(admin),
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == "newname"

    def test_admin_can_update_role(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        viewer = _seed_user(auth_db, username="promote", role="viewer")
        resp = client.put(
            f"/v1/auth/users/{viewer.id}",
            json={"role": "user"},
            headers=_auth_header(admin),
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "user"

    def test_non_admin_can_update_own_username(self, client: TestClient, auth_db: Path) -> None:
        _seed_user(auth_db)
        user = _seed_user(auth_db, username="self-edit", role="user")
        resp = client.put(
            f"/v1/auth/users/{user.id}",
            json={"username": "new-self-name"},
            headers=_auth_header(user),
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == "new-self-name"

    def test_non_admin_cannot_update_other_user(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        user = _seed_user(auth_db, username="regular", role="user")
        resp = client.put(
            f"/v1/auth/users/{admin.id}",
            json={"username": "hacked"},
            headers=_auth_header(user),
        )
        assert resp.status_code == 403

    def test_non_admin_cannot_change_role(self, client: TestClient, auth_db: Path) -> None:
        _seed_user(auth_db)
        user = _seed_user(auth_db, username="escalate", role="user")
        resp = client.put(
            f"/v1/auth/users/{user.id}",
            json={"role": "admin"},
            headers=_auth_header(user),
        )
        assert resp.status_code == 403

    def test_update_nonexistent_user_returns_404(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        resp = client.put(
            "/v1/auth/users/9999",
            json={"username": "ghost"},
            headers=_auth_header(admin),
        )
        assert resp.status_code == 404

    def test_update_duplicate_username_returns_409(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        _seed_user(auth_db, username="existing", role="viewer")
        resp = client.put(
            f"/v1/auth/users/{admin.id}",
            json={"username": "existing"},
            headers=_auth_header(admin),
        )
        assert resp.status_code == 409

    def test_update_empty_body_returns_current(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        resp = client.put(
            f"/v1/auth/users/{admin.id}",
            json={},
            headers=_auth_header(admin),
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == "admin"

    def test_update_invalid_role_rejected(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        viewer = _seed_user(auth_db, username="badrole", role="viewer")
        resp = client.put(
            f"/v1/auth/users/{viewer.id}",
            json={"role": "superadmin"},
            headers=_auth_header(admin),
        )
        assert resp.status_code == 422

    def test_unauthenticated_update_rejected(self, client: TestClient, auth_db: Path) -> None:
        resp = client.put("/v1/auth/users/1", json={"username": "anon"})
        assert resp.status_code == 401


# ---- DELETE /v1/auth/users/{id} ----


class TestDeleteUser:
    def test_admin_can_delete_user(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        victim = _seed_user(auth_db, username="deleteme", role="viewer")
        resp = client.delete(
            f"/v1/auth/users/{victim.id}",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"
        # Verify user is actually gone
        list_resp = client.get("/v1/auth/users", headers=_auth_header(admin))
        assert all(u["username"] != "deleteme" for u in list_resp.json())

    def test_admin_cannot_delete_self(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        resp = client.delete(
            f"/v1/auth/users/{admin.id}",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 400
        assert "yourself" in resp.json()["detail"]

    def test_delete_nonexistent_user_returns_404(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        resp = client.delete("/v1/auth/users/9999", headers=_auth_header(admin))
        assert resp.status_code == 404

    def test_non_admin_cannot_delete_user(self, client: TestClient, auth_db: Path) -> None:
        admin = _seed_user(auth_db)
        user = _seed_user(auth_db, username="regular", role="user")
        resp = client.delete(
            f"/v1/auth/users/{admin.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 403

    def test_unauthenticated_delete_rejected(self, client: TestClient, auth_db: Path) -> None:
        resp = client.delete("/v1/auth/users/1")
        assert resp.status_code == 401


# ---- Unit tests for auth.py CRUD functions ----


class TestAuthCrudFunctions:
    def test_create_user(self, auth_db: Path) -> None:
        from auth import create_user

        result = create_user(auth_db, "funcuser", "good-password-123", "user")
        assert result["username"] == "funcuser"
        assert result["role"] == "user"
        assert "id" in result

    def test_create_user_duplicate_raises(self, auth_db: Path) -> None:
        from auth import UserExistsError, create_user

        create_user(auth_db, "dup", "good-password-123", "user")
        with pytest.raises(UserExistsError):
            create_user(auth_db, "dup", "other-password-12", "viewer")

    def test_list_users_empty(self, auth_db: Path) -> None:
        from auth import list_users

        assert list_users(auth_db) == []

    def test_get_user_by_id_not_found(self, auth_db: Path) -> None:
        from auth import get_user_by_id

        assert get_user_by_id(auth_db, 999) is None

    def test_update_user_username(self, auth_db: Path) -> None:
        from auth import create_user, update_user

        user = create_user(auth_db, "original", "good-password-123", "user")
        updated = update_user(auth_db, user["id"], username="renamed")
        assert updated["username"] == "renamed"

    def test_update_user_role(self, auth_db: Path) -> None:
        from auth import create_user, update_user

        user = create_user(auth_db, "rolechange", "good-password-123", "viewer")
        updated = update_user(auth_db, user["id"], role="admin")
        assert updated["role"] == "admin"

    def test_update_nonexistent_user(self, auth_db: Path) -> None:
        from auth import update_user

        assert update_user(auth_db, 999, username="ghost") is None

    def test_delete_user_returns_true(self, auth_db: Path) -> None:
        from auth import create_user, delete_user

        user = create_user(auth_db, "todelete", "good-password-123", "viewer")
        assert delete_user(auth_db, user["id"]) is True

    def test_delete_nonexistent_returns_false(self, auth_db: Path) -> None:
        from auth import delete_user

        assert delete_user(auth_db, 999) is False

    def test_validate_password_boundaries(self) -> None:
        from auth import PasswordPolicyError, validate_password

        with pytest.raises(PasswordPolicyError):
            validate_password("short")
        with pytest.raises(PasswordPolicyError):
            validate_password("x" * 129)
        validate_password("x" * 8)
        validate_password("x" * 128)

    def test_validate_role(self) -> None:
        from auth import validate_role

        assert validate_role("Admin") == "admin"
        assert validate_role("USER") == "user"
        assert validate_role("viewer") == "viewer"
        with pytest.raises(ValueError, match="Invalid role"):
            validate_role("superadmin")

    def test_update_user_duplicate_username_raises(self, auth_db: Path) -> None:
        from auth import UserExistsError, create_user, update_user

        create_user(auth_db, "first", "good-password-123", "user")
        second = create_user(auth_db, "second", "good-password-123", "user")
        with pytest.raises(UserExistsError):
            update_user(auth_db, second["id"], username="first")

    def test_create_user_empty_username_raises(self, auth_db: Path) -> None:
        from auth import create_user

        with pytest.raises(ValueError, match="empty"):
            create_user(auth_db, "  ", "good-password-123", "user")

    def test_update_user_empty_username_raises(self, auth_db: Path) -> None:
        from auth import create_user, update_user

        user = create_user(auth_db, "notempty", "good-password-123", "user")
        with pytest.raises(ValueError, match="empty"):
            update_user(auth_db, user["id"], username="  ")

    def test_update_no_changes_returns_current(self, auth_db: Path) -> None:
        from auth import create_user, update_user

        user = create_user(auth_db, "unchanged", "good-password-123", "user")
        result = update_user(auth_db, user["id"])
        assert result["username"] == "unchanged"
