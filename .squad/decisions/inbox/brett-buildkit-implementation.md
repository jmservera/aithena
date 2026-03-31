# Decision: BuildKit --mount=from + --inexact for embeddings-server layer optimization

**Author:** Brett (Infrastructure Architect)
**Date:** 2026-07-26
**Status:** Implemented (blocked on base image)

## Summary

Replaced the multi-stage `COPY --from=dependencies /app/.venv` pattern in the embeddings-server Dockerfile with a single-stage BuildKit `--mount=from` approach. The app Dockerfile now bind-mounts `uv` at build time and runs `uv sync --inexact` to install only the delta of app-specific packages into the base image's pre-populated `.venv`.

## What Changed

- **Approach:** Approach 3 from the analysis — BuildKit `--mount=from` bind mount
- **App Dockerfile:** `src/embeddings-server/Dockerfile` — removed dependencies stage, added `--mount=from` + `--inexact`
- **Base image:** Issue created at jmservera/embeddings-server-base#4 — both Dockerfiles need to switch from system site-packages to `/app/.venv`
- **PR:** jmservera/aithena#1328 (draft, blocked on base image update)

## Key Design Decisions

1. **`--inexact` over `--exact`:** Preserves base image packages, installs only missing deps. This is critical — `--exact` would remove the pre-installed heavy packages.
2. **Single conditional RUN:** Both torch and openvino variants handled in one `if/else` block instead of two separate RUN commands.
3. **OV cache at `/app/ov_cache`:** Moved from `/tmp/ov_cache` for consistency and to avoid potential noexec issues.
4. **`# syntax=docker/dockerfile:1`:** Required as first line for cross-version BuildKit compatibility.

## Impact

| Metric | Before | After |
|--------|--------|-------|
| .venv layer | ~4.1 GB compressed | ~200 MB compressed |
| Build stages | 2 | 1 |
| Python symlink hack | Required | Eliminated |

## Dependencies

This is a **breaking change pair** — the base image must be updated to provide `/app/.venv` before the app Dockerfile will build. Coordination tracked via:
- Base: jmservera/embeddings-server-base#4
- App: jmservera/aithena#1328
