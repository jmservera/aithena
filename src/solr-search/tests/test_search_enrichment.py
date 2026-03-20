"""Tests for search result enrichment with collection membership (#668)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("AUTH_DB_PATH", "/tmp/test-auth.db")  # noqa: S108
os.environ.setdefault("AUTH_JWT_SECRET", "test-auth-secret")
os.environ.setdefault("AUTH_JWT_TTL", "24h")
os.environ.setdefault("AUTH_COOKIE_NAME", "aithena_auth")

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from auth import AuthenticatedUser, create_access_token, init_auth_db  # noqa: E402
from collections_service import (  # noqa: E402
    add_items,
    create_collection,
    get_collection_ids_for_documents,
    init_collections_db,
)
from config import settings  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

USER_A = AuthenticatedUser(id=10, username="alice", role="user")
USER_B = AuthenticatedUser(id=20, username="bob", role="user")

MOCK_SOLR_RESPONSE = {
    "response": {
        "numFound": 2,
        "docs": [
            {
                "id": "doc1",
                "title_s": "Book One",
                "author_s": "Author A",
                "file_path_s": "books/one.pdf",
                "score": 10.0,
            },
            {
                "id": "doc2",
                "title_s": "Book Two",
                "author_s": "Author B",
                "file_path_s": "books/two.pdf",
                "score": 8.0,
            },
        ],
    },
    "highlighting": {},
    "facet_counts": {"facet_fields": {}},
}


def _auth_header(user: AuthenticatedUser) -> dict[str, str]:
    token = create_access_token(user, settings.auth_jwt_secret, settings.auth_jwt_ttl_seconds)
    return {"Authorization": f"Bearer {token}"}


def _mock_solr():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = MOCK_SOLR_RESPONSE
    return mock_response


@pytest.fixture()
def auth_db(tmp_path: Path):
    original = settings.auth_db_path
    db = tmp_path / "auth.db"
    object.__setattr__(settings, "auth_db_path", db)
    init_auth_db(db)
    yield db
    object.__setattr__(settings, "auth_db_path", original)


@pytest.fixture()
def collections_db(tmp_path: Path):
    original = settings.collections_db_path
    db = tmp_path / "collections.db"
    object.__setattr__(settings, "collections_db_path", db)
    init_collections_db(db)
    yield db
    object.__setattr__(settings, "collections_db_path", original)


@pytest.fixture()
def client(auth_db, collections_db) -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Service-layer tests for get_collection_ids_for_documents
# ---------------------------------------------------------------------------


class TestGetCollectionIdsForDocuments:
    def test_empty_doc_ids(self, collections_db):
        result = get_collection_ids_for_documents(collections_db, "10", [])
        assert result == {}

    def test_no_matching_documents(self, collections_db):
        create_collection(collections_db, "10", "My Books", None)
        result = get_collection_ids_for_documents(collections_db, "10", ["nonexistent"])
        assert result == {}

    def test_single_document_in_one_collection(self, collections_db):
        col = create_collection(collections_db, "10", "Favourites", None)
        add_items(collections_db, col["id"], "10", ["doc1"])

        result = get_collection_ids_for_documents(collections_db, "10", ["doc1"])
        assert result == {"doc1": [col["id"]]}

    def test_document_in_multiple_collections(self, collections_db):
        col1 = create_collection(collections_db, "10", "Favourites", None)
        col2 = create_collection(collections_db, "10", "Read Later", None)
        add_items(collections_db, col1["id"], "10", ["doc1"])
        add_items(collections_db, col2["id"], "10", ["doc1"])

        result = get_collection_ids_for_documents(collections_db, "10", ["doc1"])
        assert set(result["doc1"]) == {col1["id"], col2["id"]}

    def test_batch_lookup_multiple_docs(self, collections_db):
        col = create_collection(collections_db, "10", "Favourites", None)
        add_items(collections_db, col["id"], "10", ["doc1", "doc3"])

        result = get_collection_ids_for_documents(collections_db, "10", ["doc1", "doc2", "doc3"])
        assert result["doc1"] == [col["id"]]
        assert result["doc3"] == [col["id"]]
        assert "doc2" not in result  # not in any collection

    def test_only_own_collections(self, collections_db):
        col_alice = create_collection(collections_db, "10", "Alice col", None)
        col_bob = create_collection(collections_db, "20", "Bob col", None)
        add_items(collections_db, col_alice["id"], "10", ["doc1"])
        add_items(collections_db, col_bob["id"], "20", ["doc1"])

        result_alice = get_collection_ids_for_documents(collections_db, "10", ["doc1"])
        assert result_alice == {"doc1": [col_alice["id"]]}

        result_bob = get_collection_ids_for_documents(collections_db, "20", ["doc1"])
        assert result_bob == {"doc1": [col_bob["id"]]}


# ---------------------------------------------------------------------------
# Integration tests: search endpoint enrichment
# ---------------------------------------------------------------------------


class TestSearchEnrichment:
    @patch("main.requests.post")
    def test_search_results_include_in_collections(self, mock_post, client, collections_db):
        mock_post.return_value = _mock_solr()
        col = create_collection(collections_db, "10", "Favourites", None)
        add_items(collections_db, col["id"], "10", ["doc1"])

        resp = client.get("/search", params={"q": "test"}, headers=_auth_header(USER_A))
        assert resp.status_code == 200
        data = resp.json()

        results = data["results"]
        assert len(results) == 2
        assert results[0]["in_collections"] == [col["id"]]
        assert results[1]["in_collections"] == []

    @patch("main.requests.post")
    def test_search_enrichment_empty_when_no_collections(self, mock_post, client, collections_db):
        mock_post.return_value = _mock_solr()

        resp = client.get("/search", params={"q": "test"}, headers=_auth_header(USER_A))
        assert resp.status_code == 200
        data = resp.json()

        for result in data["results"]:
            assert result["in_collections"] == []

    @patch("main.requests.post")
    def test_search_enrichment_user_isolation(self, mock_post, client, collections_db):
        """User B should NOT see User A's collection membership."""
        mock_post.return_value = _mock_solr()
        col = create_collection(collections_db, "10", "Alice only", None)
        add_items(collections_db, col["id"], "10", ["doc1"])

        resp = client.get("/search", params={"q": "test"}, headers=_auth_header(USER_B))
        assert resp.status_code == 200
        data = resp.json()

        for result in data["results"]:
            assert result["in_collections"] == []

    @patch("main.requests.post")
    def test_v1_search_includes_in_collections(self, mock_post, client, collections_db):
        """The /v1/search alias should also enrich results."""
        mock_post.return_value = _mock_solr()
        col = create_collection(collections_db, "10", "Favourites", None)
        add_items(collections_db, col["id"], "10", ["doc2"])

        resp = client.get("/v1/search", params={"q": "test"}, headers=_auth_header(USER_A))
        assert resp.status_code == 200
        data = resp.json()

        assert data["results"][0]["in_collections"] == []
        assert data["results"][1]["in_collections"] == [col["id"]]

    @patch("main.requests.post")
    @patch("main.svc_get_collection_ids_for_documents", side_effect=Exception("DB error"))
    def test_search_enrichment_graceful_on_failure(self, _mock_svc, mock_post, client, collections_db):
        """If collection lookup fails, search still returns results without in_collections."""
        mock_post.return_value = _mock_solr()

        resp = client.get("/search", params={"q": "test"}, headers=_auth_header(USER_A))
        assert resp.status_code == 200
        data = resp.json()

        for result in data["results"]:
            assert "in_collections" not in result

    @patch("main.requests.post")
    def test_search_empty_results_no_enrichment_call(self, mock_post, client, collections_db):
        """Empty result set should not trigger collection lookup."""
        mock_empty = MagicMock()
        mock_empty.status_code = 200
        mock_empty.json.return_value = {
            "response": {"numFound": 0, "docs": []},
            "highlighting": {},
            "facet_counts": {"facet_fields": {}},
        }
        mock_post.return_value = mock_empty

        with patch("main.svc_get_collection_ids_for_documents") as mock_svc:
            resp = client.get("/search", params={"q": "noresults"}, headers=_auth_header(USER_A))
            assert resp.status_code == 200
            mock_svc.assert_not_called()
