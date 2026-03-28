"""Tests for the embeddings server.

Uses unittest.mock to patch SentenceTransformer so no model download is required.
Covers both the default e5-base model and e5-family model path tests.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

DEFAULT_MODEL = "intfloat/multilingual-e5-base"
E5_MODEL = "intfloat/multilingual-e5-base"
DEFAULT_DIM = 768
E5_DIM = 768


def _make_mock_model(embedding_dim: int = DEFAULT_DIM) -> MagicMock:
    """Build a minimal SentenceTransformer mock."""
    mock = MagicMock()
    mock.get_sentence_embedding_dimension.return_value = embedding_dim
    mock.encode.side_effect = lambda sentences: np.zeros((len(sentences), embedding_dim), dtype=np.float32)
    return mock


def _fresh_import(model_name: str | None = None, embedding_dim: int = DEFAULT_DIM, *, extra_env: dict | None = None):
    """Import main.py with a mocked model, optionally overriding MODEL_NAME.

    Returns (TestClient, main_module, mock_model, mock_st_class).
    The mock_st_class can be inspected to verify what path was passed.
    """
    mock_model = _make_mock_model(embedding_dim)
    orig = os.environ.get("MODEL_NAME")
    saved_env = {}
    if model_name is not None:
        os.environ["MODEL_NAME"] = model_name
    if extra_env:
        for k, v in extra_env.items():
            saved_env[k] = os.environ.get(k)
            os.environ[k] = v
    try:
        with patch("sentence_transformers.SentenceTransformer", return_value=mock_model) as mock_st_class:
            for key in list(sys.modules):
                if key in ("main", "config"):
                    del sys.modules[key]
            import main as main_module
    finally:
        if model_name is not None:
            if orig is None:
                os.environ.pop("MODEL_NAME", None)
            else:
                os.environ["MODEL_NAME"] = orig
        if extra_env:
            for k, v in saved_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
    client = TestClient(main_module.app)
    return client, main_module, mock_model, mock_st_class


@pytest.fixture()
def app_client():
    """Return a TestClient backed by the default e5-base model (mocked)."""
    client, main_module, _, _ = _fresh_import()
    yield client, main_module


@pytest.fixture()
def e5_client():
    """Return a TestClient with MODEL_NAME set to the e5-base model (mocked)."""
    client, main_module, mock_model, _ = _fresh_import(E5_MODEL, E5_DIM)
    yield client, main_module, mock_model


# ---------------------------------------------------------------------------
# Local path detection (unit-level)
# ---------------------------------------------------------------------------


class TestLocalPathDetection:
    """Verify model_source uses local cached path when present, falls back to hub."""

    def test_uses_local_path_when_directory_exists(self, tmp_path):
        """When SENTENCE_TRANSFORMERS_HOME contains the expected model dir, load from it."""
        model_dir = tmp_path / "intfloat_multilingual-e5-base"
        model_dir.mkdir()
        _, main_mod, _, mock_st = _fresh_import(
            extra_env={"SENTENCE_TRANSFORMERS_HOME": str(tmp_path)},
        )
        call_args = mock_st.call_args
        assert call_args[0][0] == str(model_dir)
        assert main_mod.model_source == str(model_dir)

    def test_falls_back_to_hub_when_no_local_dir(self, tmp_path):
        """When SENTENCE_TRANSFORMERS_HOME has no matching dir, use model name."""
        _, main_mod, _, mock_st = _fresh_import(
            extra_env={"SENTENCE_TRANSFORMERS_HOME": str(tmp_path)},
        )
        call_args = mock_st.call_args
        assert call_args[0][0] == DEFAULT_MODEL
        assert main_mod.model_source == DEFAULT_MODEL


# ---------------------------------------------------------------------------
# Model family detection (unit-level)
# ---------------------------------------------------------------------------


class TestModelFamilyDetection:
    def test_distiluse_is_generic(self):
        from model_utils import detect_model_family

        assert detect_model_family("sentence-transformers/distiluse-base-multilingual-cased-v2") == "generic"

    def test_default_model_is_e5(self):
        from model_utils import detect_model_family

        assert detect_model_family(DEFAULT_MODEL) == "e5"

    def test_e5_base_is_e5(self):
        from model_utils import detect_model_family

        assert detect_model_family(E5_MODEL) == "e5"

    def test_e5_large_is_e5(self):
        from model_utils import detect_model_family

        assert detect_model_family("intfloat/multilingual-e5-large") == "e5"

    def test_case_insensitive(self):
        from model_utils import detect_model_family

        assert detect_model_family("intfloat/Multilingual-E5-Base") == "e5"

    def test_unknown_model_is_generic(self):
        from model_utils import detect_model_family

        assert detect_model_family("some-other/model") == "generic"


# ---------------------------------------------------------------------------
# Prefix application (unit-level)
# ---------------------------------------------------------------------------


class TestApplyPrefix:
    def test_e5_query_prefix(self):
        from model_utils import apply_prefix

        result = apply_prefix(["find books"], "e5", "query")
        assert result == ["query: find books"]

    def test_e5_passage_prefix(self):
        from model_utils import apply_prefix

        result = apply_prefix(["some passage text"], "e5", "passage")
        assert result == ["passage: some passage text"]

    def test_generic_no_prefix_for_query(self):
        from model_utils import apply_prefix

        result = apply_prefix(["hello"], "generic", "query")
        assert result == ["hello"]

    def test_generic_no_prefix_for_passage(self):
        from model_utils import apply_prefix

        result = apply_prefix(["hello"], "generic", "passage")
        assert result == ["hello"]

    def test_multiple_texts_prefixed(self):
        from model_utils import apply_prefix

        texts = ["first", "second", "third"]
        result = apply_prefix(texts, "e5", "query")
        assert result == ["query: first", "query: second", "query: third"]


# ---------------------------------------------------------------------------
# Default model (e5-base) — tests for the primary model path
# ---------------------------------------------------------------------------


class TestModelInfo:
    def test_model_name_is_e5(self, app_client):
        """The active model must be multilingual-e5-base."""
        client, main_module = app_client
        assert main_module.MODEL_NAME == DEFAULT_MODEL

    def test_model_info_endpoint_returns_correct_fields(self, app_client):
        """/v1/embeddings/model returns model name, dim, family, and requires_prefix."""
        client, _ = app_client
        response = client.get("/v1/embeddings/model")
        assert response.status_code == 200
        data = response.json()
        assert data["model"] == DEFAULT_MODEL
        assert data["embedding_dim"] == DEFAULT_DIM
        assert data["model_family"] == "e5"
        assert data["requires_prefix"] is True

    def test_embedding_dim_matches_model(self, app_client):
        """The reported embedding_dim must match the value from the loaded model."""
        _, main_module = app_client
        assert main_module.embedding_dim == DEFAULT_DIM


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
            "device": "cpu",
            "backend": "torch",
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
        assert len(data["data"][0]["embedding"]) == DEFAULT_DIM

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
        """When input_type is omitted, it defaults to 'passage'."""
        client, _ = app_client
        response = client.post("/v1/embeddings/", json={"input": "test"})
        assert response.status_code == 200

    def test_e5_default_accepts_input_type_query(self, app_client):
        """For the default e5 model, passing input_type='query' works correctly."""
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
        assert data["embedding_dim"] == DEFAULT_DIM

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
