# CI Coverage Setup Patterns

**Domain:** pytest code coverage in uv-managed and pip-managed Python services, CI integration

**Maintainer:** Brett (Infrastructure Architect)

---

## Overview: Coverage in Aithena Services

| Service | Package Manager | Config File | Coverage Tool | Status |
|---------|-----------------|-------------|---------------|--------|
| `solr-search` | `uv` (pyproject.toml) | `pyproject.toml` | pytest-cov | ✅ Setup |
| `document-indexer` | `uv` (pyproject.toml) | `pyproject.toml` | pytest-cov | ✅ Setup |
| `document-lister` | `uv` (pyproject.toml) | `pyproject.toml` | pytest-cov | ✅ Setup |
| `embeddings-server` | `pip` (requirements.txt) | `pytest.ini` | pytest-cov | ✅ Setup |
| `admin` | `uv` (pyproject.toml) | `pyproject.toml` | pytest-cov | ✅ Setup |
| `aithena-ui` | `npm` (package.json) | `vitest.config.ts` | vitest coverage | ✅ Setup |

---

## Pattern 1: Coverage Setup for UV-Managed Services (pyproject.toml)

### Prerequisites
- Service uses `pyproject.toml` + `uv.lock` (managed by uv)
- `pytest-cov` is declared in `dependencies` or `optional-dependencies`

### Step 1: Add pytest-cov to Dependencies

**File:** `src/SERVICE/pyproject.toml`

```toml
[project]
dependencies = [
    "fastapi",
    "pydantic",
    # ... other dependencies
    "pytest-cov>=4.0.0",  # Add here or in dev dependencies
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0.0",  # Or here if preferred
]
```

### Step 2: Configure Coverage in pyproject.toml

Add coverage configuration to the same `pyproject.toml`:

```toml
[tool.coverage.run]
source = ["SERVICE"]  # Replace SERVICE with package name (e.g., "solr_search")
omit = [
    "*/tests/*",
    "*/test_*.py",
    "setup.py",
]
branch = true

[tool.coverage.report]
precision = 2
show_missing = true
skip_covered = false
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]

[tool.coverage.html]
directory = "htmlcov"
```

### Step 3: Run Coverage in CI

**File:** `.github/workflows/ci.yml` (or service-specific workflow)

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install uv
        uses: astral-sh/setup-uv@v2
      
      - name: Run tests with coverage
        working-directory: src/SERVICE
        run: uv run pytest -v --cov=SERVICE --cov-report=xml --cov-report=term-missing
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./src/SERVICE/coverage.xml
          flags: SERVICE
          fail_ci_if_error: false
```

### Step 4: Verify pytest.ini Precedence

**Important:** When both `pytest.ini` and `pyproject.toml` exist, **pytest.ini takes precedence.**

- If service has `pytest.ini`, it will override `pyproject.toml` settings
- To consolidate config, remove `pytest.ini` and move all settings to `[tool.pytest.ini_options]` in `pyproject.toml`

**Check for conflicts:**
```bash
ls -la src/SERVICE/pytest.ini  # If exists, remove or sync with pyproject.toml
```

---

## Pattern 2: Coverage Setup for Pip-Managed Services (requirements.txt)

### Prerequisites
- Service uses `requirements.txt` (no pyproject.toml)
- `pytest-cov` is listed in `requirements.txt`

### Step 1: Add pytest-cov to requirements.txt

**File:** `src/SERVICE/requirements.txt`

```
fastapi>=0.100.0
pydantic>=2.0
# ... other dependencies
pytest>=7.0
pytest-cov>=4.0.0
```

### Step 2: Create pytest.ini

**Important:** pip-managed services should use `pytest.ini` (not `pyproject.toml`, which is uv convention).

**File:** `src/SERVICE/pytest.ini`

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

[coverage:run]
source = SERVICE
omit =
    */tests/*
    */test_*.py
    setup.py
branch = True

[coverage:report]
precision = 2
show_missing = True
skip_covered = False
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:

[coverage:html]
directory = htmlcov
```

### Step 3: Run Coverage in CI

