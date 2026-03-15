# Decision: Container Version Metadata Baseline

**Author:** Brett (Infrastructure Architect)  
**Date:** 2026-03-15  
**Status:** Proposed  
**Issue:** #199 — Versioning infrastructure

## Context

The v0.7.0 milestone needs a single, repeatable way to stamp every source-built container with release metadata. Without a shared convention, local builds, CI builds, and tagged releases can drift, making support and debugging harder.

## Decision

Use a repo-root `VERSION` file as the default application version source, overridden by an exact git tag when present. Pass `VERSION`, `GIT_COMMIT`, and `BUILD_DATE` through Docker Compose build args into every source-built Dockerfile, and bake them into both OCI labels and runtime environment variables.

## Rationale

- Keeps release numbering aligned with the semver tagging flow on `dev` → `main`
- Gives operators a stable fallback (`VERSION`) before a release tag exists
- Makes image provenance visible both from container registries (OCI labels) and inside running containers (`ENV`)
- Uses one metadata contract across Python, Node, and nginx-based images

## Impact

- Source-built services now share one image metadata schema
- `buildall.sh` can build tagged and untagged snapshots consistently
- CI/CD can override any of the three variables without patching Dockerfiles

## Next steps

1. Reuse the same metadata contract in release workflows that publish images
2. Surface the runtime `VERSION` in application health/status endpoints where useful
