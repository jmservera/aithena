"""Tests for the embeddings server.

Uses unittest.mock to patch SentenceTransformer so no model download is required.
Covers both distiluse (generic) and e5-family model paths.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

DEFAULT_MODEL = "sentence-transformers/distiluse-base-multilingual-cased-v2"
E5_MODEL = "intfloat/multilingual-e5-base"
DISTILUSE_DIM = 512
E5_DIM = 768


def _make_mock_model(embedding_dim: int = DISTILUSE_DIM) -> MagicMock:
    """Build a minimal SentenceTransformer mock."""
    mock = MagicMock()
    mock.get_sentence_embedding_dimension.return_value = embedding_dim
    mock.encode.side_effect = lambda sentences: np.zeros((len(sentences), embedding_dim), dtype=np.float32)
    return mock


def _fresh_import(model_name: str | None = None, embedding_dim: int = DISTILUSE_DIM):
    """Import main.py with a mocked model, optionally overriding MODEL_NAME.

    Returns (TestClient, main_module, mock_model).
    """
    mock_model = _make_mock_model(embedding_dim)
    orig = os.environ.get("MODEL_NAME")
    if model_name is not None:
        os.environ["MODEL_NAME"] = model_name
    try:
        with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
            for key in list(sys.modules):
                if key in ("main", "config"):
                    del sys.modules[key]
            import main as main_module
    finally:
        # Restore env
        if model_name is not None:
            if orig is None:
                os.environ.pop("MODEL_NAME", None)
            else:
                os.environ["MODEL_NAME"] = orig
    client = TestClient(main_module.app)
    return client, main_module, mock_model


@pytest.fixture()
def app_client():
    """Return a TestClient backed by the default distiluse model (mocked)."""
    client, main_module, _ = _fresh_import()
    yield client, main_module


@pytest.fixture()
def e5_client():
    """Return a TestClient with MODEL_NAME set to the e5-base model (mocked)."""
    client, main_module, mock_model = _fresh_import(E5_MODEL, E5_DIM)
    yield client, main_module, mock_model


# ---------------------------------------------------------------------------
# Model family detection (unit-level)
# ---------------------------------------------------------------------------


class TestModelFamilyDetection:
    def test_distiluse_is_generic(self):
        from main import detect_model_family

        assert detect_model_family(DEFAULT_MODEL) == "generic"

    def test_e5_base_is_e5(self):
        from main import detect_model_family

        assert detect_model_family(E5_MODEL) == "e5"

    def test_e5_large_is_e5(self):
        from main import detect_model_family

        assert detect_model_family("intfloat/multilingual-e5-large") == "e5"

    def test_case_insensitive(self):
        from main import detect_model_family

        assert detect_model_family("intfloat/Multilingual-E5-Base") == "e5"

    def test_unknown_model_is_generic(self):
        from main import detect_model_family

        assert detect_model_family("some-other/model") == "generic"


# ---------------------------------------------------------------------------
# Prefix application (unit-level)
# ---------------------------------------------------------------------------


class TestApplyPrefix:
    def test_e5_query_prefix(self):
        from main import apply_prefix

        result = apply_prefix(["find books"], "e5", "query")
        assert result == ["query: find books"]

    def test_e5_passage_prefix(self):
        from main import apply_prefix

        result = apply_prefix(["some passage text"], "e5", "passage")
        assert result == ["passage: some passage text"]

    def test_generic_no_prefix_for_query(self):
        from main import apply_prefix

        result = apply_prefix(["hello"], "generic", "query")
        assert result == ["hello"]

    def test_generic_no_prefix_for_passage(self):
        from main import apply_prefix

        result = apply_prefix(["hello"], "generic", "passage")
        assert result == ["hello"]

    def test_multiple_texts_prefixed(self):
        from main import apply_prefix

        texts = ["first", "second", "third"]
        result = apply_prefix(texts, "e5", "query")
        assert result == ["query: first", "query: second", "query: third"]


# ---------------------------------------------------------------------------
# Distiluse (default) model — backward compatibility
# ---------------------------------------------------------------------------


class TestModelInfo:
    def test_model_name_is_distiluse(self, app_client):
        """The active model must be the ADR-004 standard model."""
        client, main_module = app_client
        assert main_module.MODEL_NAME == DEFAULT_MODEL

    def test_model_info_endpoint_returns_correct_fields(self, app_client):
        """/v1/embeddings/model returns model name, dim, family, and requires_prefix."""
        client, _ = app_client
        response = client.get("/v1/embeddings/model")
        assert response.status_code == 200
        data = response.json()
        assert data["model"] == DEFAULT_MODEL
        assert data["embedding_dim"] == DISTILUSE_DIM
        assert data["model_family"] == "generic"
        assert data["requires_prefix"] is False

    def test_embedding_dim_matches_model(self, app_client):
        """The reported embedding_dim must match the value from the loaded model."""
        _, main_module = app_client
        assert main_module.embedding_dim == DISTILUSE_DIM


class TestVersionEndpoint:
    def test_version_endpoint_returns_build_metadata(self, app_client):
        """/version returns service build metadata including model name."""
        client, main_module = app_client
        response = client.get("/version")
        assert response.status_code == 200
        data = response.json()
        assert data == {
            "service": "embeddings-server",
            "version": main_module.VERSION,
            "commit": main_module.GIT_COMMIT,
            "built": main_module.BUILD_DATE,
            "model": DEFAULT_MODEL,
        }


class TestEmbeddingsEndpoint:
    def test_single_string_input(self, app_client):
        """A single string must be accepted and return one embedding."""
        client, _ = app_client
        response = client.post("/v1/embeddings/", json={"input": "hello world"})
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        assert len(data["data"]) == 1
        assert len(data["data"][0]["embedding"]) == DISTILUSE_DIM

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

    def test_default_input_type_is_passage(self, app_client):
        """When input_type is omitted, it defaults to 'passage' (backward compat)."""
        client, _ = app_client
        response = client.post("/v1/embeddings/", json={"input": "test"})
        assert response.status_code == 200

    def test_distiluse_ignores_input_type_query(self, app_client):
        """For distiluse, passing input_type='query' must not alter behaviour."""
        client, _ = app_client
        response = client.post("/v1/embeddings/", json={"input": "test", "input_type": "query"})
        assert response.status_code == 200
        assert len(response.json()["data"]) == 1


class TestHealthEndpoint:
    def test_health_get(self, app_client):
        client, _ = app_client
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["model"] == DEFAULT_MODEL
        assert data["embedding_dim"] == DISTILUSE_DIM

    def test_health_head(self, app_client):
        client, _ = app_client
        response = client.head("/health")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# E5-base model path
# ---------------------------------------------------------------------------


class TestE5ModelInfo:
    def test_model_family_is_e5(self, e5_client):
        _, main_module, _ = e5_client
        assert main_module.model_family == "e5"

    def test_model_info_endpoint_e5(self, e5_client):
        client, _, _ = e5_client
        response = client.get("/v1/embeddings/model")
        assert response.status_code == 200
        data = response.json()
        assert data["model"] == E5_MODEL
        assert data["embedding_dim"] == E5_DIM
        assert data["model_family"] == "e5"
        assert data["requires_prefix"] is True

    def test_embedding_dim_768(self, e5_client):
        _, main_module, _ = e5_client
        assert main_module.embedding_dim == E5_DIM


class TestE5VersionEndpoint:
    def test_version_includes_model_name(self, e5_client):
        client, _, _ = e5_client
        response = client.get("/version")
        assert response.status_code == 200
        assert response.json()["model"] == E5_MODEL


class TestE5Embeddings:
    def test_query_prefix_applied(self, e5_client):
        """For e5 model with input_type='query', the mock must receive 'query: ...' prefixed text."""
        client, _, mock_model = e5_client
        response = client.post("/v1/embeddings/", json={"input": "find books", "input_type": "query"})
        assert response.status_code == 200
        call_args = mock_model.encode.call_args[0][0]
        assert call_args == ["query: find books"]

    def test_passage_prefix_applied(self, e5_client):
        """For e5 model with input_type='passage', the mock must receive 'passage: ...' prefixed text."""
        client, _, mock_model = e5_client
        response = client.post("/v1/embeddings/", json={"input": "some document text", "input_type": "passage"})
        assert response.status_code == 200
        call_args = mock_model.encode.call_args[0][0]
        assert call_args == ["passage: some document text"]

    def test_default_input_type_is_passage_for_e5(self, e5_client):
        """Omitting input_type defaults to 'passage' — backward compat for indexing callers."""
        client, _, mock_model = e5_client
        response = client.post("/v1/embeddings/", json={"input": "raw text"})
        assert response.status_code == 200
        call_args = mock_model.encode.call_args[0][0]
        assert call_args == ["passage: raw text"]

    def test_list_input_all_prefixed(self, e5_client):
        """All items in a list input must get the prefix."""
        client, _, mock_model = e5_client
        texts = ["first", "second"]
        response = client.post("/v1/embeddings/", json={"input": texts, "input_type": "query"})
        assert response.status_code == 200
        call_args = mock_model.encode.call_args[0][0]
        assert call_args == ["query: first", "query: second"]

    def test_e5_returns_768_dim(self, e5_client):
        client, _, _ = e5_client
        response = client.post("/v1/embeddings/", json={"input": "test"})
        assert response.status_code == 200
        assert len(response.json()["data"][0]["embedding"]) == E5_DIM


class TestE5Health:
    def test_health_with_e5(self, e5_client):
        client, _, _ = e5_client
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["model"] == E5_MODEL
        assert data["embedding_dim"] == E5_DIM


# ---------------------------------------------------------------------------
# Startup failure
# ---------------------------------------------------------------------------


class TestStartupFailure:
    def test_startup_fails_when_model_unavailable(self):
        """sys.exit must be called when the model cannot be loaded."""
        for key in list(sys.modules):
            if key == "main":
                del sys.modules[key]

        orig_model_name = os.environ.get("MODEL_NAME")
        os.environ["MODEL_NAME"] = "nonexistent/model-that-does-not-exist"
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
