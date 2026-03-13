"""Shared fixtures for qdrant-search tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _make_record(point_id: str, vector: list[float], payload: dict):
    """Build a minimal mock object that mimics a qdrant_client Record."""
    record = MagicMock()
    record.id = point_id
    record.vector = vector
    record.payload = payload
    return record


def _make_scored_point(point_id: str, score: float, payload: dict):
    """Build a minimal mock object that mimics a qdrant_client ScoredPoint."""
    sp = MagicMock()
    sp.id = point_id
    sp.score = score
    sp.payload = payload
    return sp


DUMMY_VECTOR = [0.1] * 512

SOURCE_PAYLOAD = {
    "text": "Source book text chunk.",
    "path": "fiction/Author A/Book A.pdf",
    "page": 1,
    "title": "Book A",
    "author": "Author A",
    "year": 2000,
    "category": "fiction",
}

SIMILAR_PAYLOADS = [
    {
        "text": "Similar book one text chunk.",
        "path": "fiction/Author B/Book B.pdf",
        "page": 1,
        "title": "Book B",
        "author": "Author B",
        "year": 2001,
        "category": "fiction",
    },
    {
        "text": "Similar book two text chunk.",
        "path": "history/Author C/Book C.pdf",
        "page": 2,
        "title": "Book C",
        "author": "Author C",
        "year": 1999,
        "category": "history",
    },
]


@pytest.fixture()
def mock_qdrant():
    """Patch the module-level QdrantClient instance used by main.py."""
    with patch("main.qdrant") as mock_client:
        yield mock_client


@pytest.fixture()
def client(mock_qdrant):
    """Return a FastAPI test client with the Qdrant client mocked."""
    import main  # noqa: PLC0415 - imported here so mock is already in place

    return TestClient(main.api_app, raise_server_exceptions=False)
