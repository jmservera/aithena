# Squad Decisions

## Active Decisions

### Architecture Plan — aithena Solr Migration (2026-03-13)

**Author:** Ripley (Lead)  
**Status:** PROPOSED — awaiting team review  
**Branch:** `jmservera/solrstreamlitui`

#### Executive Summary

Solid SolrCloud infrastructure exists, but the indexing pipeline is Qdrant-bound. Plan: 4-phase migration to Solr-native search with semantic layer (Phase 3).

**Phases:**
1. **Core Solr Indexing:** Fix volume mounting, add schema fields, rewrite indexer for Tika extraction, metadata extraction module
2. **Search API & UI:** FastAPI search service, React search interface with faceting, PDF viewer
3. **Embeddings Enhancement:** Vector field in Solr, embedding indexing pipeline, hybrid search mode, similar books feature
4. **Polish:** File watcher (60s polling), PDF upload endpoint, admin dashboard, production hardening

#### Key Architectural Decisions (ADRs)

| ADR | Decision | Rationale |
|---|---|---|
| ADR-001 | Hybrid indexing: Solr Tika (full-text) + app-side chunking (embeddings, Ph.3) | Fast Phase 1 execution, better control for Phase 3 |
| ADR-002 | Build metadata extraction module for filesystem path parsing | Explicit book fields (title, author, year, category) in Solr |
| ADR-003 | FastAPI for search API | Consistent with Python backend stack, thin Solr wrapper |
| ADR-004 | Standardize on `distiluse-base-multilingual-cased-v2` (Phase 3) | Lightweight, good multilingual support; resolve Dockerfile/main.py mismatch |
| ADR-005 | React UI rewrite (chat → search), keep Vite/TS scaffolding | Paradigm shift requires component rewrite, not refactor |

#### Team Assignments

| Member | Ph.1 | Ph.2 | Ph.3 | Ph.4 |
|---|---|---|---|---|
| **Parker** (backend) | Indexer rewrite, metadata extraction, volume fix | Search API (FastAPI) | Embedding pipeline, hybrid search | Upload endpoint, file watcher |
| **Dallas** (frontend) | — | Search UI, PDF viewer | Similar books feature | Upload UI |
| **Ash** (search) | Schema fields (title, author, year, category, etc.) | Search API tuning | Vector field config, kNN setup | — |
| **Lambert** (tester) | Integration tests (PDF → Solr) | API + UI tests | Embedding quality tests | E2E tests, production hardening |
| **Ripley** (lead) | Architecture review, decision approval | API contract review | Model selection review | Production readiness review |

#### Immediate Next Steps

1. Ash: Add book-specific fields to Solr schema (title_s, author_s, year_i, category_s, etc.)
2. Parker: Fix `docker-compose.yml` volume mapping (`/home/jmservera/booklibrary` → `/data/documents`)
3. Parker: Rewrite `document-indexer` for Solr Tika extraction (drop Qdrant dependency)
4. Parker: Build metadata extraction module with path parsing (support `Author/Title.pdf`, `Category/Author - Title (Year).pdf` patterns)
5. Lambert: Write tests for metadata extraction using actual library paths
6. Ripley: Review & approve schema changes before cluster deployment

#### Critical Gaps (to fix in Ph.1)

1. Book library (`/home/jmservera/booklibrary`) not mounted in docker-compose
2. Indexer fully Qdrant-dependent (imports `qdrant_client`, uses `pdfplumber` not Solr Tika)
3. No search API (qdrant-search commented out)
4. Schema lacks explicit book domain fields
5. Embeddings model mismatch (Dockerfile vs main.py)
6. React UI designed for chat, not search

#### Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Large PDF library overwhelms Solr Tika | HIGH | Batch with backpressure (RabbitMQ prefetch=1), retry + DLQ |
| Old books have OCR-quality text | MEDIUM | Accept lower quality; embeddings may handle noisy text better |
| Solr kNN search performance at scale | MEDIUM | Benchmark with real data in Phase 3 (Solr 9.x HNSW suitable for <1M vectors) |
| Docker bind-mount perf on macOS | LOW | Dev only; production on Linux is fine |
| Metadata heuristics fail on irregular paths | MEDIUM | Build with fallback defaults (title=filename, author="Unknown"), improve iteratively |

