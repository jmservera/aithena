# Parker — CI Workflows for Unit & Integration Tests

**Author:** Parker (Backend Dev)  
**Date:** 2026-03-14  
**Status:** IMPLEMENTED

## Decision

Created GitHub Actions CI workflows to run automated tests for Python backend services on every push and PR.

### Implementation

**File:** `.github/workflows/ci.yml`

**Jobs:**
1. `document-indexer-tests` — Runs 15 pytest tests for metadata extraction
2. `solr-search-tests` — Runs 8 unit tests + 10 integration tests for the FastAPI search service
3. `all-tests-passed` — Summary job that requires all other jobs to succeed

**Integration Test Strategy:**
- Created `solr-search/tests/test_integration.py` with FastAPI TestClient tests
- All Solr HTTP calls are mocked using `unittest.mock.patch`
- Tests cover: search results, faceting, pagination, sorting, error handling, health/info endpoints
- **NO docker-compose** — CI runner containers are too small for full stack
- **NO real Solr** — all external dependencies mocked

**CI Configuration:**
- Python 3.11 (matches Dockerfiles)
- Triggers: push to `main` and `jmservera/solrstreamlitui`, PRs to `main`
- Pip caching for faster dependency installation
- Pytest with coverage reporting for unit tests
- Concurrency groups to cancel in-progress runs on same PR

### Critical Technical Finding

**FastAPI 0.99.1 + Starlette 0.27.0 requires `httpx<0.28` for TestClient compatibility.**

The newer httpx 0.28+ changed the Client API, breaking TestClient initialization. The CI workflow explicitly pins `httpx<0.28` when installing test dependencies.

**Why this matters:**
- Local dev environments with newer httpx will see test failures
- CI must pin httpx to ensure consistent test execution
- Future FastAPI upgrades should verify httpx compatibility

### Validation

All tests pass locally:
- `document-indexer`: 15/15 tests passing
- `solr-search` unit tests: 8/8 tests passing
- `solr-search` integration tests: 10/10 tests passing

### Impact

- **Automated testing:** Every push now validates that existing tests pass
- **PR safety:** PRs cannot merge if tests fail (when branch protection is enabled)
- **Fast feedback:** Tests run in parallel (~30-60s total runtime)
- **No infrastructure needed:** Mocked integration tests avoid docker-compose overhead
- **Coverage visibility:** Pytest coverage reports show which code is tested

### Next Steps (for team)

1. Enable branch protection on `main` requiring CI status checks
2. Consider adding frontend tests when aithena-ui test suite is ready
3. Extend integration tests as new API endpoints are added
4. Add linting jobs (ruff, black, mypy) when coding standards are defined
