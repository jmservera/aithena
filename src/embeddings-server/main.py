#!/usr/bin/env python

import logging
import sys

from config import BUILD_DATE, GIT_COMMIT, MODEL_NAME, PORT, VERSION
from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Loading embedding model: %s", MODEL_NAME)
try:
    model = SentenceTransformer(MODEL_NAME)
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


@app.head("/health")
@app.get("/health")
async def health():
    """Health check endpoint for container orchestration."""
    return {"status": "healthy", "model": MODEL_NAME, "embedding_dim": embedding_dim}


@app.get("/v1/embeddings/model")
async def model_info() -> ModelInfo:
    """Returns the active embedding model name and its output dimension."""
    return ModelInfo(model=MODEL_NAME, embedding_dim=embedding_dim)


@app.get("/version", include_in_schema=False)
async def version() -> dict[str, str]:
    """Returns service build metadata."""
    return {
        "service": "embeddings-server",
        "version": VERSION,
        "commit": GIT_COMMIT,
        "built": BUILD_DATE,
    }


@app.post("/v1/embeddings/")
async def embeddings(sentences: EmbeddingsInput):
    """Generates embeddings for a list of sentences."""
    result = EmbeddingsOutput()
    if isinstance(sentences.input, str):
        sentences.input = [sentences.input]
    embeddings = model.encode(sentences.input)
    for r in embeddings:
        result.data.append(EmbeddingsOutput.EmbeddingsList(embedding=list(r)))
    return result


if __name__ == "__main__":
    # run flask app for debugging
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)
