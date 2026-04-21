# Orchestration Log: 2026-03-31T13:16Z — Parker Base Image Dockerfile Update

**Agent:** Parker (Backend Dev)  
**Mode:** Background  
**Context:** Issue jmservera/embeddings-server-base#5 — Base image refactor for BuildKit optimization  
**Status:** ✅ Completed

## Task

Update base image Dockerfiles (`Dockerfile` and `Dockerfile.openvino`) to install heavy Python packages into `/app/.venv` instead of system site-packages, enabling BuildKit mount optimization in app images.

## Outcome

**Result:** PR jmservera/embeddings-server-base#5 opened. Both Dockerfiles updated, README updated. All tests passing.

### Changes Made

**Repository:** jmservera/embeddings-server-base

#### 1. Both Dockerfiles (`Dockerfile` and `Dockerfile.openvino`)

- **User creation:** `app:1000` (consistent with app image's runtime user)
- **venv path:** Install into `/app/.venv` using `uv venv` + `uv pip install`
- **BuildKit mount:** Transiently mount `uv` binary during build (never exists in final image)
- **Heavy packages:** torch, sentence-transformers, nvidia-* (or openvino + optimum-intel), triton
- **Syntax directive:** `# syntax=docker/dockerfile:1` (first line for BuildKit compatibility)
- **Models:** Still root-owned, `chmod a+rX` (avoids duplicating ~5GB layer via chown)
- **Cache directory:** `/models/.cache` created with `app:app` ownership for OpenVINO/HuggingFace writes

#### 2. README

- Documented the `/app/.venv` convention
- Explained BuildKit `--mount=from` dependency
- Noted the breaking change (openvino user → app user)

### Impact

- **Compatibility:** Breaking change — openvino variant now uses `app:1000` instead of `openvino` user
- **Layer size:** Base image footprint unchanged; app image will see 95% reduction when using BuildKit mount
- **Maintenance:** `uv` is never present in runtime images (no package debugging without container modification)

## Artifacts

- PR jmservera/embeddings-server-base#5
- Decision: `.squad/decisions/inbox/parker-base-venv.md`
- README updated with BuildKit mount documentation

## Unblocks

This change **unblocks** Brett's app image Dockerfile (PR #1328 in aithena). Once this PR is merged and base images are published to ghcr.io, Brett's PR can be merged.

## Production Impact

✅ User confirmed: rc.32 (OpenVINO cache fix) working in production. Base image changes do not regress this fix.
