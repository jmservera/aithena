# Lambert: Test Coverage for #1286 (IPEX) and #1287 (Solr Credentials)

**Timestamp:** 2026-03-29T10:10:00Z  
**Status:** ✅ Complete  
**Tests Added:** 14 new tests, all passing

## Summary

Wrote proactive test coverage for Brett's #1286 (IPEX addition) and Parker's #1287 (Solr credential management). Created 3 new test files with shared infrastructure following existing patterns (deterministic fixtures, mocked auth).

## Test Files Created

1. **installer/tests/test_solr_credentials.py** (6 tests)
   - `test_build_env_values_generates_solr_admin_pass()` — verifies admin password generation
   - `test_build_env_values_generates_solr_readonly_pass()` — verifies readonly password generation
   - `test_build_env_values_preserves_existing_solr_credentials()` — checks credential rotation logic
   - `test_solr_credentials_meet_security_requirements()` — validates credential strength
   - `test_solr_credentials_can_reset()` — tests manual reset workflow
   - `test_solr_user_role_assignment_matches_security_json()` — ensures role names are correct

2. **src/embeddings-server/tests/test_openvino_deps.py** (4 tests)
   - `test_openvino_extras_includes_ipex()` — verifies IPEX in pyproject.toml
   - `test_ipex_version_compatible_with_torch()` — checks IPEX 2.8.0 resolves with torch 2.10.0
   - `test_uv_lock_contains_ipex()` — validates uv.lock generation
   - `test_cpu_only_build_excludes_ipex()` — confirms non-openvino builds unaffected

3. **src/solr-search/tests/test_solr_init_script.py** (4 tests)
   - `test_solr_init_enables_auth()` — validates solr auth enable call
   - `test_solr_init_assigns_admin_role()` — checks admin role assignment
   - `test_solr_init_assigns_readonly_role()` — verifies readonly (not search) role
   - `test_solr_init_role_names_match_security_json()` — ensures role consistency

## Test Infrastructure

- **installer/tests/conftest.py** — Shared fixtures for credential mocking, deterministic secret_factory, autouse auth mock
- Follows RabbitMQ password test pattern (same structure, same reliability)
- TOML parsing uses `tomllib` (not regex) for robust validation
- Docker-compose tests parse YAML and regex-match bash script for role assignments

## Impact

- Guards against credential management regressions
- Packaging tests prevent accidental IPEX removal
- Solr role assignment tests catch typos (readonly vs search)
- All 14 tests provide clear failure messages pointing to specific issue numbers if fix is missing
