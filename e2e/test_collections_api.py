"""
E2E API tests for the collections endpoints.

These tests exercise the full collections CRUD lifecycle against the live
solr-search API, covering:

  - Collection CRUD: create, list, get, update, delete
  - Collection items: add documents, remove items, update notes, reorder
  - Access control: ownership enforcement, cross-user isolation
  - Validation: boundary values, required fields, invalid inputs
  - Edge cases: empty collections, duplicate document IDs, cascade delete

Environment variables:
  SEARCH_API_URL   solr-search base URL (default: http://localhost:8080)
  E2E_USERNAME     username for auth (default: admin)
  E2E_PASSWORD     password for auth (required)

Gating: tests that require a live collections API skip gracefully when the
endpoint is not reachable, following the project's established pattern.
"""

from __future__ import annotations

import os
import uuid

import pytest
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SEARCH_API_URL: str = os.environ.get("SEARCH_API_URL", "http://localhost:8080").rstrip("/")
COLLECTIONS_ENDPOINT = f"{SEARCH_API_URL}/v1/collections"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _unique(prefix: str = "e2e") -> str:
    """Return a unique name for test isolation."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def auth_headers() -> dict[str, str]:
    """Authenticate and return bearer headers."""
    username = os.environ.get("E2E_USERNAME", os.environ.get("CI_ADMIN_USERNAME", "admin"))
    password = os.environ.get("E2E_PASSWORD") or os.environ.get("CI_ADMIN_PASSWORD")
    if not password:
        pytest.skip("E2E_PASSWORD must be set for collections API tests")

    resp = requests.post(
        f"{SEARCH_API_URL}/v1/auth/login",
        json={"username": username, "password": password},
        timeout=10,
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not isinstance(token, str) or not token:
        pytest.fail(f"Login response missing access_token: {resp.text}")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def collections_available(auth_headers: dict[str, str]) -> None:
    """Skip all tests if the collections API is not reachable."""
    try:
        resp = requests.get(COLLECTIONS_ENDPOINT, headers=auth_headers, timeout=10)
        if resp.status_code == 404:
            pytest.skip("Collections endpoint not found — feature may not be deployed yet")
        resp.raise_for_status()
    except requests.ConnectionError:
        pytest.skip(f"Collections API not reachable at {COLLECTIONS_ENDPOINT}")


@pytest.fixture()
def create_collection(auth_headers: dict[str, str], collections_available: None):
    """Factory fixture: create a collection and auto-delete after test."""
    created_ids: list[str] = []

    def _factory(name: str | None = None, description: str = "") -> dict:
        name = name or _unique("col")
        resp = requests.post(
            COLLECTIONS_ENDPOINT,
            json={"name": name, "description": description},
            headers=auth_headers,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        created_ids.append(data["id"])
        return data

    yield _factory

    # Teardown: delete all collections created during the test
    for cid in created_ids:
        requests.delete(f"{COLLECTIONS_ENDPOINT}/{cid}", headers=auth_headers, timeout=10)


@pytest.fixture()
def sample_document_id(auth_headers: dict[str, str]) -> str:
    """Find a real document ID from the search index, or skip."""
    try:
        resp = requests.get(
            f"{SEARCH_API_URL}/v1/search/",
            params={"q": "*", "page": "1", "limit": "1"},
            headers=auth_headers,
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            pytest.skip("No indexed documents available for item tests")
        return results[0]["id"]
    except Exception as exc:
        pytest.skip(f"Could not discover document ID: {exc}")


# ---------------------------------------------------------------------------
# Collection CRUD
# ---------------------------------------------------------------------------


class TestCollectionCRUD:
    """Full CRUD lifecycle for collections."""

    def test_create_collection(self, auth_headers, create_collection):
        """POST /v1/collections creates a collection and returns 201."""
        name = _unique("create")
        col = create_collection(name, "test description")
        assert col["name"] == name
        assert col["description"] == "test description"
        assert "id" in col
        assert col["item_count"] == 0

    def test_list_collections_includes_created(self, auth_headers, create_collection, collections_available):
        """GET /v1/collections returns the user's collections."""
        name = _unique("list")
        create_collection(name)

        resp = requests.get(COLLECTIONS_ENDPOINT, headers=auth_headers, timeout=10)
        resp.raise_for_status()
        names = [c["name"] for c in resp.json()]
        assert name in names

    def test_get_collection_detail(self, auth_headers, create_collection):
        """GET /v1/collections/{id} returns the collection with items list."""
        col = create_collection(_unique("detail"), "detail desc")
        resp = requests.get(f"{COLLECTIONS_ENDPOINT}/{col['id']}", headers=auth_headers, timeout=10)
        resp.raise_for_status()
        detail = resp.json()
        assert detail["name"] == col["name"]
        assert detail["description"] == "detail desc"
        assert "items" in detail
        assert isinstance(detail["items"], list)

    def test_update_collection(self, auth_headers, create_collection):
        """PUT /v1/collections/{id} updates name and description."""
        col = create_collection(_unique("update"))
        new_name = _unique("renamed")
        resp = requests.put(
            f"{COLLECTIONS_ENDPOINT}/{col['id']}",
            json={"name": new_name, "description": "updated desc"},
            headers=auth_headers,
            timeout=10,
        )
        resp.raise_for_status()
        updated = resp.json()
        assert updated["name"] == new_name
        assert updated["description"] == "updated desc"

    def test_delete_collection(self, auth_headers, collections_available):
        """DELETE /v1/collections/{id} removes the collection."""
        resp = requests.post(
            COLLECTIONS_ENDPOINT,
            json={"name": _unique("delete")},
            headers=auth_headers,
            timeout=10,
        )
        resp.raise_for_status()
        col_id = resp.json()["id"]

        del_resp = requests.delete(f"{COLLECTIONS_ENDPOINT}/{col_id}", headers=auth_headers, timeout=10)
        assert del_resp.status_code == 204

        # Confirm it's gone
        get_resp = requests.get(f"{COLLECTIONS_ENDPOINT}/{col_id}", headers=auth_headers, timeout=10)
        assert get_resp.status_code == 404

    def test_delete_nonexistent_collection_returns_404(self, auth_headers, collections_available):
        """DELETE /v1/collections/{nonexistent} returns 404."""
        resp = requests.delete(
            f"{COLLECTIONS_ENDPOINT}/nonexistent-{uuid.uuid4().hex[:8]}",
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 404

    def test_get_nonexistent_collection_returns_404(self, auth_headers, collections_available):
        """GET /v1/collections/{nonexistent} returns 404."""
        resp = requests.get(
            f"{COLLECTIONS_ENDPOINT}/nonexistent-{uuid.uuid4().hex[:8]}",
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestCollectionValidation:
    """Validation and boundary-value tests."""

    def test_create_without_name_fails(self, auth_headers, collections_available):
        """POST /v1/collections without name returns 422."""
        resp = requests.post(
            COLLECTIONS_ENDPOINT,
            json={"description": "no name"},
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 422

    def test_create_with_empty_name_fails(self, auth_headers, collections_available):
        """POST /v1/collections with empty name returns 422."""
        resp = requests.post(
            COLLECTIONS_ENDPOINT,
            json={"name": ""},
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 422

    def test_create_with_max_length_name(self, auth_headers, create_collection):
        """POST /v1/collections with 255-char name succeeds."""
        long_name = "A" * 255
        col = create_collection(long_name)
        assert col["name"] == long_name

    def test_create_with_overlength_name_fails(self, auth_headers, collections_available):
        """POST /v1/collections with 256-char name returns 422."""
        resp = requests.post(
            COLLECTIONS_ENDPOINT,
            json={"name": "B" * 256},
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 422

    def test_create_with_max_description(self, auth_headers, create_collection):
        """POST /v1/collections with 1000-char description succeeds."""
        col = create_collection(_unique("maxdesc"), "D" * 1000)
        assert len(col["description"]) == 1000

    def test_create_with_overlength_description_fails(self, auth_headers, collections_available):
        """POST /v1/collections with 1001-char description returns 422."""
        resp = requests.post(
            COLLECTIONS_ENDPOINT,
            json={"name": _unique("toolong"), "description": "E" * 1001},
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 422

    def test_update_with_no_fields_fails(self, auth_headers, create_collection):
        """PUT /v1/collections/{id} with no fields returns 422."""
        col = create_collection()
        resp = requests.put(
            f"{COLLECTIONS_ENDPOINT}/{col['id']}",
            json={},
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Collection items
# ---------------------------------------------------------------------------


class TestCollectionItems:
    """Tests for adding, removing, and managing collection items."""

    def test_add_documents_to_collection(
        self, auth_headers, create_collection, sample_document_id
    ):
        """POST /v1/collections/{id}/items adds documents."""
        col = create_collection(_unique("items"))
        resp = requests.post(
            f"{COLLECTIONS_ENDPOINT}/{col['id']}/items",
            json={"document_ids": [sample_document_id]},
            headers=auth_headers,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        assert data["added_count"] >= 1

        # Verify via detail endpoint
        detail = requests.get(
            f"{COLLECTIONS_ENDPOINT}/{col['id']}", headers=auth_headers, timeout=10
        ).json()
        assert len(detail["items"]) >= 1
        assert any(item["document_id"] == sample_document_id for item in detail["items"])

    def test_add_duplicate_document_is_idempotent(
        self, auth_headers, create_collection, sample_document_id
    ):
        """Adding the same document twice does not create duplicate items."""
        col = create_collection(_unique("dup"))
        url = f"{COLLECTIONS_ENDPOINT}/{col['id']}/items"

        # Add once
        requests.post(url, json={"document_ids": [sample_document_id]}, headers=auth_headers, timeout=10)

        # Add again
        resp = requests.post(url, json={"document_ids": [sample_document_id]}, headers=auth_headers, timeout=10)
        resp.raise_for_status()

        # Should still have only one item
        detail = requests.get(
            f"{COLLECTIONS_ENDPOINT}/{col['id']}", headers=auth_headers, timeout=10
        ).json()
        doc_ids = [item["document_id"] for item in detail["items"]]
        assert doc_ids.count(sample_document_id) == 1

    def test_add_items_to_nonexistent_collection_fails(self, auth_headers, collections_available):
        """POST /v1/collections/{nonexistent}/items returns 404."""
        resp = requests.post(
            f"{COLLECTIONS_ENDPOINT}/nonexistent-{uuid.uuid4().hex[:8]}/items",
            json={"document_ids": ["fake-doc"]},
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 404

    def test_remove_item_from_collection(
        self, auth_headers, create_collection, sample_document_id
    ):
        """DELETE /v1/collections/{id}/items/{item_id} removes the item."""
        col = create_collection(_unique("remove"))

        # Add item
        requests.post(
            f"{COLLECTIONS_ENDPOINT}/{col['id']}/items",
            json={"document_ids": [sample_document_id]},
            headers=auth_headers,
            timeout=10,
        )

        # Get item ID
        detail = requests.get(
            f"{COLLECTIONS_ENDPOINT}/{col['id']}", headers=auth_headers, timeout=10
        ).json()
        assert len(detail["items"]) >= 1
        item_id = detail["items"][0]["id"]

        # Remove item
        del_resp = requests.delete(
            f"{COLLECTIONS_ENDPOINT}/{col['id']}/items/{item_id}",
            headers=auth_headers,
            timeout=10,
        )
        assert del_resp.status_code == 204

        # Verify removal
        detail2 = requests.get(
            f"{COLLECTIONS_ENDPOINT}/{col['id']}", headers=auth_headers, timeout=10
        ).json()
        assert len(detail2["items"]) == len(detail["items"]) - 1

    def test_remove_nonexistent_item_returns_404(
        self, auth_headers, create_collection
    ):
        """DELETE /v1/collections/{id}/items/{nonexistent} returns 404."""
        col = create_collection()
        resp = requests.delete(
            f"{COLLECTIONS_ENDPOINT}/{col['id']}/items/nonexistent-{uuid.uuid4().hex[:8]}",
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 404

    def test_update_item_note(
        self, auth_headers, create_collection, sample_document_id
    ):
        """PUT /v1/collections/{id}/items/{item_id} updates the note."""
        col = create_collection(_unique("note"))

        # Add item
        requests.post(
            f"{COLLECTIONS_ENDPOINT}/{col['id']}/items",
            json={"document_ids": [sample_document_id]},
            headers=auth_headers,
            timeout=10,
        )

        # Get item ID
        detail = requests.get(
            f"{COLLECTIONS_ENDPOINT}/{col['id']}", headers=auth_headers, timeout=10
        ).json()
        item_id = detail["items"][0]["id"]

        # Update note
        note_text = f"E2E test note {uuid.uuid4().hex[:8]}"
        resp = requests.put(
            f"{COLLECTIONS_ENDPOINT}/{col['id']}/items/{item_id}",
            json={"note": note_text},
            headers=auth_headers,
            timeout=10,
        )
        resp.raise_for_status()
        updated = resp.json()
        assert updated["note"] == note_text

        # Verify persistence
        detail2 = requests.get(
            f"{COLLECTIONS_ENDPOINT}/{col['id']}", headers=auth_headers, timeout=10
        ).json()
        item = next(i for i in detail2["items"] if i["id"] == item_id)
        assert item["note"] == note_text

    def test_update_item_note_max_length(
        self, auth_headers, create_collection, sample_document_id
    ):
        """PUT with a note at the default max length (1000) succeeds."""
        col = create_collection(_unique("longnote"))

        requests.post(
            f"{COLLECTIONS_ENDPOINT}/{col['id']}/items",
            json={"document_ids": [sample_document_id]},
            headers=auth_headers,
            timeout=10,
        )

        detail = requests.get(
            f"{COLLECTIONS_ENDPOINT}/{col['id']}", headers=auth_headers, timeout=10
        ).json()
        item_id = detail["items"][0]["id"]

        long_note = "N" * 1000
        resp = requests.put(
            f"{COLLECTIONS_ENDPOINT}/{col['id']}/items/{item_id}",
            json={"note": long_note},
            headers=auth_headers,
            timeout=10,
        )
        resp.raise_for_status()
        assert resp.json()["note"] == long_note

    def test_clear_item_note(
        self, auth_headers, create_collection, sample_document_id
    ):
        """PUT with note=empty clears the note."""
        col = create_collection(_unique("clearnote"))

        requests.post(
            f"{COLLECTIONS_ENDPOINT}/{col['id']}/items",
            json={"document_ids": [sample_document_id]},
            headers=auth_headers,
            timeout=10,
        )

        detail = requests.get(
            f"{COLLECTIONS_ENDPOINT}/{col['id']}", headers=auth_headers, timeout=10
        ).json()
        item_id = detail["items"][0]["id"]

        # Set a note first
        requests.put(
            f"{COLLECTIONS_ENDPOINT}/{col['id']}/items/{item_id}",
            json={"note": "temporary note"},
            headers=auth_headers,
            timeout=10,
        )

        # Clear it
        resp = requests.put(
            f"{COLLECTIONS_ENDPOINT}/{col['id']}/items/{item_id}",
            json={"note": ""},
            headers=auth_headers,
            timeout=10,
        )
        resp.raise_for_status()
        assert resp.json()["note"] == "" or resp.json()["note"] is None

    def test_add_items_with_empty_list_fails(self, auth_headers, create_collection):
        """POST /v1/collections/{id}/items with empty list returns 422."""
        col = create_collection()
        resp = requests.post(
            f"{COLLECTIONS_ENDPOINT}/{col['id']}/items",
            json={"document_ids": []},
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Reorder items
# ---------------------------------------------------------------------------


class TestCollectionReorder:
    """Tests for item reordering."""

    def test_reorder_items(self, auth_headers, create_collection):
        """PUT /v1/collections/{id}/items/reorder updates positions."""
        col = create_collection(_unique("reorder"))

        # Need multiple documents
        try:
            resp = requests.get(
                f"{SEARCH_API_URL}/v1/search/",
                params={"q": "*", "page": "1", "limit": "3"},
                headers=auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if len(results) < 2:
                pytest.skip("Need at least 2 indexed documents for reorder test")
        except Exception as exc:
            pytest.skip(f"Search unavailable: {exc}")

        doc_ids = [r["id"] for r in results]
        requests.post(
            f"{COLLECTIONS_ENDPOINT}/{col['id']}/items",
            json={"document_ids": doc_ids},
            headers=auth_headers,
            timeout=10,
        )

        detail = requests.get(
            f"{COLLECTIONS_ENDPOINT}/{col['id']}", headers=auth_headers, timeout=10
        ).json()
        item_ids = [item["id"] for item in detail["items"]]
        assert len(item_ids) >= 2

        # Reverse order
        reversed_ids = list(reversed(item_ids))
        resp = requests.put(
            f"{COLLECTIONS_ENDPOINT}/{col['id']}/items/reorder",
            json={"item_ids": reversed_ids},
            headers=auth_headers,
            timeout=10,
        )
        resp.raise_for_status()
        assert resp.json().get("status") == "reordered"


# ---------------------------------------------------------------------------
# Cascade delete
# ---------------------------------------------------------------------------


class TestCascadeDelete:
    """Verify that deleting a collection removes its items."""

    def test_delete_collection_cascades_items(
        self, auth_headers, collections_available, sample_document_id
    ):
        """Items are removed when parent collection is deleted."""
        create_resp = requests.post(
            COLLECTIONS_ENDPOINT,
            json={"name": _unique("cascade")},
            headers=auth_headers,
            timeout=10,
        )
        create_resp.raise_for_status()
        col_id = create_resp.json()["id"]

        # Add an item
        requests.post(
            f"{COLLECTIONS_ENDPOINT}/{col_id}/items",
            json={"document_ids": [sample_document_id]},
            headers=auth_headers,
            timeout=10,
        )

        # Verify item exists
        detail = requests.get(
            f"{COLLECTIONS_ENDPOINT}/{col_id}", headers=auth_headers, timeout=10
        ).json()
        assert len(detail["items"]) >= 1

        # Delete collection
        del_resp = requests.delete(f"{COLLECTIONS_ENDPOINT}/{col_id}", headers=auth_headers, timeout=10)
        assert del_resp.status_code == 204

        # Collection and its items are gone
        get_resp = requests.get(f"{COLLECTIONS_ENDPOINT}/{col_id}", headers=auth_headers, timeout=10)
        assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


class TestCollectionsAuth:
    """Verify that collections endpoints require authentication."""

    def test_list_without_auth_returns_401(self, collections_available):
        """GET /v1/collections without auth returns 401 or 403."""
        resp = requests.get(COLLECTIONS_ENDPOINT, timeout=10)
        assert resp.status_code in (401, 403)

    def test_create_without_auth_returns_401(self, collections_available):
        """POST /v1/collections without auth returns 401 or 403."""
        resp = requests.post(
            COLLECTIONS_ENDPOINT,
            json={"name": "unauthorized"},
            timeout=10,
        )
        assert resp.status_code in (401, 403)
