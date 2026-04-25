# Session Log: 2026-03-31T12:59 — Multi-stage Docker Analysis

**Agent:** Brett (Infrastructure Architect)  
**Duration:** Background task (async)  
**Outcome:** ✅ Analysis completed, decision written

## Summary

Brett analyzed 5 multi-stage Docker approaches for issue #1325 (embeddings-server layer optimization). Recommended Approach 3: BuildKit `--mount=from` bind mount for transient uv access during build.

**Key result:** ~95% reduction in app layer size (4.1GB → 200MB compressed when base cached), zero tools in runtime, BuildKit-native (already used in CI).

Decision document posted to inbox and issue #1325 commented.

## Decision Flow

1. **Root cause identified:** Current multi-stage creates ~4GB COPY layer because Docker copies entire `/app/.venv` (including heavy deps already in base image)
2. **Analyzed 5 approaches:** in-place, full COPY, BuildKit mount, delta-only, strip+PYTHONPATH
3. **Selected approach 3:** BuildKit `--mount=from=ghcr.io/astral-sh/uv:latest` — mount uv transiently during RUN, never in final image
4. **Prerequisite:** Base image rebuild to own `/app/.venv` with heavy deps (one-time, both variants)

**Next owner:** Parker — base image rebuild before app Dockerfile update.
