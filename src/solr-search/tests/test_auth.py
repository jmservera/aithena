from __future__ import annotations

import os
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
import pytest

os.environ.setdefault("AUTH_DB_PATH", "/tmp/test-auth.db")  # noqa: S108
os.environ.setdefault("AUTH_JWT_SECRET", "test-auth-secret")
os.environ.setdefault("AUTH_JWT_TTL", "24h")
os.environ.setdefault("AUTH_COOKIE_NAME", "aithena_auth")

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from auth import AuthenticatedUser, create_access_token, hash_password, init_auth_db  # noqa: E402
from config import settings  # noqa: E402
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
    password_hash = hash_password("CorrectHorse1")
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
        json={"username": seeded_user.username, "password": "CorrectHorse1"},
    )

    assert response.status_code == 200
    data = response.json()
    claims = jwt.decode(data["access_token"], settings.auth_jwt_secret, algorithms=["HS256"])

    assert data["token_type"] == "bearer"  # noqa: S105
    assert data["user"] == {"id": seeded_user.id, "username": seeded_user.username, "role": seeded_user.role}
    assert data["expires_in"] == settings.auth_jwt_ttl_seconds
    assert response.cookies.get(settings.auth_cookie_name) == data["access_token"]
    assert claims["sub"] == seeded_user.username
    assert claims["user_id"] == seeded_user.id
    assert claims["role"] == seeded_user.role
    assert isinstance(claims["iat"], int)
    assert isinstance(claims["exp"], int)
    assert claims["exp"] - claims["iat"] == settings.auth_jwt_ttl_seconds


def test_login_rejects_invalid_credentials(client: TestClient, seeded_user: AuthenticatedUser) -> None:
    response = client.post(
        "/v1/auth/login",
        json={"username": seeded_user.username, "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_validate_rejects_invalid_token(client: TestClient) -> None:
    response = client.get("/v1/auth/validate", headers={"Authorization": "Bearer invalid-token"})

    assert response.status_code == 401


def test_validate_requires_authentication(client: TestClient) -> None:
    response = client.get("/v1/auth/validate")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


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


def test_me_accepts_cookie_auth(client: TestClient, seeded_user: AuthenticatedUser) -> None:
    token = create_access_token(seeded_user, settings.auth_jwt_secret, settings.auth_jwt_ttl_seconds)
    client.cookies.set(settings.auth_cookie_name, token)

    response = client.get("/v1/auth/me")

    assert response.status_code == 200
    assert response.json() == {"id": seeded_user.id, "username": seeded_user.username, "role": seeded_user.role}


def test_me_rejects_expired_token(client: TestClient, seeded_user: AuthenticatedUser) -> None:
    payload = {
        "sub": seeded_user.username,
        "user_id": seeded_user.id,
        "role": seeded_user.role,
        "iat": int((datetime.now(UTC) - timedelta(hours=2)).timestamp()),
        "exp": int((datetime.now(UTC) - timedelta(hours=1)).timestamp()),
    }
    token = jwt.encode(payload, settings.auth_jwt_secret, algorithm="HS256")

    response = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Token expired"}


def test_logout_clears_auth_cookie(client: TestClient, seeded_user: AuthenticatedUser) -> None:
    token = create_access_token(seeded_user, settings.auth_jwt_secret, settings.auth_jwt_ttl_seconds)

    response = client.post("/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert settings.auth_cookie_name in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"] or "expires=" in response.headers["set-cookie"].lower()


@pytest.mark.parametrize("path", ["/search", "/v1/search"])
def test_search_requires_authentication(client: TestClient, path: str) -> None:
    response = client.get(path, params={"q": "folklore"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_login_rate_limiting(client: TestClient, seeded_user: AuthenticatedUser) -> None:
    from main import login_rate_limiter

    original_max = login_rate_limiter.max_requests
    login_rate_limiter.max_requests = 2
    login_rate_limiter.requests.clear()
    try:
        for _ in range(2):
            client.post("/v1/auth/login", json={"username": "x", "password": "y"})
        response = client.post("/v1/auth/login", json={"username": "x", "password": "y"})
        assert response.status_code == 429
    finally:
        login_rate_limiter.max_requests = original_max
        login_rate_limiter.requests.clear()


def test_jwt_without_exp_is_rejected(client: TestClient, seeded_user: AuthenticatedUser) -> None:
    payload = {
        "sub": seeded_user.username,
        "user_id": seeded_user.id,
        "role": seeded_user.role,
        "iat": int(datetime.now(UTC).timestamp()),
    }
    token = jwt.encode(payload, settings.auth_jwt_secret, algorithm="HS256")

    response = client.get("/v1/auth/validate", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
