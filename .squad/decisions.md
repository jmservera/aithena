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

### 2026-03-14T08:35: User directive — delete branches after merge
**By:** jmservera (via Copilot)
**What:** When a PR is accepted/merged, delete the branch. Only keep branches for actual in-process work. Old branches should be deleted.
**Why:** User request — keep clean branch list

### 2026-03-14T09:45: User directive — remove Azure dependencies
**By:** jmservera (via Copilot)
**What:** This is a completely on-prem project that must run on docker compose without external dependencies. Remove any dependency on Azure (azure-identity, azure-storage-blob in document-lister). The Dependabot azure-identity alert will resolve itself once the dependency is removed.
**Why:** User request — on-prem only, no cloud provider dependencies

### 2026-03-14T07:57: User directive — Ripley model override
**By:** jmservera (via Copilot)
**What:** Change Ripley's default model to Claude Opus 4.6 1M Context
**Why:** User request — Lead needs premium model for deep code review and architecture work

### 2026-03-14T08:32: User directive — local testing with Playwright
**By:** jmservera (via Copilot)
**What:** The team can run the project locally to test it, and use Playwright to check the UI
**Why:** User request — enables end-to-end validation before merging

### 2026-03-14T10:19: User directive — hybrid dev workflow
**By:** jmservera (via Copilot)
**What:** Run stable infrastructure (Solr, ZooKeeper, Redis, RabbitMQ) in Docker, but run the code being debugged (solr-search, document-indexer, aithena-ui, etc.) directly on the host. This makes debugging and fixing easier when the rest of the solution is already working correctly.
**Why:** User preference — faster dev loop, easier debugging, only containerize stable infra

### 2026-03-14T10:34: User directive — Juanma as human decision gate
**By:** jmservera / Juanma (via Copilot)
**What:** Add Juanma as human Product Owner. Route important decisions the team cannot make autonomously to Juanma and HOLD until he responds. If he forgets, insist. All clear/parallel work continues — only blocking decisions wait. Autopilot mode respects this gate.
**Why:** User request — human-in-the-loop for key decisions, no-block for clear work

### 2026-03-14T08:36: User directive — trim unused projects and containers
**By:** jmservera (via Copilot)
**What:** Analyze which projects and containers no longer make sense to keep. Trim the project accordingly — remove deprecated/unused services.
**Why:** User request — reduce maintenance burden, keep only what's actively used

### Decision: Charter Reskill — Extract Procedures to Skills
**Author:** Ripley  
**Date:** 2026-07-14  
**Status:** Implemented

#### What Changed
Extracted duplicated procedural content from 7 agent charters into shared skills, reducing total charter size from 13.4KB to 9.2KB (31% reduction).

#### Decisions Made

1. **Project Context sections removed from all charters** — Agents get project context from `decisions.md`, `team.md`, and the `project-conventions` skill at spawn time. Duplicating it in every charter wastes ~2.5KB.

2. **Tech Stack sections removed from 6 charters** — Consolidated into `project-conventions` skill. Agent-specific tool knowledge stays in responsibilities (e.g., "Configure multilingual text analyzers" implies Solr expertise).

3. **`project-conventions` skill rewritten** — Replaced the empty template with actual project context, service inventory, tech stack, testing conventions, and anti-patterns.

4. **`squad-pr-workflow` skill created** — Extracted branch naming, PR conventions, commit trailers, and stale PR detection patterns from copilot charter and Ripley's history.

5. **Copilot Capability Profile preserved** — This is functional config (self-assessment matrix), not procedure. Kept in charter.

6. **Scribe charter untouched** — Already under 1KB (936B).

