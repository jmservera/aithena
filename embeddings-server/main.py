#!/usr/bin/env python
# encoding: utf-8

from config import *
from fastapi import FastAPI

from pydantic import BaseModel
from typing import Union

from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/use-cmlm-multilingual"

model = SentenceTransformer(MODEL_NAME)

app = FastAPI(title="𐃆 Aithena Embeddings API")


class EmbeddingsInput(BaseModel):
    """Input definition for embeddings endpoint. Takes a list of strings or a single string."""
    input: Union[str, list[str]]


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


@app.post("/v1/embeddings/")
async def embeddings(sentences: EmbeddingsInput):
    """Generates embeddings for a list of sentences."""
    result = EmbeddingsOutput()
    if isinstance(sentences.input, str):
        sentences.input = [sentences.input]
    embeddings = model.encode(sentences.input)
    for r in embeddings:
        result.data.append(EmbeddingsOutput.EmbeddingsList(embedding=r))
    return result


if __name__ == "__main__":
    # run flask app for debugging
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)
