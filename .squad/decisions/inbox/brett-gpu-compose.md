# Decision: GPU acceleration via Compose override files (not profiles)

**Author:** Brett (Infrastructure Architect)
**Date:** 2026-07-26
**Status:** Implemented (PR #1213)
**Context:** Issues #1153, #1154 (v1.17.0 GPU acceleration PRD)

## Problem

Need to support NVIDIA and Intel GPU acceleration for `embeddings-server` without breaking the default CPU-only deployment.

## Decision

Use **Compose override files** (`docker-compose.nvidia.override.yml`, `docker-compose.intel.override.yml`) instead of Compose profiles.

## Rationale

- Consistent with existing overlay pattern (`docker-compose.ssl.yml`, `docker-compose.e2e.yml`)
- Override files are self-documenting with prerequisite comments and usage examples
- No service name confusion (profiles create separate services like `embeddings-server-nvidia`)
- Override files can add `deploy.resources.reservations.devices`, `devices`, `group_add`, and `build.args` — all merge cleanly
- Base compose adds `DEVICE=${DEVICE:-cpu}` and `BACKEND=${BACKEND:-torch}` — zero change for existing users

## Impact

- Parker/Dallas: `DEVICE` and `BACKEND` env vars are now available in the embeddings-server container
- Installer scripts may need updating to support `-f docker-compose.nvidia.override.yml` flag
- Future: `docker-compose.prod.yml` should also support the GPU overrides (verified: works with `-f docker-compose.prod.yml -f docker-compose.nvidia.override.yml`)
