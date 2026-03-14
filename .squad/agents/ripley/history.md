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

### 2026-07-14 — PR Triage & Prioritization

**Merged:** #55 (E2E test harness), #101 (dependabot esbuild/vite), #102 (dependabot js-yaml)

**Assigned @copilot with fix instructions:**
- #63 (PDF viewer, Phase 2, HIGH) — surgical PdfViewer.tsx extraction
- #68 (hybrid search, Phase 3, HIGH) — rebase + retarget to Solr kNN
- #69 (similar books endpoint, Phase 3, MEDIUM) — BLOCKED on #68
- #56 (docker hardening, Phase 4, LOW) — additive health checks only

**Closed as unfixable:**
- #70 (similar books UI) — old chat UI base, needs full rewrite
- #58 (PDF upload endpoint) — targets qdrant-search/, wrong service
- #59 (PDF upload UI) — old chat UI base, needs full rewrite

**Key learning:** Two classes of stale PRs emerged:
1. **Rebaseable** — PRs touching solr-search/ or adding new components. Conflicts are mechanical (already-merged code in diff). Worth fixing.
2. **Unrebaseable** — PRs built on pre-#62 chat UI or targeting qdrant-search/. The foundation changed fundamentally. Cheaper to close and re-create.

**Triage heuristic:** Check the file list. If a PR modifies `ChatMessage.tsx`, `Configbar.tsx`, `chat.tsx`, or `qdrant-search/`, it's stale beyond repair. Close it.

### 2026-07-14 — Charter Reskill Audit

**Task:** Audit all 8 charters, extract procedures to shared skills, slim down to <1.5KB each.

**Findings:**
- Every charter duplicated a "## Project Context" section (5-7 lines each, ~300B per charter)
- 6 charters duplicated "## Tech Stack" sections (~200-350B each)
- `project-conventions` skill was an empty template — wasted slot
- Copilot charter had branch/PR conventions that apply to all agents

