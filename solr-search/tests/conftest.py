"""Shared fixtures for the Solr search API contract tests."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_DOC = {
    "id": "books/amades/Auca dels costums de Barcelona amades.pdf",
    "title_s": "Auca dels costums de Barcelona",
    "author_s": "Amades",
    "year_i": 1950,
    "category_s": "folklore",
    "language_detected_s": "ca",
    "file_path_s": "amades/Auca dels costums de Barcelona amades.pdf",
    "folder_path_s": "amades",
    "file_size_l": 2048000,
    "page_count_i": 120,
}


def make_solr_response(
    num_found: int = 1,
    docs: list[dict] | None = None,
    facet_fields: dict[str, list] | None = None,
    highlighting: dict | None = None,
    start: int = 0,
) -> dict[str, Any]:
    """Build a minimal valid Solr /select JSON response."""
    if docs is None:
        docs = [SAMPLE_DOC] if num_found > 0 else []
    return {
        "responseHeader": {"status": 0, "QTime": 3},
        "response": {"numFound": num_found, "start": start, "docs": docs},
        "facet_counts": {
            "facet_fields": facet_fields
            if facet_fields is not None
            else {
                "category_s": ["folklore", 3, "history", 1],
                "author_s": ["Amades", 3, "Unknown", 1],
                "language_detected_s": ["ca", 2, "es", 2],
            }
        },
        "highlighting": highlighting
        if highlighting is not None
        else {
            "books/amades/Auca dels costums de Barcelona amades.pdf": {
                "content": ["costums de <em>Barcelona</em> és una obra"],
                "_text_": ["Auca dels costums de <em>Barcelona</em>"],
            }
        },
    }


def _make_httpx_response(payload: dict, status_code: int = 200) -> MagicMock:
    """Return a MagicMock that quacks like an httpx.Response."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = payload
    return mock_resp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    """TestClient for the search app with no real Solr dependency."""
    from main import app

    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def solr_ok(client):
    """Patch httpx so that Solr responds with a single valid document."""
    payload = make_solr_response()
    mock_resp = _make_httpx_response(payload)

    async_cm = AsyncMock()
    async_cm.__aenter__ = AsyncMock(return_value=async_cm)
    async_cm.__aexit__ = AsyncMock(return_value=False)
    async_cm.get = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=async_cm):
        yield client, payload


@pytest.fixture()
def solr_empty(client):
    """Patch httpx so that Solr returns zero documents."""
    payload = make_solr_response(
        num_found=0,
        docs=[],
        facet_fields={"category_s": [], "author_s": [], "language_detected_s": []},
        highlighting={},
    )
    mock_resp = _make_httpx_response(payload)

    async_cm = AsyncMock()
    async_cm.__aenter__ = AsyncMock(return_value=async_cm)
    async_cm.__aexit__ = AsyncMock(return_value=False)
    async_cm.get = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=async_cm):
        yield client, payload


@pytest.fixture()
def solr_error_500(client):
    """Patch httpx so that Solr responds with HTTP 500."""
    mock_resp = _make_httpx_response({"error": "Internal Solr error"}, status_code=500)

    async_cm = AsyncMock()
    async_cm.__aenter__ = AsyncMock(return_value=async_cm)
    async_cm.__aexit__ = AsyncMock(return_value=False)
    async_cm.get = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=async_cm):
        yield client


@pytest.fixture()
def solr_unreachable(client):
    """Patch httpx so that connecting to Solr raises a network error."""
    import httpx as _httpx

    async_cm = AsyncMock()
    async_cm.__aenter__ = AsyncMock(return_value=async_cm)
    async_cm.__aexit__ = AsyncMock(return_value=False)
    async_cm.get = AsyncMock(
        side_effect=_httpx.ConnectError(
            "Connection refused",
            request=_httpx.Request("GET", "http://solr1:8983/solr/books/select"),
        )
    )

    with patch("httpx.AsyncClient", return_value=async_cm):
        yield client