#### Impact
All charters now under 1.5KB target except copilot (2.2KB — contains required capability profile matrix that can't be externalized without breaking auto-assign logic).

### PR Triage & Prioritization — 2026-07-14
**Author:** Ripley (Lead)
**Status:** EXECUTED

#### Merged
- **#55** — E2E test harness (Phase 4, approved, clean merge)
- **#101** — Dependabot: Bump esbuild, vite, @vitejs/plugin-react
- **#102** — Dependabot: Bump js-yaml 4.1.0 → 4.1.1

#### Priority Order for Remaining Work

1. **#63 (Phase 2, HIGH)** — PDF viewer panel. Assigned @copilot. Surgical extraction: only PdfViewer.tsx + integration.
2. **#68 (Phase 3, HIGH)** — Hybrid search modes. Assigned @copilot. Keystone for Phase 3.
3. **#69 (Phase 3, MEDIUM)** — Similar books endpoint. Assigned @copilot. BLOCKED on #68.
4. **#56 (Phase 4, LOW)** — Docker hardening. Assigned @copilot, low priority.

#### Closed (not worth fixing)
- **#70** — Similar books UI. Built on old chat UI (pre-PR #62). Needs full rewrite, not rebase.
- **#58** — PDF upload endpoint. Targets qdrant-search/, architecturally wrong. Needs fresh implementation.
- **#59** — PDF upload UI. Built on old chat UI. Needs full rewrite after upload endpoint exists.

#### Rationale
PRs built on the old chat UI (before PR #62 rewrote to search paradigm) cannot be meaningfully rebased — the component tree is completely different. PRs targeting qdrant-search/ instead of solr-search/ are architecturally misaligned per ADR-001/ADR-003. Both classes should be re-created from scratch when their phase is prioritized.

PRs that only need conflict resolution in existing solr-search/ or aithena-ui/ files (#63, #68, #69, #56) are worth fixing because the core logic is sound.

### Feature Priorities Analysis — 2026-07-15
**Author:** Ripley (Lead)
**Status:** PROPOSED — awaiting user review
**Requested by:** jmservera

#### Priority 1: Test the Indexer — Verify End-to-End Pipeline

**Existing issue:** NEW — needs issue
**Current state:**
- ✅ `document-indexer` fully rewritten for Solr (Tika extraction + chunk/embedding indexing). Imports `SOLR_HOST`, `SOLR_COLLECTION`; POSTs to `/update/extract` with literal metadata params. No Qdrant dependency remains.
- ✅ `solr-init` service added to `docker-compose.yml` — auto-bootstraps the `books` collection (uploads configset to ZooKeeper, creates collection with RF=3, runs `add-conf-overlay.sh`).
- ✅ `document-lister` polls `/data/documents/` (configurable `POLL_INTERVAL`, default 60s via PR #71), publishes paths to RabbitMQ.
- ✅ `document-data` volume mounts `/home/jmservera/booklibrary` → `/data/documents` in containers.
- ✅ E2E test harness exists (`e2e/test_upload_index_search.py`, merged via PR #55) — but it **bypasses** the actual pipeline by POSTing directly to Solr's extract endpoint.
- ⚠️ The full pipeline (document-lister → RabbitMQ → document-indexer → Solr) has **never been verified** with real books.

**Gap:** No one has started the full stack and confirmed `numFound > 0` from an actual indexing run. The E2E test uses a synthetic fixture PDF and skips the lister/indexer services entirely. We need a manual smoke test **and** an automated pipeline integration test.

**Plan:**
1. Start the stack: `docker compose up -d`
2. Wait for `solr-init` to complete: check `docker compose logs solr-init` for "Solr init complete"
3. Wait for `document-lister` to discover files: check `docker compose logs document-lister` for listed file count
4. Wait for `document-indexer` to process queue: check `docker compose logs document-indexer` for "Indexed ... into Solr"
5. Verify: `curl http://localhost:8983/solr/books/select?q=*:*&rows=0` — expect `numFound > 0`
6. If failures, inspect Redis state via `admin/` Streamlit dashboard for error details
7. File a bug for any issues found, then write an automated pipeline test in `e2e/`

**Assigned to:** Lambert (tester) — manual verification; Brett (infra) — fix any docker/volume issues
**Effort:** M (2-3 hours manual testing, additional time for fixes)

#### Priority 2: Test Search Actually Finds Words — Keyword Search Validation

**Existing issue:** #45 (hybrid search modes) — CLOSED/MERGED as PR #68. Partially addresses this.
**Also related:** PR #72 (solr-search API, merged), PR #62 (faceted search UI, merged)
**Current state:**
- ✅ `solr-search` FastAPI service exists with `keyword`, `semantic`, and `hybrid` modes (default: `keyword`).
- ✅ API endpoint: `GET http://localhost:8080/v1/search/?q={word}&mode=keyword`
- ✅ Solr schema has `_text_` catch-all field with copyField from `title_t`, `author_t`.
- ✅ Tika extraction populates `_text_` with PDF full-text content.
- ⚠️ **No real-data search validation exists.** All tests use mocked Solr responses.
- ⚠️ Semantic search depends on embeddings-server being healthy AND chunk documents existing with `embedding_v` vectors — untested with real data.

**Gap:** Nobody has extracted a word from a known PDF, searched for it, and confirmed it appears in results. Need to: (a) confirm keyword/BM25 search works with actual indexed data; (b) assess whether semantic/hybrid search works or should be deferred.

**Plan:**
1. **Depends on Priority 1** — need indexed data first.
2. Pick a known book from `/home/jmservera/booklibrary`. Use `pdftotext <book>.pdf - | head -100` to extract distinctive words.
3. Keyword test: `curl "http://localhost:8080/v1/search/?q={distinctive_word}"` — verify the book appears in results with highlights.
4. Facet test: Verify author/year/language facets are populated in the response.
5. Semantic test: Try `curl "http://localhost:8080/v1/search/?q={word}&mode=semantic"` — if embeddings server is healthy and chunks were indexed, this should work. If not, document as future task (don't block).
6. Write a real-data validation script in `e2e/` that automates steps 2-5.

**Assigned to:** Lambert (tester) — validation script; Parker (backend) — fix any API issues
**Effort:** S (1-2 hours once data is indexed)

#### Priority 3: Make Books Folder Configurable via .env

**Existing issue:** NEW — needs issue
**Current state:**
- ✅ `.env` is already in `.gitignore` (line 123).
- ❌ No `.env` file exists.
- ❌ `docker-compose.yml` hardcodes `/home/jmservera/booklibrary` in the `document-data` volume (line 449).
- ✅ The `docker-compose.e2e.yml` already demonstrates the pattern: `device: "${E2E_LIBRARY_PATH:-/tmp/aithena-e2e-library}"` — this is the exact template to follow.
- Other volumes also hardcode paths: `/source/volumes/rabbitmq-data`, `/source/volumes/solr-data`, etc.

**Gap:** Single-line change in `docker-compose.yml` + create a `.env.example` file.

**Plan:**
1. In `docker-compose.yml`, change `device: "/home/jmservera/booklibrary"` → `device: "${BOOKS_PATH:-/home/jmservera/booklibrary}"` (preserves backward compat).
2. Create `.env.example` with documented variables:
   ```
   # Path to the book library directory
   BOOKS_PATH=/home/jmservera/booklibrary
   ```
3. Consider also parameterizing the other volume paths (`/source/volumes/*`) for portability, but keep that as a follow-up to avoid scope creep.
4. Test: `cp .env.example .env`, edit path, `docker compose config | grep device` to verify substitution.

**Assigned to:** Brett (infra)
**Effort:** S (30 minutes)

#### Priority 4: UI Indexing Status Dashboard + Library Browser

**Existing issue:** #51 (Streamlit admin dashboard) — CLOSED (PR #57 merged). But that's the **Streamlit** admin, not the **React** UI.
**Also related:** #50 (PDF upload flow, OPEN), #41 (frontend tests, OPEN)
**Current state:**
- ✅ **Streamlit admin** (`admin/src/main.py`) already shows: Total Documents, Queued, Processed, Failed counts (from Redis), RabbitMQ queue depth, and a Document Manager page for inspection/requeue. This covers the *operator* view.
- ✅ **React UI** (`aithena-ui/`) has: search bar, faceted search, pagination, sort, PDF viewer. No stats/status/library pages.
- ❌ No React UI page for indexing status, collection statistics, or library browsing.
- The React UI currently talks only to `solr-search` (`/v1/search/`). There is no backend endpoint for collection stats or library browsing.

**Gap:** This is a **new feature** requiring both backend API endpoints and frontend pages. Two sub-features:

##### A. Indexing Status + Collection Stats
**Backend:** New endpoint(s) in `solr-search`:
- `GET /v1/stats` → Returns Solr collection stats (`numDocs`, facet counts for language/author/year) + Redis pipeline stats (queued/processed/failed counts).

**Frontend:** New page/section in React UI:
- **Indexing Status:** Documents indexed, in queue, failed (from Redis via new API).
- **Collection Stats:** Total books, breakdown by language (pie chart), by author (top 20 bar), by year (histogram), by category.
- **Data source:** Combine Solr `facet.field` queries with Redis state query.

##### B. Library Browser
**Backend:** New endpoint in `solr-search`:
- `GET /v1/library?path={folder}` → Returns folder listing with document counts, or documents in a folder.
- Uses Solr `folder_path_s` facet for navigation, `file_path_s` for document listing.

**Frontend:** New page in React UI:
- **Folder tree** navigation (collapsible, driven by `folder_path_s` facet).
- **Document list** per folder (title, author, year, indexing status icon).
- Click-to-search (pre-fill search with `fq_folder={path}`) or click-to-view-PDF.

##### Proposed Menu/Page Structure
```
┌──────────────────────────────────────┐
│  🏛️ Aithena                          │
│  ┌──────┬──────────┬─────────┐       │
│  │Search│ Library  │ Status  │       │
│  └──────┴──────────┴─────────┘       │
│                                      │
│  Search  → current search UI (default)│
│  Library → folder browser + doc list  │
│  Status  → indexing pipeline + stats  │
└──────────────────────────────────────┘
```

**Plan:**
1. **Backend — Stats endpoint** (Parker): Add `GET /v1/stats` to `solr-search/main.py`. Query Solr for `numDocs` + facet summaries. Query Redis for pipeline state counts.
2. **Backend — Library endpoint** (Parker): Add `GET /v1/library` with `path` param. Use Solr `folder_path_s` facet for tree, `file_path_s` filter for listing.
3. **Frontend — Tab navigation** (Dallas): Add React Router or tab component. Three tabs: Search (current), Library, Status.
4. **Frontend — Status page** (Dallas): Fetch `/v1/stats`, render indexing pipeline metrics + collection charts.
5. **Frontend — Library page** (Dallas): Fetch `/v1/library`, render folder tree + document grid.
6. **Tests** (Lambert): API tests for new endpoints, component tests for new pages.

**Assigned to:** Parker (backend endpoints), Dallas (React pages), Lambert (tests)
**Effort:** L (1-2 weeks across team)

### Code Scanning Alerts — GitHub API Findings
**Date:** 2026-03-14
**Author:** Kane (Security Engineer)

#### Summary
- Code scanning: 3 open alerts (medium: 3; no critical/high)
- Dependabot: 4 open alerts (critical: 2, high: 1, medium: 1)
- Secret scanning: not accessible — API returned `404 Secret scanning is disabled on this repository`
- Tool breakdown: CodeQL (3)
- Cross-reference: no overlap with prior Bandit triage; current GitHub alerts are workflow-permission hardening and dependency vulnerabilities, while prior Bandit findings were dominated by third-party `.venv` noise

#### Open Code Scanning Alerts
| # | Rule | Severity | File | Line | Description |
|---|------|----------|------|------|-------------|
| 7 | `actions/missing-workflow-permissions` | medium | `.github/workflows/ci.yml` | 18 | Workflow does not contain permissions |
| 8 | `actions/missing-workflow-permissions` | medium | `.github/workflows/ci.yml` | 41 | Workflow does not contain permissions |
| 9 | `actions/missing-workflow-permissions` | medium | `.github/workflows/ci.yml` | 68 | Workflow does not contain permissions |

#### Critical/High Code Scanning Alerts (require action)
No critical or high-severity code scanning alerts are currently open.

#### Dependabot Critical/High Snapshot
| # | Package | Severity | Location | Vulnerable Range | First Patched | Summary |
|---|---------|----------|----------|------------------|---------------|---------|
| 40 | `qdrant-client` | critical | `qdrant-search/requirements.txt` | `< 1.9.0` | `1.9.0` | qdrant input validation failure |
| 41 | `qdrant-client` | critical | `qdrant-clean/requirements.txt` | `< 1.9.0` | `1.9.0` | qdrant input validation failure |
| 44 | `braces` | high | `aithena-ui/package-lock.json` (transitive via `micromatch`) | `< 3.0.3` | `3.0.3` | Uncontrolled resource consumption in braces |

#### Additional Dependabot Context
| # | Package | Severity | Location | Vulnerable Range | First Patched | Summary |
|---|---------|----------|----------|------------------|---------------|---------|
| 43 | `azure-identity` | medium | `document-lister/requirements.txt` | `< 1.16.1` | `1.16.1` | Azure Identity Libraries and Microsoft Authentication Library Elevation of Privilege Vulnerability |

#### Recommended Actions
1. Add explicit least-privilege `permissions:` to `.github/workflows/ci.yml` at workflow or job scope so each CI job only gets the token scopes it needs; this should clear all three open CodeQL alerts.
2. Upgrade `qdrant-client` to `>=1.9.0` in both `qdrant-search/requirements.txt` and `qdrant-clean/requirements.txt`; these are the highest-risk open findings because they are critical and affect request validation.
3. Refresh `aithena-ui` dependencies/lockfile so `braces` resolves to `3.0.3+` (likely via updated transitive packages such as `micromatch`/`fast-glob`); verify the lockfile no longer pins `braces` `3.0.2`.
4. Upgrade `azure-identity` in `document-lister/requirements.txt` to `>=1.16.1` after validating compatibility with the current Azure SDK usage.
5. Enable secret scanning if repository policy allows it; current API response indicates the feature is disabled, so exposed-secret coverage is absent.

### Security Audit — Initial Findings
**Date:** 2026-03-14
**Author:** Kane (Security Engineer)

#### Summary
- bandit: 1,688 raw findings (30 HIGH / 54 MEDIUM / 1,604 LOW). All 30 HIGH findings came from the checked-in `document-indexer/.venv/` third-party environment; first-party code triage is 0 HIGH / 4 MEDIUM / 136 LOW.
- checkov: 555 passed, 18 failed on Dockerfiles. `checkov --framework docker-compose` is not supported by local Checkov 3.2.508, so `docker-compose.yml` was reviewed manually.
- Dependabot: 0 open alerts via GitHub API (`gh api repos/jmservera/aithena/dependabot/alerts`).
- Actions: 15 supply chain risks (14 tag-pinned action refs across 5 workflows, plus `ci.yml` missing explicit `permissions:`).
- Dockerfiles: 14 direct hardening issues from manual review (8 images run as root, 6 `pip install` commands missing `--no-cache-dir`; no `latest` tags, no `.env`/secret copies found).

#### Critical (fix immediately)
- No confirmed critical findings in first-party application code.
- Raw Bandit HIGH results are scanner noise from the tracked `document-indexer/.venv/` tree (`pdfminer`, `pip`, `requests`, `redis`, etc.). This should be excluded from CI scanning or removed from the repository so real findings are not buried.

#### High (fix this sprint)
- **Pin GitHub Actions to commit SHAs.** Every workflow uses floating tags (`actions/checkout@v4`, `actions/setup-python@v5`, `actions/github-script@v7`) instead of immutable SHAs, leaving CI vulnerable to supply-chain tag retargeting.
- **Tighten workflow token scope.** `.github/workflows/ci.yml` has no explicit `permissions:` block, so it falls back to repository defaults.
- **Stop running containers as root.** All 8 Dockerfiles lack a `USER` directive (`document-indexer/`, `document-lister/`, `solr-search/`, `qdrant-search/`, `qdrant-clean/`, `embeddings-server/`, `llama-server/`, `llama-base/`).
- **Reduce attack surface in Compose.** `docker-compose.yml` publishes many internal service ports (Redis, RabbitMQ, ZooKeeper, Solr nodes, embeddings API) to the host, and both `zoo1` and `solr-search` map host port `8080`, creating an avoidable exposure/collision.
- **Improve Solr resilience.** `document-indexer` (`SOLR_HOST=solr`) and `solr-search` (`SOLR_URL=http://solr:8983/solr`) are pinned to a single Solr node despite the SolrCloud topology.

#### Medium (fix next sprint)
- **Add container healthchecks.** Checkov's 18 Dockerfile failures are primarily missing `HEALTHCHECK` instructions across all 8 images; this also weakens Compose readiness.
- **Bandit first-party MEDIUMs:** four `B104` findings for binding FastAPI servers to `0.0.0.0` in `embeddings-server/main.py`, `qdrant-clean/main.py`, `qdrant-search/main.py`, and `solr-search/main.py`. This is expected for containers but should be explicitly accepted/baselined.
- **Harden package installs.** `document-lister/Dockerfile`, `qdrant-search/Dockerfile`, `qdrant-clean/Dockerfile`, `llama-server/Dockerfile`, and two `python3 -m pip install` steps in `llama-base/Dockerfile` omit `--no-cache-dir`.
- **Avoid unnecessary package managers.** Checkov flags `apt` usage in `llama-server/Dockerfile` and `llama-base/Dockerfile`; review whether slimmer/prebuilt bases can remove build tooling from runtime images.
- **Compose hardening gaps.** ZooKeeper/Solr services lack health-based startup ordering and ZooKeeper restart policies; the repo's SolrCloud operations skill already calls these out as risks.

#### Low / Accepted Risk
- Bandit LOW findings are almost entirely `B101` test assertions in pytest suites; acceptable if tests stay out of production images and CI baselines them.
- No GitHub Actions shell-injection pattern was found using `github.event.*.body` inside `run:` blocks.
- No secrets were obviously echoed in workflow logs, and no Dockerfiles copy `.env` files into images.
- No Dockerfile uses a literal `latest` tag, though most base images are still mutable tags rather than digests.
- The current Dependabot API result is clean, but it conflicts with the historical note in `.squad/agents/kane/history.md`; verify in the GitHub UI if this looks unexpected.

#### Recommended Next Steps
1. Remove or ignore tracked virtualenv/vendor trees (especially `document-indexer/.venv/`) before enabling Bandit in CI; baseline the 4 accepted `B104` findings separately.
2. Pin every GitHub Action to a full commit SHA and add explicit least-privilege `permissions:` to `ci.yml`.
3. Add `USER` and `HEALTHCHECK` instructions to every Dockerfile, then wire Compose `depends_on` to health where possible.
4. Reduce published host ports, move internal services behind the Compose network only, and stop pinning application traffic to a single Solr node.
5. Add `--no-cache-dir` to remaining pip installs and review `llama-*` images for smaller, less privileged runtime stages.
6. Re-run Compose scanning with a supported policy set/tooling path (current Checkov 3.2.508 rejects `docker-compose` as a framework) and reconcile the Dependabot baseline with GitHub UI state.

### P4 UI Spec — Library, Status, Stats Tabs
**Author:** Ripley (Lead)
**Approved by:** Juanma (Product Owner) — all 3 tabs
**Date:** 2026-03-14
**Status:** APPROVED

#### Navigation
- **Tab bar** at top of `<main>`: `Search | Library | Status | Stats`
- **URL routing:** React Router — `/search`, `/library`, `/library/*`, `/status`, `/stats`
- **Default tab:** `/search` (current behavior, no regression)
- **Sidebar:** The facet sidebar is Search-specific. Other tabs get their own sidebar content or collapse the sidebar.
- **Component:** `TabNav.tsx` — shared top navigation, highlights active tab
- **Router:** Wrap `App.tsx` in `BrowserRouter`; each tab is a `<Route>` rendering its page component

#### Routing Detail
```
/                   → redirect to /search
/search             → SearchPage (current App.tsx content, extracted)
/library            → LibraryBrowser (root listing)
/library/:path*     → LibraryBrowser (nested folder)
/status             → IndexingStatus
/stats              → CollectionStats
```

#### Tab 1: Search (existing — extract, don't modify)
**Component:** `SearchPage.tsx`
**What changes:** Extract the current `App()` body into `SearchPage`. `App.tsx` becomes the router shell + tab nav. No functional changes to search behavior.

#### Tab 2: Library — Browse the Collection
**Component:** `LibraryBrowser.tsx`
**Purpose:** File-browser view of the book library (categories → authors → books). Users can explore the collection without searching.

**Backend endpoint:**
```
GET /v1/library/?path={relative_path}
GET /v1/library/                        # root listing
GET /library/?path={relative_path}      # alias
```

**Query parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `path` | string | `""` (root) | Relative path within `/data/documents`. URL-encoded. |
| `sort_by` | string | `"name"` | `name`, `size`, `count`, `modified` |
| `sort_order` | string | `"asc"` | `asc`, `desc` |

**Response shape:**
```json
{
  "path": "amades/catalan/",
  "breadcrumb": [
    {"name": "root", "path": ""},
    {"name": "amades", "path": "amades/"},
    {"name": "catalan", "path": "amades/catalan/"}
  ],
  "folders": [
    {
      "name": "Joan Amades",
      "path": "amades/catalan/Joan Amades/",
      "item_count": 14,
      "total_size": 285600000
    }
  ],
  "files": [
    {
      "name": "Folklore de Catalunya.pdf",
      "path": "amades/catalan/Folklore de Catalunya.pdf",
      "size": 24500000,
      "modified": "2024-11-03T10:15:00Z",
      "indexed": true,
      "solr_id": "base64-encoded-id",
      "metadata": {
        "title": "Folklore de Catalunya",
        "author": "Joan Amades",
        "year": 1950,
        "language": "ca",
        "page_count": 342
      }
    }
  ],
  "total_folders": 3,
  "total_files": 8
}
```

**Backend implementation notes (Parker):**
- Walk `settings.base_path / path` on the filesystem
- For each file, check Solr for indexed metadata: query `file_path_s:{escaped_path}` with `rows=1`
- Cache Solr lookups per request (batch query: `file_path_s:("path1" OR "path2" OR ...)`)
- **Security:** Validate `path` does not escape `base_path` (same traversal protection as `/documents/{id}`)
- Reject paths containing `..`, null bytes, or absolute paths
- Return 404 if path doesn't exist on filesystem

**Frontend behavior:**
- Breadcrumb navigation at top (clickable path segments)
- Folder list: click to navigate deeper (updates URL: `/library/amades/catalan/`)
- File list: show metadata inline; "View PDF" button opens `PdfViewer` (reuse existing component)
- Show folder icon + item count badge for folders
- Show PDF icon + size + indexed status badge for files
- Sort controls: name, size, count (folders), modified date
- Empty state: "This folder is empty" or "No books found in this directory"

#### Tab 3: Status — Indexing Progress & Health
**Component:** `IndexingStatus.tsx`
**Purpose:** Real-time dashboard showing indexing pipeline status and service health.

**Backend endpoint:**
```
GET /v1/status/
GET /status/
```

**No query parameters.** Returns current snapshot.

**Response shape:**
```json
{
  "timestamp": "2026-03-14T12:00:00Z",
  "indexing": {
    "total_discovered": 1247,
    "total_indexed": 1180,
    "total_queued": 42,
    "total_failed": 25,
    "total_with_embeddings": 890,
    "last_scan_time": "2026-03-14T11:55:00Z",
    "scan_interval_seconds": 600
  },
  "failed_documents": [
    {
      "file_path": "amades/broken_file.pdf",
      "error": "PDF extraction failed: encrypted document",
      "failed_at": "2026-03-14T10:30:00Z",
      "retry_count": 3
    }
  ],
  "services": {
    "solr": {
      "status": "healthy",
      "nodes": 3,
      "nodes_active": 3,
      "collection": "books",
      "docs_count": 1180
    },
    "rabbitmq": {
      "status": "healthy",
      "queue_name": "document_queue",
      "queue_depth": 42,
      "consumers": 1
    },
    "redis": {
      "status": "healthy",
      "connected": true,
      "keys_count": 1300
    },
    "embeddings_server": {
      "status": "healthy",
      "model": "distiluse-base-multilingual-cased-v2",
      "dimension": 512
    }
  }
}
```

**Backend implementation notes (Parker):**
- **Solr:** Query `admin/collections?action=CLUSTERSTATUS` for node health, `select?q=*:*&rows=0` for doc count
- **Redis:** `HLEN` or `DBSIZE` for key count; `HGETALL` on lister state hash for discovered/failed counts
- **RabbitMQ:** Management API (`GET /api/queues/{vhost}/{queue}`) for queue depth + consumer count
- **Embeddings:** `GET /v1/embeddings/model` (already exists from PR #65) for model info; count docs with `book_embedding:[* TO *]` in Solr
- **Failed docs:** Store in Redis hash `indexer:failed` with error + timestamp + retry count
- Aggregate all sources into single response — keep endpoint fast (<2s)
- Return `"status": "unhealthy"` per service if connection fails (don't 500 the whole endpoint)

**Frontend behavior:**
- **Progress section:** Big numbers for discovered / indexed / queued / failed / embedded
- Progress bar: `indexed / discovered` as percentage
- **Failed documents:** Expandable list with error details (collapsed by default)
- **Services grid:** Card per service with green/red status dot, key metric
- **Auto-refresh:** Poll every 10 seconds (`setInterval` + `useEffect` cleanup). Show "Last updated: X seconds ago" badge.
- **Manual refresh button** for immediate update

#### Tab 4: Stats — Collection Analytics
**Component:** `CollectionStats.tsx`
**Purpose:** Aggregate statistics and breakdowns of the indexed book collection.

**Backend endpoint:**
```
GET /v1/stats/
GET /stats/
```

**Query parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `top_n` | int | `20` | Max items in each breakdown (authors, categories) |

**Response shape:**
```json
{
  "timestamp": "2026-03-14T12:00:00Z",
  "totals": {
    "books": 1180,
    "total_pages": 342000,
    "average_pages": 290,
    "total_size_bytes": 48000000000,
    "average_size_bytes": 40677966
  },
  "by_language": [
    {"value": "es", "count": 420},
    {"value": "ca", "count": 310},
    {"value": "fr", "count": 250},
    {"value": "en", "count": 200}
  ],
  "by_author": [
    {"value": "Joan Amades", "count": 42},
    {"value": "Unknown", "count": 38}
  ],
  "by_year": [
    {"value": "1950", "count": 15},
    {"value": "1960", "count": 22}
  ],
  "by_category": [
    {"value": "amades", "count": 120},
    {"value": "historia", "count": 95}
  ]
}
```

**Backend implementation notes (Parker):**
- **Totals:** `q=*:*&rows=0&stats=true&stats.field=page_count_i&stats.field=file_size_l` — Solr stats component gives count, sum, mean
- **Breakdowns:** Reuse `build_solr_params()` with `rows=0` + facets. The existing `/v1/facets` endpoint already returns `by_language`, `by_author`, `by_year`, `by_category` — extract and extend.
- **by_year:** Use Solr range facets (`facet.range=year_i&f.year_i.facet.range.start=1400&f.year_i.facet.range.end=2030&f.year_i.facet.range.gap=10`) for histogram buckets, or standard facet for exact years
- `top_n` controls `facet.limit` per field
- Cache response for 60s (stats don't change fast)

**Frontend behavior:**
- **Summary cards:** Total books, total pages, avg pages, total size (human-readable)
- **Language breakdown:** Horizontal bar chart or pie chart (4-6 slices max, rest as "Other")
- **Author breakdown:** Top 20 bar chart (horizontal, sorted by count)
- **Year breakdown:** Histogram (vertical bars, year on x-axis). Group very old books into decades.
- **Category breakdown:** Treemap or horizontal bar chart
- **Chart library:** Use a lightweight lib. Recommended: **recharts** (already React-native, small bundle, good for bar/pie/histogram). Alternative: raw SVG bars if we want zero new deps.
- No auto-refresh needed (stats change slowly). Manual refresh button.

#### Shared Frontend Infrastructure
**New dependencies (Dallas):**
- `react-router-dom` — Client-side routing (already standard for React SPAs)
- `recharts` — Chart library for Stats tab (optional: can start with plain HTML tables, add charts later)

**New shared components:**
- `TabNav.tsx` — Tab bar navigation (Search | Library | Status | Stats)
- `StatusBadge.tsx` — Reusable green/yellow/red dot + label
- `ProgressBar.tsx` — Reusable progress bar (for Status tab)
- `Breadcrumb.tsx` — Clickable path breadcrumb (for Library tab)

**App.tsx restructure:**
```tsx
function App() {
  return (
    <BrowserRouter>
      <TabNav />
      <Routes>
        <Route path="/" element={<Navigate to="/search" />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/library/*" element={<LibraryBrowser />} />
        <Route path="/status" element={<IndexingStatus />} />
        <Route path="/stats" element={<CollectionStats />} />
      </Routes>
    </BrowserRouter>
  );
}
```

**Custom hooks (one per tab):**
- `useLibrary(path: string)` — fetches `/v1/library/?path=...`, returns folders/files/breadcrumb + loading/error
- `useStatus()` — fetches `/v1/status/` with 10s auto-refresh, returns full status + loading/error
- `useStats()` — fetches `/v1/stats/`, returns stats + loading/error

#### Backend Endpoints Summary
| Endpoint | Service | Method | What It Does | Depends On |
|----------|---------|--------|-------------|------------|
| `GET /v1/library/?path=` | solr-search | GET | Browse filesystem + Solr metadata | Solr, filesystem |
| `GET /v1/status/` | solr-search | GET | Aggregate pipeline health | Solr, Redis, RabbitMQ, embeddings-server |
| `GET /v1/stats/` | solr-search | GET | Collection statistics + breakdowns | Solr (stats + facets) |

All three endpoints go in `solr-search/main.py`, following existing patterns:
- Triple-alias routes (`/v1/X/`, `/v1/X`, `/X`)
- Same `Settings` config for Solr URL, timeouts, CORS
- Same error handling (HTTPException 400/404/502/504)
- Same `parse_facet_counts()` reuse where applicable

#### Implementation Order
| Step | Who | What | Depends On | Effort |
|------|-----|------|------------|--------|
| 1 | Parker | `GET /v1/stats/` endpoint | Solr running, books indexed | S — reuses existing facets + stats query |
| 2 | Parker | `GET /v1/status/` endpoint | Solr, Redis, RabbitMQ connections | M — multiple service queries |
| 3 | Parker | `GET /v1/library/?path=` endpoint | Solr running, filesystem access | M — FS walk + Solr batch lookup |
| 4 | Dallas | Tab navigation + routing (`react-router-dom`) | None | S — scaffolding only |
| 5 | Dallas | `CollectionStats.tsx` (Stats tab) | Step 1 | S — tables first, charts later |
| 6 | Dallas | `IndexingStatus.tsx` (Status tab) | Step 2 | M — auto-refresh, service cards |
| 7 | Dallas | `LibraryBrowser.tsx` (Library tab) | Step 3 | L — breadcrumb nav, file browser UX |
| 8 | Lambert | Integration tests for all 3 endpoints | Steps 1-3 | M |

**Parallelism:** Parker works steps 1-3 (backend) while Dallas starts step 4 (routing). Dallas picks up 5-7 as endpoints land. Lambert tests after endpoints exist.

**Recommended sequence for Dallas:** Stats → Status → Library (increasing complexity). Stats is simplest because it's mostly rendering data. Status adds auto-refresh. Library is the most complex UX (navigation, breadcrumbs, PDF viewer integration).

#### Open Questions (non-blocking)
1. **Charts:** Should Dallas use `recharts` or start with plain HTML tables? Recommend: tables first in initial PR, add `recharts` in a follow-up. Keeps initial PR small.
2. **Status polling:** WebSocket vs polling? Recommend polling (10s interval). WebSocket adds infrastructure complexity for marginal benefit at this refresh rate.
3. **Library caching:** Should `/v1/library/` cache Solr lookups across requests? Recommend: per-request batch only for now. Add Redis caching if performance is an issue.
4. **RabbitMQ access:** solr-search currently doesn't connect to RabbitMQ. The `/v1/status/` endpoint needs the management API URL added to `Settings`. New env var: `RABBITMQ_MANAGEMENT_URL=http://rabbitmq:15672`.


---

## Session 3 Decisions — Released 2026-03-14

### Branching Strategy — Release Gating

**Date:** 2026-03-14  
**Author:** Ripley (Lead)  
**Approved by:** Juanma (Product Owner)

#### Branches

- `dev` — active development, all squad/copilot PRs target this
- `main` — production-ready, always has a working version
- Feature branches: `squad/{issue}-{slug}` or `copilot/{slug}` — short-lived, merge to `dev`

#### Release Flow

1. Work happens on `dev` (PRs from feature branches)
2. At phase end, Ripley or Juanma runs integration test on `dev`
3. If tests pass: merge `dev` → `main`
4. Create semver tag: `git tag -a v{X.Y.Z} -m "Release v{X.Y.Z}: {phase description}"`
5. Push tag: `git push origin v{X.Y.Z}`

#### Merge Authority

- `dev` ← feature branches: any squad member can merge (with Ripley review)
- `main` ← `dev`: ONLY Ripley or Juanma
- Tags: ONLY Ripley or Juanma

#### Current Version

Based on the phase system:
- v0.1.0 — Phase 1 (Solr indexing) ✅
- v0.2.0 — Phase 2 (Search API + UI) ✅
- v0.3.0 — Phase 3 (Embeddings + hybrid search) ✅
- v0.4.0 — Phase 4 (Dashboard + polish) — in progress

---

### Backlog Organization into GitHub Milestones

**Author:** Ripley (Lead)  
**Date:** 2026-03-14  
**Status:** Accepted

#### Context

The backlog had 49 open issues with no milestone structure. 13 issues were completed by merged PRs but never closed. Work needed grouping into release phases with clear completion criteria and a pause-reflect-reskill cadence.

#### Actions Taken

- **Created 5 GitHub milestones** (v0.3.0 through v1.0.0)
- **Closed 13 issues** completed by merged PRs (#81–#84, #91, #110–#113, #124–#126, #133)
- **Assigned 36 remaining open issues** to milestones

#### Milestone Structure

##### v0.3.0 — Stabilize Core (5 issues)

Finish the UV/ruff migration cleanup and document the new dev setup.

| # | Title | Owner |
|---|-------|-------|
| 92 | UV-8: Update buildall.sh and CI for uv | Dallas |
| 95 | LINT-4: Replace pylint/black with ruff in document-lister | Ripley |
| 96 | DOC-1: Document uv migration and dev setup in README | Dallas |
| 99 | LINT-5: Run ruff auto-fix across all Python services | Lambert |
| 100 | LINT-6: Run eslint + prettier auto-fix on aithena-ui | Dallas |

**Done when:** `buildall.sh` works with uv, all Python services pass `ruff check`, README has current dev setup instructions, CI green.  
**Effort:** ~2–3 sessions.

##### v0.4.0 — Dashboard & Polish (7 issues)

Add dashboard endpoints + React tabs, establish frontend lint/test baseline.

| # | Title | Owner |
|---|-------|-------|
| 114 | P4: Add /v1/status/ endpoint to solr-search | Parker |
| 120 | P4: Add tab navigation to React UI | Dallas |
| 121 | P4: Build Stats tab in React UI | Dallas/Copilot |
| 122 | P4: Build Status tab in React UI | Dallas/Copilot |
| 41 | Phase 2: Add frontend test coverage | Parker |
| 93 | LINT-2: Add prettier config for aithena-ui | Dallas |
| 94 | LINT-3: Add eslint + prettier CI jobs for frontend | Dallas |

**Done when:** Status + Stats endpoints return real data, React UI has 4 tabs (Search/Library/Status/Stats), eslint+prettier CI green, frontend test coverage > 0%.  
**Effort:** ~4–5 sessions.

##### v0.5.0 — Advanced Search (3 issues)

Page-level search results and similar-books UI.

| # | Title | Owner |
|---|-------|-------|
| 134 | Return page numbers in search results from chunk-level hits | Ash/Parker |
| 135 | Open PDF viewer at specific page from search results | Dallas |
| 47 | Phase 3: Show similar books in React UI | Parker |

**Done when:** Search results show page numbers, clicking a result opens PDF at the correct page, similar-books panel renders for each book.  
**Effort:** ~3–4 sessions.

##### v0.6.0 — Security & Hardening (19 issues)

Security CI pipeline, vulnerability remediation, docker hardening.

| # | Title | Owner |
|---|-------|-------|
| 88 | SEC-1: Add bandit Python security scanning to CI | Kane/Ripley |
| 89 | SEC-2: Add checkov IaC scanning to CI | Kane/Ripley |
| 90 | SEC-3: Add zizmor GitHub Actions security scanning | Kane/Ripley |
| 97 | SEC-4: Create OWASP ZAP manual security audit guide | Kane |
| 98 | SEC-5: Security scanning validation and baseline tuning | Lambert |
| 52 | Phase 4: Harden docker-compose and service health checks | Brett |
| 5–7, 17–18, 20, 29–35 | Mend dependency vulnerability fixes (13 issues) | Kane/Copilot |

**Done when:** bandit+checkov+zizmor CI green, all HIGH+ Mend vulnerabilities resolved or suppressed with justification, docker-compose has health checks on all services.  
**Note:** Many Mend issues may be auto-resolved — qdrant-clean/qdrant-search/llama-server were removed in PR #115. Triage each: close if the vulnerable package is gone, fix or suppress if still present.  
**Effort:** ~5–6 sessions.

##### v1.0.0 — Production Ready (2 issues + future work)

Upload flow, E2E coverage, production stability.

| # | Title | Owner |
|---|-------|-------|
| 49 | Phase 4: Add a PDF upload endpoint to the FastAPI backend | Parker |
| 50 | Phase 4: Build a PDF upload flow in the React UI | Dallas |

**Future work (no issues yet):**
- Vector/semantic search validation end-to-end
- Hybrid search mode toggle in UI
- Branch rename (dev → main)
- Full test coverage (backend + frontend)
- docker-compose.infra.yml for hybrid local dev

**Done when:** Full upload → index → search → view flow works E2E, branch renamed, CI green on default branch, all services have tests.  
**Effort:** ~8–10 sessions.

#### Cadence

After each milestone is complete:

1. **Pause** — Stop new feature work
2. **Scribe logs** — Scribe captures session learnings, updates decisions.md
3. **Reskill** — Team reviews what worked, what didn't, update charters if needed
4. **Tag release** — `git tag v{X.Y.0}` on dev
5. **Merge to default** — PR from dev to main (once branch rename happens, this simplifies)

#### Issue Summary

| Milestone | Open | Closed Today |
|-----------|------|-------------|
| v0.3.0 — Stabilize Core | 5 | — |
| v0.4.0 — Dashboard & Polish | 7 | — |
| v0.5.0 — Advanced Search | 3 | — |
| v0.6.0 — Security & Hardening | 19 | — |
| v1.0.0 — Production Ready | 2 | — |
| **Completed (closed)** | — | **13** |
| **Total** | **36** | **13** |

---

### User Directives — 2026-03-14

#### Branching Strategy + Release Gating

**By:** jmservera / Juanma (via Copilot)  
**Date:** 2026-03-14T15:31

**What:**
1. Create a `dev` branch for all active work
2. The current default branch (`jmservera/solrstreamlitui` or successor) is the "production-ready" branch
3. At the end of each phase, when the solution works, merge dev → default and create a semver tag
4. ONLY Ripley (Lead) or Juanma (Product Owner) can merge to the default branch and create release tags. Nobody else.
5. Think about CI/CD workflows needed for this (tag-triggered builds, release notes, etc.)

**Why:** User request — production readiness, always have a working version available via semver tags

---

#### Milestone-Based Backlog Management

**By:** jmservera / Juanma (via Copilot)  
**Date:** 2026-03-14T16:13

**What:** Ripley owns the backlog. Use GitHub milestones to group issues into phases. After each milestone: pause, summarize learnings, reskill. Ripley decides what goes into each phase.

**Why:** User request — structured delivery cadence with knowledge consolidation between phases

---

#### PDF Page Navigation from Search Results

**By:** jmservera / Juanma (via Copilot)  
**Date:** 2026-03-14T15:12

**What:** Search results must show which page number(s) contain the matching text. Clicking a result should open the PDF at the correct page. This requires:
1. Solr to track page numbers during indexing
2. Search API to return page numbers with highlights
3. PDF viewer to open at a specific page

**Why:** Critical usability — users need to find the exact location of search hits in large PDFs

---

#### Rename Default Branch (Mid-Long Term)

**By:** jmservera / Juanma (via Copilot)  
**Date:** 2026-03-14T15:40

**What:** The actual default branch is `jmservera/solrstreamlitui`, not `main`. Eventually rename it to something cleaner (e.g., `main`) and remove the old `main`. Low priority — do it when everything else is working.

**Why:** User clarification — current branch naming is legacy, clean up later

---

## Phase 4 Inbox Merges (2026-03-14)

### User Directive: TDD + Clean Code

**Date:** 2026-03-14T17:05  
**By:** jmservera / Juanma (via Copilot)  
**What:** All development tasks must follow TDD (Test-Driven Development) and Uncle Bob's Clean Code and Clean Architecture principles. Tests first, then implementation. Code must be clean, well-structured, with clear separation of concerns.  
**Why:** User requirement — quality-first development, maintainable codebase

---

### nginx Admin Entry Point Consolidation

**Date:** 2026-03-14  
**By:** Copilot working as Brett  
**What:** Standardize local/prod-style web ingress through the repo-managed nginx service. The main React UI is now served at `/`, and admin tooling is grouped under `/admin/`.

**Implementation details:**
- `/admin/solr/` proxies Solr Admin
- RabbitMQ now uses the management image plus `management.path_prefix = /admin/rabbitmq` so both the UI and API work behind `/admin/rabbitmq/`
- Streamlit runs with `--server.baseUrlPath=/admin/streamlit`
- Redis Commander is added with `URL_PREFIX=/admin/redis`
- `/admin/` serves a simple landing page linking to all admin surfaces

**Impact on teammates:**
- Frontend/UI traffic should go through nginx at `http://localhost/` in proxied runs
- Ops/testing docs should prefer the `/admin/...` URLs over direct service ports, though direct ports remain available for local debugging

---

### PRD: v0.3.0 — Stabilize Core (Close-Out)

**Date:** 2026-03-14  
**Status:** PROPOSED  
**Goal:** Close v0.3.0 by completing the 6 remaining stabilization issues. These are cleanup, lint, and documentation tasks — no new features.

**Current State:**
- Open: 6 issues
- Closed: 0 issues (all work done but issues not formally closed via PRs)
- Merged PRs supporting v0.3.0: #115 (qdrant removal), #117 (ruff CI), #116/#129/#130/#131 (UV migrations)

**Remaining Issues:**
| # | Title | Owner | Effort | Status |
|---|-------|-------|--------|--------|
| #139 | Clean up smoke test artifacts from repo root | Dallas | S | PR #140 DRAFT |
| #100 | LINT-6: eslint + prettier auto-fix on aithena-ui | Dallas | S | Not started |
| #99 | LINT-5: ruff auto-fix across all Python services | Lambert | S | Not started |
| #96 | DOC-1: Document uv migration and dev setup in README | Dallas | S | Not started |
| #95 | LINT-4: Replace pylint/black with ruff in document-lister | Ripley | S | Not started |
| #92 | UV-8: Update buildall.sh and CI for uv | Dallas | S | Not started |

**Dependencies:** None — all 6 issues are independent and can be worked in parallel

**Acceptance Criteria:**
1. All smoke test artifacts (.png, .md snapshots, .txt logs) removed from repo root; .gitignore updated
2. `ruff check --fix` and `ruff format` pass cleanly across all Python services
3. `eslint` and `prettier` pass cleanly on `aithena-ui/`
4. `document-lister/` uses ruff instead of pylint/black (pyproject.toml updated, old configs removed)
5. `buildall.sh` uses `uv` for builds; CI workflows use `uv pip install`
6. README documents: prerequisites (Docker, uv, Node 20+), dev setup, `docker compose up`, running tests

**Close-Out Criteria:**
When all 6 issues have merged PRs on `dev`:
1. Run full CI suite (all green)
2. Tag `v0.3.0`
3. Merge `dev` → `main`
4. Create GitHub Release
5. Scribe logs session

---

### PRD: v0.4.0 — Dashboard & Polish

**Date:** 2026-03-14  
**Status:** PROPOSED  
**Milestone:** v0.4.0 — Dashboard & Polish

**Vision:** Transform aithena from a single-page search app into a multi-tab application with Library browsing, Status monitoring, and Stats dashboards — while hardening the frontend with linting, formatting, and test coverage.

**User Stories:**
- US-1: Tab Navigation — access different views without leaving the app
- US-2: Library Browser — browse book collection by folder/author
- US-3: Status Dashboard — see indexing progress and service health
- US-4: Stats Dashboard — see collection statistics (total, by language, by author)
- US-5: Frontend Test Coverage — catch regressions before merge
- US-6: Frontend Code Quality — consistent style via eslint + prettier

**Architecture:** Clean Architecture layers for both backend (Presentation → Application → Domain → Infrastructure) and frontend (Pages → Components → Hooks → API)

**Implementation Tasks (TDD):** 9 tasks total
- T1: Status endpoint service extraction (Parker, S)
- T2: Stats endpoint service extraction (Parker, S)
- T3: Tab navigation React Router (Dallas, S)
- T4: Stats tab frontend (Dallas, S, depends T2+T3)
- T5: Status tab frontend (Dallas, M, depends T1+T3)
- T6: Library endpoint backend (Parker, M)
- T7: Library browser frontend (Dallas, L, depends T3+T6)
- T8: Prettier + ESLint config (Dallas, S)
- T9: Frontend test coverage (Lambert, L, depends T3–T7)

**Risks:** Stale branches, path traversal vulnerability, polling overwhelm, peer dependency conflicts

**Success Criteria:**
1. All 4 tabs render and navigate correctly
2. Status page shows real service health
3. Stats page shows collection statistics
4. Library page browses real filesystem with metadata
5. `npm run lint` and `npm run format:check` pass in CI
6. `npm run test` passes with ≥70% component coverage
7. All existing search functionality preserved (no regressions)

---

### Retro — v0.3.0 Stabilize Core (Post-Phase 2/3)

**Date:** 2026-03-14  
**Scope:** Sessions 1–3, Phase 1–3 work

**What Went Well:**
1. Pipeline bugs caught and fixed fast — Parker found critical lister + indexer bugs
2. Smoke tests with Playwright caught real API contract issues before users
3. Parallel work model scaled — copilot delivered 14 PRs while squad worked locally
4. Skills system paid off (solrcloud, path-metadata heuristics)
5. Milestone cadence established (v0.3.0–v1.0.0)
6. Branching strategy prevented further UI breakage via `dev` integration branch

**What Didn't Go Well:**
1. UI broke from uncoordinated PR merges (pre-dev-branch)
2. Stale branches / conflicts recurring time sink
3. Smoke test artifacts committed to repo root
4. Collection bootstrap missing piece (no auto-create)
5. document-indexer didn't start automatically

**Key Learnings:**
1. Hybrid dev workflow (Docker infra + local code) is essential
2. Must validate UI build before merging frontend PRs
3. API contract mismatches (`/v1/` prefix) cost significant debugging time
4. Page-level search needs app-side extraction (Solr Tika loses page boundaries)
5. `solr-init` container pattern works for bootstrap
6. `--legacy-peer-deps` is required for aithena-ui (needs documentation)
7. FastAPI 0.99.1 + Starlette 0.27.0 requires `httpx<0.28`

**Action Items:**
| # | Action | Owner | Target |
|---|--------|-------|--------|
| 1 | Create `smoke-testing` skill | Ripley | This retro |
| 2 | Create `api-contract-alignment` skill | Ripley | This retro |
| 3 | Create `pr-integration-gate` skill | Ripley | This retro |
| 4 | Update `solrcloud-docker-operations` confidence → high | Ripley | This retro |
| 5 | Update `path-metadata-heuristics` confidence → high | Ripley | This retro |
| 6 | Clean smoke artifacts from repo root | Dallas | v0.4.0 |
| 7 | Add `npm run build` gate to CI for `aithena-ui/` | Parker/Lambert | v0.4.0 |
| 8 | Document `--legacy-peer-deps` requirement | Dallas | v0.4.0 |

---

### v0.4.0 Task Decomposition — TDD Specs

**Date:** 2026-03-14  
**Milestone:** v0.4.0 — Dashboard & Polish

**Task Summary:**
| # | Task | Agent | Layer | Effort | Depends On |
|---|------|-------|-------|--------|------------|
| T1 | Status endpoint — service extraction | Parker | App + Infra | S | — |
| T2 | Stats endpoint — service extraction | Parker | Application | S | — |
| T3 | Tab navigation — React Router | Dallas | Presentation | S | — |
| T4 | Stats tab — frontend | Dallas | Components + Hooks | S | T2, T3 |
| T5 | Status tab — frontend | Dallas | Components + Hooks | M | T1, T3 |
| T6 | Library endpoint — backend | Parker | App + Infra | M | — |
| T7 | Library browser — frontend | Dallas | Pages + Components | L | T3, T6 |
| T8 | Prettier + ESLint config | Dallas | Infrastructure | S | — |
| T9 | Frontend test coverage | Lambert | All frontend | L | T3–T7 |

**Total: 9 tasks (4S + 2M + 2L + 1S-config = ~3 sprints)**

**Full detailed TDD specs:** See full PRD v0.4.0 above for each task's Red/Green/Refactor cycle, Clean Architecture layer assignments, and test specifications.

# Phase 4 Reflection: PR Review Patterns & Process Improvements

**Author:** Ripley (Lead)
**Date:** 2026-03-14
**Scope:** Phase 4 (v0.4.0 Dashboard & Polish) — @copilot PR batch review
**Status:** RECOMMENDATION

---

## Summary

Reviewed 6 open @copilot PRs for Phase 4. **1 approved, 5 rejected (17% approval rate).** The rejections cluster into 4 systemic patterns that have recurred since Phase 2. This is not a quality problem — the code inside each PR was consistently well-written. It is a **workflow and decomposition problem** that we can fix with process changes.

---

## PR Results

| PR | Feature | Verdict | Failure Mode |
|----|---------|---------|--------------|
| #137 | Page ranges in search | ✅ Approved (needs rebase) | — |
| #140 | Cleanup smoke artifacts | ❌ Rejected | Wrong target branch, broad gitignore, 88 unrelated files |
| #128 | Status tab UI | ❌ Rejected | Stale branch — would delete router from PR #123 |
| #138 | PDF viewer page nav | ❌ Rejected | Depends on unmerged #137, adds unused backend field |
| #127 | Stats tab UI | ❌ Rejected | Stale branch — same as #128 |
| #119 | Status endpoint | ❌ Rejected | Scope bloat (108 files), Redis perf issues |

---

## Failure Mode Analysis

### 1. Stale Branches (3 PRs: #127, #128, #119)

**Pattern:** Copilot branched from a commit before PR #123 (router architecture) merged. The resulting diffs carry the entire pre-router state of `App.tsx`, effectively deleting `TabNav`, `react-router-dom` routing, and all 4 page components.

**History:** This is the same failure class seen in Phase 2 (PR #64 would have deleted `solr-search/` and CI workflows) and Phase 3 (PRs #68-#70 targeted `qdrant-search/` because they branched before the Solr migration). It has now occurred in **every phase** and accounts for the majority of rejections.

**Root cause:** @copilot creates branches from whatever commit is current when the issue is assigned. If multiple issues are assigned simultaneously, all branches fork from the same (soon-to-be-stale) point. The agent does not rebase before opening the PR.

**Fix:** Issue gating — assign issues sequentially after prerequisites merge, not in parallel batches.

### 2. Scope Bloat (2 PRs: #119, #140)

**Pattern:** PRs contain changes far beyond the issue scope. #119 was a backend endpoint PR that included ~500 lines of unrelated frontend code (the entire router architecture from #128, re-introduced). #140 was a 3-file chore that ballooned to 88 files from branch divergence.

**Root cause:** When copilot's branch diverges from the base, it sometimes manually syncs files to resolve conflicts, creating a massive diff. The agent doesn't distinguish "files I changed" from "files that differ from base."

**Fix:** Add "scope fence" to issue descriptions — explicit file/directory boundaries. Add review heuristic: any PR where `git diff --stat | wc -l` exceeds 2× the expected file count gets auto-flagged.

### 3. Wrong Target Branch (1 PR: #140)

**Pattern:** PR #140 targeted `jmservera/solrstreamlitui` instead of `dev`. This is documented in `.github/copilot-instructions.md`, the squad-pr-workflow skill, and the custom instructions block. The agent ignored all three.

**Root cause:** The agent may have read stale instructions or inherited a branch that was tracking the old default. This same issue occurred with all 14 PRs in the Phase 3 batch (all retargeted manually).

**Fix:** CI gate that rejects PRs not targeting `dev`. Belt-and-suspenders: repeat the target branch rule in the issue description itself.

### 4. Dependency Ordering (1 PR: #138)

**Pattern:** PR #138 adds a new `pages_i` Solr field to pass page numbers to the UI. But PR #137 (approved, not yet merged) already normalizes `page_start_i`/`page_end_i` into a `pages` API response field — making the new field redundant.

**Root cause:** Issues #134 and #135 were assigned simultaneously. The agent working on #135 didn't check whether #134's solution (PR #137) was merged, and invented its own backend approach.

**Fix:** Dependent issues must state the dependency explicitly: "This issue REQUIRES PR #NNN to be merged first. Do not start until that PR is on `dev`." Better yet: don't create the dependent issue until the prerequisite PR merges.

---

## What Went Well

Despite the 17% approval rate, several things worked:

1. **Code quality is consistently good.** Every rejected PR contained well-structured TypeScript/Python code. `useStatus()`, `useStats()`, `CollectionStats.tsx`, `IndexingStatus.tsx` — all properly typed, accessible, with clean component decomposition. The problem is never "bad code" — it's "good code in the wrong context."

2. **PR #137 proves the model works for leaf-node issues.** It was small, independent, correctly scoped, targeted `dev`, and had comprehensive tests. The pattern: issues with no dependencies and a clear file scope produce good PRs from copilot.

3. **The review process caught everything.** No regressions were introduced. The stale-branch detection heuristic (check `--stat` for unexpected deletions of recently-added files) continues to work reliably.

4. **TDD specs helped.** PRs that followed the TDD specs from the v0.4.0 task decomposition had better test coverage than Phase 2-3 PRs.

---

## Recommendations for Phase 5

### Process Changes

| # | Change | Effort | Impact |
|---|--------|--------|--------|
| 1 | **Sequential issue assignment** — don't assign dependent issues until prerequisites merge | None | Eliminates stale branches and dependency violations |
| 2 | **Scope fences in issue descriptions** — list "touch these files" and "do NOT touch these files" | Low | Eliminates scope bloat |
| 3 | **Branch freshness CI check** — reject PRs >10 commits behind base | Medium | Catches stale branches before review |
| 4 | **Single-layer PR rule** — backend PRs touch `solr-search/` only, frontend PRs touch `aithena-ui/` only | None | Prevents cross-layer contamination |
| 5 | **Target branch in issue body** — repeat "target: dev" in every issue, not just global instructions | None | Redundancy prevents the #140 class of error |

### Issue Template Additions

Every issue assigned to @copilot should include:

```markdown
## Scope
- **Target branch:** `dev`
- **Files to modify:** [explicit list]
- **Files NOT to modify:** [explicit exclusions]
- **Prerequisites:** [PR #NNN must be merged first / None]

## Before Starting
1. `git fetch origin && git checkout -b squad/{issue}-{slug} origin/dev`
2. Verify prerequisite PRs are merged: [list]
```

### Decomposition Rule

**The "leaf node" principle:** Copilot produces good PRs for issues that are:
- Independent (no unmerged prerequisites)
- Scoped to one service/layer
- Small (1-5 files changed)
- Self-contained (test + implementation in same PR)

Issues that violate any of these should be broken down further or assigned to squad members who can coordinate across branches.

---

## Conclusion

The Phase 4 review results are disappointing at face value (17% approval) but instructive. The failure modes are **entirely preventable** with process discipline — none require changes to copilot's coding ability, which remains strong. The key insight: **copilot is a good coder but a poor branch manager.** Our job as a team is to structure issues so that branch management is trivial: one branch, one service, no dependencies, clear scope.

If we implement the 5 recommendations above, I expect Phase 5 approval rates to exceed 80%.

---

# Branch Repair Strategy — 9 Broken @copilot PRs

**Author:** Ripley (Lead)  
**Date:** 2026-03-14  
**Status:** APPROVED  
**Merged by:** Scribe, 2026-03-14T18:00:00Z

## Situation Assessment

All 9 PRs share the same root cause: @copilot branched from `main` (or old
`jmservera/solrstreamlitui`) instead of `dev`, then tried manual "rebases" that
actually merged or duplicated hundreds of unrelated files. The branches are 28
commits behind `dev` (some 126 behind). Most carry ghost diffs from the old repo
layout.

### What `dev` already has that these PRs re-introduce

| Feature | Already on `dev` | PR trying to add it |
|---------|-----------------|---------------------|
| ruff.toml + CI lint job | `ba81148` LINT-1 merged | #143 (redundant) |
| uv migrations (all 4 services) | #116, #129, #130, #131 | #141 (redundant CI changes) |
| /v1/stats/ endpoint + parse_stats_response | `fc2ac86` | #127, #119 (partial overlap) |
| Solr schema page_start_i / page_end_i fields | In managed-schema.xml | #137 (adds the search_service code) |
| PdfViewer component | `aithena-ui/src/Components/PdfViewer.tsx` (92 lines) | #138 (different version) |

## Triage: Three Categories

### 🟥 Category A — CLOSE (no salvageable value)

| PR | Reason | Effort to repair | Value of code |
|----|--------|------------------|---------------|
| **#143** Ruff in document-lister | 100% redundant — LINT-1 (#117) already merged with identical ruff.toml + CI job. PR adds a conflicting local config. | Low | **Zero** |
| **#141** buildall.sh + CI for uv | dev already has uv CI with `setup-uv@v5` + `uv sync --frozen`. PR's version is older/different. buildall.sh change is trivial (2 lines). | Low | **Near-zero** |
| **#128** Status tab UI | Branch is 28 commits behind, carries 109 files in diff. The "status tab" is 1 component + hook, but the branch would obliterate the current App.tsx (no router, flatten the faceted search UI). | High | **Low** (no router exists on dev yet, component is simple) |
| **#127** Stats tab UI | Same stale branch problem as #128. Nearly identical CSS + App.tsx changes. The CollectionStats component is ~80 lines but depends on a /stats UI contract that doesn't exist yet. | High | **Low** |
| **#119** Status endpoint | 108-file diff, 6656 insertions. Bundles frontend code, has Redis `KEYS *` perf bug, includes its own copy of uv migration. The actual `/v1/status/` endpoint is ~40 lines of useful code buried in garbage. | Very High | **Low** (one endpoint, easy to rewrite) |

**Action:** Close all 5 with a comment thanking @copilot and explaining why. Link to the replacement approach.

### 🟨 Category B — CHERRY-PICK specific code onto fresh branch

| PR | What's worth saving | How to extract |
|----|--------------------|--------------------|
| **#140** Clean up smoke test artifacts | Deletes 8 legitimate stale files (smoke screenshots, nginx-home.md/png, snapshot.md). The `.gitignore` additions are fine after narrowing the PNG pattern. Only 5 commits ahead, 7 behind — small branch, but targeted at wrong repo. | Cherry-pick the file deletions + gitignore onto a fresh `squad/140-clean-artifacts` from `dev`. Drop the broad `*.png` gitignore — use `/aithena-ui-*.png` pattern instead. ~10 min of work. |
| **#138** PDF viewer page navigation | Has page-navigation enhancement to PdfViewer (jump to specific page from search results). But it depends on #137's `pages` field in search results, and its branch is **126 commits behind** with 70 files changed. Most of the diff is re-adding files that already exist on dev. | Wait for #137 to land. Then create fresh `squad/138-pdf-page-nav` from `dev`. Cherry-pick only the PdfViewer page-jump logic (the component changes, not the entire branch). Review carefully for the `pages_i` backend field — it's unused dead code that should be dropped. ~30 min. |

### 🟩 Category C — REWRITE from scratch (faster than repair)

| PR | What to rewrite | Why rewrite beats repair |
|----|----------------|--------------------------|
| **#145** Ruff across all Python | The ruff auto-fixes are mechanical — just run `ruff check --fix . && ruff format .` from dev. The PR's branch includes fixes to deprecated qdrant-search code we already removed. | `squad/lint-ruff-autofix` from `dev`: run ruff, commit, done. 5 min. |
| **#144** Prettier + eslint on aithena-ui | Same pattern — run the formatters. The PR includes a SearchPage.tsx that doesn't exist on dev (stale code). | `squad/lint-eslint-prettier` from `dev`: add configs, run formatters, commit. 15 min. |

## Optimal Merge Order

```
Step 1:  #137 (approved, page ranges) — rebase onto dev, merge
         └── Unblocks #138

Step 2:  #140 (clean up artifacts) — cherry-pick onto fresh branch, merge
         └── Independent, quick win

Step 3:  #145-replacement (ruff autofix) — fresh branch, run ruff
         └── Independent, should go before any new Python code

Step 4:  #144-replacement (eslint/prettier) — fresh branch, run formatters
         └── Independent, should go before any new UI code

Step 5:  #138-replacement (PDF page nav) — cherry-pick after #137 lands
         └── Depends on #137

Step 6:  Close #143, #141, #128, #127, #119 with explanation
```

Steps 2-4 can run in parallel once Step 1 is done.

## Prevention & Guardrails

To stop this from recurring:
1. **Branch protection on `dev`**: require PRs, block force pushes
2. **Issue assignment instructions**: always include `base branch: dev` in issue body
3. **PR template**: add "Target branch: [ ] dev" checkbox
4. **Limit @copilot to single-issue PRs** — never let it bundle multiple features
5. **Auto-close PRs that target `main`** from copilot branches (GitHub Action)

## Summary

Of 9 broken PRs: **close 5, cherry-pick 2, rewrite 2 from scratch**. The total
salvageable code is small — maybe 200 lines of actual value across all 9 PRs.
Most of the "work" in these PRs is ghost diffs from stale branches. The fastest
path to value is: rebase #137 (approved), run formatters on fresh branches, and
close everything else.

---

# Post-Cleanup Issue Reassignment

**Author:** Ripley (Lead)  
**Date:** 2026-03-14  
**Status:** IMPLEMENTED  
**Context:** After closing 9 broken @copilot PRs and adding scope fences, reassigned all 9 affected issues with fresh labels.

## Closed Issues (PRs merged)

| Issue | PR | Status |
|-------|----|--------|
| #96 — DOC-1: Document uv migration | #142 | ✅ Closed |
| #134 — Return page numbers in search results | #137 | ✅ Closed |

## @copilot Batch 1 (3 issues — sequential, simplest first)

| Issue | Title | Rating | Rationale |
|-------|-------|--------|-----------|
| #139 | Clean up smoke test artifacts | 🟢 | Pure file deletion + .gitignore. Repo root only. Zero judgment. |
| #95 | LINT-4: Replace pylint/black with ruff in document-lister | 🟢 | Single directory (document-lister/), Size S, mechanical pyproject.toml edit. |
| #100 | LINT-6: Run eslint + prettier auto-fix on aithena-ui | 🟢 | Single directory (aithena-ui/), Size S, run linter and commit. |

## Squad Member Assignments (6 issues — hold for now)

| Issue | Title | Assigned To | Rating | Rationale |
|-------|-------|-------------|--------|-----------|
| #99 | LINT-5: Run ruff auto-fix across all Python services | 🔧 Parker | 🟡 | Size M, multi-directory. Reconsider for @copilot after batch 1. |
| #114 | P4: Add /v1/status/ endpoint | 🔧 Parker | 🔴 | Multi-service integration (Solr + Redis + RabbitMQ). Needs backend expertise. |
| #135 | Open PDF viewer at specific page | ⚛️ Dallas | 🟡 | UI feature with backend dependency. Needs UX judgment. |
| #122 | P4: Build Status tab in React UI | ⚛️ Dallas | 🟡 | Blocked on #120 + #114. Pick up after deps land. |
| #121 | P4: Build Stats tab in React UI | ⚛️ Dallas | 🟡 | Blocked on #120. Pick up after tab nav lands. |
| #92 | UV-8: Update buildall.sh and CI for uv | ⚙️ Brett | 🟡 | CI/build infra, blocked on UV-1 through UV-7. |

## Labels Removed

All stale `squad:*` and `go:needs-research` labels removed from all 9 issues before reassignment.

## Guardrails Applied

- @copilot issues limited to 3 (batch 1) — not all at once
- Each @copilot issue is single-directory, purely mechanical, with clear scope fences
- Remaining issues stay with squad members until batch 1 succeeds
- Phase 4 lesson: assign sequentially, not in parallel, to avoid PR sprawl

## Note on Copilot Assignee

The GitHub `Copilot` user cannot be directly assigned via `gh issue edit --add-assignee`. The `squad:copilot` label is the primary routing mechanism per team.md (`copilot-auto-assign: true`).

---

## User Directive: Branch Restructuring (2026-03-14T18:32)

**By:** jmservera (via Copilot)

**What:** Restructured repo branches: `dev` is now the default branch. Renamed `main` → `oldmain` and `jmservera/solrstreamlitui` → `main`. This means @copilot will now naturally target `dev` (the default). All PRs still target `dev`. Only Ripley or Juanma merge `dev` → `main`.

**Why:** User request — fixes the root cause of @copilot always targeting the wrong branch (it targets the GitHub default, which is now `dev`).

---

### 2026-03-14T19:33: UV Migration Complete Across All CI

**By:** jmservera (manual)
**What:** Release workflow (`.github/workflows/release.yml`) updated to use `astral-sh/setup-uv@v5`, `uv sync --frozen`, and `uv run pytest -v`. This was the last pip-based workflow. All CI now uses uv exclusively.
**Why:** Completes the uv migration started in PR #152/#153. Validated by 137 passing tests (73 document-indexer + 64 solr-search) and successful release workflow run `23094831631`.

---

### 2026-03-14T20:30: PR Review Batch — Branch Discipline & Redis Compliance (4 PRs approved & merged)

**By:** Ripley (Lead Reviewer)  
**Scope:** 4 @copilot PRs reviewed; all targeting `dev` branch

#### Verdicts

| PR | Title | Status | Key Finding |
|----|-------|--------|-------------|
| #156 | Add GET /v1/stats/ endpoint tests | ✅ APPROVED | 4 unit tests for existing `parse_stats_response`. Title misleading; endpoint already exists. |
| #159 | Add GET /v1/status/ endpoint | ✅ APPROVED | Clean health endpoint. Redis: ConnectionPool singleton ✅, scan_iter ✅, mget ✅. 11 tests. |
| #158 | LINT-3: ESLint + Prettier CI jobs | ✅ APPROVED | Workflow well-structured. Depends on #162 (prettier config) — merge second. |
| #162 | LINT-2: Add prettier config | ✅ APPROVED | Clean config. Merge first (dependency for #158). |

#### Merge Execution

**Order:** #162→#158 (rebase)→#156→#159
- #162 merged cleanly (commit `fdb6bf7`)
- #158 rebased on dev after #162, resolved package.json conflict (commit `4d7fe68`)
- #156 & #159 merged independently (commits `2cedc7c`, `e53374b`)

#### Key Observations

1. **Branch discipline:** All 4 PRs correctly target `dev`. Major improvement over Phase 4 (6/9 had wrong targets).
2. **CI gap:** Only CodeQL runs on PR branches. Check `ci.yml` path filters — unit test jobs may be excluded.
3. **Overlap pattern:** PRs #158 & #162 both modify identical files (prettier config + CI). Proper sequencing prevented conflicts.
4. **Redis compliance:** PR #159 fully adheres to team standards (ConnectionPool singleton, scan_iter, mget, graceful error handling).

---

### 2026-03-14T20:02: User Directive — PM Gates All Releases

**By:** jmservera (via Copilot)  
**Status:** IMPLEMENTED (Newt added to team as Product Manager)

**Decision:**
Before merging `dev` → `main` and creating a release tag, Newt (Product Manager) must validate the release:
- Run the app end-to-end
- Verify old and new features work
- Take screenshots
- Update documentation
- Approve or request rework

No release proceeds without PM sign-off.

**Rationale:** Ensures quality and documentation are current before shipping. Enforces a quality gate with human judgment.
