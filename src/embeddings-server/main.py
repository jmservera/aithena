#!/usr/bin/env python

import logging
import sys
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

from config import BACKEND, BUILD_DATE, DEVICE, GIT_COMMIT, MODEL_NAME, PORT, VERSION
from model_utils import apply_prefix, detect_model_family

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

model_family = detect_model_family(MODEL_NAME)

# Resolve device: "auto" means let PyTorch decide
device = None if DEVICE == "auto" else DEVICE

# Build kwargs for SentenceTransformer
model_kwargs = {}
if device and device != "cpu":
    model_kwargs["device"] = device
if BACKEND != "torch":
    model_kwargs["backend"] = BACKEND

logger.info("Loading embedding model: %s (family=%s, device=%s, backend=%s)", MODEL_NAME, model_family, DEVICE, BACKEND)

try:
    model = SentenceTransformer(MODEL_NAME, **model_kwargs)
    embedding_dim = model.get_sentence_embedding_dimension()
    logger.info("Model loaded successfully: %s (embedding_dim=%d)", MODEL_NAME, embedding_dim)
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
        embedding: list[float] = []

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
    return {"status": "healthy", "model": MODEL_NAME, "embedding_dim": embedding_dim, "device": DEVICE, "backend": BACKEND}


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
        result.data.append(EmbeddingsOutput.EmbeddingsList(embedding=list(r)))
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)
