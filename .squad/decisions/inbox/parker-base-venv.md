# Decision: Base image uses /app/.venv with uv

**Date:** 2026-07-16
**Author:** Parker (Backend Dev)
**Status:** Proposed
**Related:** jmservera/aithena#1325, jmservera/embeddings-server-base#5

## Context

The embeddings-server base image previously installed heavy Python packages (torch, sentence-transformers, nvidia-*, etc.) into system site-packages via `pip install`. The app image then had to COPY the entire ~4GB .venv from a build stage, creating a massive duplicate layer.

## Decision

Both base image Dockerfiles (`Dockerfile` and `Dockerfile.openvino`) now:

1. **Install packages into `/app/.venv`** using `uv venv` + `uv pip install` instead of system `pip`
2. **Use BuildKit `--mount=from`** to transiently mount the `uv` binary — it never exists in the final image
3. **Create `app:1000` user** that owns `/app` — consistent with the app image's runtime user
4. **Keep `/models` root-owned** with `chmod a+rX` to avoid duplicating the ~5GB model layer via chown

## Consequences

- The app Dockerfile (in aithena) **must** be updated to use `uv sync --inexact` instead of the current multi-stage COPY pattern. This is a coordinated change.
- The `# syntax=docker/dockerfile:1` directive is now required (first line of each Dockerfile) to enable BuildKit mount syntax.
- `uv` is never present at runtime — any debugging requiring package installs must use a temporary mount or exec into the container with a different approach.
- The openvino variant now uses `app:1000` instead of the base image's `openvino` user, which is a breaking change for anything that depended on that user identity.

## Impact on Team

- **Brett (Infra):** This implements the prerequisite from his BuildKit mount analysis. The app Dockerfile changes can now proceed.
- **Lambert (Tester):** Base image rebuild required before testing the full optimization pipeline.
- **Dallas (Frontend):** No impact.
