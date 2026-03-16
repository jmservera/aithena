from __future__ import annotations

from auth import AuthenticatedUser, create_access_token
from config import settings
from fastapi.testclient import TestClient
from main import app


def create_authenticated_client(user: AuthenticatedUser | None = None) -> TestClient:
    client = TestClient(app)
    auth_user = user or AuthenticatedUser(id=1, username="test-user", role="admin")
    token = create_access_token(auth_user, settings.auth_jwt_secret, settings.auth_jwt_ttl_seconds)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client
