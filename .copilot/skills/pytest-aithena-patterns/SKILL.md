---
name: "pytest-aithena-patterns"
description: "Pytest fixture strategies, mock patterns, and service-specific testing quirks for aithena Python services"
domain: "testing, pytest, python"
confidence: "high"
source: "earned — Lambert's test work across solr-search, document-indexer, admin, embeddings-server (v1.2.0–v1.10.0)"
author: "Lambert"
created: "2025-07-17"
last_validated: "2025-07-17"
---

## Context

Use when writing or reviewing pytest tests for any aithena Python service. Covers fixture patterns, mock strategies, and per-service quirks that trip up new contributors.

## Pattern 1: Frozen Dataclass Settings Patching

aithena config objects are frozen dataclasses. Normal `monkeypatch.setattr()` fails on them.

```python
# WRONG — raises FrozenInstanceError
monkeypatch.setattr(settings, "auth_db_path", db_path)

# CORRECT — bypass frozen protection
object.__setattr__(settings, "auth_db_path", db_path)
```

Use in `conftest.py` fixtures that need to override config for test isolation.

## Pattern 2: Rate Limiter Cleanup (autouse fixture)

FastAPI rate limiters (e.g., `login_rate_limiter`) accumulate state across tests when using `TestClient` against the shared app instance.

```python
@pytest.fixture(autouse=True)
def clear_rate_limiter():
    login_rate_limiter.requests.clear()
    yield
    login_rate_limiter.requests.clear()
```

Without this, later tests in the suite hit 429 Too Many Requests unexpectedly.

## Pattern 3: Environment-Dependent Test Skipping

document-indexer has 4 tests that depend on RabbitMQ/Solr host env vars. Pattern:

```python
@pytest.mark.skipif(
    not os.environ.get("RABBITMQ_HOST"),
    reason="Requires RABBITMQ_HOST env var"
)
def test_indexing_pipeline():
    ...
```

This keeps CI green when infra isn't available while preserving tests for local/integration runs.

## Pattern 4: Real-Library Corpus Fixtures

Tests that use real file paths from `/home/jmservera/booklibrary` should:

1. Guard with `skipif` so CI doesn't fail when library is unavailable
2. Use portable temp-path fixtures for canonical patterns
3. Keep real-path tests for edge cases that can't be synthesized (OCR artifacts, old text encodings)

```python
LIBRARY_PATH = Path("/home/jmservera/booklibrary")

@pytest.mark.skipif(
    not LIBRARY_PATH.exists(),
    reason="Requires local book library"
)
def test_bsal_year_range_edge_case():
    ...
```

## Pattern 5: FastAPI TestClient + Mocked Services

For integration tests against FastAPI endpoints:

```python
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

@pytest.fixture
def client():
    from main import app
    return TestClient(app)

def test_search_returns_results(client):
    with patch("search_service.query_solr", return_value=mock_response):
        response = client.get("/v1/search/?q=test")
        assert response.status_code == 200
```

Mock at the service boundary (Solr, Redis, RabbitMQ), not at the HTTP layer.

## Service-Specific Quirks

| Service | Quirk | Workaround |
|---------|-------|------------|
| embeddings-server | `requirements.txt` lacks `pytest`, `httpx` | Run `pip install pytest httpx` before testing |
| document-indexer | 4 tests skip without env vars | Set RABBITMQ_HOST, SOLR_HOST in CI env |
| admin (Streamlit) | 19 InsecureKeyLengthWarning | Ignore — test-only HMAC keys, use 256-bit in prod |
| all uv services | SSL errors in codespace | Set `UV_NATIVE_TLS=1` before `uv sync` |

## Anti-Patterns

- **Don't mock the thing you're testing** — mock external dependencies (Solr, Redis, RabbitMQ), not the service under test
- **Don't use `monkeypatch` on frozen dataclasses** — use `object.__setattr__()` instead
- **Don't ignore rate limiter state** — use autouse cleanup fixtures
- **Don't hardcode real library paths without skipif** — breaks CI

## References

- `src/solr-search/tests/conftest.py` — fixture examples
- `src/solr-search/tests/test_auth.py` — rate limiter + frozen settings patterns
- `.squad/skills/path-metadata-tdd/` — metadata-specific TDD patterns
- `.squad/skills/tdd-clean-code/` — general TDD principles
