#!/usr/bin/env python

import contextlib
import logging
import os
import sys
from typing import Literal

import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel
from quantization import quantize_embedding, validate_quantization_quality
from sentence_transformers import SentenceTransformer

from config import (
    BACKEND,
    BUILD_DATE,
    DEVICE,
    GIT_COMMIT,
    MODEL_NAME,
    PORT,
    VECTOR_QUANTIZATION,
    VECTOR_QUANTIZATION_VALIDATE,
    VERSION,
)
from model_utils import apply_prefix, detect_model_family

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

model_family = detect_model_family(MODEL_NAME)

# Resolve device: "auto" means let PyTorch decide
device = None if DEVICE == "auto" else DEVICE

# Build kwargs for SentenceTransformer
model_kwargs = {}
if BACKEND == "openvino":
    model_kwargs["backend"] = BACKEND
    # OpenVINO uses its own device names (CPU, GPU, AUTO), not PyTorch names (cpu, xpu, cuda).
    # The device must be passed via model_kwargs so it reaches OVModel.from_pretrained(),
    # not as the top-level 'device' param which only controls PyTorch's .to().
    _ov_device_map = {"xpu": "GPU", "gpu": "GPU", "cuda": "GPU", "auto": "AUTO", "cpu": "CPU"}
    ov_device = _ov_device_map.get(device, "CPU") if device else "CPU"
    if ov_device != "CPU":
        model_kwargs["model_kwargs"] = {"device": ov_device}
    # optimum-intel sets CACHE_DIR to {model_dir}/model_cache when device is GPU,
    # which fails if /models/ is read-only. Override via ov_config so the compiled
    # model cache goes to a writable location instead.
    _ov_cache = os.environ.get("OPENVINO_CACHE_DIR", "").strip() or "/tmp/ov_cache"  # noqa: S108
    model_kwargs["model_kwargs"] = {
        **model_kwargs.get("model_kwargs", {}),
        "ov_config": {"CACHE_DIR": _ov_cache},
    }
elif BACKEND != "torch":
    model_kwargs["backend"] = BACKEND
    if device and device != "cpu":
        model_kwargs["device"] = device
else:
    if device and device != "cpu":
        model_kwargs["device"] = device

# Check if model is pre-cached locally (base image saves to this path)
_st_home = os.environ.get("SENTENCE_TRANSFORMERS_HOME", "/models/sentence_transformers")
local_model_path = os.path.join(_st_home, MODEL_NAME.replace("/", "_"))

if os.path.isdir(local_model_path):
    model_source = local_model_path
    _source_label = "local-cache"
elif os.path.isdir(MODEL_NAME) or os.path.isfile(MODEL_NAME):
    model_source = MODEL_NAME
    _source_label = "local-path"
else:
    model_source = MODEL_NAME
    _source_label = "hub"

logger.info(
    "Loading embedding model: %s (family=%s, device=%s, backend=%s, source=%s, quantization=%s)",
    MODEL_NAME,
    model_family,
    DEVICE,
    BACKEND,
    _source_label,
    VECTOR_QUANTIZATION,
)

try:
    model = SentenceTransformer(model_source, **model_kwargs)
    embedding_dim = model.get_sentence_embedding_dimension()
    # OVBaseModel.device always returns torch.device("cpu"); show the real OV device instead
    _reported_device = model.device
    if BACKEND == "openvino":
        with contextlib.suppress(AttributeError, IndexError):
            _reported_device = model[0].auto_model._device
    logger.info(
        "Model loaded successfully: %s (embedding_dim=%d, backend=%s, device=%s)",
        MODEL_NAME,
        embedding_dim,
        model.backend,
        _reported_device,
    )
except Exception as exc:
    logger.critical("Failed to load embedding model '%s': %s (%s)", MODEL_NAME, exc, type(exc).__name__)
    logger.debug("Model loading stack trace:", exc_info=True)
    sys.exit(1)

app = FastAPI(title="𐃆 Aithena Embeddings API", version=VERSION)


class EmbeddingsInput(BaseModel):
    """Input definition for embeddings endpoint. Takes a list of strings or a single string."""

    input: str | list[str]
    input_type: Literal["query", "passage"] = "passage"


class EmbeddingsOutput(BaseModel):
    """Output definition for embeddings endpoint. Returns a list of embeddings."""

    class EmbeddingsList(BaseModel):
        """The list of embeddings."""

        object: str = "embedding"
        embedding: list[int | float] = []
        field_name: str = "embedding"

    class Usage(BaseModel):
        """Usage statistics. Not used, just for compatibility with LLaMA.cpp API."""

        prompt_tokens: int
        total_tokens: int

    object: str = "list"
    data: list[EmbeddingsList] = []
    model: str = MODEL_NAME
    usage: Usage = None


class ModelInfo(BaseModel):
    """Active model metadata for downstream consumers (e.g. Solr vector field sizing)."""

    model: str
    embedding_dim: int
    model_family: str
    requires_prefix: bool


@app.head("/health")
@app.get("/health")
async def health():
    """Health check endpoint for container orchestration."""
    return {
        "status": "healthy",
        "model": MODEL_NAME,
        "embedding_dim": embedding_dim,
        "device": DEVICE,
        "backend": BACKEND,
    }


@app.get("/v1/embeddings/model")
async def model_info_endpoint() -> ModelInfo:
    """Returns the active embedding model name and its output dimension."""
    return ModelInfo(
        model=MODEL_NAME,
        embedding_dim=embedding_dim,
        model_family=model_family,
        requires_prefix=model_family == "e5",
    )


@app.get("/version", include_in_schema=False)
async def version() -> dict[str, str]:
    """Returns service build metadata."""
    return {
        "service": "embeddings-server",
        "version": VERSION,
        "commit": GIT_COMMIT,
        "built": BUILD_DATE,
        "model": MODEL_NAME,
        "device": DEVICE,
        "backend": BACKEND,
    }


@app.post("/v1/embeddings/")
async def embeddings(sentences: EmbeddingsInput):
    """Generates embeddings for a list of sentences."""
    result = EmbeddingsOutput()
    texts = sentences.input if isinstance(sentences.input, list) else [sentences.input]
    texts = apply_prefix(texts, model_family, sentences.input_type)
    encoded = model.encode(texts)
    for r in encoded:
        original = np.asarray(r)
        quantized, field_name = quantize_embedding(original, VECTOR_QUANTIZATION)
        if VECTOR_QUANTIZATION_VALIDATE and VECTOR_QUANTIZATION != "none":
            validate_quantization_quality(original, quantized)
        result.data.append(
            EmbeddingsOutput.EmbeddingsList(
                embedding=[int(x) if quantized.dtype == np.int8 else float(x) for x in quantized],
                field_name=field_name,
            )
        )
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)
