"""Tests for the embeddings server.

Uses unittest.mock to patch SentenceTransformer so no model download is required.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

DEFAULT_MODEL = "sentence-transformers/distiluse-base-multilingual-cased-v2"
EMBEDDING_DIM = 512


def _make_mock_model(embedding_dim: int = EMBEDDING_DIM) -> MagicMock:
    """Build a minimal SentenceTransformer mock."""
    mock = MagicMock()
    mock.get_sentence_embedding_dimension.return_value = embedding_dim
    mock.encode.side_effect = lambda sentences: np.zeros(
        (len(sentences), embedding_dim), dtype=np.float32
    )
    return mock


@pytest.fixture()
def app_client(monkeypatch):
    """Return a TestClient backed by a freshly imported main module (model mocked)."""
    mock_model = _make_mock_model()

    # Patch SentenceTransformer before main.py is imported so the module-level
    # instantiation is intercepted.
    with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
        # Remove cached module so we get a fresh import each test run.
        for key in list(sys.modules):
            if key == "main":
                del sys.modules[key]

        import main as main_module

    client = TestClient(main_module.app)
    yield client, main_module


class TestModelInfo:
    def test_model_name_is_distiluse(self, app_client):
        """The active model must be the ADR-004 standard model."""
        client, main_module = app_client
        assert main_module.MODEL_NAME == DEFAULT_MODEL

    def test_model_info_endpoint_returns_correct_fields(self, app_client):
        """/v1/embeddings/model returns model name and embedding_dim."""
        client, _ = app_client
        response = client.get("/v1/embeddings/model")
        assert response.status_code == 200
        data = response.json()
        assert data["model"] == DEFAULT_MODEL
        assert data["embedding_dim"] == EMBEDDING_DIM

    def test_embedding_dim_matches_model(self, app_client):
        """The reported embedding_dim must match the value from the loaded model."""
        _, main_module = app_client
        assert main_module.embedding_dim == EMBEDDING_DIM


class TestEmbeddingsEndpoint:
    def test_single_string_input(self, app_client):
        """A single string must be accepted and return one embedding."""
        client, _ = app_client
        response = client.post("/v1/embeddings/", json={"input": "hello world"})
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        assert len(data["data"]) == 1
        assert len(data["data"][0]["embedding"]) == EMBEDDING_DIM

    def test_list_input(self, app_client):
        """A list of strings must produce one embedding per item."""
        client, _ = app_client
        sentences = ["first sentence", "second sentence", "third sentence"]
        response = client.post("/v1/embeddings/", json={"input": sentences})
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == len(sentences)

    def test_response_model_field(self, app_client):
        """The response model field must match the configured model name."""
        client, _ = app_client
        response = client.post("/v1/embeddings/", json={"input": "test"})
        assert response.status_code == 200
        assert response.json()["model"] == DEFAULT_MODEL

    def test_embedding_object_field(self, app_client):
        """Each embedding entry must have object='embedding'."""
        client, _ = app_client
        response = client.post("/v1/embeddings/", json={"input": "test"})
        assert response.json()["data"][0]["object"] == "embedding"


class TestStartupFailure:
    def test_startup_fails_when_model_unavailable(self):
        """sys.exit must be called when the model cannot be loaded."""
        for key in list(sys.modules):
            if key == "main":
                del sys.modules[key]

        import os

        orig_model_name = os.environ.get("MODEL_NAME")
        os.environ["MODEL_NAME"] = "nonexistent/model-that-does-not-exist"
        # Also patch config to reflect the env change before main imports it
        if "config" in sys.modules:
            del sys.modules["config"]

        try:
            with patch(
                "sentence_transformers.SentenceTransformer",
                side_effect=OSError("model not found"),
            ):
                with pytest.raises(SystemExit) as exc_info:
                    import main  # noqa: F401
                assert exc_info.value.code == 1
        finally:
            if orig_model_name is None:
                os.environ.pop("MODEL_NAME", None)
            else:
                os.environ["MODEL_NAME"] = orig_model_name
            for key in list(sys.modules):
                if key in ("main", "config"):
                    del sys.modules[key]