**File:** `.github/workflows/ci.yml`

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      
      - name: Install dependencies
        working-directory: src/SERVICE
        run: |
          pip install -r requirements.txt
      
      - name: Run tests with coverage
        working-directory: src/SERVICE
        run: pytest -v --cov=SERVICE --cov-report=xml --cov-report=term-missing
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./src/SERVICE/coverage.xml
          flags: SERVICE
          fail_ci_if_error: false
```

---

## Pattern 3: pytest.ini vs pyproject.toml — Precedence & Migration

### Precedence Rules

**pytest.ini takes precedence over pyproject.toml:**
1. If `pytest.ini` exists → **all pytest settings must be in pytest.ini** (pyproject.toml settings ignored)
2. If only `pyproject.toml` → pytest reads from `[tool.pytest.ini_options]`
3. If both exist with conflicting settings → pytest.ini wins, pyproject.toml settings are silent failures

### Migration Path (pip → uv)

When migrating a service from `pip` + `requirements.txt` to `uv` + `pyproject.toml`:

1. **Create `pyproject.toml`** with all dependencies from `requirements.txt`
2. **Move pytest config from `pytest.ini` to `[tool.pytest.ini_options]` in `pyproject.toml`**
3. **Delete `pytest.ini`** (optional, but cleaner)
4. **Verify:** Run `pytest --collect-only` to ensure config loads correctly

**Example migration:**

**Before (pip + pytest.ini):**
```
src/SERVICE/
├── requirements.txt
├── pytest.ini
└── src/
    └── SERVICE/
        └── __init__.py
```

**After (uv + pyproject.toml):**
```
src/SERVICE/
├── pyproject.toml
└── src/
    └── SERVICE/
        └── __init__.py
```

### Configuration Consolidation Example

**Old pytest.ini:**
```ini
[pytest]
testpaths = tests
python_files = test_*.py

[coverage:run]
source = SERVICE
branch = True
```

**New pyproject.toml:**
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]

[tool.coverage.run]
source = ["SERVICE"]
branch = true
```

---

## Pattern 4: Coverage CI Integration & Codecov Upload

### Step 1: Generate Coverage Report

```bash
# UV service
cd src/SERVICE && uv run pytest --cov=SERVICE --cov-report=xml --cov-report=term-missing

# Pip service
cd src/SERVICE && pytest --cov=SERVICE --cov-report=xml --cov-report=term-missing
```

**Output files:**
- `coverage.xml` — Codecov format (upload this)
- `.coverage` — Coverage database
- Console output with line-by-line miss summary

### Step 2: Upload to Codecov

**Action:** `codecov/codecov-action@v3`

```yaml
- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v3
  with:
    files: ./src/SERVICE/coverage.xml
    flags: SERVICE
    fail_ci_if_error: false  # Don't block CI if Codecov is down
```

**Parameters:**
- `files` — Path to coverage.xml (relative to repo root)
- `flags` — Badge label for this service (used in Codecov dashboard)
- `fail_ci_if_error` — Graceful degradation if Codecov is unavailable

### Step 3: Monitor Coverage Thresholds

**In `pyproject.toml` or `pytest.ini`, add fail-under threshold:**

```toml
[tool.coverage.report]
fail_under = 70  # Fail if coverage drops below 70%
```

**Run locally to validate:**
```bash
uv run pytest --cov=SERVICE --cov-report=term-missing --cov-fail-under=70
```

---

## Pattern 5: Multi-Service Coverage in CI

### Consolidated CI Workflow

**File:** `.github/workflows/ci.yml`

```yaml
name: CI - Tests & Coverage

on: [push, pull_request]

jobs:
  test-python:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        service: [solr-search, document-indexer, document-lister, admin, embeddings-server]
    steps:
      - uses: actions/checkout@v4
      
      - name: Install uv
        uses: astral-sh/setup-uv@v2
      
      - name: Run tests with coverage (${{ matrix.service }})
        working-directory: src/${{ matrix.service }}
        run: uv run pytest -v --cov --cov-report=xml --cov-report=term-missing
      
      - name: Upload coverage (${{ matrix.service }})
        uses: codecov/codecov-action@v3
        with:
          files: ./src/${{ matrix.service }}/coverage.xml
          flags: ${{ matrix.service }}
          fail_ci_if_error: false
  
  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: src/aithena-ui/package-lock.json
      
      - name: Install dependencies
        working-directory: src/aithena-ui
        run: npm ci
      
      - name: Run tests with coverage
        working-directory: src/aithena-ui
        run: npm run test:coverage
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./src/aithena-ui/coverage/coverage-final.json
          flags: frontend
          fail_ci_if_error: false
```

