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

## Session 2026-07-21 — PR #882 (P1-2: Solr 768D Schema)

Created `books_e5base` configset and collection for the embedding model A/B test.

**Changes delivered:**
- New configset `src/solr/books_e5base/` with `knn_vector_768` field type (768D, HNSW, cosine)
- `embedding_v` and `book_embedding` fields updated to 768D in new configset
- `solr-init` container creates both `books` and `books_e5base` collections on startup
- README updated to document dual configsets

**Learnings:**
- The configset copy approach (full directory copy + targeted edits) keeps the two schemas independently versionable while ensuring all non-vector config (analyzers, stopwords, synonyms, update chains) stays in sync.
- The `add-conf-overlay.sh` script is collection-agnostic (parameterized by `SOLR_COLLECTION` env var), so it works for both collections without modification.
- The `grep -q` idempotency pattern in solr-init is critical — it prevents duplicate configset uploads or collection creates on container restarts.

**PR:** #882 → dev (branch: `squad/873-solr-768d-schema`)
## Session 2026-03-22 — PR #883 (P1-1: E5-Base Embeddings Support)

Implemented multilingual-e5-base support in the embeddings server (issue #874, milestone v1.12.0).

**Key decisions:**
- Model family detection via simple substring match (`"e5"` in model name, case-insensitive) — extensible if new model families are added later
- Prefix handling fully internal: callers pass `input_type: "query"|"passage"` (default `"passage"` for backward compat with indexing callers), server applies `"query: "` or `"passage: "` prefix for e5-family only
- `/v1/embeddings/model` now returns `model_family` and `requires_prefix` so downstream services (solr-search, document-indexer) can verify configuration
- `/version` includes `model` field for operational visibility

**Test coverage:** 33 tests (was 9), covering both distiluse and e5 paths with mocked models.

## Learnings

### E5 Prefix Design (P1-1)
Keeping prefix logic inside the embeddings-server was the right call — it prevents every caller from needing to know model-specific prefixes. The `input_type` field is the stable API contract; prefix strings are an implementation detail. This pattern should be preserved if additional model families are added.

## Session 2026-07-21 — PR (P2-1: Index Test Corpus, #877)

Created scripts for indexing test corpus through both pipelines and verifying collection parity.

**Changes delivered:**
- `scripts/index_test_corpus.py` — Publishes document paths to the `documents` fanout exchange so both indexers process them. Supports `--dry-run`, `--limit`, `--status-only`, custom `--base-path`.
- `scripts/verify_collections.py` — Verifies both Solr collections: parent doc count match, ID parity, embedding dimensionality (512D vs 768D). Exits 0/1 for CI integration. JSON output mode.
- 33 new tests in `scripts/benchmark/tests/` covering discovery, publishing, Solr queries, verification logic, report formatting, serialization.
- Updated `scripts/benchmark/README.md` with end-to-end A/B test workflow documentation.

**Learnings:**
- The fanout exchange pattern makes test corpus indexing trivial — a single publish to the `documents` exchange reaches both indexers without any routing logic. The idempotency comes from Solr's unique key dedup, not from the scripts.
- The parent/chunk distinction matters for verification: parent docs have no `parent_id_s` field, chunks do. Filtering with `-parent_id_s:[* TO *]` is the reliable way to count only parent documents across collections.
- When scripts import dependencies lazily (inside functions), `unittest.mock.patch` can't find the attribute on the module. Top-level imports are required for mockability.

## Session 2026-07-21 — PR #TBD (P2-2: Benchmark Query Suite)

Created benchmark query suite and runner for A/B testing distiluse vs e5-base (#879).

**Changes delivered:**
- `scripts/benchmark/queries.json` — 30 queries across 5 categories (simple keyword, natural language, multilingual, long/complex, edge cases)
- `scripts/benchmark/run_benchmark.py` — CLI runner that executes queries against both `books` and `books_e5base` collections via the solr-search API, collects top-K results/scores/latency, computes Jaccard similarity, outputs JSON + human-readable summary
- `scripts/benchmark/tests/test_benchmark.py` — 25 tests covering query loading, Jaccard computation, result comparison, API interaction (mocked), summary aggregation, serialization, and report formatting

**Learnings:**
- The solr-search API's `collection` parameter and automatic `input_type=query` injection for e5 collections (via `is_e5_collection()`) means the benchmark runner needs no special e5 handling — it just passes the collection name and the API handles the rest.
- Jaccard similarity of top-K is a simple but effective overlap metric for human evaluation. Low-overlap queries (Jaccard < 0.3) are the most interesting for manual review since they show where models disagree most.
- Catching `OSError` alongside `requests.RequestException` is necessary for robustness — bare `ConnectionError` from mocks or network issues inherits from `OSError`, not `requests.RequestException`.
