"""Security tests for Collections API — access control, input validation, injection prevention."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("AUTH_DB_PATH", "/tmp/test-auth.db")  # noqa: S108
os.environ.setdefault("AUTH_JWT_SECRET", "test-auth-secret")
os.environ.setdefault("AUTH_JWT_TTL", "24h")
os.environ.setdefault("AUTH_COOKIE_NAME", "aithena_auth")

sys.path.append(str(Path(__file__).resolve().parents[1]))

from auth import AuthenticatedUser, create_access_token, init_auth_db  # noqa: E402
from collections_service import (  # noqa: E402
    add_items,
    create_collection,
    get_collection,
    init_collections_db,
)
from config import settings  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

USER_A = AuthenticatedUser(id=10, username="alice", role="user")
USER_B = AuthenticatedUser(id=20, username="bob", role="user")
VIEWER = AuthenticatedUser(id=30, username="viewer", role="viewer")


def _auth_header(user: AuthenticatedUser) -> dict[str, str]:
    token = create_access_token(user, settings.auth_jwt_secret, settings.auth_jwt_ttl_seconds)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_db(tmp_path: Path):
    original = settings.auth_db_path
    db = tmp_path / "auth.db"
    object.__setattr__(settings, "auth_db_path", db)
    init_auth_db(db)
    yield db
    object.__setattr__(settings, "auth_db_path", original)


@pytest.fixture
def collections_db(tmp_path: Path):
    original = settings.collections_db_path
    db = tmp_path / "collections.db"
    object.__setattr__(settings, "collections_db_path", db)
    init_collections_db(db)
    yield db
    object.__setattr__(settings, "collections_db_path", original)


@pytest.fixture
def client(auth_db, collections_db) -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Access Control — Cross-user isolation
# ---------------------------------------------------------------------------


class TestCrossUserAccessControl:
    """Verify user B cannot access/modify/delete user A's collections."""

    def test_user_b_cannot_list_user_a_collections(self, client, collections_db):
        create_collection(collections_db, str(USER_A.id), "Alice Private", None)
        resp = client.get("/v1/collections", headers=_auth_header(USER_B))
        assert resp.status_code == 200  # noqa: S101
        assert resp.json() == []  # noqa: S101

    def test_user_b_cannot_get_user_a_collection(self, client, collections_db):
        col = create_collection(collections_db, str(USER_A.id), "Alice Books", None)
        resp = client.get(f"/v1/collections/{col['id']}", headers=_auth_header(USER_B))
        assert resp.status_code == 404  # noqa: S101

    def test_user_b_cannot_update_user_a_collection(self, client, collections_db):
        col = create_collection(collections_db, str(USER_A.id), "Alice Books", None)
        resp = client.put(
            f"/v1/collections/{col['id']}",
            json={"name": "Stolen"},
            headers=_auth_header(USER_B),
        )
        assert resp.status_code == 404  # noqa: S101
        # Verify name unchanged
        original = get_collection(collections_db, col["id"], str(USER_A.id))
        assert original["name"] == "Alice Books"  # noqa: S101

    def test_user_b_cannot_delete_user_a_collection(self, client, collections_db):
        col = create_collection(collections_db, str(USER_A.id), "Alice Books", None)
        resp = client.delete(f"/v1/collections/{col['id']}", headers=_auth_header(USER_B))
        assert resp.status_code == 404  # noqa: S101
        # Verify collection still exists
        assert get_collection(collections_db, col["id"], str(USER_A.id)) is not None  # noqa: S101

    def test_user_b_cannot_add_items_to_user_a_collection(self, client, collections_db):
        col = create_collection(collections_db, str(USER_A.id), "Alice Books", None)
        resp = client.post(
            f"/v1/collections/{col['id']}/items",
            json={"document_ids": ["doc-1"]},
            headers=_auth_header(USER_B),
        )
        assert resp.status_code == 404  # noqa: S101

    def test_user_b_cannot_reorder_user_a_items(self, client, collections_db):
        col = create_collection(collections_db, str(USER_A.id), "Alice Books", None)
        items = add_items(collections_db, col["id"], str(USER_A.id), ["doc-1", "doc-2"])
        resp = client.put(
            f"/v1/collections/{col['id']}/items/reorder",
            json={"item_ids": [items[1]["id"], items[0]["id"]]},
            headers=_auth_header(USER_B),
        )
        assert resp.status_code == 404  # noqa: S101

    def test_user_b_cannot_update_user_a_item(self, client, collections_db):
        col = create_collection(collections_db, str(USER_A.id), "Alice Books", None)
        items = add_items(collections_db, col["id"], str(USER_A.id), ["doc-1"])
        resp = client.put(
            f"/v1/collections/{col['id']}/items/{items[0]['id']}",
            json={"note": "hacked"},
            headers=_auth_header(USER_B),
        )
        assert resp.status_code == 404  # noqa: S101

    def test_user_b_cannot_delete_user_a_item(self, client, collections_db):
        col = create_collection(collections_db, str(USER_A.id), "Alice Books", None)
        items = add_items(collections_db, col["id"], str(USER_A.id), ["doc-1"])
        resp = client.delete(
            f"/v1/collections/{col['id']}/items/{items[0]['id']}",
            headers=_auth_header(USER_B),
        )
        assert resp.status_code == 404  # noqa: S101


