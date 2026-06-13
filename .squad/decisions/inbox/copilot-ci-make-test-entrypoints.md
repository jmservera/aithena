# Decision: CI workflows should call root make test entrypoints

**Author:** Brett (Infrastructure Architect)  
**Date:** 2026-06-13T15:44:59Z  
**Status:** Proposed  
**Related:** #1747, #1741, #1452

## Decision

Route GitHub Actions test execution through the root `Makefile` instead of calling
pytest, Vitest, or Playwright directly from workflows.

Workflows may still override runner-specific arguments such as junit/coverage flags
and the Python test launcher (`uv run pytest` vs `pytest`) via make variables so
they can preserve existing artifacts while sharing one orchestration layer.

## Rationale

This removes duplicated test-command wiring across CI jobs while keeping workflow
structure, artifacts, and dependency-install steps stable. Centralizing the suite
entrypoints in `Makefile` also makes workflow logs clearer because the target names
announce which backend or E2E suite is running.

## Notes

- Added `test-e2e` and `test-e2e-python` so integration workflows can use one make
  entrypoint for Python E2E + Playwright without forcing `make test` to require a
  running stack in local development.
- `test-embeddings-server` remains compatible with the current CI install flow by
  allowing `PYTEST_CMD=pytest` overrides until or unless that job moves fully to
  `uv`.
