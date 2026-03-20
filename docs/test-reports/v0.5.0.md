# Aithena v0.5.0 Test Report

_Date:_ 2026-03-15  
_Prepared by:_ Newt (Product Manager)

## Scope and evidence collected

Commands executed for this report:

```bash
cd /home/jmservera/source/aithena/src/solr-search && uv run pytest -v --tb=short
cd /home/jmservera/source/aithena/src/document-indexer && uv run pytest -v --tb=short
cd /home/jmservera/source/aithena/src/aithena-ui && npx vitest run
```

## Executive summary

- **Overall result:** **197 / 197 tests passed**.
- **Backend:** **173 passing tests** across `solr-search` and `document-indexer`.
- **Frontend:** **24 passing tests** across 4 Vitest component suites.
- **Failures:** none.
- **Warnings:** `solr-search` emitted **43 warnings** during the pytest run, but the suite still passed cleanly.

## Summary table

| Area | Command | Result |
|---|---|---|
| `solr-search` | `uv run pytest -v --tb=short` | **78 passed**, 43 warnings |
| `document-indexer` | `uv run pytest -v --tb=short` | **95 passed** |
| `aithena-ui` | `npx vitest run` | **24 passed** across 4 files |
| **Total** | — | **197 passed** |

## Backend results

### `solr-search`

**Status:** PASS  
**Command:** `cd /home/jmservera/source/aithena/solr-search && uv run pytest -v --tb=short`

**Run summary:**

- **78 passed**
- **43 warnings**
- runtime in this run: **1.56s**

**What the suite covers:**

- keyword search behavior and API aliases
- pagination and sorting
- keyword / semantic / hybrid mode behavior
- similar-books endpoint behavior
- stats endpoint contracts
- status endpoint contracts
- Solr parameter building, filtering, escaping, pagination, and result normalization
- reciprocal rank fusion helpers
- document token/path safety checks

**Warnings observed:**

- `PendingDeprecationWarning` from `starlette.formparsers` about `multipart`
- `DeprecationWarning` from `httpx` TestClient's `app` shortcut

These warnings did not cause failures, but they remain upgrade-risk signals for future dependency work.

### `document-indexer`

**Status:** PASS  
**Command:** `cd /home/jmservera/source/aithena/document-indexer && uv run pytest -v --tb=short`

**Run summary:**

- **95 passed**
- runtime in this run: **1.24s**

**What the suite covers:**

- chunking behavior and page-aware chunk propagation
- document indexing orchestration
- Solr startup gating
- Redis failure-state recording
- literal parameter generation for Solr extract uploads
- chunk document generation for embedding docs
- metadata extraction from filenames and folders
- the v0.5.0 language fix, including folder-based language detection and `language_s` propagation

## Frontend results

### `aithena-ui`

**Status:** PASS  
**Command:** `cd /home/jmservera/source/aithena/aithena-ui && npx vitest run`

**Run summary:**

- **4 / 4 test files passed**
- **24 / 24 tests passed**
- runtime in this run: **4.57s**

### Suite breakdown

| Test file | Tests | Focus |
|---|---:|---|
| `src/__tests__/SearchPage.test.tsx` | 6 | search input, empty state, results, API error, PDF open flow, Similar Books selection |
| `src/__tests__/SimilarBooks.test.tsx` | 4 | loading, success, empty, click-through, error handling |
| `src/__tests__/FacetPanel.test.tsx` | 6 | facet rendering, counts, select/deselect behavior, hidden empty groups |
| `src/__tests__/PdfViewer.test.tsx` | 8 | dialog rendering, close controls, iframe URLs, page anchors, missing-document fallback |

### Frontend test environment

The shipped frontend tests run with:

- **Vitest 4.1.0**
- **jsdom** test environment
- **@testing-library/react**
- **@testing-library/user-event**
- **@testing-library/jest-dom** via `vitest.setup.ts`

## Quality assessment for v0.5.0

The release now has stronger automated coverage than v0.4.0 because the UI no longer relies only on backend tests. The biggest gains in this report are:

1. **Search mode coverage** in the backend and UI,
2. **Similar Books coverage** in the backend and UI,
3. **language detection fix coverage** in `document-indexer`, and
4. **component-level regression coverage** for the React search experience.

The remaining caution is not test failure, but maintenance noise from the existing `solr-search` warnings. They do not block the release, but they should stay on the backlog for dependency cleanup.
