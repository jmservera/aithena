## v0.7.0 Milestone Completion

**2026-03-15T15:00Z** — v0.7.0 milestone complete. All 7 issues closed, 7 PRs merged to `dev`. 
- Versioning infrastructure (#199, #204) ✅
- Version endpoints (#200, #203) ✅  
- UI version footer (#201) ✅
- Admin containers endpoint (#202) ✅
- Documentation-first release process (#205) ✅

3 decisions recorded. Ready for release to `main`.

---

# Ash — History

## Project Context
- **Project:** aithena — Book library search engine with Solr indexing, multilingual embeddings, PDF processing
- **User:** jmservera
- **Stack:** Apache Solr 9.7, Docker Compose, multilingual embeddings (`distiluse-base-multilingual-cased-v2`, 512D)
- **Languages:** Spanish, Catalan, French, English (including very old texts)
- **Current setup:** Solr 3-node SolrCloud cluster with Tika extraction and langid detection

## Core Context

**Solr Schema & Vector Setup (v0.4-v0.5):**
- **Book metadata fields:** `title_s/t`, `author_s/t`, `year_i`, `page_count_i`, `file_path_s`, `folder_path_s`, `category_s`, `language_detected_s`
- **copyField rules:** `title_t`, `author_t` → `_text_` for catch-all search
- **Highlighting config:** unified highlighter with `content` snippet source, `_text_` alternate-field fallback
- **Dense vector field:** `book_embedding` (512D, HNSW cosine similarity for kNN)
- **Tika extraction:** Full-text + langid auto-detection enabled on all nodes
- **Faceting:** author, category, year, language aggregations enabled

**Phase 1-3 Deliverables:**
- Phase 1: 11 book metadata fields + copyFields, Tika + langid chains live
- Phase 2: Faceting config, highlighting tuning, result ranking
- Phase 3: Dense vector field `book_embedding`, kNN handler enabled

**Search Modes (v0.5):**
- `keyword` (BM25 on `_text_`)
- `semantic` (kNN on `book_embedding`)
- `hybrid` (RRF fusion with configurable weights)

## Learnings

<!-- Append learnings below -->

### 2026-03-20 — PRD decomposition: Folder Path Facet (#592)

**PRD:** `docs/prd/folder-path-facet.md` — decomposed into 4 GitHub issues for v1.10.0 milestone:

| Issue | Title | Routed to |
|-------|-------|-----------|
| #650 | Add folder_path_s as search facet in solr-search API | squad:ash |
| #652 | Folder facet hierarchical tree UI component | squad:dallas |
| #653 | Folder facet unit and integration tests | squad:lambert |
| #656 | Folder facet as selection mechanism for batch operations | squad:dallas + squad:parker |

**Decomposition decisions:**
- Split backend (small, 3-5 LOC) from frontend (medium, tree rendering) since they're independently implementable
- Kept the entire frontend tree UI as one issue rather than splitting flat list vs. tree — they're tightly coupled and one developer should own the full component
- Tests as a separate issue routed to Lambert, not embedded in backend/frontend issues — follows the squad routing table
- Batch operations integration kept as its own issue because it depends on the sister batch editing feature (#593) and involves both Dallas and Parker
- Used Option A (client-side tree building) per PRD recommendation — simpler first, Solr PathHierarchy upgrade deferred

### 2026-03-20 — Fix #562: Vector/hybrid 502 errors (nginx timeout issue)

**Problem**: Vector/hybrid search was returning 502 Bad Gateway errors intermittently. Additionally, user reported "keyword search returns no results" but this was not reproducible in tests.

**Root cause (502)**: The nginx `/v1/` location block was missing `proxy_read_timeout` and `proxy_connect_timeout` directives:
- Embeddings-server timeout: 120s (configured via `EMBEDDINGS_TIMEOUT`)
- Nginx default `proxy_read_timeout`: 60s
- Long queries (complex embeddings) exceeded 60s → nginx killed the connection → 502

**Fix**: Added timeout directives to `src/nginx/default.conf`:
- `proxy_read_timeout 180s` (1.5× embeddings timeout for safety margin)
- `proxy_connect_timeout 10s` (fast failure on connection issues)

**Key insight**: `default.conf.template` already had these timeouts from PR #568, but `default.conf` was out of sync. This suggests someone manually edited `default.conf` or regenerated it from an older template. The template file is the source of truth — `default.conf` should be generated from it.

**Keyword search "no results" investigation**:
- All 503 unit tests pass, including keyword search tests
- Code logic is correct (94.03% coverage)
- No code changes found that would break keyword search
- **Conclusion**: Likely a data issue (Solr index empty) or environment issue (Solr not running), not a code bug
- Recommended verifying Solr index via admin dashboard

**Empty query behavior** (also part of #562):
- Keyword mode: empty query → 200 with 0 results (normalized to `*:*`) ✅ correct
- Semantic/hybrid: empty query → 400 error ✅ correct (per PR #622, intentional — can't generate embedding from empty string)

**Lesson**: When debugging 502 errors from nginx → upstream service:
1. Check nginx timeout configs first (`proxy_read_timeout`, `proxy_connect_timeout`, `proxy_send_timeout`)
2. Compare against upstream service timeouts (embeddings, Solr, etc.)
3. Always set nginx timeout > upstream timeout (1.5× is a good safety margin)
4. Check both `.conf` and `.conf.template` files for drift

### 2026-03-19 — Fix #562: Empty query + 502 in vector/hybrid search

**Issue A (empty query):** `_search_semantic` and `_search_hybrid` raised HTTP 400 on blank queries. Fixed to return empty result sets (mode, empty results, empty facets) — consistent with keyword mode which normalizes blank to `*:*`.

**Issue B (502 Bad Gateway):** Root cause was nginx `/v1/` location using default `proxy_read_timeout` of 60s while `EMBEDDINGS_TIMEOUT` is 120s. Embedding generation for long queries could exceed 60s, causing nginx to kill the upstream connection. Fixed by adding `proxy_read_timeout 180s` (1.5× the embeddings timeout) and `proxy_connect_timeout 10s` to the `/v1/` location block.

**Key insight:** Any nginx proxy location that routes to services with long timeouts (embeddings, Solr bulk ops) must have `proxy_read_timeout` set to at least match the upstream timeout. The Streamlit location already had `proxy_read_timeout 86400` — the API location was missing it.

### 2026-03-14 — Reskill: Solr configuration snapshot + vector search readiness

**Managed-schema.xml structure:**
- 11 explicit book fields (all implemented + copyFields to `_text_`)
- DenseVectorField `book_embedding` (512D) configured for HNSW kNN with cosine similarity
- Tika extraction handler on `/update/extract` with langid detection chain
- Unified highlighter configured for search result snippets

**Faceting & Search Tuning:**
- Author, category, year, language facets enabled on `/select` handler
- `edismax` query parser for natural language search (default qf: `_text_`, pf: `title_t^2`)
- Highlighting enabled with context window sizing

**Vector search architecture (Phase 3):**
- Query embeddings generated by embeddings-server POST `/v1/embeddings/` (512D)
- Solr kNN handler queries `book_embedding` field with configurable `k` (default 10)
- Book-level embeddings: generated during indexing by document-indexer
- Integration: `solr-search` backend manages embedding calls + RRF fusion

**Performance considerations:**
- HNSW indexing during ingestion; kNN queries <100ms per benchmark expectations
- 3-node cluster with replication factor 3 → distributed kNN across shards
- No current performance bottlenecks identified; benchmarking deferred to post-v0.5

**Remaining roadmap:**
- v0.5 completion: #163 (search mode selector UI), #41 (frontend tests), #47 (similar-books UI)
- v0.6 planning: upload endpoint, file watcher, hardening
- Post-v1.0: query reranking, semantic similarity tuning, OCR quality improvements

## v1.10.0 PRD Decomposition Session (2026-03-20)

Ash decomposed the Folder Path Facet PRD into 4 GitHub issues for v1.10.0:

- #650: Solr schema & backend folder facet
- #652: Frontend folder tree UI (tree parsing, filter, breadcrumb)
- #653: Testing & benchmarks
- #656: Batch operations coordination (depends on #593)

Key decisions:
- Option A (client-side tree building) chosen for simplicity
- Frontend consolidated to avoid handoff overhead
- Lambert assigned to testing as separate work item

Status: Backend (#650) and frontend (#652) can start in parallel; tests wait for both to be ready.