**Full architecture plan, current state assessment, phased breakdown, service diagram, and team roadmap:** See `.squad/decisions/archive/2026-03-13-ripley-architecture-plan.md`

---

## Phase 1 Implementation Decisions

### Ash — Schema Field Design

**Author:** Ash (Search Engineer)  
**Date:** 2026-03-13  
**Status:** IMPLEMENTED

**Decision:**
- Add explicit single-value fields for title, author, year, page count, file path, folder path, category, file size, and detected language.
- Copy `title_t` and `author_t` into `_text_` so the catch-all default query field includes book metadata.
- Keep `_text_` unstored in Phase 1 to avoid duplicating the full extracted body; use `content` as the stored highlight source and configure `_text_` highlighting with `f._text_.hl.alternateField=content`.

**Impact:**
- Parker can populate stable Solr field names directly from filesystem metadata extraction.
- Search clients can use `/select` or `/query` with default highlighting and receive snippets from `content` while still querying against `_text_`.
- Existing Tika/PDF metadata remains available for later tuning and faceting work.

---

### Parker — Solr Indexer Rewrite

**Author:** Parker (Backend Dev)  
**Date:** 2026-03-13  
**Status:** IMPLEMENTED

**Context:**
Phase 1 required the indexer to stop treating the library as Azure/Qdrant-backed storage and instead process local PDFs mounted into the containers.

**Decision:**
The rewritten `document-indexer` now treats RabbitMQ messages as local filesystem paths under `/data/documents` and sends the raw PDF to Solr's `/update/extract` handler with `literal.*` metadata fields.

**Metadata Heuristic:**
For single-folder paths, infer the parent folder as the author only when the filename does not look like a journal/category pattern. Journal/category signals currently include:
- Uppercase underscore series names
- Explicit year ranges like `1885 - 1886`
- Category-like folder names echoed in the filename (e.g., `balearics/ESTUDIS_BALEARICS_01.pdf`)

Otherwise, use the parent folder as author and strip repeated author tokens from the title (e.g., `amades/... amades.pdf`).

**Impact:**
- Keeps Phase 1 indexing working with the real mounted library while preserving support for requested `Author/Title.pdf` and `Category/Author - Title (Year).pdf` conventions.
- Avoids coupling indexing to Azure Blob Storage or Qdrant, which are no longer part of the Solr-first pipeline.

---

### Lambert — Metadata Extraction Test Contract

**Author:** Lambert (Tester)  
**Date:** 2026-03-13  
**Status:** IMPLEMENTED

**Test-Facing Decisions:**

1. `extract_metadata()` should return `file_path` and `folder_path` relative to `base_path`.
2. Real library conventions are mixed:
   - `amades/` should be treated as an author folder.
   - `balearics/` should be treated as a category/series folder.
   - `bsal/` is a category-like folder, but filenames containing year ranges such as `1885 - 1886` must not trigger `author - title` parsing or set `year`.
3. Unknown or unsupported shapes should stay conservative:
   - title = raw filename stem
   - author = `Unknown`
   - extra nesting must not invent an author from intermediate folders
4. Fallback title handling should preserve the original stem for unknown patterns (including underscores), because the spec explicitly says `title=filename`.

**Impact:**
These expectations are now encoded in `document-indexer/tests/test_metadata.py`. Parker and Ash should align implementation + Solr field usage to this contract so metadata is stable for indexing, faceting, and UI display.

---

---

## Phase 1 Polish & Metadata Decisions

### Parker — Metadata Extraction Heuristic Refinements

**Author:** Parker (Backend Dev)  
**Date:** 2026-03-13  
**Status:** IMPLEMENTED

**Decision:**
Refined metadata extraction to handle real library conventions more robustly:

1. **Preserve raw filename stem** as the fallback title for unknown patterns so special characters like underscores are not normalized away.
2. **Only infer `category/author`** from directory structure when the relative path is exactly two levels deep; deeper archive paths should keep the top-level category and leave author unknown unless the filename supplies one.
3. **Treat year ranges** such as `1885 - 1886` as series metadata rather than a single publication year.
4. **Normalize category acronyms** like `bsal` to uppercase when used as categories.

