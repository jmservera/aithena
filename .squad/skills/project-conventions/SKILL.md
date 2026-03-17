---
name: "project-conventions"
description: "Project context, tech stack, and conventions for the aithena codebase"
domain: "project-conventions"
confidence: "high"
source: "earned — consolidated from all agent charters during reskill audit"
author: "Ripley"
created: "2026-07-14"
last_validated: "2026-03-17"
last_reskilled: "2026-03-17 (Lambert)"
---

## Project Context

- **Project:** aithena — Book library search engine
- **User:** jmservera
- **Book library:** `/home/jmservera/booklibrary` (bind-mounted to `/data/documents` in containers)
- **Languages in texts:** Spanish, Catalan, French, English (including very old texts)
- **Key concern:** Transitioning from Qdrant vector DB to Solr for full-text + semantic search
- **Approach:** Phased — keyword search first, embeddings later

## Services

| Service | Path | Role |
|---------|------|------|
| document-lister | `document-lister/` | Polls `/data/documents/` for new PDFs, publishes to RabbitMQ |
| document-indexer | `document-indexer/` | Consumes queue, indexes into Solr via Tika extraction |
| embeddings-server | `embeddings-server/` | FastAPI server for `distiluse-base-multilingual-cased-v2` |
| solr-search | `solr-search/` | FastAPI search API (BM25 + facets + document serving) |
| aithena-ui | `aithena-ui/` | React/Vite frontend (search + facets + PDF viewer) |
| solr | `solr/` | SolrCloud 3-node cluster with ZooKeeper ensemble |

## Tech Stack

### Backend (Python 3.x)
- FastAPI + uvicorn (APIs)
- pysolr (Solr client)
- PyPDF2 / pdfplumber / PyMuPDF (PDF processing)
- watchdog (file system monitoring)
- RabbitMQ (message queue), Redis (caching/state)
- pytest (testing)

### Frontend (TypeScript)
- React 18+ with Vite
- Vitest + React Testing Library (testing)
- PDF.js / react-pdf (PDF viewing)

### Infrastructure
- Docker / Docker Compose / multi-stage builds
- Apache Solr 9.x / SolrCloud / ZooKeeper ensemble
- astral uv (Python package management in containers)
- nginx reverse proxy

## Testing

### Test Counts (v1.3.0 Baseline)

| Service | Test Count | Coverage | Notes |
|---------|------------|----------|-------|
| **solr-search** | 193 | 94.60% | Core search, auth, facets, PDF serving |
| **aithena-ui** | 189 | — | Vitest + React Testing Library; covers search, facets, PDF viewer |
| **document-indexer** | 91 + 4 skipped | 81.50% | 4 tests skip if env vars misconfigured; RabbitMQ consumer tests |
| **admin** | 81 | — | Streamlit app; 19 InsecureKeyLengthWarning from test-only HMAC keys (not a prod issue) |
| **document-lister** | 12 | — | File watcher and RabbitMQ publisher tests |
| **embeddings-server** | 9 | — | Multilingual embedding server; requires manual test deps install |
| **TOTAL** | **469** | — | All passing as of v1.3.0 release |

### Service-Specific Testing Quirks

#### embeddings-server ⚠️
- **Issue:** `requirements.txt` lacks test dependencies (`pytest`, `httpx`)
- **Solution:** Manually install test deps: `.venv/bin/pip install pytest httpx` before running tests
- **Why:** Keeps production image lightweight; test deps only needed in dev
- **Status:** Known and accepted; document in test runbooks

#### document-indexer ⚠️
- **Issue:** 4 tests skip if environment variables are misconfigured (RabbitMQ host, Solr host, etc.)
- **Impact:** Test count may vary depending on CI env setup
- **Solution:** Ensure CI sets required env vars before running pytest
- **Pattern:** Tests check for env vars and `skip()` gracefully rather than fail

#### admin (Streamlit) ⚠️
- **Issue:** Test-only HMAC keys generate `InsecureKeyLengthWarning` (openssl constraint)
- **Impact:** 19 warnings during test run; non-blocking, test-only concern
- **Production:** Use 256-bit keys in production
- **Acceptable:** False positive from test key generation; ignore in CI

### Coverage Baselines

- **solr-search:** ≥ 90% (currently 94.60%)
- **document-indexer:** ≥ 80% (currently 81.50%)
- Other services: No thresholds currently enforced

### Patterns

### File Structure
- Each service is a top-level directory with its own `Dockerfile` and `requirements.txt`
- Solr config lives in `solr/books/` (managed-schema.xml, solrconfig.xml)
- Docker Compose orchestrates all services

### Testing
- Python: pytest — tests live alongside source or in `tests/` subdirectory
- Frontend: Vitest — test files as `*.test.ts` / `*.test.tsx`
- E2E: Playwright (`e2e/playwright/`) reads live `/v1/search/` API results; no fixtures

### Error Handling
- FastAPI services use HTTP status codes + JSON error responses
- PDF processing uses try/catch with fallbacks for corrupted files


## Anti-Patterns

- **Don't target qdrant-search for new work** — it's deprecated; use solr-search
- **Don't use pdfplumber for full-text when Solr Tika is available** — see skill `solr-pdf-indexing`
- **Don't pin application traffic to a single Solr node** — see skill `solrcloud-docker-operations`