class TestUnauthenticatedAccess:
    """Verify unauthenticated requests are rejected."""

    def test_no_token_returns_401(self, client, collections_db):
        resp = client.get("/v1/collections")
        assert resp.status_code == 401  # noqa: S101

    def test_invalid_token_returns_401(self, client, collections_db):
        resp = client.get("/v1/collections", headers={"Authorization": "Bearer invalid.jwt.token"})
        assert resp.status_code == 401  # noqa: S101

    def test_expired_token_returns_401(self, client, collections_db):
        from datetime import UTC, datetime, timedelta

        user = AuthenticatedUser(id=1, username="expired-user", role="user")
        past = datetime.now(UTC) - timedelta(hours=25)
        token = create_access_token(user, settings.auth_jwt_secret, 1, now=past)
        resp = client.get("/v1/collections", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401  # noqa: S101


class TestCollectionNotFoundHandling:
    """Verify non-existent collections return 404 (no information leakage)."""

    def test_get_nonexistent_collection(self, client, collections_db):
        resp = client.get("/v1/collections/nonexistent-uuid", headers=_auth_header(USER_A))
        assert resp.status_code == 404  # noqa: S101

    def test_update_nonexistent_collection(self, client, collections_db):
        resp = client.put(
            "/v1/collections/nonexistent-uuid",
            json={"name": "Test"},
            headers=_auth_header(USER_A),
        )
        assert resp.status_code == 404  # noqa: S101

    def test_delete_nonexistent_collection(self, client, collections_db):
        resp = client.delete("/v1/collections/nonexistent-uuid", headers=_auth_header(USER_A))
        assert resp.status_code == 404  # noqa: S101


# ---------------------------------------------------------------------------
# Input Validation — Boundary conditions
# ---------------------------------------------------------------------------


class TestCollectionNameValidation:
    """Validate collection name: 1-255 chars, non-empty after trim."""

    def test_empty_name_rejected(self, client, collections_db):
        resp = client.post(
            "/v1/collections", json={"name": ""}, headers=_auth_header(USER_A)
        )
        assert resp.status_code == 422  # noqa: S101

    def test_name_max_length_255_accepted(self, client, collections_db):
        resp = client.post(
            "/v1/collections",
            json={"name": "A" * 255},
            headers=_auth_header(USER_A),
        )
        assert resp.status_code == 201  # noqa: S101

    def test_name_over_255_rejected(self, client, collections_db):
        resp = client.post(
            "/v1/collections",
            json={"name": "A" * 256},
            headers=_auth_header(USER_A),
        )
        assert resp.status_code == 422  # noqa: S101


class TestDescriptionValidation:
    """Validate description: ≤1000 chars."""

    def test_description_max_1000_accepted(self, client, collections_db):
        resp = client.post(
            "/v1/collections",
            json={"name": "Test", "description": "D" * 1000},
            headers=_auth_header(USER_A),
        )
        assert resp.status_code == 201  # noqa: S101

    def test_description_over_1000_rejected(self, client, collections_db):
        resp = client.post(
            "/v1/collections",
            json={"name": "Test", "description": "D" * 1001},
            headers=_auth_header(USER_A),
        )
        assert resp.status_code == 422  # noqa: S101


class TestNoteValidation:
    """Validate item note length constraints."""

    def test_note_at_max_length_accepted(self, client, collections_db):
        col = create_collection(collections_db, str(USER_A.id), "Test", None)
        items = add_items(collections_db, col["id"], str(USER_A.id), ["doc-1"])
        max_len = settings.collections_note_max_length
        resp = client.put(
            f"/v1/collections/{col['id']}/items/{items[0]['id']}",
            json={"note": "N" * max_len},
            headers=_auth_header(USER_A),
        )
        assert resp.status_code == 200  # noqa: S101

    def test_note_over_max_length_rejected(self, client, collections_db):
        col = create_collection(collections_db, str(USER_A.id), "Test", None)
        items = add_items(collections_db, col["id"], str(USER_A.id), ["doc-1"])
        max_len = settings.collections_note_max_length
        resp = client.put(
            f"/v1/collections/{col['id']}/items/{items[0]['id']}",
            json={"note": "N" * (max_len + 1)},
            headers=_auth_header(USER_A),
        )
        assert resp.status_code == 422  # noqa: S101


class TestPositionValidation:
    """Validate item position is non-negative integer."""

    def test_position_zero_accepted(self, client, collections_db):
        col = create_collection(collections_db, str(USER_A.id), "Test", None)
        items = add_items(collections_db, col["id"], str(USER_A.id), ["doc-1"])
        resp = client.put(
            f"/v1/collections/{col['id']}/items/{items[0]['id']}",
            json={"position": 0},
            headers=_auth_header(USER_A),
        )
        assert resp.status_code == 200  # noqa: S101

    def test_positive_position_accepted(self, client, collections_db):
        col = create_collection(collections_db, str(USER_A.id), "Test", None)
        items = add_items(collections_db, col["id"], str(USER_A.id), ["doc-1"])
        resp = client.put(
            f"/v1/collections/{col['id']}/items/{items[0]['id']}",
            json={"position": 42},
            headers=_auth_header(USER_A),
        )
        assert resp.status_code == 200  # noqa: S101

    def test_negative_position_rejected(self, client, collections_db):
        col = create_collection(collections_db, str(USER_A.id), "Test", None)
        items = add_items(collections_db, col["id"], str(USER_A.id), ["doc-1"])
        resp = client.put(
            f"/v1/collections/{col['id']}/items/{items[0]['id']}",
            json={"position": -1},
            headers=_auth_header(USER_A),
        )
        assert resp.status_code == 422  # noqa: S101


class TestBulkOperationLimits:
    """Validate bulk operation size limits."""

    def test_add_items_max_50_accepted(self, client, collections_db):
        col = create_collection(collections_db, str(USER_A.id), "Test", None)
        doc_ids = [f"doc-{i}" for i in range(50)]
        resp = client.post(
            f"/v1/collections/{col['id']}/items",
            json={"document_ids": doc_ids},
            headers=_auth_header(USER_A),
        )
        assert resp.status_code == 201  # noqa: S101

    def test_add_items_over_50_rejected(self, client, collections_db):
        col = create_collection(collections_db, str(USER_A.id), "Test", None)
        doc_ids = [f"doc-{i}" for i in range(51)]
        resp = client.post(
            f"/v1/collections/{col['id']}/items",
            json={"document_ids": doc_ids},
            headers=_auth_header(USER_A),
        )
        assert resp.status_code == 422  # noqa: S101

    def test_add_items_empty_list_rejected(self, client, collections_db):
        col = create_collection(collections_db, str(USER_A.id), "Test", None)
        resp = client.post(
            f"/v1/collections/{col['id']}/items",
            json={"document_ids": []},
            headers=_auth_header(USER_A),
        )
        assert resp.status_code == 422  # noqa: S101

    def test_reorder_over_50_rejected(self, client, collections_db):
        col = create_collection(collections_db, str(USER_A.id), "Test", None)
        item_ids = [f"fake-item-{i}" for i in range(51)]
        resp = client.put(
            f"/v1/collections/{col['id']}/items/reorder",
            json={"item_ids": item_ids},
            headers=_auth_header(USER_A),
        )
        assert resp.status_code == 422  # noqa: S101


# ---------------------------------------------------------------------------
# SQL Injection Prevention
# ---------------------------------------------------------------------------


class TestSQLInjectionPrevention:
    """Verify SQL injection payloads are safely handled via parameterized queries."""

    PAYLOADS = [
        "'; DROP TABLE collections; --",
        "' OR '1'='1",
        "' UNION SELECT * FROM users --",
        "Robert'); DROP TABLE collections;--",
        "1; DELETE FROM collections WHERE 1=1",
    ]

    def test_sql_injection_in_collection_name(self, client, collections_db):
        for payload in self.PAYLOADS:
            resp = client.post(
                "/v1/collections",
                json={"name": payload},
                headers=_auth_header(USER_A),
            )
            assert resp.status_code == 201  # noqa: S101
        # Verify all collections exist (SQL wasn't executed)
        resp = client.get("/v1/collections", headers=_auth_header(USER_A))
        assert len(resp.json()) == len(self.PAYLOADS)  # noqa: S101

    def test_sql_injection_in_description(self, client, collections_db):
        payload = "'; DROP TABLE collections; --"
        resp = client.post(
            "/v1/collections",
            json={"name": "Normal Name", "description": payload},
            headers=_auth_header(USER_A),
        )
        assert resp.status_code == 201  # noqa: S101
        data = resp.json()
        assert data["description"] == payload  # noqa: S101

    def test_sql_injection_in_note(self, client, collections_db):
        col = create_collection(collections_db, str(USER_A.id), "Test", None)
        items = add_items(collections_db, col["id"], str(USER_A.id), ["doc-1"])
        payload = "'; DELETE FROM collection_items; --"
        resp = client.put(
            f"/v1/collections/{col['id']}/items/{items[0]['id']}",
            json={"note": payload},
            headers=_auth_header(USER_A),
        )
        assert resp.status_code == 200  # noqa: S101
        assert resp.json()["note"] == payload  # noqa: S101

    def test_sql_injection_in_document_id(self, client, collections_db):
        col = create_collection(collections_db, str(USER_A.id), "Test", None)
        payload = "doc-1'; DROP TABLE collections; --"
        resp = client.post(
            f"/v1/collections/{col['id']}/items",
            json={"document_ids": [payload]},
            headers=_auth_header(USER_A),
        )
        assert resp.status_code == 201  # noqa: S101

    def test_sql_injection_in_collection_id_path(self, client, collections_db):
        payload = "' OR '1'='1"
        resp = client.get(
            f"/v1/collections/{payload}",
            headers=_auth_header(USER_A),
        )
        assert resp.status_code == 404  # noqa: S101


# ---------------------------------------------------------------------------
# Service-layer: ownership boundary in cascading deletes
# ---------------------------------------------------------------------------


class TestCascadingDeleteOwnership:
    """Verify cascading deletes respect ownership boundaries."""

    def test_delete_collection_cascades_items(self, client, collections_db):
        col = create_collection(collections_db, str(USER_A.id), "ToDelete", None)
        add_items(collections_db, col["id"], str(USER_A.id), ["doc-1", "doc-2"])
        resp = client.delete(f"/v1/collections/{col['id']}", headers=_auth_header(USER_A))
        assert resp.status_code == 204  # noqa: S101
        # Items should be gone
        assert get_collection(collections_db, col["id"], str(USER_A.id)) is None  # noqa: S101

    def test_delete_does_not_affect_other_users(self, client, collections_db):
        col_a = create_collection(collections_db, str(USER_A.id), "Alice Col", None)
        col_b = create_collection(collections_db, str(USER_B.id), "Bob Col", None)
        add_items(collections_db, col_a["id"], str(USER_A.id), ["doc-1"])
        add_items(collections_db, col_b["id"], str(USER_B.id), ["doc-2"])

        # Delete Alice's collection
        client.delete(f"/v1/collections/{col_a['id']}", headers=_auth_header(USER_A))

        # Bob's collection should be intact
        bob_col = get_collection(collections_db, col_b["id"], str(USER_B.id))
        assert bob_col is not None  # noqa: S101
        assert len(bob_col["items"]) == 1  # noqa: S101
