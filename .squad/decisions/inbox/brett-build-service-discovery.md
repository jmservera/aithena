# Decision: Shared build-service discovery

**Author:** Brett (Infrastructure Architect)
**Date:** 2026-06-13
**Status:** Proposed
**Related:** #1744

## Decision

Centralize build-service discovery in `scripts/lib/build-services.sh` and source it from both `buildall.sh` and `manage.sh`. Discovery starts from `find src -name Dockerfile`, then the Python prep path narrows that list to directories that also carry `pyproject.toml`.

## Why

- New buildable services under `src/` now register automatically without editing shell arrays.
- `manage.sh build` and `buildall.sh` stay behaviorally aligned instead of drifting on separate service lists.
- Infra images such as `src/solr` still participate in Compose builds, while `uv sync` remains limited to Python services.

## Validation

- `bash tests/test-buildall-failure-reporting.sh`
- `bash tests/test-build-service-discovery.sh`
- `bash tests/test-manage-cli.sh`
- `AUTH_DB_DIR=$PWD/.test-artifacts/auth-db AUTH_JWT_SECRET=test-secret docker compose build aithena-ui document-indexer document-lister embeddings-server solr-search`
