# Parker — Embeddings Dockerfile Alignment

**Author:** Parker (Backend Dev)  
**Date:** 2026-03-15  
**Status:** PROPOSED

## Context

The repository's `embeddings-server` implementation is a custom FastAPI application that exposes `POST /v1/embeddings/` and `GET /v1/embeddings/model` for downstream consumers. The previous Dockerfile used the Weaviate `semitechnologies/transformers-inference:custom` base image, which serves a different API shape (`/vectors/` on port 8080) and never starts the repo's `main.py`.

## Decision

Build `embeddings-server` from `python:3.11-slim`, install `requirements.txt`, preload the configured SentenceTransformer model during the image build, copy `main.py` plus `config/`, and run `uvicorn` for the custom FastAPI app on internal port `8080`.

## Impact

- `document-indexer` and `solr-search` can rely on the project-specific OpenAI-compatible embeddings endpoint.
- The image contract is now aligned with ADR-004's model standardization and avoids the `/vectors/` vs `/v1/embeddings/` mismatch.
- Startup behavior is more predictable because the model is cached into the image during build.
