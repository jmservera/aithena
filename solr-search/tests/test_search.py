"""Unit tests for the solr-search service."""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Make the solr-search package importable without installing it
# ---------------------------------------------------------------------------

SERVICE_ROOT = Path(__file__).parent.parent


def _load_main():
    """Import main.py from solr-search, injecting a stub config module."""
    config_stub = types.ModuleType("config")
    config_stub.TITLE = "Test Search API"
    config_stub.VERSION = "0.0.0"
    config_stub.SOLR_HOST = "localhost"
    config_stub.SOLR_PORT = "8983"
    config_stub.SOLR_COLLECTION = "books"
    config_stub.DOCUMENTS_BASE_URL = "/documents"
    config_stub.PORT = 8080
    sys.modules.setdefault("config", config_stub)

    spec = importlib.util.spec_from_file_location(
        "solr_search_main", SERVICE_ROOT / "main.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


main = _load_main()


# ---------------------------------------------------------------------------
# _make_document_url
# ---------------------------------------------------------------------------


class TestMakeDocumentUrl:
    def test_basic_path(self):
        url = main._make_document_url("amades/book.pdf")
        assert url == "/documents/amades/book.pdf"

    def test_none_returns_none(self):
        assert main._make_document_url(None) is None

    def test_spaces_are_encoded(self):
        url = main._make_document_url("some folder/my book.pdf")
        assert " " not in url
        assert "my%20book.pdf" in url

    def test_slashes_preserved(self):
        url = main._make_document_url("cat/sub/book.pdf")
        assert url == "/documents/cat/sub/book.pdf"


# ---------------------------------------------------------------------------
# _normalize_doc
# ---------------------------------------------------------------------------


class TestNormalizeDoc:
    SAMPLE_DOC = {
        "id": "doc-1",
        "title_s": "My Book",
        "author_s": "Jane Doe",
        "year_i": 1990,
        "category_s": "amades",
        "language_detected_s": "ca",
        "file_path_s": "amades/my_book.pdf",
        "score": 3.14,
    }

    def test_all_core_fields_mapped(self):
        result = main._normalize_doc(self.SAMPLE_DOC, {})
        assert result["id"] == "doc-1"
        assert result["title"] == "My Book"
        assert result["author"] == "Jane Doe"
        assert result["year"] == 1990
        assert result["category"] == "amades"
        assert result["language"] == "ca"
        assert result["file_path"] == "amades/my_book.pdf"
        assert result["score"] == pytest.approx(3.14)

    def test_document_url_built_from_file_path(self):
        result = main._normalize_doc(self.SAMPLE_DOC, {})
        assert result["document_url"] == "/documents/amades/my_book.pdf"

    def test_highlights_collected_from_all_fields(self):
        highlighting = {
            "doc-1": {
                "content": ["snippet one", "snippet two"],
                "_text_": ["snippet three"],
            }
        }
        result = main._normalize_doc(self.SAMPLE_DOC, highlighting)
        assert set(result["highlights"]) == {"snippet one", "snippet two", "snippet three"}

    def test_no_highlights_returns_empty_list(self):
        result = main._normalize_doc(self.SAMPLE_DOC, {})
        assert result["highlights"] == []

    def test_missing_optional_fields_are_none(self):
        result = main._normalize_doc({"id": "x"}, {})
        assert result["title"] is None
        assert result["author"] is None
        assert result["year"] is None
        assert result["document_url"] is None


# ---------------------------------------------------------------------------
# _parse_facets
# ---------------------------------------------------------------------------


class TestParseFacets:
    def test_parses_flat_list(self):
        facet_counts = {
            "facet_fields": {
                "author_s": ["Amades", 5, "Doe", 3],
                "language_detected_s": ["ca", 7, "es", 2],
            }
        }
        result = main._parse_facets(facet_counts)
        assert result["author_s"] == [
            {"value": "Amades", "count": 5},
            {"value": "Doe", "count": 3},
        ]
        assert result["language_detected_s"][0]["value"] == "ca"

    def test_zero_count_excluded(self):
        facet_counts = {
            "facet_fields": {
                "category_s": ["balearics", 0, "amades", 2],
            }
        }
        result = main._parse_facets(facet_counts)
        buckets = result["category_s"]
        values = [b["value"] for b in buckets]
        assert "balearics" not in values
        assert "amades" in values

    def test_none_returns_empty(self):
        assert main._parse_facets(None) == {}

    def test_no_facet_fields_key(self):
        assert main._parse_facets({}) == {}


# ---------------------------------------------------------------------------
# /v1/search/ endpoint (via TestClient)
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    return TestClient(main.api_app)


MOCK_SOLR_RESPONSE = {
    "response": {
        "numFound": 1,
        "start": 0,
        "docs": [
            {
                "id": "doc-42",
                "title_s": "Test Book",
                "author_s": "Test Author",
                "year_i": 2000,
                "category_s": "bsal",
                "language_detected_s": "es",
                "file_path_s": "bsal/test.pdf",
                "score": 1.0,
            }
        ],
    },
    "highlighting": {
        "doc-42": {
            "content": ["<em>search term</em> in context"],
        }
    },
    "facet_counts": {
        "facet_fields": {
            "author_s": ["Test Author", 1],
            "category_s": ["bsal", 1],
            "language_detected_s": ["es", 1],
        }
    },
}


class TestSearchEndpoint:
    def test_search_returns_normalized_results(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_SOLR_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_ac:
            instance = MagicMock()
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            instance.get = AsyncMock(return_value=mock_resp)
            mock_ac.return_value = instance

            response = client.get("/search/?q=test")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["results"][0]["title"] == "Test Book"
        assert body["results"][0]["author"] == "Test Author"
        assert body["results"][0]["year"] == 2000
        assert body["results"][0]["document_url"] == "/documents/bsal/test.pdf"
        assert "<em>search term</em> in context" in body["results"][0]["highlights"]

    def test_facets_included_in_response(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_SOLR_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_ac:
            instance = MagicMock()
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            instance.get = AsyncMock(return_value=mock_resp)
            mock_ac.return_value = instance

            response = client.get("/search/?q=test")

        facets = response.json()["facets"]
        assert "author_s" in facets
        assert facets["author_s"][0]["value"] == "Test Author"

    def test_wildcard_query_when_q_omitted(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "response": {"numFound": 0, "start": 0, "docs": []},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_ac:
            instance = MagicMock()
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            instance.get = AsyncMock(return_value=mock_resp)
            mock_ac.return_value = instance

            response = client.get("/search/")

        assert response.status_code == 200
        assert response.json()["query"] == "*:*"

    def test_solr_error_returns_502(self, client):
        import httpx as _httpx

        with patch("httpx.AsyncClient") as mock_ac:
            instance = MagicMock()
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            mock_req = MagicMock()
            mock_err_resp = MagicMock()
            mock_err_resp.status_code = 500
            instance.get = AsyncMock(
                side_effect=_httpx.HTTPStatusError(
                    "error", request=mock_req, response=mock_err_resp
                )
            )
            mock_ac.return_value = instance

            response = client.get("/search/?q=fail")

        assert response.status_code == 502

    def test_solr_unreachable_returns_503(self, client):
        import httpx as _httpx

        with patch("httpx.AsyncClient") as mock_ac:
            instance = MagicMock()
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            instance.get = AsyncMock(
                side_effect=_httpx.RequestError("connection refused")
            )
            mock_ac.return_value = instance

            response = client.get("/search/?q=down")

        assert response.status_code == 503


# ---------------------------------------------------------------------------
# /v1/info endpoint
# ---------------------------------------------------------------------------


class TestInfoEndpoint:
    def test_info_returns_title_and_version(self, client):
        response = client.get("/info")
        assert response.status_code == 200
        body = response.json()
        assert "title" in body
        assert "version" in body
