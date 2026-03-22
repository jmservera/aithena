# HF_TOKEN Build Integration

**Author:** Brett (Infrastructure Architect)
**Date:** 2025-03-22

## Decision

Wire HuggingFace API token through Docker build for faster model downloads in embeddings-server.

## Context

The embeddings-server Dockerfile pre-downloads a large SentenceTransformer model (~500MB) during the build stage. Without authentication to HuggingFace Hub, downloads are rate-limited and slow. With HF_TOKEN, authenticated requests get prioritized bandwidth.

## Implementation

1. **Dockerfile** (`src/embeddings-server/Dockerfile`):
   - Added `ARG HF_TOKEN` to the builder stage (line 9)
   - Set `ENV HF_TOKEN=${HF_TOKEN}` in the builder environment (line 16)
   - HF_TOKEN is NOT persisted in the runtime stage (multi-stage isolation)
   - Runtime stage sets `HF_HUB_OFFLINE=1` to prevent runtime downloads

2. **docker-compose.yml**:
   - Added `HF_TOKEN: ${HF_TOKEN:-}` to embeddings-server build args
   - Falls back to empty string if not set (prevents build failures)

3. **buildall.sh**:
   - Added `source .env` at script start to load environment variables
   - This ensures HF_TOKEN from `.env` is available to docker compose

4. **GitHub Actions** (`.github/workflows/integration-test.yml`):
   - Added `HF_TOKEN: ${{ secrets.HF_TOKEN || '' }}` to job env
   - Pulls from GitHub Secrets (must be configured by user/org)
   - Defaults to empty string if secret is not set

## Security

- HF_TOKEN is only used at build time (builder stage)
- Not persisted in final image layers (multi-stage benefit)
- Treated as a secret in CI/CD (GitHub Actions secrets mechanism)
- Optional: builds continue without token, just slower

## Notes

- `docker-compose.prod.yml` uses prebuilt GHCR images, not local builds—no changes needed
- Integration test workflow calls `docker compose build`, which will now use HF_TOKEN if set
