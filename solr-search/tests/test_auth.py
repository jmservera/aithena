from __future__ import annotations

import os
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from jose import jwt

os.environ.setdefault("AUTH_DB_PATH", "/tmp/test-auth.db")
os.environ.setdefault("AUTH_JWT_SECRET", "test-auth-secret")
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


@pytest.fixture
def seeded_user(auth_db: Path) -> AuthenticatedUser:
    password_hash = hash_password("correct-horse-battery-staple")
    created_at = datetime.now(UTC).isoformat()
    with sqlite3.connect(auth_db) as connection:
        connection.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            ("parker", password_hash, "admin", created_at),
        )
        user_id = connection.execute("SELECT id FROM users WHERE username = ?", ("parker",)).fetchone()[0]
        connection.commit()
    return AuthenticatedUser(id=user_id, username="parker", role="admin")


def test_login_returns_jwt_and_sets_cookie(client: TestClient, seeded_user: AuthenticatedUser) -> None:
    response = client.post(
        "/v1/auth/login",
        json={"username": seeded_user.username, "password": "correct-horse-battery-staple"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["user"] == {"id": seeded_user.id, "username": seeded_user.username, "role": seeded_user.role}
    assert data["expires_in"] == settings.auth_jwt_ttl_seconds
    assert response.cookies.get(settings.auth_cookie_name) == data["access_token"]


def test_login_rejects_invalid_credentials(client: TestClient, seeded_user: AuthenticatedUser) -> None:
    response = client.post(
        "/v1/auth/login",
        json={"username": seeded_user.username, "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_validate_rejects_invalid_token(client: TestClient) -> None:
    response = client.get("/v1/auth/validate", headers={"Authorization": "Bearer invalid-token"})

    assert response.status_code == 401


def test_validate_rejects_expired_token(client: TestClient, seeded_user: AuthenticatedUser) -> None:
    payload = {
        "sub": seeded_user.username,
        "user_id": seeded_user.id,
        "role": seeded_user.role,
        "iat": int((datetime.now(UTC) - timedelta(hours=2)).timestamp()),
        "exp": int((datetime.now(UTC) - timedelta(hours=1)).timestamp()),
    }
    token = jwt.encode(payload, settings.auth_jwt_secret, algorithm="HS256")

    response = client.get("/v1/auth/validate", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_validate_accepts_bearer_header(client: TestClient, seeded_user: AuthenticatedUser) -> None:
    token = create_access_token(seeded_user, settings.auth_jwt_secret, settings.auth_jwt_ttl_seconds)

    response = client.get("/v1/auth/validate", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["user"] == {"id": seeded_user.id, "username": seeded_user.username, "role": seeded_user.role}


def test_validate_accepts_cookie_auth(client: TestClient, seeded_user: AuthenticatedUser) -> None:
    token = create_access_token(seeded_user, settings.auth_jwt_secret, settings.auth_jwt_ttl_seconds)
    client.cookies.set(settings.auth_cookie_name, token)

    response = client.get("/v1/auth/validate")

    assert response.status_code == 200
    assert response.json()["authenticated"] is True


def test_me_returns_current_user_info(client: TestClient, seeded_user: AuthenticatedUser) -> None:
    token = create_access_token(seeded_user, settings.auth_jwt_secret, settings.auth_jwt_ttl_seconds)

    response = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"id": seeded_user.id, "username": seeded_user.username, "role": seeded_user.role}


def test_logout_clears_auth_cookie(client: TestClient, seeded_user: AuthenticatedUser) -> None:
    token = create_access_token(seeded_user, settings.auth_jwt_secret, settings.auth_jwt_ttl_seconds)

    response = client.post("/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert settings.auth_cookie_name in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"] or "expires=" in response.headers["set-cookie"].lower()


def test_search_requires_authentication() -> None:
    client = TestClient(app)
    response = client.get("/search", params={"q": "folklore"})

    assert response.status_code == 401
