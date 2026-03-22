# Ash — History

## Core Context

**Project:** aithena — Book library search engine
**Stack:** Solr 9.7, 3-node SolrCloud, distiluse-base-multilingual-cased-v2 (512D), Docker Compose
**Languages indexed:** Spanish, Catalan, French, English (incl. historical texts)

### Solr Data Model (Parent-Chunk Architecture)

- **Parent documents:** Book metadata (`id` = SHA-256 of file path), no embeddings
  - Fields: `title_s/t`, `author_s/t`, `year_i`, `page_count_i`, `file_path_s`, `folder_path_s`, `category_s`, `language_detected_s`
- **Chunk documents:** Text fragments + `embedding_v` (512-dim HNSW cosine), linked via `parent_id_s`
  - Chunking: 400 words, 50-word overlap, page-aware
  - Fields: `chunk_text_t`, `embedding_v`, `chunk_index_i`, `parent_id_s`, `page_start_i`, `page_end_i`
- **⚠ Critical rule:** `EXCLUDE_CHUNKS_FQ = "-parent_id_s:[* TO *]"` — applied to keyword leg only, NEVER to kNN
- copyField rules: `title_t`, `author_t` → `_text_` for catch-all search
- Dense vector: `book_embedding` (book-level, 512D) + `embedding_v` (chunk-level, 512D)
- Tika extraction + langid auto-detection on `/update/extract`

### Search Modes

- **keyword:** BM25 via edismax on `_text_`, facets + highlighting enabled
- **semantic:** kNN on chunk `embedding_v`, collapse by `parent_id_s`
- **hybrid:** Parallel BM25 + kNN, merged with RRF (k=60)
- All modes support filter queries (`fq_author`, `fq_category`, `fq_language`, `fq_year`)
- Highlighting: unified highlighter, `content` source, `_text_` alternate-field fallback
- edismax: default qf `_text_`, pf `title_t^2`
- Empty query: keyword returns 0 results (normalized `*:*`); semantic/hybrid returns 400 (can't embed empty string)

### Faceting

- Active: author, category, year, language
- Added in v1.10.0: `folder_path_s` (client-side tree building, Solr PathHierarchy deferred)
- Also v1.10.0: `series_s` field for book series grouping

### Key Architecture Docs

- `docs/architecture/solr-data-model.md` — Parent/chunk model, search flows, critical rules (PR #723)
- `src/solr-search/README.md` — Service README with data model summary

## Learned Patterns

### Nginx ↔ Upstream Timeout Alignment (#562)
When nginx proxies to services with long timeouts (embeddings: 120s), set `proxy_read_timeout` ≥ 1.5× upstream timeout. The `/v1/` location lacked this → intermittent 502s. Also check `.conf` vs `.conf.template` for drift — template is source of truth.

### PRD Decomposition for Search Features (#592 → v1.10.0)
Decomposed folder-path-facet PRD into 4 issues: #650 (backend API, squad:ash), #652 (frontend tree, squad:dallas), #653 (tests, squad:lambert), #656 (batch ops, squad:dallas+parker). Principles: split backend/frontend for parallel work, route tests separately per squad table, choose simpler option first.

### Schema Coordination Across Features (v1.10.0)
Three features needed schema changes (#650 folder facet, #677 series field, #681 metadata). Ash coordinates all schema PRs per wave to prevent conflicts. Schema changes are the critical path.

### Architecture Docs Prevent Incidents (PR #701 → R2 retro)
PR #701 nearly broke semantic search — implementer didn't know embeddings live on chunks, not parents. Created `docs/architecture/solr-data-model.md` as retro action. **Lesson:** Document data model alongside features, not after incidents.

## Completed Milestones

- v0.4–v0.5: Schema phases 1-3 (metadata fields, faceting, vector search) — all delivered
- v0.7.0: Versioning infrastructure, endpoints, UI footer, admin containers — all 7 issues closed
- v1.10.0: Wave 0 bugs (#646, #648), Wave 1 schema (#650, #677), Wave 2 search features

## Reskill Notes

**Date:** 2026-03-21
**Self-assessment:** Strong on Solr schema design, parent-chunk architecture, search mode implementation, and facet configuration. The parent/chunk model is the most critical knowledge — it's non-obvious and has caused near-incidents. Good at PRD decomposition and schema coordination across features.

**Knowledge gaps:**
- No hands-on performance benchmarking data yet (HNSW tuning, query latency profiling)
- OCR quality improvement patterns unexplored
- Query reranking beyond RRF not yet implemented
- Advanced relevance tuning (learning-to-rank, field weight optimization) not yet needed

**Confidence levels:**
- 🟢 Schema design, faceting, vector field config, search modes, data model documentation
- 🟡 Cluster operations (documented via Brett's skill, not hands-on)
- 🔴 Production performance tuning, advanced relevance engineering

**Skills referenced:** `solr-pdf-indexing`, `solrcloud-docker-operations`, `hybrid-search-parent-chunk` (new)

## Session 2026-03-22T10:50Z — PR #863 Merged (Embedding Research)

Embedding model research for issue #861 completed and merged to dev. Recommendation: **multilingual-e5-base** (512-token window, 768D, MTEB 61.5) as primary candidate for A/B testing. Report includes:
- Model selection rationale and competitive analysis
- In-repo dual-collection A/B testing strategy (5 phases, 2-3 weeks)
- Success criteria: ≥5% nDCG@10, ≤50ms latency increase, ≤2× index growth
- Detailed team impact breakdown and risk mitigation

**Decision status:** Awaiting PO approval for infrastructure setup phase. Prepared for collaboration with Brett (infrastructure) in Phase 1 setup.

**Next:** Phase 1 kickoff when approved — Solr collection setup and schema design for 768D vectors.
