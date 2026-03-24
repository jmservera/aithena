## Decision: Thumbnail Volume Permission Handling

**Author:** Brett (Infrastructure Architect)
**Date:** 2026-03-24
**Status:** Implemented (PR #1090)
**Context:** Issue #1089

### Problem

Pre-release log analyzer flags `Permission denied: '/data/thumbnails/'` errors from document-indexer as security findings. These are caused by missing directory ownership in the Dockerfile — the named volume is root-owned but the container runs as UID 1000.

### Decision

1. **Allowlist rule:** `security:*permission denied*/data/thumbnails/*=ignore` — thumbnail generation is non-critical; indexing succeeds without thumbnails
2. **Dockerfile fix:** `RUN mkdir -p /data/thumbnails && chown app:app /data/thumbnails` — named volumes inherit image layer permissions on first creation

### Rationale

- Thumbnail failures don't block document indexing (non-critical feature)
- The Dockerfile fix is the correct infrastructure-level approach for named volume permissions
- The allowlist provides defense-in-depth for CI environments where volumes may not initialize cleanly

### Impact

- Unblocks v1.15.0 release (PR #1088)
- Pattern applies to any future service that writes to named volumes as non-root
