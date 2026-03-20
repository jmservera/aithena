"""Comprehensive metadata-editing test suite — integration-style scenarios.

Covers cross-cutting concerns that span the single-edit, batch-edit, and
security test modules:
  • Redis override store lifecycle (write → read → structure)
  • Concurrent edit behaviour
  • Solr / Redis unavailability (graceful degradation)
  • Full round-trip field-mapping validation
"""

from __future__ import annotations

import json
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
from fastapi.testclient import TestClient  # noqa: E402

from tests.auth_helpers import create_authenticated_client  # noqa: E402

_TEST_ADMIN_KEY = "test-metadata-editing-key"
DOC_ID = "editing-doc-001"
SINGLE_ENDPOINT = f"/v1/admin/documents/{DOC_ID}/metadata"
BATCH_ENDPOINT = "/v1/admin/documents/batch/metadata"


def get_client() -> TestClient:
    client = create_authenticated_client()
    client.headers["X-API-Key"] = _TEST_ADMIN_KEY
    return client


@pytest.fixture(autouse=True)
def _enable_admin_api_key():
    with patch("admin_auth._get_admin_api_key", return_value=_TEST_ADMIN_KEY):
        yield


def _solr_found(num: int = 1) -> dict:
    return {"response": {"numFound": num, "docs": []}}


# ---------------------------------------------------------------------------
# Redis override store — write, read, structure, missing key
# ---------------------------------------------------------------------------


class TestRedisOverrideStore:
    """Verify the Redis metadata-override lifecycle."""

    @patch("main._get_redis_pool")
    @patch("main._raw_solr_query", return_value=_solr_found())
    @patch("main.requests.post")
    def test_override_written_on_single_edit(
        self, mock_post: MagicMock, _q: MagicMock, _p: MagicMock
    ) -> None:
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
        redis_mock = MagicMock()
        with patch("main._get_admin_redis_client", return_value=redis_mock):
            resp = get_client().patch(SINGLE_ENDPOINT, json={"title": "Override"})

        assert resp.status_code == 200  # noqa: S101
        redis_mock.set.assert_called_once()
        key = redis_mock.set.call_args[0][0]
        assert key == f"aithena:metadata-override:{DOC_ID}"  # noqa: S101

    @patch("main._get_redis_pool")
    @patch("main._raw_solr_query", return_value=_solr_found())
    @patch("main.requests.post")
    def test_override_contains_edited_by_and_timestamp(
        self, mock_post: MagicMock, _q: MagicMock, _p: MagicMock
    ) -> None:
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
        redis_mock = MagicMock()
        with patch("main._get_admin_redis_client", return_value=redis_mock):
            get_client().patch(SINGLE_ENDPOINT, json={"author": "Tolkien"})

        data = json.loads(redis_mock.set.call_args[0][1])
        assert data["edited_by"] == "admin"  # noqa: S101
        assert "edited_at" in data  # noqa: S101

    @patch("main._get_redis_pool")
    @patch("main._raw_solr_query", return_value=_solr_found())
    @patch("main.requests.post")
    def test_override_maps_all_solr_fields(
        self, mock_post: MagicMock, _q: MagicMock, _p: MagicMock
    ) -> None:
        """Updating all five fields stores every mapped Solr field."""
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
        redis_mock = MagicMock()
        with patch("main._get_admin_redis_client", return_value=redis_mock):
            get_client().patch(
                SINGLE_ENDPOINT,
                json={
                    "title": "T",
                    "author": "A",
                    "year": 2000,
                    "category": "C",
                    "series": "S",
                },
            )

        data = json.loads(redis_mock.set.call_args[0][1])
        for field in ("title_s", "title_t", "author_s", "author_t", "year_i", "category_s", "series_s"):
            assert field in data, f"Missing Solr field {field} in Redis override"  # noqa: S101

    @patch("main._get_redis_pool")
    @patch("main._raw_solr_query", return_value=_solr_found())
    @patch("main.requests.post")
    def test_batch_stores_one_override_per_document(
        self, mock_post: MagicMock, _q: MagicMock, _p: MagicMock
    ) -> None:
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
        redis_mock = MagicMock()
        ids = ["batch-a", "batch-b", "batch-c"]
        with patch("main._get_admin_redis_client", return_value=redis_mock):
            get_client().patch(
                BATCH_ENDPOINT,
                json={"document_ids": ids, "updates": {"category": "History"}},
            )

        keys = [c[0][0] for c in redis_mock.set.call_args_list]
        for doc_id in ids:
            assert f"aithena:metadata-override:{doc_id}" in keys  # noqa: S101


