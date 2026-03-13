# Ripley — History

## Project Context
- **Project:** aithena — Book library search engine with Solr indexing, multilingual embeddings, PDF processing
- **User:** jmservera
- **Stack:** Python (backend), TypeScript/React + Vite (UI), Docker Compose, Apache Solr, multilingual embeddings
- **Book library:** `/home/jmservera/booklibrary`
- **Existing services:** Redis, RabbitMQ, Qdrant (being replaced), LLaMA server, embeddings server, document lister/indexer, search API, React UI

## Learnings

<!-- Append learnings below -->

### 2026-03-13T20:58 — Phase 2-4 Issue Decomposition (`jmservera/solrstreamlitui`)

- **COMPLETED:** Broke the remaining roadmap into 18 single-owner GitHub issues targeted at `squad:copilot`: Phase 2 (#36-#41), Phase 3 (#42-#47), and Phase 4 (#48-#53).
- Established the dependency spine as search API → UI shell/facets/PDF/tests, embeddings model → Solr vectors → embedding indexing → hybrid search → similar books, and 60s file polling → upload/admin/hardening/E2E.
- Kept the planned upload endpoint in the FastAPI backend so new ingestion work stays aligned with ADR-003 and the existing Redis/RabbitMQ/Solr pipeline.
- Recorded decision in `.squad/decisions.md` under "Ripley — Phase 2–4 Issue Decomposition". All 18 issues now tracked with explicit dependencies and milestones.

### 2026-03-13 — Branch Architecture Review (`jmservera/solrstreamlitui`)

**Architecture decisions made:**
- Hybrid indexing strategy: Solr Tika for full-text, app-side chunking for embeddings (Phase 3)
- FastAPI for search API (consistent with Python backend stack)
- Standardize on `distiluse-base-multilingual-cased-v2` for multilingual embeddings
- React UI effectively needs rewrite from chat to search paradigm; keep Vite/TS scaffolding
- Keep 60s polling over inotify for file watching (Docker bind-mount reliability)

**Key file paths:**
- `docker-compose.yml` — 3-node SolrCloud + 3 ZK + Redis + RabbitMQ + nginx/certbot
- `solr/books/managed-schema.xml` — Solr schema with ~20 multilingual field types, Tika-extracted fields
- `solr/books/solrconfig.xml` — Solr config (extraction, langid, spellcheck)
- `solr/add-conf-overlay.sh` — Config overlay script (sets up /update/extract handler + langid chain)
- `solr/config.json` — Full Solr config dump (Lucene 9.10, langid chain, extraction handler)
- `document-lister/document_lister/__main__.py` — File scanner (polls /data/documents/ every 10 min)
- `document-lister/document_lister/__init__.py` — Env config (RABBITMQ, REDIS, QUEUE_NAME, BASE_PATH)
- `document-indexer/document_indexer/__main__.py` — **Still Qdrant-bound!** Needs full rewrite for Solr
- `document-indexer/document_indexer/blob_storage/__init__.py` — Azure Blob Storage client (to be replaced with local FS)
- `embeddings-server/Dockerfile` — Uses `distiluse-base-multilingual-cased-v2` (semitechnologies image)
- `embeddings-server/main.py` — FastAPI server loading `use-cmlm-multilingual` (MODEL MISMATCH)
- `admin/src/main.py` — Streamlit main page
- `admin/src/pages/document_lister.py` — Shows Redis queue state
- `aithena-ui/src/App.tsx` — Chat-oriented React UI (talks to /v1/question/ — old qdrant-search)

**Critical gaps identified:**
1. Book library path (`/home/jmservera/booklibrary`) not mounted in docker-compose
2. Document indexer fully Qdrant-dependent (imports qdrant_client, uses pdfplumber instead of Solr Tika)
3. No search API service exists (qdrant-search commented out)
4. Schema lacks explicit book domain fields (title, author, year, category)
5. Embeddings server has model mismatch between Dockerfile and main.py
6. React UI designed for chat, not search+facets+PDF viewing

**User preferences:**
- Multilingual focus: Spanish, Catalan, French, English (including very old texts)
- Local-first: books on local filesystem, no cloud dependency for core features
- Phased approach: keyword search first, embeddings later

### 2026-03-13T23:15 — PR #72 Review & Phase 2 Draft PR Assessment

**PR #72 Review (APPROVED):**
- Reviewed \`solr-search/\` FastAPI service implementation (+867/-65 lines)
- **Code quality:** Excellent. Clean separation of concerns (config.py, search_service.py, main.py), comprehensive type hints, proper error handling
- **Security:** Strong. Path traversal protection, local-parameter injection blocking, safe URL encoding, Content-Disposition sanitization
- **Test coverage:** 11 unit tests covering core logic, security edge cases, pagination, faceting, normalization
- **Architecture:** Full ADR-003 compliance (FastAPI for search API), integrates cleanly with existing docker-compose and service patterns
- **Integration:** Properly configured in docker-compose.yml with volume mount, CORS, and dependencies on Solr
- **Minor notes (non-blocking):** Pinned FastAPI 0.99.1 and uvicorn 0.23.1 are stable but slightly dated; test uses sys.path.append instead of proper package structure

**Phase 2 Draft PR Assessment:**
- **#54 & #60:** REDUNDANT with PR #72. Both attempt to solve issue #36/#37, but PR #72 is superior implementation with better security and test coverage. Recommended closure.
- **#61:** Search UI rewrite looks reasonable but blocked on PR #72 merge (needs /search endpoint). Should rebase after #72 lands.
- **#62:** Faceted search UI likely overlaps with #61 (both claim to "replace chat shell"). Need clarification on relationship—pick one or sequence them.
- **#63:** PDF viewer panel is appropriately layered on search UI + depends on /documents/{id} from PR #72. Should wait for base UI + backend.
- **#64:** Large test suite PR (+3.7k lines) should be broken into feature-aligned test PRs or held until UI features stabilize. Risk of maintenance burden if added before features exist.

**Decision outcome:** PR #72 approved and ready to merge. Recommended closing #54/#60, sequencing #61→#63, and clarifying #62 vs #61 overlap. Test suite #64 needs scoping discussion.

**Key architectural insight:** The copilot agents generated multiple overlapping solutions for the same issue (#36). In future, triage should assign issues one-at-a-time to avoid draft PR sprawl.

### 2026-03-13T23:20 — Phase 2 Frontend PR Review (#61, #62, #63)

**Context:** PR #72 (solr-search backend) merged to `jmservera/solrstreamlitui`. Reviewed three Phase 2 frontend PRs from @copilot.

**PR #61 — "Replace chat shell with React search page"** (CLOSED as redundant)
- Clean implementation: basic search UI (query + results), proper React patterns, good TypeScript
- Security: Excellent `sanitizeSnippet()` XSS protection (escape all HTML, restore only `<em>`)
- API mismatch: Uses `limit` instead of `page_size`, missing pagination params
- **Verdict:** Closed in favor of PR #62 (superset with facets + pagination)

**PR #62 — "Faceted search UI — full search interface"** (APPROVED ✅)
- Complete Phase 2 implementation: search + facets + filters + pagination + sort
- Excellent component structure: FacetPanel, ActiveFilters, BookCard, Pagination, useSearch hook
- API contract: Correctly uses `q`, `page`, `fq_*` filters, consumes facets
- Minor fix needed: Change `limit` to `page_size` for exact API alignment
- **Verdict:** APPROVED and marked ready for review. This is the definitive Phase 2 search UI.

**PR #63 — "PDF viewer panel integrated into React search UI"** (NEEDS CHANGES ❌)
- **Critical issue:** Modifies **qdrant-search** instead of **solr-search** (wrong service!)
- Phase 2 is Solr-first (ADR-001, architecture plan) — qdrant-search is deprecated
- API mismatch: Uses `input` param instead of `q`, wrong response shape
- **Good parts:** PdfViewer.tsx component is well-designed (iframe, escape-to-close, error handling)
- **Required changes:**
  1. Remove all qdrant-search modifications
  2. Rebase on PR #62 (layer PDF viewer on top of faceted search UI)
  3. Fix useSearch hook to match solr-search API (`q` param, `page_size`, consume `document_url`)
  4. Use existing `/documents/{document_id}` endpoint from solr-search
- **Verdict:** NEEDS CHANGES — commented with detailed fix guidance

**Overlap resolution:** #61 and #62 both replace the chat shell. #62 is a superset (adds facets/pagination), so closing #61 eliminates redundancy. #63 should build on #62, not rewrite the UI from scratch.

**Key learning:** The three PRs show different copilot agents solving overlapping issues (#38, #39, #40) independently. #61 (minimal search) and #62 (full search) conflict because both rewrite `App.tsx`. The right sequence is: #62 → #63 (rebase with PDF viewer on top).

**Next steps:**
- PR #62 needs one-line fix (`limit` → `page_size`), then merge
- PR #63 needs full rework (remove qdrant-search changes, rebase on #62, fix API calls)
- Future Phase 2 PRs should build incrementally on the merged #62 base

### 2026-03-13T23:35 — Phase 2-3 Draft PR Review (#64, #65)

**Context:** Reviewed two @copilot PRs after PR #62 (faceted search UI) merged to `jmservera/solrstreamlitui`.

**PR #64 — "Add Vitest test coverage"** (CLOSED ❌)
- **Critical blocking issue:** Branched from old state BEFORE PR #72 (solr-search) and PR #62 (faceted UI) merged
- Would DELETE critical infrastructure if merged:
  - Entire `solr-search/` service (Dockerfile, main.py, requirements.txt, all tests)
  - `.github/workflows/ci.yml` (CI workflows just added by Parker)
  - `.squad/` team metadata
  - docker-compose.yml Phase 2 changes
- **Root cause:** PR created when base was at old commit; attempting to merge stale state over fresh work
- **What was valuable:** 39 vitest tests for search/facets/PDF viewing, proper test infrastructure setup
- **Verdict:** CLOSED with detailed explanation. If tests still needed, must create NEW PR rebased on current state, ONLY adding test files (no production code overlap with already-merged #62)

**PR #65 — "Align embeddings-server with distiluse model"** (APPROVED ✅)
- Clean ADR-004 implementation: fixes Dockerfile/main.py model mismatch
- Changes `use-cmlm-multilingual` → `distiluse-base-multilingual-cased-v2`
- Single source of truth: `MODEL_NAME` in `config/__init__.py` (env-overridable)
- New `GET /v1/embeddings/model` endpoint exposes model + dimension for Solr vector field sizing
- Existing `/v1/embeddings/` contract unchanged (backward compatible)
- Fail-fast startup with `sys.exit(1)` and `CRITICAL` log on model load failure
- 8 pytest tests, all mocked (no model download required)
- **Verdict:** APPROVED and marked ready. This is Phase 3 step 1, independent of Phase 2 UI work.

**Key architectural learning:** When reviewing PRs in rapid succession, ALWAYS check the branch point. PRs branched before recent merges can become "time bombs" that delete fresh work. The git diff stat showing massive deletions of recently-added services was the red flag.

**Stale PR detection pattern:**
1. Check PR diff stat for unexpected deletions
2. Compare PR file list against current branch state
3. If PR adds files that already exist with different content, it's likely stale
4. If PR deletes files that were recently added, it's DEFINITELY stale

**Triage improvement:** When batching copilot issues, ensure agents pull latest base branch before starting work to avoid this class of conflict.

### 2026-03-14 — Phase 3 PR Review (#68, #69, #70)

**Context:** Reviewed three Phase 3 PRs after #65 (embeddings), #66 (Solr vectors), #67 (chunking) merged.

**ALL THREE PRs NEED CHANGES** — Stale branch + wrong service

**PR #68 — Keyword/Semantic/Hybrid Search** (❌ NEEDS MAJOR CHANGES)
- **Critical issue:** Modifies `qdrant-search/` instead of `solr-search/`
- Uses Qdrant for semantic search, but PR #66 added Solr vector fields with kNN handler
- Architecture (ADR-001, ADR-003) requires Solr-first hybrid search
- Docker naming confusion: creates service named `solr-search` but uses `qdrant-search/Dockerfile`
- **What was good:** RRF implementation, normalized models, 22 tests, backward-compatible defaults
- **Required:** Rebase, target `solr-search/main.py`, use Solr `/knn` handler, combine Solr BM25 + Solr kNN

**PR #69 — Similar Books Endpoint** (❌ NEEDS MAJOR CHANGES)
- **Critical issue:** Modifies `qdrant-search/`, uses Qdrant `.retrieve()` and `.search()`
- Should add endpoint to `solr-search/main.py` using Solr kNN on `book_embedding` field
- Endpoint should accept Solr doc ID, not Qdrant point ID
- Depends on #68, which is blocked
- **What was good:** Clean endpoint design, self-exclusion, chunk dedup, 13 tests, error handling
- **Required:** Wait for #68 fix, rebase, target `solr-search`, query Solr vectors

**PR #70 — Similar Books UI** (⏸️ BLOCKED)
- **Issue:** Blocked by #69 needing reimplementation
- API contract mismatch (endpoint path, ID format)
- **What was good:** Clean React hooks, good UX, proper separation, component quality
- **Recommendation:** Put on hold; likely needs minor fixes after #69 lands

**Root Cause:**
All three PRs branched before #66/#67 merged. Agents didn't see:
- Solr vector fields now exist (PR #66)
- Architecture established `solr-search` as canonical service (PR #72)
- Chunking targets Solr (PR #67)

Work based on outdated assumptions (use Qdrant, modify old service).

**Key Learning:**
When batching copilot issues, ensure agents pull latest base before starting. Stale branch state causes fundamental architecture violations requiring complete rework, not incremental fixes.

**Triage Improvement:**
Before labeling next Phase 3 batch, wait for these to be reworked and merged. The dependency chain (#45→#46→#47) must flow through correct service.