**Impact:**
- Metadata extraction now handles edge cases in the real library structure (`amades/`, `balearics/`, `bsal/`) consistently.
- Fallback title behavior is explicit and preserved; title=filename for unknown patterns.
- Indexing pipeline produces stable, predictable field values for Solr schema and UI display.

---

## Ripley — Phase 2–4 Issue Decomposition

**Author:** Ripley (Lead)  
**Date:** 2026-03-13  
**Status:** ACTIVE

**Decision:**
Track the remaining Solr migration work as 18 single-owner GitHub issues assigned to `@copilot`, ordered by dependency and release:

- **v0.4.0 / Phase 2:** Issues #36–#41 (Solr FastAPI search service)
- **v0.5.0 / Phase 3:** Issues #42–#47 (React search, embeddings, hybrid search)
- **v0.6.0 / Phase 4:** Issues #48–#53 (File watcher, upload endpoint, admin, E2E)

**Dependency Backbone:**
1. Solr FastAPI search service first.
2. React search rewrite, faceting, PDF viewing, and frontend tests on that service.
3. Embeddings model alignment before Solr vector schema, before indexer chunk/vector indexing, before hybrid search and similar-books.
4. 60s polling in `document-lister` before upload/admin polish, with E2E tests last.

**Team-Level Scope Choice:**
The PDF upload endpoint lives in the FastAPI backend (not a new service) to reuse the existing Redis/RabbitMQ/Solr ingestion path and avoid unnecessary service sprawl.

**Impact:**
- Squad triage can route Phase 2 work immediately without reopening architecture questions.
- Later semantic and polish work references concrete dependencies instead of broad phase notes.
- Future PR reviewers can validate against the numbered dependency chain rather than the epic-style roadmap.

---

## User Directive — Local Testing Setup

**Captured:** 2026-03-13T19:47:58Z  
**Source:** jmservera (via Copilot)

**Directive:**
To test the current setup locally, spin up the Docker Compose containers and assign a volume to `/home/jmservera/booklibrary` so the team has access to the local books.

**Why:** Critical context for all testing and development work in Phases 1–4.

---

## User Directives — Copilot Enterprise & Issue Routing

### 2026-03-13T20:56: Copilot Enterprise Label Activation

**Captured:** jmservera (via Copilot)

**Directive:**
@copilot cannot be assigned via gh CLI on personal repos, but will activate via the `squad:copilot` label through GitHub Actions. To trigger @copilot pickup, remove and re-add the `squad:copilot` label after the branch becomes the default.

---

### 2026-03-13T21:05: Staggered @copilot Issue Routing

**Captured:** jmservera (via Copilot)

**Directive:**
When routing issues to @copilot, use staggered batching instead of labeling everything at once:

1. Identify which issues within a phase can be done in parallel (no inter-dependencies)
2. Label only that batch with `squad:copilot`
3. Wait for PRs to be reviewed and merged
4. Label the next batch

**Why:** Labeling all 18 issues at once caused @copilot to work on Phase 3/4 before Phase 2 foundations existed, resulting in 18 simultaneous draft PRs, dependency violations, and wasted work.

**Batching Pattern:**
- **Phase 2 batch 1:** #36 (FastAPI search) — foundation, no deps
- **Phase 2 batch 2:** #37 (API tests), #38 (React search) — depend on #36
- **Phase 2 batch 3:** #39 (facets), #40 (PDF viewer), #41 (frontend tests) — depend on #38
- **Phase 3 batch 1:** #42 (embeddings model), #43 (vector fields) — independent infra
- **Phase 3 batch 2:** #44 (chunking pipeline) — depends on #42+#43
- (Continue similarly through Phase 4)

---

### 2026-03-13T21:15: Review Workflow Directives

**Captured:** jmservera (via Copilot)

**Directives:**
1. Let all @copilot PRs run — don't close or restart them.
2. Don't review next-phase PRs until all previous-phase PRs are reviewed and merged.
3. To request @copilot fix something in a PR, @ mention it in a PR comment (e.g., `@copilot please fix X`).

---

### 2026-03-13T22:15: CI Workflows & Testing Infrastructure

**Captured:** jmservera (via Copilot)

**Directive:**
Add GitHub Actions workflows for unit tests and integration tests. Use mocks for integration tests instead of full docker-compose, since the CI runner container is too small for the full stack.

---

## Parker — Phase 2 Implementation Decisions

### CI Workflows for Unit & Integration Tests

