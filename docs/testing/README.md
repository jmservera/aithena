# Test Infrastructure Guide

This document provides comprehensive guidance on running, maintaining, and extending tests across the Aithena project.

## Table of Contents

- [Quick Start](#quick-start)
- [Prerequisites](#prerequisites)
- [Test Commands](#test-commands)
- [Test Frameworks](#test-frameworks)
- [Interpreting Results](#interpreting-results)
- [Adding New Tests](#adding-new-tests)
- [CI/CD Integration](#cicd-integration)
- [Known Issues & Gotchas](#known-issues--gotchas)
- [Debugging & Troubleshooting](#debugging--troubleshooting)

---

## Quick Start

The fastest way to verify your changes:

```bash
# Run all verification checks (lint, format, tests)
.squad/scripts/verify.sh

# Or test a specific service
.squad/scripts/verify.sh --service solr-search
.squad/scripts/verify.sh --service aithena-ui
```

**Exit code 0** = all checks pass. The script auto-detects changed services and runs relevant tests.

---

## Prerequisites

### Required Versions

| Tool/Service | Minimum Version | Installation |
|---|---|---|
| **Node.js** | 18.0.0 | https://nodejs.org |
| **Python** | 3.12+ | https://www.python.org (or via pyenv) |
| **Docker** | 24.0.0+ | https://docs.docker.com/get-docker/ |
| **Docker Compose** | 2.20.0+ | Included with Docker Desktop |
| **Apache Solr** | 9.7 / 10.x | Runs in Docker (see setup) |
| **ZooKeeper** | 3.9+ | Bundled with Solr |
| **Redis** | 7.0+ | Runs in Docker |
| **RabbitMQ** | 3.12+ | Runs in Docker |

### Local Setup

```bash
# Clone the repository
git clone https://github.com/jmservera/aithena.git
cd aithena

# Install Python virtual environment (automatic via uv)
# For each Python service, uv will auto-create and sync dependencies:
# uv sync is called automatically by pytest and the verify script

# Install Node dependencies
cd src/aithena-ui
npm ci
cd ../..

# Start the Docker Compose stack (all services)
docker-compose up -d

# Or start just what you need for a specific test
# See "Running a Single Service" below
```

### Environment Configuration

Create `.env` in the project root:

```bash
cp .env.example .env
# Edit .env to override defaults (Solr URL, Redis host, etc.)
```

---

## Test Commands

### Unified Test Interface (via verify.sh)

The `.squad/scripts/verify.sh` script is the primary quality gate. It automatically detects which services changed and runs appropriate checks:

```bash
# Auto-detect changed services (staged or unstaged changes vs origin/dev)
.squad/scripts/verify.sh

# Check everything
.squad/scripts/verify.sh --all

# Check only lint/format (skip tests)
.squad/scripts/verify.sh --lint-only

# Check a specific service
.squad/scripts/verify.sh --service solr-search
.squad/scripts/verify.sh --service document-indexer
.squad/scripts/verify.sh --service aithena-ui
```

### Python Services (Backend)

Each Python service uses `uv` for dependency management and `pytest` for testing.

#### Running Tests

```bash
# Full test suite with coverage
cd src/solr-search
uv run pytest -v

# Run with coverage report
uv run pytest --cov --cov-report=html

# Run specific test
uv run pytest -k "test_auth" -v

# Run a single file
uv run pytest tests/test_auth.py -v

# Run and stop on first failure
uv run pytest -x

# Show print statements
uv run pytest -s
```

#### Available Python Services

| Service | Tests | Location | Commands |
|---------|-------|----------|----------|
| **solr-search** | ~1,000+ unit & integration | `src/solr-search/tests/` | `uv run pytest` |
| **document-indexer** | ~80+ | `src/document-indexer/tests/` | `uv run pytest` |
| **document-lister** | ~20+ | `src/document-lister/tests/` | `uv run pytest` |
| **embeddings-server** | ~30+ | `src/embeddings-server/tests/` | `uv run pytest` |
| **admin** | ~100+ | `src/admin/tests/` | `uv run pytest` |
| **aithena-common** | (shared) | `src/aithena-common/tests/` | `uv run pytest` |

#### Coverage Reporting

```bash
cd src/solr-search

# Generate HTML coverage report
uv run pytest --cov --cov-report=html

# View in browser
open htmlcov/index.html
```

**Coverage targets:**
- `solr-search`: ≥91%
- `document-indexer`: ≥80%
- Other services: ≥75%

### Node Service (Frontend)

The UI uses **Vitest** for unit and integration tests.

```bash
cd src/aithena-ui

# Run all tests
npm test
# or
npx vitest run

# Watch mode (re-run on file changes)
npx vitest

# Run specific test
npx vitest -t "test name pattern"

# Update snapshots
npx vitest update

# Generate coverage
npx vitest --coverage
```

### E2E Tests (Playwright)

End-to-end tests validate the full stack via the browser.

```bash
cd e2e

# Run all E2E tests
uv run pytest -v

# Run specific E2E test
uv run pytest test_search_page.py -v

# Run with browser visible
uv run pytest --headed

# Run against specific API URL
E2E_API_URL="http://localhost:8000" uv run pytest -v

# Generate HTML report (after run)
# Report available at htmlcov/index.html
```

**Environment variables:**
- `E2E_API_URL` — API endpoint (default: `http://localhost:8000`)
- `E2E_API_TOKEN` — Bearer token for auth tests (optional)
- `PWDEBUG=1` — Launch Playwright Inspector
- `E2E_HEADED=1` — Show browser during tests

### Stress & Performance Tests

```bash
cd tests/stress

# Install dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run indexing stress test
python3 -m pytest test_indexing.py -v

# Run concurrent search test
python3 -m pytest test_concurrent.py -v

# Run Locust load test (interactive)
locust -f locustfile.py --host="http://localhost:8000"
```

### Backup & Restore Tests

```bash
# Test backup/restore pipeline
bash tests/backup/test_backup_high.sh
bash tests/backup/test_restore_high.sh

# Test restore verification
bash tests/verify-restore.sh
```

### Pre-Release Checks

```bash
# Comprehensive pre-release validation
bash tests/test-pre-release-check.sh

# Security scan (compose file)
bash tests/test-compose-security.sh
```

---

## Test Frameworks

### Pytest (Python Backend)

**Framework**: pytest v8.3.4+  
**Configuration**: `pyproject.toml` in each service  
**Coverage**: pytest-cov v6.1.1+

#### Key Features

- **Fixtures**: Reusable test setup (database, mocks, API clients)
- **Parametrization**: Run the same test with multiple inputs
- **Markers**: Organize tests with tags (`@pytest.mark.unit`, `@pytest.mark.integration`)
- **Mocking**: `unittest.mock` and `pytest-mock` for isolating dependencies

#### Example Pytest Test

```python
import pytest
from httpx import Client

@pytest.fixture
def client():
    """Fixture provides HTTP client"""
    return Client(base_url="http://localhost:8000")

def test_search_keyword(client):
    """Test keyword search endpoint"""
    response = client.get("/v1/search?q=python")
    assert response.status_code == 200
    assert "results" in response.json()
```

#### Configuration (pyproject.toml)

```toml
[tool.pytest.ini_options]
addopts = "--cov=src --cov-report=term-missing --cov-report=html -ra"
testpaths = ["tests"]
```

### Vitest (TypeScript/React Frontend)

**Framework**: Vitest (Vite-native test runner)  
**Configuration**: `vitest.config.ts`  
**Mocking**: `vitest` built-in, plus `@testing-library/react`

#### Key Features

- **Fast**: Reuses Vite's dependency pipeline
- **ESM-native**: No transpilation overhead
- **Snapshots**: Visual regression detection
- **Mocking**: Component mocks and module mocks

#### Example Vitest Test

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SearchPage } from './SearchPage';

describe('SearchPage', () => {
  it('renders search input', () => {
    render(<SearchPage />);
    expect(screen.getByRole('textbox')).toBeDefined();
  });
});
```

### Playwright (Browser E2E)

**Framework**: Playwright  
**Configuration**: `e2e/pytest.ini`  
**Target**: Full stack validation (UI + API)

#### Key Features

- **Browser automation**: Chrome, Firefox, Safari
- **Cross-browser**: Same test runs in multiple browsers
- **Trace capture**: Debugging traces on failure
- **Screenshots & Videos**: Artifact capture for failed tests

#### Example Playwright Test

```python
from playwright.async_api import async_playwright

async def test_search_flow():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        await page.goto("http://localhost:3000")
        await page.fill('input[placeholder="Search"]', 'python')
        await page.press('input', 'Enter')
        
        # Wait for results
        await page.wait_for_selector('.search-result')
        results = await page.locator('.search-result').all()
        assert len(results) > 0
        
        await browser.close()
```

---

## Interpreting Results

### Test Output Format

#### Pytest Output

```
==================== test session starts ====================
collected 42 items

src/solr-search/tests/test_auth.py::test_login PASSED        [2%]
src/solr-search/tests/test_auth.py::test_invalid_password FAILED [4%]
src/solr-search/tests/test_search.py::test_keyword_search PASSED [50%]

================ 41 passed, 1 failed in 2.34s ================
```

- **PASSED** — Test succeeded
- **FAILED** — Test assertion failed (see traceback below)
- **SKIPPED** — Test was skipped (usually due to marker or fixture unavailable)
- **XFAIL** — Expected failure (intentional; not a regression)

#### Vitest Output

```
✓ src/components/SearchBox.test.tsx (3)
  ✓ renders search input
  ✓ handles enter key
  ✓ clears on reset button click

✓ src/pages/SearchPage.test.tsx (5)

Test Files  2 passed (2)
     Tests  8 passed (8)
```

### Coverage Reports

#### Coverage Summary

```
Name                    Stmts   Miss  Cover   Missing
─────────────────────────────────────────────────────
search_service.py        125      5    96%    45-47
auth.py                   80      1    99%    42
config.py                 60      10   83%    5-15
─────────────────────────────────────────────────────
TOTAL                    1200     25   98%
```

**Interpretation:**
- **Stmts** — Total statements
- **Miss** — Uncovered statements
- **Cover** — Coverage percentage
- **Missing** — Line ranges not covered by tests

#### Acceptable Coverage Levels

| Scope | Target |
|-------|--------|
| solr-search | ≥91% |
| document-indexer | ≥80% |
| aithena-ui | ≥75% |
| E2E suite | N/A (integration validation) |

### Common Failure Patterns

#### Flaky Tests

**Symptom**: Test passes locally but fails in CI (or vice versa).  
**Common causes**:
- **Timing**: Tests depending on exact timing (use `await`/`wait_for` helpers)
- **External state**: Solr/Redis/RabbitMQ state not reset between tests
- **Race conditions**: Concurrent operations without proper locking

**Fix**:
- Use fixtures to reset state before each test
- Add explicit waits for async operations
- Use `pytest.mark.flaky(reruns=2)` temporarily while investigating

#### Import Errors

**Symptom**: `ModuleNotFoundError` or `ImportError` during test collection.  
**Cause**: Dependencies not installed or Python path misconfigured.

**Fix**:
```bash
# Reinstall dependencies
cd src/solr-search
uv sync
uv run pytest
```

#### Network Timeouts

**Symptom**: Tests hang or timeout connecting to Solr/Redis.  
**Cause**: Service not running or misconfigured host.

**Fix**:
```bash
# Ensure Docker services are running
docker-compose ps

# Check logs
docker-compose logs solr
docker-compose logs redis
```

---

## Adding New Tests

### Before Writing Tests

1. **Audit existing coverage** — Check if similar tests exist to avoid duplication
2. **Understand the scope** — Unit test? Integration? E2E?
3. **Plan fixtures** — What setup is needed? Can you reuse existing fixtures?

### Unit Tests (Isolated)

**Purpose**: Validate a single function/class in isolation.  
**Location**: `src/{service}/tests/test_{module}.py`  
**Pattern**: Mock external dependencies.

```python
# src/solr-search/tests/test_new_feature.py
import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_solr():
    """Mock Solr client"""
    with patch('search_service.solr_client') as mock:
        yield mock

def test_new_feature(mock_solr):
    """Test feature with mocked Solr"""
    mock_solr.search.return_value = {"results": []}
    
    from search_service import do_thing
    result = do_thing()
    
    assert result is not None
    mock_solr.search.assert_called_once()
```

### Integration Tests

**Purpose**: Validate feature with real dependencies (Solr, Redis, etc.).  
**Location**: `src/{service}/tests/test_{module}.py` (same as unit tests).  
**Setup**: Use `docker-compose` services; reset state in `conftest.py`.

```python
# src/solr-search/tests/conftest.py
import pytest

@pytest.fixture(scope="session", autouse=True)
def setup_services():
    """Ensure Solr is running"""
    # Check Solr health, seed test data, etc.
    pass

@pytest.fixture(autouse=True)
def reset_state():
    """Reset state before each test"""
    # Clear cache, reset rate limiter, etc.
    yield
    # Cleanup
```

### E2E Tests (Full Stack)

**Purpose**: Validate end-to-end user flows.  
**Location**: `e2e/test_{feature}.py`  
**Pattern**: Use Playwright to interact with UI and API.

```python
# e2e/test_new_feature.py
import pytest
from playwright.async_api import async_playwright

@pytest.mark.asyncio
async def test_user_uploads_and_searches():
    """E2E: Upload document and search"""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        # Navigate to upload page
        await page.goto("http://localhost:3000/upload")
        
        # Upload file
        await page.set_input_files('input[type="file"]', '/path/to/test.pdf')
        await page.click('button:has-text("Upload")')
        
        # Wait for indexing
        await page.wait_for_selector('text=Upload successful')
        
        # Navigate to search
        await page.goto("http://localhost:3000/search")
        await page.fill('input[placeholder="Search"]', 'test')
        await page.press('input', 'Enter')
        
        # Verify result appears
        await page.wait_for_selector('.search-result')
        
        await browser.close()
```

### Test Naming Conventions

**Pattern**: `test_{action}_{scenario}_{expected_result}`

```python
# Good names
def test_login_with_valid_credentials_returns_token():
    pass

def test_search_with_empty_query_returns_400():
    pass

def test_upload_pdf_with_valid_file_adds_to_queue():
    pass

# Avoid generic names
def test_feature():  # ❌ Too vague
    pass

def test_works():  # ❌ Unhelpful
    pass
```

### Documentation in Tests

Add docstrings to clarify test intent:

```python
def test_similar_books_updates_after_metadata_change():
    """
    When document metadata changes (e.g., author), the similar_books
    panel should reflect the new embeddings on next API call.
    
    This test validates that:
    1. Initial metadata generates embeddings
    2. Update triggers re-embedding
    3. Similar books results match new embeddings
    """
    # Test implementation
    pass
```

---

## CI/CD Integration

### GitHub Actions Workflows

The project runs tests automatically on:

- **Push to `dev`**: Runs lint + unit tests on changed services
- **Pull requests against `dev`**: Full suite including E2E
- **Schedule**: Nightly integration tests (3 AM UTC, Mon–Fri)
- **Manual dispatch**: On-demand full suite

#### Workflow Files

| File | Trigger | Scope |
|------|---------|-------|
| `.github/workflows/ci.yml` | Push to dev | Lint + unit tests |
| `.github/workflows/integration-test.yml` | PR → dev | Full suite + E2E |
| `.github/workflows/stress-tests.yml` | Manual dispatch | Stress/load testing |
| `.github/workflows/dev-integration-test.yml` | Manual/scheduled | Extended integration |

### Quality Gates

**Required checks to merge to `dev`:**

1. ✅ **Lint** — No style violations (`ruff`, `eslint`)
2. ✅ **Format** — Code matches style (`ruff`, `prettier`)
3. ✅ **Build** — Code compiles/transpiles (`npm run build` for TypeScript)
4. ✅ **Unit tests** — All tests pass
5. ✅ **Coverage** — Meets minimum thresholds

**Optional but recommended:**

- E2E tests (can be flaky; rerun if needed)
- Security scans (bandit, checkov)

### Checking CI Status

```bash
# Check status of a specific PR
gh pr checks <PR_NUMBER>

# Watch for CI completion
gh pr checks <PR_NUMBER> --watch

# View logs for a specific check
gh run view <RUN_ID> --log
```

### Rerunning Failed Checks

```bash
# Rerun a single failed check
gh run rerun <RUN_ID> --failed

# View recent runs
gh run list
```

---

## Known Issues & Gotchas

### Python Services

#### 1. **Environment Reload After Manifest Changes**

After modifying `pyproject.toml` or resolving dependency conflicts:

```bash
cd src/solr-search
uv sync
uv run pytest
```

**Why**: Old `.venv` may have stale dependencies.

#### 2. **Rate Limiter Reset Between Tests**

In tests that exercise rate limiting:

```python
@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Clear rate limiter state between tests"""
    from config import login_rate_limiter
    login_rate_limiter.requests.clear()
    yield
```

#### 3. **Solr Readiness Polling**

E2E tests should wait for Solr to be fully ready:

```python
def test_search_after_startup():
    """Wait for Solr replicas to become ACTIVE"""
    import time
    for _ in range(30):
        status = solr.cluster_status()
        if all(r['state'] == 'active' for r in status['replicas']):
            break
        time.sleep(1)
    
    # Now run test
    pass
```

#### 4. **Circuit Breaker in Tests**

When mocking circuit breaker failures:

```python
from search_service import CircuitOpenError

@patch('solr_client.query')
def test_circuit_breaker_opens(mock_query):
    """Circuit breaker should open after repeated failures"""
    mock_query.side_effect = HTTPException(503)
    
    # Trigger failures
    for _ in range(5):
        try:
            search_query("python")
        except CircuitOpenError as e:
            # Verify it includes (name, remaining_seconds)
            assert e.args == ("search", 30)
            break
```

### TypeScript/React Frontend

#### 1. **i18n Badge Rendering**

CollectionBadge renders via i18n middleware; use accessible selectors:

```typescript
// ✅ Good
const badge = screen.getByRole('img', { name: /collection/i });

// ❌ Avoid raw text
expect(screen.queryByText('42')).toBeDefined();
```

#### 2. **Focus & Focus Trap**

BookDetail uses `useId()` and manages focus on mount:

```typescript
// Test that focus trap is active
const modal = screen.getByRole('dialog');
expect(document.activeElement).toBeInTheDocument();
expect(modal).toContainElement(document.activeElement);
```

#### 3. **PDF Viewer Sequencing**

PDF viewer must open before related panels:

```typescript
// ✅ Correct order
await user.click(screen.getByText('Open PDF'));
await screen.findByRole('region', { name: /pdf viewer/i });

// Then interact with similar books panel
await screen.findByRole('region', { name: /similar books/i });
```

### E2E / Playwright

#### 1. **Graceful Data-Dependent Test Skip**

Some tests depend on specific indexed data. Use annotations:

```python
@pytest.mark.skipif(
    condition=not CORPUS_AVAILABLE,
    reason="Test requires representative corpus"
)
async def test_semantic_search_recall():
    """Only runs if test corpus is indexed"""
    pass
```

#### 2. **PDF & Similar Books Discovery**

Use live `/v1/search/` for read-only discovery:

```python
async def test_similar_books_recommendations():
    """Validate recommendations via API before browser test"""
    response = await fetch('/v1/search?q=python&mode=semantic')
    books = response.json()['results']
    
    # Test that book IDs are valid
    assert all('id' in b for b in books)
```

#### 3. **Auth Token Reuse**

In CI, reuse `E2E_API_TOKEN` before re-authenticating:

```python
@pytest.fixture
def api_token():
    """Reuse token from environment if available"""
    if os.getenv('E2E_API_TOKEN'):
        return os.getenv('E2E_API_TOKEN')
    
    # Otherwise, authenticate
    response = requests.post(
        f"{API_URL}/v1/auth/login",
        json={"username": "test", "password": "test"}
    )
    return response.json()['token']
```

### General

#### 1. **Test Isolation**

Always reset state between tests:

```python
@pytest.fixture(autouse=True)
def cleanup():
    """Auto-runs before each test"""
    yield
    # Cleanup after test
    clear_cache()
    reset_database()
```

#### 2. **Naming Clarity**

Chunk IDs follow format `{parent_hash}_chunk_{index:04d}`:

```python
def test_chunk_lookup_by_id():
    """Chunks are keyed by parent_id_s + index"""
    chunk_id = "abc123_chunk_0001"
    parent_hash = chunk_id.split('_chunk_')[0]
    # Query Solr for parent
    pass
```

#### 3. **File Generation in Tests**

Use `pathlib.Path` instead of bash heredocs:

```python
from pathlib import Path

@pytest.fixture
def test_pdf(tmp_path):
    """Create a test PDF"""
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"PDF content")
    return pdf_path
```

---

## Debugging & Troubleshooting

### Enable Verbose Output

```bash
# Show print statements
uv run pytest -s

# Extra verbose (function names, durations)
uv run pytest -vv --durations=10

# Show local variables on failure
uv run pytest -l
```

### Debug a Single Test

```bash
# Run one test with debugger
uv run pytest test_auth.py::test_login -s --pdb

# Show what's happening (uses ipdb or pdb)
# Type 'c' to continue, 'l' to list, 'n' to step
```

### Capture Logs

```bash
# Show log output during tests
uv run pytest --log-cli-level=DEBUG

# Also save to file
uv run pytest --log-file=test.log --log-level=DEBUG
```

### Browser Debugging (Playwright)

```bash
# Launch Playwright Inspector
PWDEBUG=1 uv run pytest e2e/test_search.py -s

# Or run with headed browser
E2E_HEADED=1 uv run pytest e2e/test_search.py -s
```

### Check Service Health

```bash
# Is Solr running?
curl http://localhost:8983/solr/admin/cores

# Is Redis running?
redis-cli ping

# Is RabbitMQ running?
curl http://localhost:15672/api/overview

# Check Docker services
docker-compose ps
docker-compose logs -f solr
```

### Clear Caches

Sometimes tests fail due to stale caches:

```bash
# Clear pytest cache
rm -rf .pytest_cache htmlcov .coverage

# Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} +
find . -name "*.pyc" -delete

# Reinstall Python dependencies
cd src/solr-search && uv sync && uv run pytest
```

---

## Additional Resources

- [Pytest Documentation](https://docs.pytest.org)
- [Vitest Documentation](https://vitest.dev)
- [Playwright Documentation](https://playwright.dev)
- [Test Quality Gates](../.squad/quality-gates.md)
- [Pre-Release Testing](../pre-release-testing.md)

---

*Last updated: 2026-06-13 | Maintained by Lambert (QA/Tester)*
