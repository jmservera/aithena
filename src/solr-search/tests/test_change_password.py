"""Tests for the change-password endpoint PUT /v1/auth/change-password (#551)."""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import UTC, datetime
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
def auth_db(tmp_path: Path):
    original = settings.auth_db_path
    db_path = tmp_path / "change-pw.db"
    object.__setattr__(settings, "auth_db_path", db_path)
    init_auth_db(db_path)
    yield db_path
    object.__setattr__(settings, "auth_db_path", original)


def _seed_user(db_path: Path, username: str, password: str, role: str = "user") -> AuthenticatedUser:
    pw_hash = hash_password(password)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (username, pw_hash, role, datetime.now(UTC).isoformat()),
        )
        uid = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()[0]
        conn.commit()
    return AuthenticatedUser(id=uid, username=username, role=role)


def _auth_header(user: AuthenticatedUser) -> dict[str, str]:
    token = create_access_token(user, settings.auth_jwt_secret, settings.auth_jwt_ttl_seconds)
    return {"Authorization": f"Bearer {token}"}


def test_change_password_success(client: TestClient, auth_db: Path) -> None:
    user = _seed_user(auth_db, "alice", "OldPass123")
    headers = _auth_header(user)

    resp = client.put(
        "/v1/auth/change-password",
        json={"current_password": "OldPass123", "new_password": "NewPass456"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "password_changed"

    # Verify new password works for login
    login_resp = client.post("/v1/auth/login", json={"username": "alice", "password": "NewPass456"})
    assert login_resp.status_code == 200


def test_change_password_wrong_current(client: TestClient, auth_db: Path) -> None:
    user = _seed_user(auth_db, "bob", "Correct1Pass")
    headers = _auth_header(user)

    resp = client.put(
        "/v1/auth/change-password",
        json={"current_password": "WrongPass1", "new_password": "NewPass456"},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "incorrect" in resp.json()["detail"].lower()


def test_change_password_same_password(client: TestClient, auth_db: Path) -> None:
    user = _seed_user(auth_db, "carol", "Same1Pass!")
    headers = _auth_header(user)

    resp = client.put(
        "/v1/auth/change-password",
        json={"current_password": "Same1Pass!", "new_password": "Same1Pass!"},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "different" in resp.json()["detail"].lower()


def test_change_password_policy_violation_too_short(client: TestClient, auth_db: Path) -> None:
    user = _seed_user(auth_db, "dave", "Valid1Pass")
    headers = _auth_header(user)

    resp = client.put(
        "/v1/auth/change-password",
        json={"current_password": "Valid1Pass", "new_password": "Sh1"},
        headers=headers,
    )
    assert resp.status_code == 422
    assert "at least" in resp.json()["detail"].lower()


def test_change_password_policy_no_uppercase(client: TestClient, auth_db: Path) -> None:
    user = _seed_user(auth_db, "eve", "Valid1Pass")
    headers = _auth_header(user)

    resp = client.put(
        "/v1/auth/change-password",
        json={"current_password": "Valid1Pass", "new_password": "nouppercase1"},
        headers=headers,
    )
    assert resp.status_code == 422
    assert "uppercase" in resp.json()["detail"].lower()


def test_change_password_policy_no_digit(client: TestClient, auth_db: Path) -> None:
    user = _seed_user(auth_db, "frank", "Valid1Pass")
    headers = _auth_header(user)

    resp = client.put(
        "/v1/auth/change-password",
        json={"current_password": "Valid1Pass", "new_password": "NoDigitsHere"},
        headers=headers,
    )
    assert resp.status_code == 422
    assert "digit" in resp.json()["detail"].lower()


def test_change_password_requires_authentication(client: TestClient) -> None:
    resp = client.put(
        "/v1/auth/change-password",
        json={"current_password": "old", "new_password": "new"},
    )
    assert resp.status_code == 401


def test_change_password_trailing_slash(client: TestClient, auth_db: Path) -> None:
    user = _seed_user(auth_db, "grace", "OldPass123")
    headers = _auth_header(user)

    resp = client.put(
        "/v1/auth/change-password/",
        json={"current_password": "OldPass123", "new_password": "NewPass456"},
        headers=headers,
    )
    assert resp.status_code == 200


def test_change_password_viewer_can_change_own(client: TestClient, auth_db: Path) -> None:
    """Any authenticated user, including viewers, can change their own password."""
    user = _seed_user(auth_db, "viewer1", "OldPass123", role="viewer")
    headers = _auth_header(user)

    resp = client.put(
        "/v1/auth/change-password",
        json={"current_password": "OldPass123", "new_password": "NewPass456"},
        headers=headers,
    )
    assert resp.status_code == 200
