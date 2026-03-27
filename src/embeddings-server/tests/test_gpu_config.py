"""Tests for GPU device/backend configuration.

Validates DEVICE and BACKEND environment variable handling,
SentenceTransformer initialization kwargs, and endpoint exposure
of GPU configuration.

Tests that depend on Parker's GPU config implementation are marked
with @pytest.mark.xfail so CI stays green until the feature lands.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

DEFAULT_MODEL = "intfloat/multilingual-e5-base"
DEFAULT_DIM = 768


def _make_mock_model(embedding_dim: int = DEFAULT_DIM) -> MagicMock:
    """Build a minimal SentenceTransformer mock."""
    mock = MagicMock()
    mock.get_sentence_embedding_dimension.return_value = embedding_dim
    mock.encode.side_effect = lambda sentences: np.zeros(
        (len(sentences), embedding_dim), dtype=np.float32
    )
    return mock


def _fresh_import(
    model_name: str | None = None,
    embedding_dim: int = DEFAULT_DIM,
    device: str | None = None,
    backend: str | None = None,
):
    """Import main.py with a mocked model, optionally setting DEVICE/BACKEND.

    Returns (TestClient, main_module, mock_model, mock_st_class).
    """
    mock_model = _make_mock_model(embedding_dim)

    env_overrides: dict[str, str] = {}
    if model_name is not None:
        env_overrides["MODEL_NAME"] = model_name
    if device is not None:
        env_overrides["DEVICE"] = device
    if backend is not None:
        env_overrides["BACKEND"] = backend

    orig_env = {k: os.environ.get(k) for k in env_overrides}
    for k, v in env_overrides.items():
        os.environ[k] = v

    try:
        with patch(
            "sentence_transformers.SentenceTransformer", return_value=mock_model
        ) as mock_st_class:
            for key in list(sys.modules):
                if key in ("main", "config"):
                    del sys.modules[key]
            import main as main_module
    finally:
        for k, orig in orig_env.items():
            if orig is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = orig

    client = TestClient(main_module.app)
    return client, main_module, mock_model, mock_st_class


# ---------------------------------------------------------------------------
# Config tests — DEVICE and BACKEND env var defaults and overrides
# ---------------------------------------------------------------------------


class TestGpuConfig:
    @pytest.mark.xfail(reason="Requires GPU config implementation")
    def test_default_device_is_cpu(self):
        """DEVICE defaults to 'cpu' when not set."""
        os.environ.pop("DEVICE", None)
        for key in list(sys.modules):
            if key == "config":
                del sys.modules[key]
        from config import DEVICE

        assert DEVICE == "cpu"

    @pytest.mark.xfail(reason="Requires GPU config implementation")
    def test_default_backend_is_torch(self):
        """BACKEND defaults to 'torch' when not set."""
        os.environ.pop("BACKEND", None)
        for key in list(sys.modules):
            if key == "config":
                del sys.modules[key]
        from config import BACKEND

        assert BACKEND == "torch"

    @pytest.mark.xfail(reason="Requires GPU config implementation")
    def test_device_from_env(self):
        """DEVICE reads from environment variable."""
        os.environ["DEVICE"] = "cuda"
        try:
            for key in list(sys.modules):
                if key == "config":
                    del sys.modules[key]
            from config import DEVICE

            assert DEVICE == "cuda"
        finally:
            os.environ.pop("DEVICE", None)

    @pytest.mark.xfail(reason="Requires GPU config implementation")
    def test_backend_from_env(self):
        """BACKEND reads from environment variable."""
        os.environ["BACKEND"] = "openvino"
        try:
            for key in list(sys.modules):
                if key == "config":
                    del sys.modules[key]
            from config import BACKEND

            assert BACKEND == "openvino"
        finally:
            os.environ.pop("BACKEND", None)


# ---------------------------------------------------------------------------
# Model initialization tests — SentenceTransformer constructor kwargs
# ---------------------------------------------------------------------------


class TestGpuModelInit:
    def test_cpu_torch_no_extra_kwargs(self):
        """With DEVICE=cpu, BACKEND=torch (defaults), SentenceTransformer gets no extra kwargs."""
        _, _, _, mock_st_class = _fresh_import()
        call_kwargs = mock_st_class.call_args
        # Default invocation: just the model name, no device/backend
        assert call_kwargs[0] == (DEFAULT_MODEL,)
        assert "device" not in call_kwargs[1]
        assert "backend" not in call_kwargs[1]

    @pytest.mark.xfail(reason="Requires GPU config implementation")
    def test_cuda_passes_device(self):
        """With DEVICE=cuda, SentenceTransformer gets device='cuda'."""
        _, _, _, mock_st_class = _fresh_import(device="cuda")
        call_kwargs = mock_st_class.call_args
        assert call_kwargs[1].get("device") == "cuda"

    @pytest.mark.xfail(reason="Requires GPU config implementation")
    def test_xpu_passes_device(self):
        """With DEVICE=xpu, SentenceTransformer gets device='xpu'."""
        _, _, _, mock_st_class = _fresh_import(device="xpu")
        call_kwargs = mock_st_class.call_args
        assert call_kwargs[1].get("device") == "xpu"

    @pytest.mark.xfail(reason="Requires GPU config implementation")
    def test_openvino_passes_backend(self):
        """With BACKEND=openvino, SentenceTransformer gets backend='openvino'."""
        _, _, _, mock_st_class = _fresh_import(backend="openvino")
        call_kwargs = mock_st_class.call_args
        assert call_kwargs[1].get("backend") == "openvino"

    def test_auto_device_passes_none(self):
        """With DEVICE=auto, device parameter is not passed (let PyTorch decide)."""
        _, _, _, mock_st_class = _fresh_import(device="auto")
        call_kwargs = mock_st_class.call_args
        assert "device" not in call_kwargs[1]

    @pytest.mark.xfail(reason="Requires GPU config implementation")
    def test_cuda_with_openvino(self):
        """With DEVICE=cuda + BACKEND=openvino, both params are passed."""
        _, _, _, mock_st_class = _fresh_import(device="cuda", backend="openvino")
        call_kwargs = mock_st_class.call_args
        assert call_kwargs[1].get("device") == "cuda"
        assert call_kwargs[1].get("backend") == "openvino"


# ---------------------------------------------------------------------------
# Health endpoint tests — device/backend fields in /health response
# ---------------------------------------------------------------------------


class TestGpuHealthEndpoint:
    @pytest.mark.xfail(reason="Requires GPU config implementation")
    def test_health_includes_device(self):
        """Health endpoint response includes device field."""
        client, _, _, _ = _fresh_import()
        response = client.get("/health")
        assert response.status_code == 200
        assert "device" in response.json()

    @pytest.mark.xfail(reason="Requires GPU config implementation")
    def test_health_includes_backend(self):
        """Health endpoint response includes backend field."""
        client, _, _, _ = _fresh_import()
        response = client.get("/health")
        assert response.status_code == 200
        assert "backend" in response.json()

    @pytest.mark.xfail(reason="Requires GPU config implementation")
    def test_health_default_values(self):
        """Health endpoint shows cpu/torch by default."""
        client, _, _, _ = _fresh_import()
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["device"] == "cpu"
        assert data["backend"] == "torch"


# ---------------------------------------------------------------------------
# Version endpoint tests — device/backend in /version response
# ---------------------------------------------------------------------------


class TestGpuVersionEndpoint:
    @pytest.mark.xfail(reason="Requires GPU config implementation")
    def test_version_includes_device_and_backend(self):
        """Version endpoint includes device and backend fields."""
        client, _, _, _ = _fresh_import()
        response = client.get("/version")
        assert response.status_code == 200
        data = response.json()
        assert "device" in data
        assert "backend" in data
        assert data["device"] == "cpu"
        assert data["backend"] == "torch"


# ---------------------------------------------------------------------------
# Backward compatibility tests — existing behavior unchanged
# ---------------------------------------------------------------------------


class TestGpuBackwardCompat:
    def test_existing_embeddings_still_work(self):
        """Embeddings endpoint produces same output with default GPU config."""
        client, _, _, _ = _fresh_import()
        response = client.post(
            "/v1/embeddings/", json={"input": "hello world"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        assert len(data["data"]) == 1
        assert len(data["data"][0]["embedding"]) == DEFAULT_DIM

    def test_model_info_unchanged(self):
        """/v1/embeddings/model returns same data regardless of GPU config."""
        client, _, _, _ = _fresh_import()
        response = client.get("/v1/embeddings/model")
        assert response.status_code == 200
        data = response.json()
        assert data["model"] == DEFAULT_MODEL
        assert data["embedding_dim"] == DEFAULT_DIM
        assert data["model_family"] == "e5"
        assert data["requires_prefix"] is True
