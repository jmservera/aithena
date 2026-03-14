# v0.5.0 Release Plan — Phase 3: Embeddings Enhancement

**Author:** Ripley (Lead)
**Date:** 2026-03-14
**Status:** PROPOSED

---

## Confirmed Delivered (Verified on `dev`)

| Issue | Title | Verification | Status |
|-------|-------|-------------|--------|
| #42 | Align embeddings-server with distiluse | `config/__init__.py` + `Dockerfile` both use `distiluse-base-multilingual-cased-v2`; `/v1/embeddings/model` endpoint returns dim; tests assert model name | ✅ Delivered |
| #43 | Dense vector fields in Solr | `managed-schema.xml`: `knn_vector_512` field type (512-dim, cosine, HNSW) + `book_embedding` and `embedding_v` fields | ✅ Delivered |
| #44 | Document-indexer chunking + embeddings | `chunker.py` (page-aware word chunking with overlap) + `embeddings.py` (HTTP client to embeddings-server) + `test_indexer.py` covers chunk docs and index flow | ✅ Delivered |
| #45 | Keyword/semantic/hybrid search modes | `SearchMode = Literal["keyword","semantic","hybrid"]` + `?mode=` param + `_search_keyword`, `_search_semantic`, `_search_hybrid` implementations + RRF fusion | ✅ Delivered |
| #46 | Similar-books endpoint | `GET /books/{id}/similar` with kNN query, limit, min_score; excludes source doc; 404/422 error handling | ✅ Delivered |

**No gaps found in any closed issue.** All 5 backend features are complete, tested, and on `dev`.

---

## Remaining Work (Open Issues)

### 1. #163 — Search mode selector in React UI (NEW — gap identified)
- **Why:** Backend supports 3 search modes but UI has no way to switch. Semantic/hybrid search is invisible to users.
- **Scope:** Add mode to `useSearch` hook + mode selector component in SearchPage
- **Copilot fit:** 🟢 Good fit — bounded, follows existing patterns
- **Dependencies:** None (backend delivered)
- **Estimate:** Small

### 2. #47 — Similar books in React UI
- **Why:** Core Phase 3 feature — surface semantic recommendations in the UI
- **Scope:** New `useSimilarBooks` hook + `SimilarBooks` component + SearchPage integration
- **Copilot fit:** 🟡 Needs review — requires some UI layout judgment
- **Dependencies:** None (API delivered)
- **Estimate:** Medium

### 3. #41 — Frontend test coverage (carried from v0.4)
- **Why:** No tests exist for the React UI. Needed before Phase 4 adds more complexity.
- **Scope:** Vitest setup + tests for useSearch, BookCard, FacetPanel, PdfViewer, SearchPage
- **Copilot fit:** 🟢 Good fit — mechanical setup, well-documented
- **Dependencies:** None
- **Estimate:** Medium

---

## Task Breakdown for @copilot

### Batch 1 (parallel — no dependencies between them)

| Issue | Task | Priority | Notes |
|-------|------|----------|-------|
| #41 | Frontend test coverage | P1 | Land first so subsequent PRs can add tests |
| #163 | Search mode selector | P1 | Makes Phase 3 semantic search visible |

### Batch 2 (after Batch 1)

| Issue | Task | Priority | Notes |
|-------|------|----------|-------|
| #47 | Similar books UI | P2 | Can start after #163 lands (both touch SearchPage) |

### Merge Order

```
#41 (tests) ──────────────────┐
                               ├──→ #47 (similar books UI)
#163 (mode selector) ─────────┘
```

- #41 and #163 can merge in parallel (they touch different files mostly)
- #47 should go after both to avoid conflicts in SearchPage.tsx
- All PRs target `dev`

---

## Gaps Considered but Deferred

| Gap | Decision | Rationale |
|-----|----------|-----------|
| Embeddings-server `/health` endpoint | Defer to Phase 4 | Not user-facing; docker-compose can use process checks |
| Embedding dimension config validation | Defer | Schema and model already aligned at 512-dim |
| E2E test for semantic search | Defer to Phase 4 | Phase 4 includes E2E hardening |

---

## Questions for Juanma

1. **Merge cadence:** Should we merge #41/#163 as they land, or batch into a single v0.5 release? My recommendation: merge as they land on `dev`, tag v0.5.0 after #47 merges.
2. **Search mode default:** Should the UI default to `keyword` or `hybrid`? Backend defaults to `keyword`. I'd keep `keyword` as default until embeddings are confirmed indexed for the full library.
3. **v0.5 scope freeze:** Are there any other features you want in v0.5 beyond these 3 issues? If not, I'll close the milestone after #47 merges.
