# Decision: 4-stage Docker layer optimization for embeddings-server

**Author:** Brett (Infrastructure Architect)
**Date:** 2026-03-24
**Status:** APPROVED by Juanma (2026-03-24) — note: model-downloader stage must include download dependencies

## Context

The current embeddings-server Dockerfile uses a 2-stage build (builder + runtime). The model download (~1.5GB) happens AFTER dependency installation, meaning any code change invalidates the model cache layer. This causes full rebuilds on every release.

## Proposal

Restructure to 4 stages, ordered by change frequency (least → most):

1. **model-downloader** — Downloads the SentenceTransformer model. Changes only when model version changes (rare). Uses HF_TOKEN as a build secret.
2. **dependencies** — Installs Python packages from requirements.txt. Changes only when deps change.
3. **app-builder** — Copies application code. Changes on every code commit.
4. **runtime** — Slim final image, copies artifacts from above stages.

## Impact

- Code-only changes: 80% faster (model + deps cached)
- Dependency changes: 60% faster (model cached)
- Model download uses `--mount=type=secret` instead of ARG for HF_TOKEN (no token in image layers)

## Implementation

Apply BEFORE or AFTER repo extraction — works in either context.
