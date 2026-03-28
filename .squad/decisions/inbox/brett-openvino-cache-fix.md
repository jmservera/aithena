# Decision: HF Hub snapshot_download Required for Offline Base Images

**Author:** Brett (Infrastructure Architect)
**Date:** 2026-07-26
**Status:** Implemented
**Context:** OpenVINO base image fails at runtime with `HF_HUB_OFFLINE=1`

## Problem

The `embeddings-server-base` Dockerfile only called `SentenceTransformer()` to cache the model. This downloads model weights but does NOT cache HF Hub API metadata (tree listings, model info endpoints). At runtime with `HF_HUB_OFFLINE=1`, the `optimum-intel` loading path tries to call `huggingface.co/api/models/.../tree/main` to discover openvino files, which fails.

## Decision

1. **Always call `huggingface_hub.snapshot_download(model_name)` before `SentenceTransformer()`** in base image Dockerfiles. This caches the full HF Hub repo including metadata needed for offline loading.
2. **Always add an offline verification step** in the Dockerfile: `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python -c "..."`. This fails the build if the cache is incomplete.
3. **Removed `render` from `group_add`** in `docker-compose.intel.override.yml` — the group doesn't exist in slim Python images, causing container startup failures.

## Rationale

- `snapshot_download()` is the only HF Hub function that caches API tree metadata; `SentenceTransformer()` uses a different code path that skips this
- The offline verification RUN step provides a build-time safety net — catches cache issues before the image ships
- The `render` group is a host-level concept for native Linux DRM access; not needed for WSL2 `/dev/dxg` passthrough

## Impact

- Base image repo (`embeddings-server-base`): Dockerfile updated, pushed to main, CI rebuilds both variants
- Aithena repo: `docker-compose.intel.override.yml` fixed, PR #1258 against dev
- Pattern applies to any future base image that pre-caches HF models for offline use