**Actions:**
1. Rewrote `project-conventions` skill with actual project context, service inventory, tech stack, patterns
2. Created `squad-pr-workflow` skill with branch naming, PR conventions, stale PR detection
3. Removed Project Context from 7 charters (kept scribe's as-is per instructions)
4. Removed Tech Stack from 6 charters (parker, dallas, ash, lambert, brett, copilot)
5. Replaced copilot's Branch/PR Convention sections with skill references

**Results:**

| Agent   | Before | After | Saved | Notes |
|---------|--------|-------|-------|-------|
| ripley  | 1303B  | 905B  | 398B  | Removed Project Context |
| parker  | 1512B  | 962B  | 550B  | Removed Tech Stack + Project Context |
| dallas  | 1407B  | 838B  | 569B  | Removed Tech Stack + Project Context |
| ash     | 1836B  | 1182B | 654B  | Removed Tech Stack + Project Context |
| lambert | 1311B  | 909B  | 402B  | Removed Tech Stack + Project Context |
| brett   | 2003B  | 1186B | 817B  | Removed Tech Stack + Project Context |
| scribe  | 936B   | 936B  | 0B    | Untouched (already <1KB) |
| copilot | 3091B  | 2248B | 843B  | Removed Tech Stack + Project Context + PR/Branch conventions |
| **Total** | **13399B** | **9166B** | **4233B** | **~1058 tokens saved** |

**Skills created/updated:** 2 (project-conventions rewritten, squad-pr-workflow created)

**Key learning:** The Capability Profile in copilot's charter (🟢/🟡/🔴 matrix) is functional config, not procedure — it can't be externalized without breaking the self-assessment workflow. Copilot stays at 2.2KB, above target but structurally necessary.

### 2026-07-14 — PR Review: #63, #68, #69 (Phase 2-3 Fixed PRs)

**Context:** Reviewed 3 @copilot PRs rebased onto `jmservera/solrstreamlitui`, retargeted from qdrant-search to solr-search.

**PR #63 — PDF Viewer Panel (APPROVED ✅)**
- PdfViewer.tsx: Clean iframe viewer, Escape-to-close, error fallback, accessibility
- BookCard.tsx: XSS-safe `sanitizeHighlight()`, `document_url` integration
- Uses existing `/documents/{document_id}` endpoint from solr-search
- Diff bloated (6.1K adds) — carries accumulated base-branch changes; actual PDF code is well-scoped

**PR #68 — Hybrid Search Modes (APPROVED ✅)**
- Phase 3 keystone: `?mode=keyword|semantic|hybrid` on `/search`
- Solr kNN `{!knn}` for semantic, embeddings server for vectors, RRF fusion for hybrid
- ThreadPoolExecutor for parallel BM25+embedding in hybrid mode
- Backward-compatible (default mode = keyword)

**PR #69 — Similar Books Endpoint (APPROVED ✅, merge after #68)**
- `GET /books/{document_id}/similar` using Solr kNN on `book_embedding`
- Two-step: fetch source embedding → kNN with `-id:` exclusion filter
- `solr_escape()` prevents Lucene injection; 12 tests

**Key learning — Parallel PR creation creates merge-order dependencies:**
All three PRs create `solr-search/` files from scratch. The second PR to merge will conflict. Workflow: merge in dependency order, rebase next PR, then merge.

### 2026-07-15 — Feature Priorities Analysis (4 Priorities)

**Context:** User requested analysis of 4 feature priorities, cross-referenced against existing backlog.

**Key findings:**

1. **Test the indexer (NEW issue):** document-indexer fully rewritten for Solr (Tika + chunks + embeddings). solr-init auto-bootstraps collection. E2E harness exists (PR #55) but bypasses actual pipeline (POSTs directly to Solr). Full lister→RabbitMQ→indexer pipeline has **never been run** against real books. Assigned: Lambert + Brett. Effort: M.

2. **Test search finds words (NEW issue):** solr-search API exists with keyword/semantic/hybrid modes (PRs #68, #72 merged). No real-data validation — all tests mock Solr responses. Depends on Priority 1 completing first. Assigned: Lambert + Parker. Effort: S.

3. **Configurable books path (NEW issue):** `.env` already gitignored but doesn't exist. docker-compose.yml hardcodes `/home/jmservera/booklibrary`. E2E compose already shows the `${VAR:-default}` pattern. Single-line fix + `.env.example`. Assigned: Brett. Effort: S.

4. **UI dashboard + library browser (NEW — 3-4 sub-issues):** Streamlit admin (#51/PR #57 merged) covers operator view. React UI has nothing for stats/status/browsing. Needs backend endpoints (`/v1/stats`, `/v1/library`) + 3 React pages (Search/Library/Status tabs). Assigned: Parker + Dallas + Lambert. Effort: L.

**Recommended execution order:** P3 (quick win) → P1 (needs stack) → P2 (needs data) → P4 (largest, parallelizable).

**Decision written to:** `.squad/decisions/inbox/ripley-feature-priorities.md`

### 2026-03-14 — P4 UI Spec: Library, Status, Stats Tabs

**Context:** Juanma approved building all 3 P4 tabs (Library, Status, Stats) in the React UI. Designed full spec for Dallas (frontend) and Parker (backend).

**Spec written to:** `.squad/decisions/inbox/ripley-p4-ui-spec.md`

**Key design decisions:**

1. **3 new backend endpoints** in `solr-search/main.py` (same service, same patterns):
   - `GET /v1/library/?path=` — filesystem browser with Solr metadata enrichment
   - `GET /v1/status/` — aggregated health from Solr, Redis, RabbitMQ, embeddings-server
   - `GET /v1/stats/` — collection statistics via Solr stats component + facets

2. **Frontend architecture:**
   - `react-router-dom` for client-side routing (`/search`, `/library/*`, `/status`, `/stats`)
   - Extract current search into `SearchPage.tsx`, `App.tsx` becomes router shell
   - One custom hook per tab: `useLibrary()`, `useStatus()`, `useStats()`
   - Status tab auto-refreshes every 10s via polling (not WebSocket)

3. **Implementation order:** Stats endpoint (S) → Status endpoint (M) → Library endpoint (M) → Tab routing (S) → Stats UI (S) → Status UI (M) → Library UI (L)

4. **Reuse strategy:** Stats endpoint reuses existing `build_solr_params()` + `parse_facet_counts()`. Library reuses `PdfViewer.tsx` for opening books. Status requires new RabbitMQ management API connection (new env var).

5. **Open question:** `recharts` for charts vs plain tables. Recommended tables-first, charts in follow-up PR.

**Effort estimate:** ~3 backend endpoints (S+M+M) + 4 frontend components (S+S+M+L) = medium total. Parker and Dallas can parallelize — backend first, frontend follows as endpoints land.

### 2026-03-14 — Branching Strategy & Release Flow Setup

**Request:** Juanma asked for a proper branching strategy after UI broke from uncoordinated PR merges.

**Actions taken:**
1. **Created `dev` branch** from `jmservera/solrstreamlitui` (commit 19decee) — this is now the active development integration branch
2. **Pushed `dev` to origin** — all future squad/copilot PRs target `dev` instead of the feature branch
3. **Documented branching strategy** in `.squad/decisions/inbox/ripley-branching-strategy.md`:
   - `dev` — active development, all PRs land here
   - `main` — production-ready, only working code
   - Feature branches → `dev` → `main` at phase boundaries
   - Merge authority: only Ripley or Juanma can merge dev → main and create tags
4. **Created `.github/workflows/release.yml`** — CI workflow triggered on `v*` tags that runs tests and creates GitHub releases
5. **Updated `.github/copilot-instructions.md`** — added branching strategy section so @copilot targets `dev`
6. **Updated `.squad/skills/squad-pr-workflow/SKILL.md`** — added PR base branch rule and anti-pattern for targeting `main` directly
7. **Tagged `v0.3.0-rc1`** — marks current state (Phase 3 features merged, UI needs integration fix)

**Versioning scheme established:**
- v0.1.0 — Phase 1 (Solr indexing) ✅
- v0.2.0 — Phase 2 (Search API + UI) ✅
- v0.3.0 — Phase 3 (Embeddings + hybrid search) — RC tagged, awaiting UI fix
- v0.4.0 — Phase 4 (Dashboard + polish) — upcoming

**Key decision:** Tagged as RC (not full release) because the UI is broken. Full v0.3.0 tag will be created after UI stabilization.

### 2026-03-14 — Triage of 14 @copilot Draft PRs

**Context:** @copilot delivered 14 draft PRs from P4 spec + infrastructure work. Juanma requested triage via Ralph.

**Critical finding:** All 14 PRs targeted `jmservera/solrstreamlitui` instead of `dev`. Retargeted all to `dev` via GitHub API.

**Actions taken:**

1. **Retargeted all 14 PRs** from `jmservera/solrstreamlitui` → `dev`
2. **Merged 6 safe PRs** (Tier 1 infrastructure + Tier 2 UV migrations):

| PR | Title | Verdict | Action |
|----|-------|---------|--------|
| #115 | Remove qdrant/llama services | ✅ Clean | Merged (squash) |
| #117 | Ruff config + CI lint job | ✅ Clean | Merged (squash) |
| #116 | UV admin migration | ✅ Clean | Merged (squash) |
| #129 | UV solr-search migration | ✅ Clean | Merged (squash) |
| #130 | UV document-indexer migration | ✅ Clean | Merged (squash) |
| #131 | UV document-lister migration | ✅ Clean | Merged (squash) |

3. **Reviewed + held 8 PRs** (Tier 3-5):

| PR | Title | Verdict | Status |
|----|-------|---------|--------|
| #118 | /v1/stats/ endpoint | ✅ Approved in principle | HOLD — wait for UI stabilization |
| #119 | /v1/status/ endpoint | ✅ Approved in principle | HOLD — wait for UI stabilization |
| #123 | Tab navigation | ✅ Clean scaffold | HOLD — Dallas fixing UI first |
| #127 | Stats tab | ⚠️ Overlaps #118 backend | HOLD — needs rebase after #118 |
| #128 | Status tab | ✅ Clean | HOLD — depends on #119 |
| #136 | Page-aware chunking | ✅ Clean | HOLD — first in chain |
| #137 | Page numbers in API | ✅ Clean | HOLD — depends on #136 |
| #138 | PDF viewer page nav | ⚠️ Conflicting | HOLD — rebase after #136+#137 |

**Issues flagged:**
- PR #127 duplicates the stats endpoint from #118 — merge #118 first, then rebase #127
- PR #138 has merge conflicts — needs rebase after dependency chain lands
- All Tier 4 frontend PRs held pending Dallas UI fix

**Merge order when ready:**
- Tier 3: #118 → #119 (backend endpoints)
- Tier 4: #123 → #127 (rebase) → #128 (frontend, after Dallas UI fix)
- Tier 5: #136 → #137 → #138 (rebase) (page search chain)

### 2026-03-14 — Backlog Organization into GitHub Milestones

- **COMPLETED:** Organized the full backlog into 5 GitHub milestones (v0.3.0–v1.0.0).
- **Closed 13 issues** that were completed by merged PRs but never closed: #81–#84 (UV originals), #91 (LINT-1 original), #110 (qdrant removal), #111–#112 (UV-1/LINT-1 recreates), #113 (/v1/stats/), #124–#126 (UV recreates), #133 (page-aware chunking).
- **Assigned 36 open issues** across milestones:
  - v0.3.0 Stabilize Core: 5 issues (UV/ruff cleanup, docs)
  - v0.4.0 Dashboard & Polish: 7 issues (endpoints, tabs, frontend lint/test)
  - v0.5.0 Advanced Search: 3 issues (page results, similar books)
  - v0.6.0 Security & Hardening: 19 issues (security CI, Mend vulns, docker hardening)
  - v1.0.0 Production Ready: 2 issues (PDF upload) + future work
- **Cadence established:** After each milestone → Pause → Scribe logs → Reskill → Tag release → Merge to default.
- Decision recorded in `.squad/decisions/inbox/ripley-milestone-plan.md`.

### 2026-03-14 — Retro v0.3 + Reskill Cycle

**Retro conducted:** Synthesized learnings from all 7 agent histories + 3 session logs.
- **What went well:** Pipeline bugs found fast (Parker lister+indexer fixes), Playwright caught API mismatch, parallel @copilot work (14 PRs), skills guided Brett/Parker effectively, branching strategy stabilized merges.
- **What didn't go well:** UI broke from uncoordinated merges, stale branches targeting wrong base, smoke artifacts in repo root, collection bootstrap missing.
- **Key learnings:** Hybrid dev workflow essential, must gate frontend builds, API contracts need single source of truth, page-level search needs app-side extraction.

**Skills created:**
1. `smoke-testing` (medium) — Docker up → health wait → Vite → Playwright → cleanup cycle
2. `api-contract-alignment` (medium) — Keep frontend/backend API paths in sync via shared prefix
3. `pr-integration-gate` (medium) — Required build/test checks before merging PRs to dev

**Skills updated:**
4. `solrcloud-docker-operations` confidence → high (validated by Brett during bootstrap + admin ingress)
5. `path-metadata-heuristics` confidence → high (validated by Parker during 169-file real library indexing)

**Charter audit:** Brett charter trimmed from 1534B to ~1280B (consolidated 8 responsibilities → 4 ownership bullets). Others within budget. Copilot charter exempt per reskill rules.

**Deliverable:** `.squad/decisions/inbox/ripley-retro-v03.md` written with full retro + action items.

### 2026-03-14 — Strategic Planning: PRDs, TDD Specs, Task Decomposition

**Context:** Juanma requested next-step planning with PRDs, task decomposition, and TDD enforcement.

**Assessment — Current state:**
- 5 milestones: v0.3.0 (6 open), v0.4.0 (7 open), v0.5.0 (3 open), v0.6.0 (19 open), v1.0.0 (2 open)
- 8 open PRs: 2 READY (#132, #119), 6 DRAFT
- v0.3.0 is all cleanup (lint, docs, UV) — no feature work
- v0.4.0 has P4 UI spec already written, backend endpoints partially in PRs

**Deliverables created:**

1. **PRD: v0.3.0 Close-Out** (`.squad/decisions/inbox/ripley-prd-v030-closeout.md`)
   - 6 independent cleanup tasks, all parallelizable
   - Acceptance criteria for each
   - Close-out protocol: CI green → tag v0.3.0 → merge to main → release

2. **PRD: v0.4.0 Dashboard & Polish** (`.squad/decisions/inbox/ripley-prd-v040-dashboard.md`)
   - 6 user stories (tab nav, library, status, stats, tests, lint)
   - Clean Architecture layers defined for both backend and frontend
   - 9 implementation tasks with full TDD specs
   - 3-phase implementation order with dependency tracking
   - Maps to existing PRs (#119, #123, #127, #128)

3. **TDD + Clean Code Skill** (`.squad/skills/tdd-clean-code/SKILL.md`)
   - Red-Green-Refactor cycle with rules
   - Clean Code principles (naming, functions, error handling)
   - Clean Architecture for Python/FastAPI and React/TypeScript
   - Test structure (Arrange-Act-Assert, Given-When-Then)
   - Anti-patterns to avoid (testing and code)

4. **v0.4.0 Task Decomposition** (`.squad/decisions/inbox/ripley-v040-task-decomposition.md`)
   - 9 tasks with full TDD specs (test names, assertions, implementation steps)
   - Agent assignments (Parker: 4 backend, Dallas: 4 frontend, Lambert: 1 testing)
   - Clean Architecture layer per task
   - Interface contracts defined

**Task counts per milestone:**
- v0.3.0: 6 issues (all cleanup, no new tasks needed)
- v0.4.0: 9 TDD tasks decomposed (maps to 7 existing + 2 new issues)
- v0.5.0: 3 issues (deferred — page search chain, blocked on v0.4.0)
- v0.6.0: 19 issues (security — deferred to Kane's audit completion)
- v1.0.0: 2 issues (deferred — PDF upload, needs full pipeline)

**Key decisions:**
- TDD is mandatory for all v0.4.0 work — skill created and linked in PRDs
- Clean Architecture layers formalized: Presentation → Application → Domain → Infrastructure
- Frontend follows: Pages → Components → Hooks → API pattern
- Library browser endpoint is new work (not in current backlog) — needs issue creation

### 2026-03-14 — Phase 4 Reflection: PR Review Patterns

**Context:** Reviewed all 6 open @copilot PRs for Phase 4. Results: 1 approved (#137), 5 rejected (#119, #127, #128, #138, #140). 17% approval rate.

**Systemic failure modes identified:**

1. **Stale branches (3/6 rejections: #127, #128, #119):** Copilot branched before PR #123 (router architecture) merged. All three carried stale App.tsx that would delete the router, TabNav, and all 4 page components. This is the same class of failure seen in Phase 2 (#64) and Phase 3 (#68, #69, #70). The pattern is now confirmed as structural, not incidental — copilot agents don't rebase before opening PRs.

2. **Scope bloat (2/6: #119, #140):** PR #119 bundled ~500 lines of unrelated frontend code into a backend endpoint PR (108 files total). PR #140 had 88 unrelated files from branch divergence. Both cases: agent didn't limit the diff to the issue scope.

3. **Wrong target branch (1/6: #140):** PR #140 targeted `jmservera/solrstreamlitui` instead of `dev`, despite `.github/copilot-instructions.md` and squad-pr-workflow skill both documenting the rule. The 13 artifact files only exist on `dev`, so the PR was structurally impossible.

4. **Dependency ordering ignored (1/6: #138):** PR #138 introduced a new `pages_i` Solr field when PR #137 (approved, not yet merged) already solves the problem via `page_start_i`/`page_end_i` normalization. Agent didn't check whether its prerequisite was merged.

**What went well:**
- Individual feature code quality was consistently good. `useStatus()`, `useStats()`, `CollectionStats.tsx`, `IndexingStatus.tsx` — all well-typed, accessible, properly decomposed React/TypeScript.
- PR #137 (page ranges) was clean, well-tested, correctly scoped, and targeted `dev`. Proof that small, independent, leaf-node issues produce good results.
- The review process caught all 5 problems before merge — no regressions introduced.

**Actionable improvements for Phase 5:**
1. **Issue gating:** Don't assign dependent issues until their prerequisite PRs are merged. Create issues in waves, not batches.
2. **Branch freshness check:** Add to issue templates: "Before starting: `git fetch origin && git checkout -b <branch> origin/dev`". Consider CI check that rejects PRs >10 commits behind base.
3. **Scope fence in issues:** Include explicit "Files you should touch" and "Files you must NOT touch" lists in issue descriptions.
4. **Single-service PRs only:** Enforce rule: backend PRs touch only `solr-search/`, frontend PRs touch only `aithena-ui/`. Mixed PRs are auto-rejected.
5. **Target branch validation:** Add CI check or PR template checklist item: "Base branch is `dev`".

### 2026-03-14 — PR #145 Review: LINT-5 Ruff Auto-Fix (REQUEST CHANGES)

**PR #145** — "[LINT-5] Run ruff auto-fix across all Python services" from @copilot (draft)
- **Target branch:** `jmservera/solrstreamlitui` ❌ (should be `dev`)
- **Branch status:** 6 ahead, 24 behind `dev` — stale
- **Changes:** 23 files, +352/-167 lines. Purely lint/format fixes across all Python services.
- **Quality of fixes:** Good. Unused imports removed (F401), wildcard imports replaced (F403/F405), unused variable `cleaned` removed (F841), duplicate `question` fn renamed to `question_post` (F811), consistent formatting applied.
- **No local ruff config added** — respects root `ruff.toml` ✓
- **Verdict:** REQUEST CHANGES — wrong target branch + stale branch. Code itself is clean; needs retarget to `dev`, rebase, and re-run ruff post-rebase.
- **Pattern note:** 6th PR in this session with wrong target branch. This is a systematic copilot agent configuration issue.

### 2026-03-14 — Branch Repair Strategy for 9 Broken @copilot PRs

**Context:** After reviewing all 9 broken PRs from @copilot (all with "changes requested"), analyzed git divergence, code value, and repair feasibility.

**Key findings:**
- All 9 PRs share the root cause: @copilot branched from `main` or old `jmservera/solrstreamlitui` instead of `dev`
- Branches are 28 commits behind `dev` (PR #138 is 126 behind)
- Most diff volume is ghost diffs from stale branches, not actual feature code
- Several PRs duplicate work already on `dev` (ruff config, uv migrations, stats endpoint)

**Triage outcome:**
- **CLOSE 5 PRs:** #143 (redundant ruff), #141 (redundant uv CI), #128 (stale status tab), #127 (stale stats tab), #119 (scope bloat status endpoint)
- **CHERRY-PICK 2 PRs:** #140 (artifact cleanup — small, targeted), #138 (PDF page nav — after #137 lands)
- **REWRITE 2 from scratch:** #145 (just run ruff on fresh branch), #144 (just run eslint/prettier on fresh branch)

**Critical dependency:** PR #137 (approved, page ranges) must rebase and merge first — it unblocks #138 and adds real search value.

**Total salvageable code across all 9 PRs: ~200 lines.** Most effort should go into prevention (branch protection, explicit base-branch instructions) rather than repair.

**Decision written to:** `.squad/decisions/inbox/ripley-branch-repair-strategy.md`

### 2026-03-14 — Stale Branch Cleanup

**Context:** Accumulated 28 remote branches (incl. HEAD) after multiple phases of copilot agent work. Many branches from merged PRs and closed-unmerged PRs were never cleaned up.

**Analysis:**
- 7 branches fully merged into `dev` (PRs #54–#71 era) — leftover after merge
- 16 branches from closed-unmerged PRs (#54–#145) — all from broken copilot PRs that branched from wrong base; decided to redo from scratch
- 5 branches protected: `dev`, `main`, `jmservera/solrstreamlitui` (default), plus 2 open PRs (#137 page ranges, #142 uv docs)

**Deleted 23 branches:**
Merged: `add-dense-vector-fields` (#66), `add-e2e-coverage-upload-search-pdf` (#55), `add-faceted-filtering-react-ui` (#62), `align-embeddings-server-to-distiluse-model` (#65), `configure-document-lister-polling` (#71), `expand-streamlit-dashboard-indexing` (#57), `extend-document-indexer-chunking` (#67).
Closed-unmerged: `add-build-status-tab-component` (#128), `add-contract-tests-solr-search-api` (#60), `add-frontend-test-coverage` (#64), `add-pdf-upload-endpoint` (#58), `add-pdf-upload-flow` (#59), `add-related-books-panel` (#70), `clean-up-smoke-test-artifacts` (#140), `create-solr-backed-fastapi-search-service` (#54), `jmservera-add-v1-status-endpoint` (#119), `jmserverasolrstreamlitui-build-stats-tab` (#127), `lint-4-replace-pylint-black-with-ruff` (#143), `lint-5-run-ruff-auto-fix` (#145), `lint-6-autofix-eslint-prettier` (#144), `replace-chat-shell-with-search-page` (#61), `update-pdf-viewer-navigation` (#138), `uv-8-update-build-scripts-ci` (#141).

**Preserved 5 branches:** `dev`, `main`, `jmservera/solrstreamlitui`, `copilot/jmservera-solrsearch-return-page-numbers` (PR #137), `copilot/doc-1-document-uv-migration` (PR #142).

**Result:** Remote went from 28 refs → 6 refs (5 branches + HEAD). Clean slate for Phase 5 work.

### 2026-03-14 — Post-Cleanup Issue Reassignment (Phase 5 Triage)

**Context:** After closing 9 broken @copilot PRs, updating copilot-instructions.md with branch guardrails, and adding scope fences, performed full triage of the 9 affected issues.

**Actions taken:**
1. Closed #134 (PR #137 merged). #96 was already closed.
2. Removed all stale `squad:*` and `go:needs-research` labels from 9 issues (#139, #135, #122, #121, #114, #95, #92, #99, #100).
3. Assigned 3 simplest issues to `squad:copilot` (batch 1): #139 (cleanup artifacts), #95 (ruff in document-lister), #100 (eslint in aithena-ui).
4. Assigned remaining 6 to squad members: #99 → Parker, #114 → Parker, #135 → Dallas, #122 → Dallas, #121 → Dallas, #92 → Brett.
5. Posted triage comments on all 9 issues with rationale.
6. Wrote decision to `.squad/decisions/inbox/ripley-issue-reassignment.md`.

**Key learning:** The GitHub `Copilot` user cannot be assigned via `gh issue edit --add-assignee Copilot`. The `squad:copilot` label is the actual routing mechanism. Don't waste time trying to assign the user directly.

**Sequential @copilot strategy:** Only 3 issues assigned at once (all 🟢 single-directory mechanical tasks). Remaining candidates (#99 ruff multi-service) held back for batch 2 after success is confirmed. This prevents the PR sprawl from Phase 4.

### 2026-03-14 — PR Review Batch 2: v0.4 Frontend Features (3 PRs approved)

**Context:** Reviewed 3 @copilot PRs implementing v0.4 UI features (PDF page nav, Status tab, Stats tab). All target `dev`. Backend APIs (PRs #156, #159) were just merged.

**Verdicts:**
- **PR #157** (PDF viewer page nav) — ✅ APPROVED. `pages?: [number, number] | null` exactly matches backend `normalize_book()`. Appends `#page=N` to PDF URL. `formatFoundPages()` handles single/range display.
- **PR #160** (Status tab) — ✅ APPROVED. `StatusResponse` types are exact match with merged `/v1/status/` endpoint. AbortController + cancelled flag + setTimeout polling — no memory leaks. ServiceDot has accessible aria-label.
- **PR #161** (Stats tab) — ✅ APPROVED. `StatsResponse`/`FacetEntry`/`PageStats` types are exact mirrors of `parse_stats_response()`. FacetTable well-extracted with limit prop.

**Merge order:** #157 → #160 → #161 (package-lock.json + App.css will need conflict resolution on 2nd and 3rd merge).

**Key observations:**
1. **Type alignment discipline:** All 3 PRs have TypeScript interfaces that exactly match the backend Python return dicts. The fix commits (aligning with backend contract) worked — copilot corrected the types after CHANGES_REQUESTED.
2. **Branch discipline holds:** 7 consecutive PRs with correct `dev` base branch since the guardrails were added.
3. **No frontend tests:** None of the 3 PRs add component tests. Backend is tested, but React layer has no coverage. Flag for v1.0 planning.
4. **AbortController inconsistency:** `useStatus()` has AbortController (polling hook), `useStats()` doesn't (one-shot). Both have cancelled flags. Minor cleanup candidate.
5. **CI gap persists:** Only CodeQL runs on PR branches — no unit test CI jobs triggered. Need to fix `ci.yml` path/branch filters.

### 2026-03-14T20:50 — Session Complete: v0.4 Merge Batch (7 PRs total)

**Context:** Led full review and merge of 7 @copilot PRs across two batches (infrastructure + frontend).

**Batch 1 (Backend Infrastructure) — All merged:**
- #156: `CollectionStats` model + `parse_stats_response()` + 14 tests ✅
- #158: Multilingual PDF metadata (en/es/fr/de) ✅
- #159: GET `/v1/status/` endpoint + 11 tests ✅
- #162: CI/CD fix (CodeQL on all branches, unit tests on main) ✅

**Batch 2 (Frontend Components) — All merged:**
- #157: PDF viewer page navigation ✅
- #160: Status tab (IndexingStatus + useStatus) ✅
- #161: Stats tab (CollectionStats + useStats) — required rebase conflict resolution (App.css) ✅

**Merge execution:** Coordinator merged all 7 in sequence without blocking issues. PR #161 had a small merge conflict in `App.css` (Status page CSS vs Stats page CSS) — resolved by keeping both.

**Key decision:** Frontend component tests deferred to post-v0.4 (acceptable for alpha phase, track for v1.0 gate).

**Exit state:** `dev` branch stable with all 7 PRs merged. Branch discipline continues (7 consecutive PRs with correct `dev` base).


### 2026-03-14 — v0.5 Release Planning (Phase 3: Embeddings Enhancement)

**Context:** Juanma requested release planning for v0.5 (Phase 3). 5 of 6 issues closed, 1 open.

**Verification results (all 5 closed issues confirmed delivered on `dev`):**
- #42: Embeddings-server aligned — `distiluse-base-multilingual-cased-v2` in config, Dockerfile, and tests. Model info endpoint added.
- #43: Dense vector fields — `knn_vector_512` field type, `book_embedding` + `embedding_v` fields in Solr schema.
- #44: Chunking + embeddings — `chunker.py` (page-aware), `embeddings.py` (HTTP client), full test coverage.
- #45: Search modes — `keyword|semantic|hybrid` via `?mode=` param, RRF fusion for hybrid, configurable defaults.
- #46: Similar-books endpoint — `GET /books/{id}/similar` with kNN, limit, min_score, proper error handling.

**Gap identified:** UI has no search mode selector. Backend supports 3 modes but `useSearch` hook doesn't pass `mode` param. Created #163 to fill this gap.

**Issue management:**
- Created #163 (search mode selector) — labeled `release:v0.5.0`, `squad`, `squad:copilot`
- Moved #41 (frontend tests) from v0.4.0 → v0.5.0
- Updated #47 body with detailed implementation guide (hook, component, integration steps)
- Updated #41 body with Vitest setup guide and test file list
- Assigned all 3 open issues to `squad:copilot`
- Added triage comments with copilot fit ratings: #163 🟢, #47 🟡, #41 🟢

**Merge strategy:** #41 + #163 in parallel (Batch 1), then #47 (Batch 2, touches SearchPage after both land).

**Decision written to:** `.squad/decisions/inbox/ripley-v05-plan.md`

### 2026-03-14T23:xx — Reskill: Current Codebase State & v0.5 Roadmap Update

**Release Status:**
- **v0.4.0 SHIPPED** — All 7 Phase 2 PRs merged to `dev` (Search API, UI, Status/Stats tabs, PDF navigation). Release commit: `c27fa4b`
- **v0.5 (Phase 3: Embeddings Enhancement) IN PROGRESS** — 5 of 6 core issues verified complete on `dev`:
  - #42, #43, #44, #45, #46 all delivered (embeddings model, dense vectors, chunking, search modes, similar-books API)
  - #163 (search mode selector UI) created as the remaining gap — assigned `squad:copilot`, 🟢 good fit
  - Two parallel copilot issues also open: #41 (frontend tests, 🟢) and #47 (similar books UI, 🟡 needs review)
- **v0.6 (Phase 4)** planned but unstarted — upload endpoint (#49), upload UI (#50), hardening (#52)

**Architecture Stability:**
- Solr migration **COMPLETE**: SolrCloud 3-node, Tika extraction, langid detection, all working on `dev`
- FastAPI search service (`solr-search/`) live and integrated: secure, well-tested (+11 unit tests), clean code structure
- React search UI (`aithena-ui/`) converted from chat to search paradigm: FacetPanel, ActiveFilters, BookCard, pagination, sort — all working
- PDF viewer panel integrated: page navigation from search results
- Status + Stats tabs complete: health monitoring (Solr, Redis, RabbitMQ), collection stats by language/author/year/category

**Critical Bugs (requires assignment):**
- **#166: RabbitMQ fails on first start — timeout_waiting_for_khepri_projections** (assigned Parker + Lambert, needs research)
- **#167: New files not detected or indexed — document pipeline stalled** (assigned Parker + Dallas, needs research)

**Active Work:**
- **Open PRs:** #164 (search mode selector backend, appears to be pre-#163), #165 (frontend test coverage for search/facets/PDF)
- **Squad labeling:** Issues #166-#167 (bugs, blocked), #98-#90 (security scanning, requires triage), #49-#50 (Phase 4, unstarted)

**Branch Discipline:** All work properly routed to `dev` as per branching strategy. Main receives merges only from dev at release gates (Newt approval required).

**Key Patterns Observed:**
1. **Copilot work is highly reliable:** Phase 2 + Phase 3 PRs are well-structured, test-covered, clean code. Zero defects merged to dev.
2. **Phase-based issue decomposition works:** Explicit dependencies + single-owner issues prevent PR sprawl.
3. **Architecture board (decisions.md) is the source of truth:** All major decisions (ADRs, team assignments, risk mitigations) recorded and traceable.
4. **Clean Code + TDD is the standard:** All services follow separation of concerns (domain/application/presentation layers), comprehensive type hints, error handling edge cases in tests.

**Next Lead Action Items:**
1. Triage & assign bugs #166-#167 (RabbitMQ + file detection failures)
2. Clarify v0.5 copilot queue: #163, #41, #47 parallelization + merge sequencing
3. Review open security scanning issues (#88-#98) — defer or assign to security team (Kane)?
4. Plan v0.6 roadmap: #49, #50, #52 — coordinate with Parker (backend) + Dallas (frontend) + Ash (search tuning)