**Author:** Parker (Backend Dev)  
**Date:** 2026-03-14  
**Status:** IMPLEMENTED

**Implementation:** `.github/workflows/ci.yml`

**Jobs:**
- `document-indexer-tests` — 15 pytest tests for metadata extraction
- `solr-search-tests` — 8 unit tests + 10 integration tests for FastAPI search service
- `all-tests-passed` — Summary job requiring all to succeed

**Integration Test Strategy:**
- Created `solr-search/tests/test_integration.py` with FastAPI TestClient
- All Solr HTTP calls mocked with `unittest.mock.patch`
- Covers: search results, faceting, pagination, sorting, error handling, health/info endpoints
- NO docker-compose, NO real Solr — external dependencies mocked

**Critical Finding:**
FastAPI 0.99.1 + Starlette 0.27.0 requires `httpx<0.28` for TestClient compatibility. Newer httpx 0.28+ changed the Client API, breaking TestClient initialization. CI workflow explicitly pins `httpx<0.28`.

**Validation:** All tests passing locally (15+8+10 = 33 tests)

**Impact:**
- Every push validates existing tests pass
- PRs cannot merge if tests fail (when branch protection enabled)
- Tests run in parallel (~30-60s total runtime)
- No infrastructure needed — mocked integration tests avoid docker-compose overhead

---

### FastAPI Search URL & Language Compatibility

**Author:** Parker (Backend Dev)  
**Date:** 2026-03-13T23:00  
**Status:** DECIDED

**Context:**
Phase 2 needs search results the React UI can consume immediately, including links that open PDFs without exposing filesystem paths. Solr language data may appear as `language_detected_s` (Phase 1 contract) or `language_s` (current langid output), requiring stable client contract.

**Decision:**
- Expose `document_url` as `/documents/{token}`, where token is URL-safe base64 encoding of `file_path_s`
- Serve PDFs after decoding token and verifying resolved path stays under `BASE_PATH`
- Normalize language by preferring `language_detected_s`, falling back to `language_s`

**Impact:**
- Dallas and frontend work can open PDFs through stable API route (no filesystem-aware links)
- Backend maintains compatibility with already-indexed documents during Phase 1→Phase 3 language field standardization

---

## Ripley — Phase 2 Review & Planning Decisions

### PR #72 (FastAPI Search Service) — APPROVED

**Author:** Ripley (Lead)  
**Date:** 2026-03-13T23:15  
**Status:** MERGED

**Review Result:** PR #72 APPROVED — Ready to merge

**Strong Points:**
- Clean ADR-003-compliant architecture
- Comprehensive security (path traversal, injection protection)
- 11 unit tests covering core logic and edge cases
- Proper Docker integration

**Draft PR Assessment:**
1. **#54 & #60** — CLOSE — Redundant with PR #72 (same issues, inferior implementations)
2. **#61** (Search UI) — HOLD — Rebase after PR #72 merges
3. **#62** (Faceted UI) — HOLD — Clarify overlap with #61 before proceeding
4. **#63** (PDF viewer) — HOLD — Sequenced after search UI, depends on #72
5. **#64** (Test suite) — RETHINK — 3.7k lines too high-risk; break into feature-aligned PRs or hold

**Architectural Principle:** When multiple agents generate solutions for the same issue, prefer:
1. Security-first implementation
2. Test coverage for edge cases
3. Clean separation of concerns
4. Established patterns over novel approaches

---

### Phase 2 Frontend PR Overlap Resolution (#61, #62, #63)

**Author:** Ripley (Lead)  
**Date:** 2026-03-13T23:20  
**Status:** DECIDED

**Problem:**
- **#61** and **#62** both rewrite `App.tsx` from chat to search — direct conflict
- **#63** modifies wrong service (qdrant-search instead of solr-search)
- All three use different/incorrect API contracts

**Decision:**

| PR | Action | Rationale |
|----|--------|-----------|
| #61 | CLOSED ❌ | Redundant with #62 (superset); #62 is feature-complete |
| #62 | APPROVED ✅ | Canonical Phase 2 search UI with facets, pagination, sorting; one-line fix needed (`limit` → `page_size`) |
| #63 | NEEDS CHANGES ❌ | Must rebase on #62, layer PDF viewer, fix qdrant-search → solr-search |