---

## Pattern 6: Troubleshooting Coverage Issues

### Issue 1: Coverage Not Running (pip-managed service)

**Symptom:** `pytest --cov=SERVICE` doesn't generate coverage.xml

**Solution:**
1. Verify `pytest-cov` is installed: `pip list | grep pytest-cov`
2. Verify pytest.ini exists and has `[coverage:run]` section
3. Verify source path is correct in pytest.ini: `source = SERVICE` (should match package name)
4. Run verbose: `pytest --cov=SERVICE -v --cov-config=pytest.ini`

### Issue 2: pytest.ini Overriding pyproject.toml

**Symptom:** Coverage config in pyproject.toml ignored when pytest.ini exists

**Solution:**
- Pytest reads pytest.ini first (takes precedence)
- Either:
  - Move all config to pytest.ini, OR
  - Delete pytest.ini and use only pyproject.toml (preferred for uv services)

### Issue 3: Coverage Report Missing Lines

**Symptom:** `.coverage` exists but `--cov-report=term-missing` shows no line numbers

**Solution:**
1. Verify `source` in config points to correct package: `source = SERVICE` (not `.` or absolute path)
2. Check file structure: coverage should find `src/SERVICE/SERVICE/*.py` or `SERVICE/*.py`
3. Run from repo root: `cd repo && pytest src/SERVICE --cov=SERVICE`

### Issue 4: Codecov Upload Fails

**Symptom:** Codecov action fails in CI but tests pass

**Solution:**
1. Set `fail_ci_if_error: false` to graceful-degrade
2. Verify `files:` path is correct relative to repo root
3. Check Codecov token permissions (if using PAT instead of GHCR)
4. Look at action logs for Codecov API errors

---

## Aithena Services: Coverage Implementation Status

### UV-Managed Services (pyproject.toml)

**solr-search** (`src/solr-search/pyproject.toml`)
```toml
[tool.coverage.run]
source = ["solr_search"]
branch = true
```

**document-indexer** (`src/document-indexer/pyproject.toml`)
```toml
[tool.coverage.run]
source = ["document_indexer"]
branch = true
```

**document-lister** (`src/document-lister/pyproject.toml`)
```toml
[tool.coverage.run]
source = ["document_lister"]
branch = true
```

**admin** (`src/admin/pyproject.toml`)
```toml
[tool.coverage.run]
source = ["admin"]
branch = true
```

### Pip-Managed Service (pytest.ini)

**embeddings-server** (`src/embeddings-server/pytest.ini`)
```ini
[coverage:run]
source = embeddings_server
branch = True
```

### Frontend (npm)

**aithena-ui** (`src/aithena-ui/vitest.config.ts`)
```typescript
export default defineConfig({
  test: {
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/**/*.{js,ts,jsx,tsx}'],
      exclude: ['src/**/*.test.{js,ts}'],
    },
  },
});
```

---

## CI Configuration Summary

### Across All Services

**Workflow file:** `.github/workflows/ci.yml`

**Coverage steps:**
1. Install dependencies (uv sync or pip install)
2. Run pytest with `--cov --cov-report=xml --cov-report=term-missing`
3. Upload to Codecov with service flag

**Service-specific notes:**
- **UV services:** Use `uv run pytest`
- **Pip services:** Use `pip install && pytest`
- **Frontend:** Use `npm run test:coverage`

---

## References
- **pytest-cov Documentation:** https://pytest-cov.readthedocs.io/
- **Coverage.py Configuration:** https://coverage.readthedocs.io/en/latest/config.html
- **Codecov GitHub Actions:** https://github.com/codecov/codecov-action
- **Aithena CI Workflows:** `.github/workflows/ci.yml`
