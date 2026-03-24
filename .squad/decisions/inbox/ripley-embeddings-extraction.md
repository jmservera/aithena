# Decision: Extract embeddings-server to its own repository

**Author:** Ripley (Lead Architect)
**Date:** 2026-03-24
**Status:** PROPOSED — awaiting PO approval
**Verdict:** GO

## Context

The embeddings-server is the largest and slowest Docker image to build (~9GB, 15+ min). It changes infrequently (model updates are rare), but every release rebuilds it because it lives in the monorepo. This bottleneck dominated every release in the v1.12–v1.14 cycle.

## Proposal

Extract `src/embeddings-server/` into its own GitHub repository (`jmservera/aithena-embeddings`) with:
- Independent semver versioning and release cycle
- Pre-built Docker images published to GHCR
- The main aithena repo references the image by tag in docker-compose.yml

## Migration Plan (4 weeks)

1. **Week 1:** Create new repo, copy code, set up CI/CD with model caching
2. **Week 2:** Publish first independent release, update aithena docker-compose to use GHCR image
3. **Week 3:** Remove src/embeddings-server from monorepo, update all workflows
4. **Week 4:** Validate release pipeline end-to-end without embeddings rebuild

## Impact

- Release workflow drops from ~25 min to ~10 min (no embeddings rebuild)
- Model updates become independent releases
- Code changes to embeddings don't trigger full aithena CI
- Aithena release only pulls a pre-built image tag

## Risk

- Cross-repo version coordination (mitigated by pinned image tags)
- Need to set up independent GHCR publishing pipeline