**Why Close #61?**
- Both rewrite same `App.tsx` — one must win
- #62 is feature-complete for Phase 2; #61 would need follow-up PR for facets anyway
- Simpler to merge one complete PR than sequence two partial ones

**Why Reject #63?**
- Phase 2 architecture is explicitly Solr-first (ADR-001, decisions.md)
- qdrant-search is Phase 1 artifact, not Phase 2
- Mixing backends breaks migration path and creates API inconsistency

**Impact:**
- PR #62 becomes baseline for all Phase 2 UI work
- PR #63 must rebase on #62 and add features incrementally
- Prevents fragmentation: one search UI, not three competing versions

---

---

## User Directives — Tooling Modernization

### 2026-03-13T22:30: UV, Security Scanning, Linting Initiative

**Captured:** jmservera (via Copilot)

**Directive:**
1. Move Python projects to astral's `uv` for package management (replace pip + requirements.txt)
2. Add security scanning tools to CI: bandit, checkov, zizmor, OWASP ZAP
3. Add linting to CI: ruff (Python), eslint + prettier (TypeScript/React)
4. These should be part of the project instructions/CI workflows

**Why:** User request — security-first CI, modern Python tooling, consistent code quality

---

## Ripley — UV Migration + Security Scanning + Linting Implementation Plan

**Author:** Ripley (Lead)  
**Date:** 2026-03-14  
**Status:** PROPOSED  
**Requested by:** jmservera

### Executive Summary

Three parallel initiatives to modernize aithena:
1. **UV Migration:** Migrate 7 Python services from pip+requirements.txt to astral's `uv`
2. **Security Scanning:** Add bandit, checkov, and zizmor to CI
3. **Linting:** Add ruff (Python) and prettier (TypeScript/JS) to CI

**Total Issues:** 22 issues across 3 phases (11 Phase A parallel, 7 Phase B sequential, 4 Phase C validation)

### Phased Approach

**Phase A (Parallel):** 11 issues
- UV-1 through UV-7: Migrate 7 Python services (admin, solr-search, document-indexer, document-lister, qdrant-search, qdrant-clean, llama-server)
- SEC-1 through SEC-3: Add bandit, checkov, zizmor security scanning to CI
- LINT-1: Add ruff configuration and CI job

**Phase B (Sequential):** 7 issues
- UV-8, UV-9: Update build scripts and CI setup for UV
- LINT-2 through LINT-4: Add prettier and eslint CI jobs for aithena-ui
- LINT-5: Remove deprecated pylint/black from document-lister
- DOC-1: Document UV migration in root README

**Phase C (Validation):** 4 issues
- SEC-4: Create OWASP ZAP manual audit guide
- SEC-5: Run scanners, triage findings, validate baselines
- LINT-6, LINT-7: Run linters, auto-fix, validate clean state

### Services Migrated

- **Migrating:** document-indexer, document-lister, solr-search, qdrant-search, qdrant-clean, admin, llama-server (7 services)
- **Skipping:** embeddings-server (custom base image), llama-base (complex multi-stage build)

### Architectural Principles

1. **UV as default, pip as fallback** — Keep requirements.txt temporarily for backward compatibility
2. **Security scanning before production** — All HIGH/CRITICAL findings triaged before release
3. **Linting as gatekeeper** — CI fails on linting errors to prevent regression
4. **Incremental adoption** — Per-service migrations allow rollback if needed
5. **Documentation over automation** — Manual OWASP ZAP guide preferred over complex CI integration

### Key Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| UV alpine compatibility | UV has standalone installer; test early with document-indexer |
| Security scanners find false positives | Triage in SEC-5, create baseline exceptions, tune thresholds |
| Ruff finds linting issues | Auto-fix with `ruff check --fix` and `ruff format` |
| UV lock file merge conflicts | Phase A is per-service, minimal overlap |

### Execution Plan

1. Label Phase A issues (11 in parallel) with `squad:copilot`
2. Review and merge Phase A PRs
3. Label Phase B issues (7 sequential) with `squad:copilot`
4. Review and merge Phase B PRs
5. Label Phase C issues (4 validation) with `squad:copilot`

**Timeline:** Phase A (1-2 weeks) → Phase B (1 week) → Phase C (1 week) → **Total 3-4 weeks**

---

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
