# Feature Priorities Analysis — 2026-07-15

**Author:** Ripley (Lead)
**Status:** PROPOSED — awaiting user review
**Requested by:** jmservera

---

## Priority 1: Test the Indexer — Verify End-to-End Pipeline

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

---

## Priority 2: Test Search Actually Finds Words — Keyword Search Validation

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

---

## Priority 3: Make Books Folder Configurable via .env

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

---

## Priority 4: UI Indexing Status Dashboard + Library Browser

**Existing issue:** #51 (Streamlit admin dashboard) — CLOSED (PR #57 merged). But that's the **Streamlit** admin, not the **React** UI.
**Also related:** #50 (PDF upload flow, OPEN), #41 (frontend tests, OPEN)
**Current state:**
- ✅ **Streamlit admin** (`admin/src/main.py`) already shows: Total Documents, Queued, Processed, Failed counts (from Redis), RabbitMQ queue depth, and a Document Manager page for inspection/requeue. This covers the *operator* view.
- ✅ **React UI** (`aithena-ui/`) has: search bar, faceted search, pagination, sort, PDF viewer. No stats/status/library pages.
- ❌ No React UI page for indexing status, collection statistics, or library browsing.
- The React UI currently talks only to `solr-search` (`/v1/search/`). There is no backend endpoint for collection stats or library browsing.

**Gap:** This is a **new feature** requiring both backend API endpoints and frontend pages. Two sub-features:

### A. Indexing Status + Collection Stats
**Backend:** New endpoint(s) in `solr-search`:
- `GET /v1/stats` → Returns Solr collection stats (`numDocs`, facet counts for language/author/year) + Redis pipeline stats (queued/processed/failed counts).

**Frontend:** New page/section in React UI:
- **Indexing Status:** Documents indexed, in queue, failed (from Redis via new API).
- **Collection Stats:** Total books, breakdown by language (pie chart), by author (top 20 bar), by year (histogram), by category.
- **Data source:** Combine Solr `facet.field` queries with Redis state query.

### B. Library Browser
**Backend:** New endpoint in `solr-search`:
- `GET /v1/library?path={folder}` → Returns folder listing with document counts, or documents in a folder.
- Uses Solr `folder_path_s` facet for navigation, `file_path_s` for document listing.

**Frontend:** New page in React UI:
- **Folder tree** navigation (collapsible, driven by `folder_path_s` facet).
- **Document list** per folder (title, author, year, indexing status icon).
- Click-to-search (pre-fill search with `fq_folder={path}`) or click-to-view-PDF.

### Proposed Menu/Page Structure
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

---

## Cross-Reference Summary

| Priority | Existing Issue | Existing PR | Status | New Issue Needed? |
|----------|---------------|-------------|--------|-------------------|
| 1. Test indexer | None (closest: #41 frontend tests, #53 E2E) | #55 (E2E harness, merged) | Pipeline untested with real data | ✅ YES |
| 2. Test search | #45 (hybrid modes, closed) | #68 (hybrid, merged), #72 (API, merged) | API exists, untested with real data | ✅ YES |
| 3. Configurable books path | None | docker-compose.e2e.yml shows pattern | Hardcoded path | ✅ YES |
| 4. UI dashboard + browser | #51 (Streamlit admin, closed) | #57 (admin, merged) | Streamlit done, React UI has nothing | ✅ YES — decompose into 3-4 sub-issues |

### Open PRs to Consider
- **PR #106** (remove qdrant/llama services) — cleanup, should merge. Reduces confusion.
- **PR #105** (ruff linting CI) — nice-to-have, not blocking.
- **PR #104** (uv migration for admin) — nice-to-have, not blocking.

### Recommended Execution Order
```
Priority 3 (quick win, 30min)
  → Priority 1 (needs working stack)
    → Priority 2 (needs indexed data from P1)
      → Priority 4 (largest scope, can start backend in parallel with P1/P2 testing)
```

Priority 3 unblocks portable development. Priority 1 unblocks Priority 2. Priority 4 is independent but benefits from validated search/indexing.
