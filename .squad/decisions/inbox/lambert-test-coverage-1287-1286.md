# Decision: Test Coverage for #1287 (Solr Credentials) and #1286 (IPEX)

**Author:** Lambert (Tester)
**Date:** 2026-03-29
**Status:** Implemented

## Context

Issues #1286 and #1287 required proactive test coverage to verify fixes for:
1. Installer Solr credential management (generate, preserve, rotate, reset passwords)
2. IPEX in openvino optional-dependencies
3. Solr-init readonly role assignment (fix from "search" to "readonly")

## Decision

Added 14 tests across 3 new test files:
- `installer/tests/test_solr_credentials.py` — 6 tests for `build_env_values()` Solr credential handling
- `src/embeddings-server/tests/test_openvino_deps.py` — 4 tests for pyproject.toml/uv.lock validation
- `src/solr-search/tests/test_solr_init_script.py` — 4 tests for docker-compose.yml solr-init script

Created shared installer test infrastructure (`conftest.py`) with auth mocking and deterministic fixtures.

## Rationale

- Installer tests follow the same pattern as RabbitMQ password tests (deterministic secret_factory, autouse auth mock)
- Config/packaging tests (openvino deps) use `tomllib` for reliable TOML parsing rather than regex
- Docker-compose tests parse YAML and use regex on the inline bash script to verify role assignments
- All tests produce clear failure messages pointing to the specific issue number if a fix is missing

## Impact

- 14 new tests guard against credential management regressions in the installer
- Packaging tests prevent accidental removal of IPEX from openvino extras
- Solr-init tests prevent role assignment regressions (readonly vs search)
