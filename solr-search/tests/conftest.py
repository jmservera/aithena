"""Shared fixtures for solr-search tests."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

DUMMY_VECTOR = [round(0.001 * i, 3) for i in range(512)]

SOURCE_DOC = {
    "id": "abc123",
    "file_path_s": "fiction/Author A/Book A.pdf",
    "embedding_v": DUMMY_VECTOR,
    "title_s": "Book A",
    "author_s": "Author A",
    "year_i": 2000,
    "category_s": "fiction",
}

SIMILAR_DOCS = [
    {
        "id": "def456",
        "title_s": "Book B",
        "author_s": "Author B",
        "year_i": 2001,
        "category_s": "fiction",
        "file_path_s": "fiction/Author B/Book B.pdf",
        "score": 0.92,
    },
    {
        "id": "ghi789",
        "title_s": "Book C",
        "author_s": "Author C",
        "year_i": 1999,
        "category_s": "history",
        "file_path_s": "history/Author C/Book C.pdf",
        "score": 0.81,
    },
]


def _solr_response(docs: list[dict], num_found: int | None = None) -> MagicMock:
    """Build a mock requests.Response that returns a Solr JSON response."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {
        "response": {
            "numFound": num_found if num_found is not None else len(docs),
            "start": 0,
            "docs": docs,
        }
    }
    return mock_resp


def _solr_error_response(status_code: int = 500) -> MagicMock:
    """Build a mock requests.Response that raises an HTTPError."""
    import requests

    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = requests.HTTPError(
        response=MagicMock(status_code=status_code)
    )
    return mock_resp


@pytest.fixture()
def mock_requests_get():
    """Patch requests.get inside main.py."""
    with patch("main.requests.get") as mock_get:
        yield mock_get


@pytest.fixture()
def client(mock_requests_get):
    """Return a FastAPI test client with requests.get mocked."""
    import main  # noqa: PLC0415 - imported after mock is patched to avoid module-level QdrantClient init

    return TestClient(main.api_app, raise_server_exceptions=False)