# ---------------------------------------------------------------------------
# Solr field-mapping round-trip
# ---------------------------------------------------------------------------


class TestSolrFieldMapping:
    """Verify that each metadata field is correctly mapped to Solr fields."""

    @patch("main._get_redis_pool")
    @patch("main._raw_solr_query", return_value=_solr_found())
    @patch("main.requests.post")
    def test_title_maps_to_title_s_and_title_t(
        self, mock_post: MagicMock, _q: MagicMock, _p: MagicMock
    ) -> None:
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
        with patch("main._get_admin_redis_client", return_value=MagicMock()):
            get_client().patch(SINGLE_ENDPOINT, json={"title": "Mapped"})

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload[0]["title_s"] == {"set": "Mapped"}  # noqa: S101
        assert payload[0]["title_t"] == {"set": "Mapped"}  # noqa: S101

    @patch("main._get_redis_pool")
    @patch("main._raw_solr_query", return_value=_solr_found())
    @patch("main.requests.post")
    def test_author_maps_to_author_s_and_author_t(
        self, mock_post: MagicMock, _q: MagicMock, _p: MagicMock
    ) -> None:
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
        with patch("main._get_admin_redis_client", return_value=MagicMock()):
            get_client().patch(SINGLE_ENDPOINT, json={"author": "Asimov"})

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload[0]["author_s"] == {"set": "Asimov"}  # noqa: S101
        assert payload[0]["author_t"] == {"set": "Asimov"}  # noqa: S101

    @patch("main._get_redis_pool")
    @patch("main._raw_solr_query", return_value=_solr_found())
    @patch("main.requests.post")
    def test_year_maps_to_year_i(
        self, mock_post: MagicMock, _q: MagicMock, _p: MagicMock
    ) -> None:
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
        with patch("main._get_admin_redis_client", return_value=MagicMock()):
            get_client().patch(SINGLE_ENDPOINT, json={"year": 1965})

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload[0]["year_i"] == {"set": 1965}  # noqa: S101

    @patch("main._get_redis_pool")
    @patch("main._raw_solr_query", return_value=_solr_found())
    @patch("main.requests.post")
    def test_category_maps_to_category_s(
        self, mock_post: MagicMock, _q: MagicMock, _p: MagicMock
    ) -> None:
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
        with patch("main._get_admin_redis_client", return_value=MagicMock()):
            get_client().patch(SINGLE_ENDPOINT, json={"category": "Fantasy"})

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload[0]["category_s"] == {"set": "Fantasy"}  # noqa: S101

    @patch("main._get_redis_pool")
    @patch("main._raw_solr_query", return_value=_solr_found())
    @patch("main.requests.post")
    def test_series_maps_to_series_s(
        self, mock_post: MagicMock, _q: MagicMock, _p: MagicMock
    ) -> None:
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
        with patch("main._get_admin_redis_client", return_value=MagicMock()):
            get_client().patch(SINGLE_ENDPOINT, json={"series": "Foundation"})

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload[0]["series_s"] == {"set": "Foundation"}  # noqa: S101


# ---------------------------------------------------------------------------
# Solr unavailability
# ---------------------------------------------------------------------------


