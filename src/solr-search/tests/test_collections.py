"""Tests for Collections CRUD API endpoints and service layer."""

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
    delete_collection,
    get_collection,
    init_collections_db,
    list_collections,
    remove_item,
    reorder_items,
    update_collection,
    update_item,
)
from config import settings  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

ADMIN_USER = AuthenticatedUser(id=1, username="test-admin", role="admin")
USER_A = AuthenticatedUser(id=10, username="alice", role="user")
USER_B = AuthenticatedUser(id=20, username="bob", role="user")


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
# Service-layer tests
# ---------------------------------------------------------------------------


class TestCollectionsService:
    def test_create_and_get(self, collections_db):
        result = create_collection(collections_db, "10", "My Books", "My favourite reads")
        assert result["name"] == "My Books"
        assert result["description"] == "My favourite reads"
        assert result["user_id"] == "10"
        assert result["item_count"] == 0
        assert result["id"]

        detail = get_collection(collections_db, result["id"], "10")
        assert detail is not None
        assert detail["name"] == "My Books"
        assert detail["items"] == []

    def test_list_collections(self, collections_db):
        create_collection(collections_db, "10", "Col A", None)
        create_collection(collections_db, "10", "Col B", None)
        create_collection(collections_db, "20", "Col C", None)

        cols = list_collections(collections_db, "10")
        assert len(cols) == 2
        assert all(c["user_id"] == "10" for c in cols)

    def test_update_collection(self, collections_db):
        col = create_collection(collections_db, "10", "Original", "Desc")
        updated = update_collection(collections_db, col["id"], "10", name="Renamed")
        assert updated is not None
        assert updated["name"] == "Renamed"

    def test_delete_collection(self, collections_db):
        col = create_collection(collections_db, "10", "ToDelete", None)
        assert delete_collection(collections_db, col["id"], "10") is True
        assert get_collection(collections_db, col["id"], "10") is None

    def test_other_user_cannot_access(self, collections_db):
        col = create_collection(collections_db, "10", "Private", None)
        assert get_collection(collections_db, col["id"], "20") is None
        assert update_collection(collections_db, col["id"], "20", name="Hack") is None
        assert delete_collection(collections_db, col["id"], "20") is False

    def test_add_items(self, collections_db):
        col = create_collection(collections_db, "10", "Books", None)
        added = add_items(collections_db, col["id"], "10", ["doc1", "doc2", "doc3"])
        assert len(added) == 3
        assert added[0]["position"] == 1
        assert added[2]["position"] == 3

    def test_add_items_skip_duplicates(self, collections_db):
        col = create_collection(collections_db, "10", "Books", None)
        add_items(collections_db, col["id"], "10", ["doc1", "doc2"])
        added = add_items(collections_db, col["id"], "10", ["doc2", "doc3"])
        assert len(added) == 1
        assert added[0]["document_id"] == "doc3"

    def test_add_items_other_user(self, collections_db):
        col = create_collection(collections_db, "10", "Books", None)
        added = add_items(collections_db, col["id"], "20", ["doc1"])
        assert added == []

    def test_remove_item(self, collections_db):
        col = create_collection(collections_db, "10", "Books", None)
        added = add_items(collections_db, col["id"], "10", ["doc1"])
        assert remove_item(collections_db, col["id"], "10", added[0]["id"]) is True
        detail = get_collection(collections_db, col["id"], "10")
        assert len(detail["items"]) == 0

    def test_remove_item_not_found(self, collections_db):
        col = create_collection(collections_db, "10", "Books", None)
        assert remove_item(collections_db, col["id"], "10", "nonexistent") is False

    def test_remove_item_other_user(self, collections_db):
        col = create_collection(collections_db, "10", "Books", None)
        added = add_items(collections_db, col["id"], "10", ["doc1"])
        assert remove_item(collections_db, col["id"], "20", added[0]["id"]) is False

    def test_update_item_note(self, collections_db):
        col = create_collection(collections_db, "10", "Books", None)
        added = add_items(collections_db, col["id"], "10", ["doc1"])
        result = update_item(collections_db, col["id"], "10", added[0]["id"], note="Great book!")
        assert result is not None
        assert result["note"] == "Great book!"

    def test_update_item_position(self, collections_db):
        col = create_collection(collections_db, "10", "Books", None)
        added = add_items(collections_db, col["id"], "10", ["doc1"])
        result = update_item(collections_db, col["id"], "10", added[0]["id"], position=5)
        assert result is not None
        assert result["position"] == 5

    def test_update_item_not_found(self, collections_db):
        col = create_collection(collections_db, "10", "Books", None)
        assert update_item(collections_db, col["id"], "10", "nonexistent", note="x") is None

    def test_update_item_other_user(self, collections_db):
        col = create_collection(collections_db, "10", "Books", None)
        added = add_items(collections_db, col["id"], "10", ["doc1"])
        assert update_item(collections_db, col["id"], "20", added[0]["id"], note="hack") is None

    def test_update_item_note_too_long(self, collections_db):
        col = create_collection(collections_db, "10", "Books", None)
        added = add_items(collections_db, col["id"], "10", ["doc1"])
        with pytest.raises(ValueError, match="exceeds maximum length"):
            update_item(collections_db, col["id"], "10", added[0]["id"], note="x" * 1001, note_max_length=1000)

    def test_reorder_items(self, collections_db):
        col = create_collection(collections_db, "10", "Books", None)
        added = add_items(collections_db, col["id"], "10", ["doc1", "doc2", "doc3"])
        ids = [a["id"] for a in added]
        assert reorder_items(collections_db, col["id"], "10", list(reversed(ids))) is True

        detail = get_collection(collections_db, col["id"], "10")
        positions = {item["id"]: item["position"] for item in detail["items"]}
        assert positions[ids[2]] == 1
        assert positions[ids[1]] == 2
        assert positions[ids[0]] == 3

    def test_reorder_items_other_user(self, collections_db):
        col = create_collection(collections_db, "10", "Books", None)
        added = add_items(collections_db, col["id"], "10", ["doc1"])
        assert reorder_items(collections_db, col["id"], "20", [added[0]["id"]]) is False

    def test_cascade_delete(self, collections_db):
        col = create_collection(collections_db, "10", "Books", None)
        add_items(collections_db, col["id"], "10", ["doc1", "doc2"])
        assert delete_collection(collections_db, col["id"], "10") is True
        assert get_collection(collections_db, col["id"], "10") is None

    def test_update_collection_no_changes(self, collections_db):
        col = create_collection(collections_db, "10", "Books", "desc")
        updated = update_collection(collections_db, col["id"], "10")
        assert updated is not None
        assert updated["name"] == "Books"

    def test_delete_nonexistent(self, collections_db):
        assert delete_collection(collections_db, "no-such-id", "10") is False

    def test_update_nonexistent(self, collections_db):
        assert update_collection(collections_db, "no-such-id", "10", name="x") is None


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestCollectionsAPI:
    def test_create_collection(self, client):
        resp = client.post("/v1/collections", json={"name": "Favourites"}, headers=_auth_header(USER_A))
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Favourites"
        assert data["user_id"] == str(USER_A.id)
        assert data["item_count"] == 0

    def test_create_collection_with_description(self, client):
        resp = client.post(
            "/v1/collections",
            json={"name": "Sci-Fi", "description": "Science fiction picks"},
            headers=_auth_header(USER_A),
        )
        assert resp.status_code == 201
        assert resp.json()["description"] == "Science fiction picks"

    def test_create_collection_name_too_short(self, client):
        resp = client.post("/v1/collections", json={"name": ""}, headers=_auth_header(USER_A))
        assert resp.status_code == 422

    def test_create_collection_name_too_long(self, client):
        resp = client.post("/v1/collections", json={"name": "x" * 256}, headers=_auth_header(USER_A))
        assert resp.status_code == 422

    def test_create_collection_description_too_long(self, client):
        resp = client.post(
            "/v1/collections", json={"name": "Ok", "description": "x" * 1001}, headers=_auth_header(USER_A)
        )
        assert resp.status_code == 422

    def test_list_collections(self, client):
        client.post("/v1/collections", json={"name": "A"}, headers=_auth_header(USER_A))
        client.post("/v1/collections", json={"name": "B"}, headers=_auth_header(USER_A))
        client.post("/v1/collections", json={"name": "C"}, headers=_auth_header(USER_B))

        resp = client.get("/v1/collections", headers=_auth_header(USER_A))
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_collection(self, client):
        create = client.post("/v1/collections", json={"name": "Mine"}, headers=_auth_header(USER_A))
        col_id = create.json()["id"]

        resp = client.get(f"/v1/collections/{col_id}", headers=_auth_header(USER_A))
        assert resp.status_code == 200
        assert resp.json()["name"] == "Mine"
        assert resp.json()["items"] == []

    def test_get_other_users_collection_returns_404(self, client):
        create = client.post("/v1/collections", json={"name": "Secret"}, headers=_auth_header(USER_A))
        col_id = create.json()["id"]

        resp = client.get(f"/v1/collections/{col_id}", headers=_auth_header(USER_B))
        assert resp.status_code == 404

    def test_update_collection(self, client):
        create = client.post("/v1/collections", json={"name": "Old"}, headers=_auth_header(USER_A))
        col_id = create.json()["id"]

        resp = client.put(f"/v1/collections/{col_id}", json={"name": "New"}, headers=_auth_header(USER_A))
        assert resp.status_code == 200
        assert resp.json()["name"] == "New"

    def test_update_collection_no_fields(self, client):
        create = client.post("/v1/collections", json={"name": "X"}, headers=_auth_header(USER_A))
        col_id = create.json()["id"]
        resp = client.put(f"/v1/collections/{col_id}", json={}, headers=_auth_header(USER_A))
        assert resp.status_code == 422

    def test_update_other_users_collection_returns_404(self, client):
        create = client.post("/v1/collections", json={"name": "X"}, headers=_auth_header(USER_A))
        col_id = create.json()["id"]
        resp = client.put(f"/v1/collections/{col_id}", json={"name": "Hacked"}, headers=_auth_header(USER_B))
        assert resp.status_code == 404

    def test_delete_collection(self, client):
        create = client.post("/v1/collections", json={"name": "ToDelete"}, headers=_auth_header(USER_A))
        col_id = create.json()["id"]

        resp = client.delete(f"/v1/collections/{col_id}", headers=_auth_header(USER_A))
        assert resp.status_code == 204

        resp = client.get(f"/v1/collections/{col_id}", headers=_auth_header(USER_A))
        assert resp.status_code == 404

    def test_delete_other_users_collection_returns_404(self, client):
        create = client.post("/v1/collections", json={"name": "X"}, headers=_auth_header(USER_A))
        col_id = create.json()["id"]
        resp = client.delete(f"/v1/collections/{col_id}", headers=_auth_header(USER_B))
        assert resp.status_code == 404

    def test_add_items(self, client):
        create = client.post("/v1/collections", json={"name": "Books"}, headers=_auth_header(USER_A))
        col_id = create.json()["id"]

        resp = client.post(
            f"/v1/collections/{col_id}/items",
            json={"document_ids": ["doc1", "doc2"]},
            headers=_auth_header(USER_A),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["added_count"] == 2

    def test_add_items_skip_duplicates(self, client):
        create = client.post("/v1/collections", json={"name": "Books"}, headers=_auth_header(USER_A))
        col_id = create.json()["id"]

        client.post(
            f"/v1/collections/{col_id}/items", json={"document_ids": ["doc1"]}, headers=_auth_header(USER_A)
        )
        resp = client.post(
            f"/v1/collections/{col_id}/items",
            json={"document_ids": ["doc1", "doc2"]},
            headers=_auth_header(USER_A),
        )
        assert resp.status_code == 201
        assert resp.json()["added_count"] == 1

    def test_add_items_to_other_users_collection(self, client):
        create = client.post("/v1/collections", json={"name": "X"}, headers=_auth_header(USER_A))
        col_id = create.json()["id"]
        resp = client.post(
            f"/v1/collections/{col_id}/items", json={"document_ids": ["doc1"]}, headers=_auth_header(USER_B)
        )
        assert resp.status_code == 404

    def test_add_items_empty_list(self, client):
        create = client.post("/v1/collections", json={"name": "Books"}, headers=_auth_header(USER_A))
        col_id = create.json()["id"]
        resp = client.post(
            f"/v1/collections/{col_id}/items", json={"document_ids": []}, headers=_auth_header(USER_A)
        )
        assert resp.status_code == 422

    def test_add_items_too_many(self, client):
        create = client.post("/v1/collections", json={"name": "Books"}, headers=_auth_header(USER_A))
        col_id = create.json()["id"]
        resp = client.post(
            f"/v1/collections/{col_id}/items",
            json={"document_ids": [f"doc{i}" for i in range(51)]},
            headers=_auth_header(USER_A),
        )
        assert resp.status_code == 422

    def test_remove_item(self, client):
        create = client.post("/v1/collections", json={"name": "Books"}, headers=_auth_header(USER_A))
        col_id = create.json()["id"]
        add_resp = client.post(
            f"/v1/collections/{col_id}/items", json={"document_ids": ["doc1"]}, headers=_auth_header(USER_A)
        )
        item_id = add_resp.json()["added"][0]["id"]

        resp = client.delete(f"/v1/collections/{col_id}/items/{item_id}", headers=_auth_header(USER_A))
        assert resp.status_code == 204

    def test_remove_item_not_found(self, client):
        create = client.post("/v1/collections", json={"name": "Books"}, headers=_auth_header(USER_A))
        col_id = create.json()["id"]
        resp = client.delete(f"/v1/collections/{col_id}/items/nonexistent", headers=_auth_header(USER_A))
        assert resp.status_code == 404

    def test_update_item(self, client):
        create = client.post("/v1/collections", json={"name": "Books"}, headers=_auth_header(USER_A))
        col_id = create.json()["id"]
        add_resp = client.post(
            f"/v1/collections/{col_id}/items", json={"document_ids": ["doc1"]}, headers=_auth_header(USER_A)
        )
        item_id = add_resp.json()["added"][0]["id"]

        resp = client.put(
            f"/v1/collections/{col_id}/items/{item_id}",
            json={"note": "Amazing read"},
            headers=_auth_header(USER_A),
        )
        assert resp.status_code == 200
        assert resp.json()["note"] == "Amazing read"

    def test_update_item_note_too_long(self, client):
        create = client.post("/v1/collections", json={"name": "Books"}, headers=_auth_header(USER_A))
        col_id = create.json()["id"]
        add_resp = client.post(
            f"/v1/collections/{col_id}/items", json={"document_ids": ["doc1"]}, headers=_auth_header(USER_A)
        )
        item_id = add_resp.json()["added"][0]["id"]

        resp = client.put(
            f"/v1/collections/{col_id}/items/{item_id}",
            json={"note": "x" * 1001},
            headers=_auth_header(USER_A),
        )
        assert resp.status_code == 422

    def test_update_item_not_found(self, client):
        create = client.post("/v1/collections", json={"name": "Books"}, headers=_auth_header(USER_A))
        col_id = create.json()["id"]
        resp = client.put(
            f"/v1/collections/{col_id}/items/nonexistent", json={"note": "x"}, headers=_auth_header(USER_A)
        )
        assert resp.status_code == 404

    def test_reorder_items(self, client):
        create = client.post("/v1/collections", json={"name": "Books"}, headers=_auth_header(USER_A))
        col_id = create.json()["id"]
        add_resp = client.post(
            f"/v1/collections/{col_id}/items",
            json={"document_ids": ["doc1", "doc2", "doc3"]},
            headers=_auth_header(USER_A),
        )
        items = add_resp.json()["added"]
        ids = [i["id"] for i in items]

        resp = client.put(
            f"/v1/collections/{col_id}/items/reorder",
            json={"item_ids": list(reversed(ids))},
            headers=_auth_header(USER_A),
        )
        assert resp.status_code == 200

        detail = client.get(f"/v1/collections/{col_id}", headers=_auth_header(USER_A)).json()
        positions = {item["id"]: item["position"] for item in detail["items"]}
        assert positions[ids[2]] == 1

    def test_reorder_other_users_collection(self, client):
        create = client.post("/v1/collections", json={"name": "X"}, headers=_auth_header(USER_A))
        col_id = create.json()["id"]
        resp = client.put(
            f"/v1/collections/{col_id}/items/reorder",
            json={"item_ids": ["x"]},
            headers=_auth_header(USER_B),
        )
        assert resp.status_code == 404

    def test_unauthenticated_returns_401(self):
        client = TestClient(app)
        resp = client.get("/v1/collections")
        assert resp.status_code == 401

    def test_nonexistent_collection_returns_404(self, client):
        resp = client.get("/v1/collections/no-such-id", headers=_auth_header(USER_A))
        assert resp.status_code == 404

    def test_delete_nonexistent_collection_returns_404(self, client):
        resp = client.delete("/v1/collections/no-such-id", headers=_auth_header(USER_A))
        assert resp.status_code == 404

    def test_add_items_to_nonexistent_collection(self, client):
        resp = client.post(
            "/v1/collections/no-such-id/items",
            json={"document_ids": ["doc1"]},
            headers=_auth_header(USER_A),
        )
        assert resp.status_code == 404

    def test_reorder_nonexistent_collection(self, client):
        resp = client.put(
            "/v1/collections/no-such-id/items/reorder",
            json={"item_ids": ["x"]},
            headers=_auth_header(USER_A),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Migration tests
# ---------------------------------------------------------------------------


class TestCollectionsMigration:
    def test_init_creates_tables(self, collections_db):
        import sqlite3

        with sqlite3.connect(collections_db) as conn:
            tables = {
                r[0]
                for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }
        assert "collections" in tables
        assert "collection_items" in tables

    def test_init_idempotent(self, tmp_path):
        db = tmp_path / "coll.db"
        init_collections_db(db)
        init_collections_db(db)  # should not raise
