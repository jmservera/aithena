# Decision: GPU Config Design for embeddings-server

**Author:** Parker (Backend Dev)
**Date:** 2026-03-25
**Status:** Proposed (PR #1215)
**Context:** Issues #1152, #1151 — v1.17.0 GPU Acceleration PRD

## Decision

GPU device and backend selection uses two environment variables (`DEVICE`, `BACKEND`) with defaults that produce identical behavior to pre-change code. OpenVINO is an optional Dockerfile build arg, not a runtime dependency.

## Key Design Choices

1. **Kwargs only when non-default:** `DEVICE=cpu` and `BACKEND=torch` pass zero extra kwargs to SentenceTransformer. This guarantees backward compatibility without conditional logic in downstream consumers.

2. **`DEVICE=auto` maps to `None`:** Lets PyTorch's internal device detection run (CUDA > CPU fallback). Useful for environments where GPU availability isn't known at config time.

3. **OpenVINO as build arg:** `INSTALL_OPENVINO=true` installs ~150MB of optional deps into `.venv`. Not in `pyproject.toml` because it's an acceleration backend, not a core dependency. This keeps the default image slim.

4. **Endpoint exposure:** `/health` and `/version` include `device` and `backend` fields so operators can verify GPU config without checking env vars directly.

## Impact

- Docker Compose files may add `DEVICE` and `BACKEND` env vars for GPU-enabled deployments
- CI/CD pipelines that build embeddings-server can pass `--build-arg INSTALL_OPENVINO=true` for Intel GPU targets
- No changes needed for existing CPU-only deployments