class TestSolrUnavailability:
    """Verify error handling when Solr is down."""

    @patch("main._get_redis_pool")
    @patch("main._raw_solr_query", return_value=_solr_found())
    @patch("main.requests.post")
    def test_single_edit_solr_timeout(
        self, mock_post: MagicMock, _q: MagicMock, _p: MagicMock
    ) -> None:
        import requests as req_lib

        mock_post.side_effect = req_lib.Timeout("timed out")
        with patch("main._get_admin_redis_client", return_value=MagicMock()):
            resp = get_client().patch(SINGLE_ENDPOINT, json={"title": "T"})
        assert resp.status_code == 504  # noqa: S101

    @patch("main._get_redis_pool")
    @patch("main._raw_solr_query", return_value=_solr_found())
    @patch("main.requests.post")
    def test_single_edit_solr_connection_error(
        self, mock_post: MagicMock, _q: MagicMock, _p: MagicMock
    ) -> None:
        import requests as req_lib

        mock_post.side_effect = req_lib.ConnectionError("refused")
        with patch("main._get_admin_redis_client", return_value=MagicMock()):
            resp = get_client().patch(SINGLE_ENDPOINT, json={"title": "T"})
        assert resp.status_code == 502  # noqa: S101

    @patch("main._get_redis_pool")
    @patch("main._raw_solr_query", return_value=_solr_found())
    @patch("main.requests.post")
    def test_batch_edit_continues_on_solr_failure(
        self, mock_post: MagicMock, _q: MagicMock, _p: MagicMock
    ) -> None:
        """Batch edit should continue processing remaining docs when one Solr call fails."""
        import requests as req_lib

        call_count = 0

        def _side_effect(*a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise req_lib.ConnectionError("first doc fails")
            return MagicMock(status_code=200, raise_for_status=MagicMock())

        mock_post.side_effect = _side_effect
        redis_mock = MagicMock()
        with patch("main._get_admin_redis_client", return_value=redis_mock):
            resp = get_client().patch(
                BATCH_ENDPOINT,
                json={"document_ids": ["fail-doc", "ok-doc"], "updates": {"title": "T"}},
            )

        assert resp.status_code == 200  # noqa: S101
        data = resp.json()
        assert data["updated"] == 1  # noqa: S101
        assert data["failed"] == 1  # noqa: S101


# ---------------------------------------------------------------------------
# Redis unavailability (graceful degradation)
# ---------------------------------------------------------------------------


class TestRedisUnavailability:
    """Verify behaviour when Redis is unavailable."""

    @patch("main._get_redis_pool")
    @patch("main._raw_solr_query", return_value=_solr_found())
    @patch("main.requests.post")
    def test_single_edit_redis_down_returns_503(
        self, mock_post: MagicMock, _q: MagicMock, _p: MagicMock
    ) -> None:
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
        redis_mock = MagicMock()
        redis_mock.set.side_effect = ConnectionError("Redis down")
        with patch("main._get_admin_redis_client", return_value=redis_mock):
            resp = get_client().patch(SINGLE_ENDPOINT, json={"title": "T"})
        assert resp.status_code == 503  # noqa: S101

    @patch("main._get_redis_pool")
    @patch("main._raw_solr_query", return_value=_solr_found())
    @patch("main.requests.post")
    def test_batch_edit_redis_failure_reports_partial(
        self, mock_post: MagicMock, _q: MagicMock, _p: MagicMock
    ) -> None:
        """Batch edit continues after Redis failure on one document."""
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
        count = 0

        def _redis_set(*a, **kw):
            nonlocal count
            count += 1
            if count == 1:
                raise Exception("Redis unavailable")  # noqa: TRY002

        redis_mock = MagicMock()
        redis_mock.set.side_effect = _redis_set
        with patch("main._get_admin_redis_client", return_value=redis_mock):
            resp = get_client().patch(
                BATCH_ENDPOINT,
                json={"document_ids": ["r-fail", "r-ok"], "updates": {"author": "A"}},
            )

        assert resp.status_code == 200  # noqa: S101
        data = resp.json()
        assert data["failed"] == 1  # noqa: S101
        assert data["updated"] == 1  # noqa: S101


# ---------------------------------------------------------------------------
# Concurrent edit scenarios
# ---------------------------------------------------------------------------


class TestConcurrentEdits:
    """Simulate concurrent edit behaviour (last-write-wins)."""

    @patch("main._get_redis_pool")
    @patch("main._raw_solr_query", return_value=_solr_found())
    @patch("main.requests.post")
    def test_last_write_wins_on_single_document(
        self, mock_post: MagicMock, _q: MagicMock, _p: MagicMock
    ) -> None:
        """Two sequential edits to the same doc — last value is what Solr receives last."""
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
        redis_mock = MagicMock()
        with patch("main._get_admin_redis_client", return_value=redis_mock):
            client = get_client()
            client.patch(SINGLE_ENDPOINT, json={"title": "First"})
            client.patch(SINGLE_ENDPOINT, json={"title": "Second"})

        assert mock_post.call_count == 2  # noqa: S101
        last_payload = mock_post.call_args_list[-1].kwargs.get("json") or mock_post.call_args_list[-1][1].get("json")
        assert last_payload[0]["title_s"] == {"set": "Second"}  # noqa: S101

        last_redis_value = json.loads(redis_mock.set.call_args_list[-1][0][1])
        assert last_redis_value["title_s"] == "Second"  # noqa: S101

    @patch("main._get_redis_pool")
    @patch("main._raw_solr_query", return_value=_solr_found())
    @patch("main.requests.post")
    def test_batch_and_single_edit_same_document(
        self, mock_post: MagicMock, _q: MagicMock, _p: MagicMock
    ) -> None:
        """A batch edit followed by a single edit — both succeed independently."""
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
        redis_mock = MagicMock()
        with patch("main._get_admin_redis_client", return_value=redis_mock):
            client = get_client()
            r1 = client.patch(
                BATCH_ENDPOINT,
                json={"document_ids": [DOC_ID], "updates": {"category": "Batch"}},
            )
            r2 = client.patch(SINGLE_ENDPOINT, json={"category": "Single"})

        assert r1.status_code == 200  # noqa: S101
        assert r2.status_code == 200  # noqa: S101
        assert mock_post.call_count == 2  # noqa: S101


# ---------------------------------------------------------------------------
# Error scenarios — validation edge cases
# ---------------------------------------------------------------------------


class TestValidationEdgeCases:
    """Extended validation scenarios not covered by single/batch test modules."""

    def test_single_edit_only_null_fields_returns_422(self) -> None:
        resp = get_client().patch(SINGLE_ENDPOINT, json={"title": None, "year": None})
        assert resp.status_code == 422  # noqa: S101

    def test_batch_edit_duplicate_document_ids_accepted(self) -> None:
        """Duplicate IDs in the list are not rejected — they are processed."""
        with (
            patch("main._get_redis_pool"),
            patch("main._raw_solr_query", return_value=_solr_found()),
            patch("main.requests.post", return_value=MagicMock(status_code=200, raise_for_status=MagicMock())),
            patch("main._get_admin_redis_client", return_value=MagicMock()),
        ):
            resp = get_client().patch(
                BATCH_ENDPOINT,
                json={"document_ids": ["dup", "dup"], "updates": {"title": "T"}},
            )
        assert resp.status_code == 200  # noqa: S101
        assert resp.json()["matched"] == 2  # noqa: S101

    def test_single_edit_nonexistent_doc_returns_404(self) -> None:
        with (
            patch("main._get_redis_pool"),
            patch("main._raw_solr_query", return_value={"response": {"numFound": 0, "docs": []}}),
        ):
            resp = get_client().patch(SINGLE_ENDPOINT, json={"title": "Ghost"})
        assert resp.status_code == 404  # noqa: S101

    def test_batch_with_single_id_works(self) -> None:
        with (
            patch("main._get_redis_pool"),
            patch("main._raw_solr_query", return_value=_solr_found()),
            patch("main.requests.post", return_value=MagicMock(status_code=200, raise_for_status=MagicMock())),
            patch("main._get_admin_redis_client", return_value=MagicMock()),
        ):
            resp = get_client().patch(
                BATCH_ENDPOINT,
                json={"document_ids": ["only-one"], "updates": {"series": "Solo"}},
            )
        assert resp.status_code == 200  # noqa: S101
        assert resp.json()["updated"] == 1  # noqa: S101
