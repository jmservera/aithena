# Ash — History

## Core Context

**Project:** aithena — Book library search engine with hybrid semantic+keyword search

**Current Stack:**
- **Solr 9.7** SolrCloud (3 nodes), ZooKeeper 3-node ensemble
- **Primary embedding:** multilingual-e5-base (768D, HNSW cosine) — active A/B test
- **Legacy embedding:** distiluse-base-multilingual-cased-v2 (512D) — baseline collection
- **Docker Compose** with proper ZooKeeper quorum and health checks
- **Languages:** Spanish, Catalan, French, English (historical text variants supported)

**Solr Data Model (Parent-Chunk Architecture):**
- **Parent docs:** Book metadata (id = SHA-256 of path), metadata fields only
  - `title_s/t`, `author_s/t`, `year_i`, `page_count_i`, `file_path_s`, `folder_path_s`, `category_s`, `language_detected_s`, `series_s`
  - Optional `book_embedding` (768D or 512D per model variant)
  - **No `parent_id_s`** — distinguishes parents from chunks
- **Chunk docs:** Text fragments (400w/50w overlap, page-aware), `embedding_v` (primary vector field)
  - `chunk_text_t`, `embedding_v`, `chunk_index_i`, `parent_id_s`, `page_start_i`, `page_end_i`
  - Inherits parent metadata for post-kNN display
- **Critical invariant:** `EXCLUDE_CHUNKS_FQ = "-parent_id_s:[* TO *]"` applied ONLY to keyword/hybrid BM25 leg, NEVER to kNN

**Three Search Modes (defined in `search_service.py`):**
1. **Keyword (BM25):** edismax on `_text_`, chunk exclusion applied, facets + highlights
2. **Semantic (kNN):** chunk vectors, no chunk exclusion, no facets/highlights
3. **Hybrid (RRF):** parallel BM25 + kNN, RRF fusion (k=60), book-level dedup, facets/highlights from BM25 leg

**Metadata Extraction:** Path heuristics (`Category/Author/Title.pdf` or `Author - Title (Year).pdf`) with always-available fallbacks

## Key Patterns & Critical Knowledge (Always Preserve)

### 1. Parent-Chunk Model Correctness
- **Distinguishing test:** Does a field/query need parent docs or chunk docs? Parents hold metadata, chunks hold vectors.
- **Query rule:** `EXCLUDE_CHUNKS_FQ` only on BM25, never on kNN (would return zero).
- **Deletion:** Must delete parent AND all chunks with matching `parent_id_s`.
- **Why it matters:** This is the single most common source of search bugs in Aithena.

### 2. Timeout Alignment & Network Patterns
- Embeddings service: 120s, nginx `proxy_read_timeout` ≥ 180s to prevent 502s
- Solr queries: Use POST body (not GET URI) for vectors >4KB to avoid truncation

### 3. A/B Testing for Model Changes
- Dual-collection strategy: `{base}` (legacy model) + `{base}_{tag}` (new model)
- Dual configsets with independent vector dimensions but shared analyzers/synonyms
- Success metrics: ≥5% nDCG@10 gain, ≤50ms latency increase
- E5-prefix handling: internal to embeddings-server, transparent to callers via `input_type` parameter

### 4. Schema Coordination
- Changes to schema are the critical path in feature delivery
- Coordinate all schema PRs across waves to prevent conflicts

### 5. E5-Base Model Profile (Multilingual-e5-base)
- 768D vectors, HNSW cosine similarity
- Requires prefix: `"query: "` for queries, `"passage: "` for indexing (handled by embeddings-server)
- MTEB score: 61.5 (competitive with state-of-art)
- 512-token window: ~400 words/chunk recommended
- A/B testing approved; Phase 1 (schema) completed, Phase 2+ in flight

## Current Confidence & Gaps

**🟢 High confidence domains:**
- Solr schema design for hybrid search (parent-chunk, vector fields, faceting)
- Parent/chunk model correctness and query patterns
- Search mode boundaries (keyword/semantic/hybrid)
- RRF fusion implementation
- Multilingual text analysis (ICU, stemmers, ASCII folding)
- Embedding model evaluation methodology
- A/B testing framework design
- E5-Base model integration

**🟡 Medium confidence (documented, not hands-on):**
- SolrCloud cluster operations (recovery, failover) — refer to Brett's skill
- Docker Compose orchestration for ZooKeeper/SolrCloud
- ZooKeeper quorum maintenance

**🔴 Knowledge gaps (not yet encountered):**
- Performance benchmarking & HNSW tuning (cluster size, segment merges)
- OCR quality improvement workflows
- Advanced relevance engineering (LTR, field weight optimization)
- Query-time reranking beyond RRF
- Production incident response playbooks

## Session References

**Completed phases:**
- v0.4–v0.5: Schema phases 1-3 (metadata, faceting, vector)
- v1.10.0: Folder facets, series field, metadata fields
- A/B test Phase 1-2: E5-base schema, dual collections, test corpus indexing, benchmark suite

**Skills reviewed & validated:**
- `solr-pdf-indexing/SKILL.md` — no updates needed (pattern still accurate)
- `solrcloud-docker-operations/SKILL.md` — no updates (Brett's work, not hands-on for Ash)
- `solr-parent-chunk-model/SKILL.md` — validated; all patterns remain accurate
- `embedding-model-selection/SKILL.md` — validated; e5-base research stands
- `path-metadata-heuristics/SKILL.md` — validated; fallback patterns in use

**Skills created/updated this reskill:**
- **NEW:** `aithena-ab-testing-benchmarking/SKILL.md` — Consolidates dual-collection A/B testing, query benchmarking, result comparison metrics, and E5-base integration patterns

## Consolidation Notes (2026-07-21)

**What was consolidated:**
- Reorganized history to reflect current dual-collection reality (512D legacy + 768D primary)
- Collapsed detailed milestone history into compact "Completed phases" summary
- Preserved all critical correctness patterns (parent-chunk invariants, EXCLUDE_CHUNKS_FQ behavior)
- Moved old session logs into pattern descriptions to keep active knowledge front-and-center
- Updated confidence levels to reflect completed A/B testing work

**Preserved critical knowledge:**
- Parent/chunk model is foundational; source of near-incidents; must remain core
- Timeout alignment and query-to-POST patterns prevent runtime failures
- A/B testing framework is the pattern for future model evaluation
- E5-Base is now integrated; framework can scale to additional model families

**No removals:** Nothing was deleted; just reorganized for easier navigation during future search work.

## Learnings

### Solr 9.7 vs Solr 10 Benchmark Evidence (#1354, 2026-06-06)

Benchmark claims must be generated from same-host, same-corpus paired runs only. Key paths: `scripts/benchmark/run_benchmark.py` records reproducibility metadata, `scripts/benchmark/compare_solr_versions.py` gates Solr 9.7 vs 10 comparisons, and `docs/research/solr-97-vs-10-benchmark-evidence.md` documents the required runbook.

Required evidence before publishing 4× memory or 40× indexing claims: paired benchmark JSON, Docker stats with byte-valued memory samples, corpus ID/document count/byte count, startup/index timing, and failed query IDs.

### Solr 10 Language-Models Module (2025-07-22)

**Key finding:** Solr 10's `language-models` module (available since 9.8) does NOT run models locally. It is a bridge to **remote embedding APIs** (OpenAI, Cohere, HuggingFace Inference API, MistralAI) via LangChain4j. No ONNX, no in-process inference.

**Critical facts:**
- Module name: `language-models` (enable via `solr.modules=language-models`)
- Provides: `knn_text_to_vector` query parser + `TextToVectorUpdateProcessorFactory`
- All four supported model classes call remote HTTP APIs — no local execution
- **SOLR-17446** tracks in-process ONNX support — not implemented, no timeline
- Sease (module authors) list "local models" as **future work** in their July 2025 blog post
- No text preprocessing hooks: E5 prefixes ("query:"/"passage:") cannot be injected by Solr
- Index-time encoding is per-document (no batching), with explicit performance warnings

**ONNX compatibility of multilingual-e5-base:**
- Official ONNX exports exist on HuggingFace (onnx/ directory in model repo)
- LangChain4j's `OnnxEmbeddingModel` can load custom ONNX models with tokenizer.json
- Numerical precision differs from PyTorch by 1e-6 to 1e-4 — requires full re-index if switching
- LangChain4j ONNX: CPU-only (no GPU support yet), parallelized across CPU cores

**Verdict:** Cannot replace embeddings-server today. Keep current architecture. Monitor SOLR-17446.
**Full report:** `docs/research/solr10-language-models-embeddings.md`

### Vector Quantization Schema Support (#1502, 2025-07-22)

**What:** Added `knn_vector_768_byte` field type with `vectorEncoding="BYTE"` and `embedding_byte` field to support int8 quantization mode alongside existing float32 fields.

**Key decisions:**
- Dual-field approach: `embedding_v` (float32) and `embedding_byte` (int8) coexist; indexer selects based on `VECTOR_QUANTIZATION` env var
- HNSW tuned to `hnswMaxConnections="12"` for byte field (lower than default 16) to save memory since byte vectors already reduce footprint ~4x
- Existing fields untouched for full backward compatibility
- Runtime field selection happens in the indexer (Parker's domain), not in schema

### Dependabot Batch Sweep (2026-05-31)

No direct Ash service dependencies in batch PR #1584 (dependencies are in Parker's backend services + Dallas UI deps). Deferred high-risk items:
- **Solr 10** (#1562) deferred to v2.5 milestone (tracked in #1335) — requires schema/config validation
- **Python 3.14** — if selected for embeddings-server, requires testing via Parker coordination
- See `.squad/decisions.md` for full batch summary

---

### PR #1562 Review: Solr 10 Bump Deferred (2026-05-31, Ralph PR-Review Round)

**Status:** 🔴 Closed (Deferred to Epic)

Reviewed dependabot PR #1562 (Solr 9.7→10.0 version bump). Verdict: **CLOSE** — incomplete migration, belongs in v2.5 Solr 10 epic.

- **Issue:** Dockerfile version bump without CLI migration. Solr 10 removes single-dash flags (`-c` → `--collection`). luceneMatchVersion schema bump also missing.
- **Action:** Closed PR with scope fence comment, routed to #1335 (v2.5 epic planning).
- **Learning:** Dependabot PRs touching major versions require full integration scope review, not just version number change. Flag for epic routing early.

This decision establishes the precedent: version bumps are coordinated at epic level when they touch multiple services or schema. Improves reliability and prevents broken intermediate states.

## 2026-06-06 — v2.5.1 Board Completion

Completed #1349 (Evaluate hybrid search improvements) via PR #1702, merged to dev. Advanced #1348 (Prototype DocumentCategorizerUpdateProcessorFactory) via PR #1703, merged to dev; issue remains open for real ONNX/model/runtime validation. Documented decision: DocumentCategorizer stays disabled until model fixture validation.

Related: #1348, #1349, v2.5.1 board
### DocumentCategorizer Prototype Feasibility (#1348, 2026-06-06)

Solr 10 `DocumentCategorizerUpdateProcessorFactory` is feasible for index-time ONNX classification, but it lives in `analysis-extras`, not `language-models`, and requires both `model.onnx` and matching `vocab.txt` in SolrCloud FileStore. Do not enable it in active `solrconfig.xml` until a real model fixture exists.

Safe pattern: keep manual `category_s` untouched; write classifier output to separate fields such as `topic_category_s` and `document_sentiment_s`. A disabled scaffold is acceptable, but no accuracy/performance claims should be made without a labeled corpus and measured indexing/JVM validation.

### Solr 10 Combined Query / Hybrid Search Evaluation (#1349, 2026-06-06)

**Finding:** Solr 10.0.0 does not include a native RRF/combined-query handler. SOLR-17319 / Apache Solr PR #3418 is merged on mainline after the 10.0.0 tag and adds `CombinedQuerySearchHandler` + `CombinedQueryComponent` for multiple JSON DSL queries with built-in RRF (`combiner.algorithm=rrf`, `combiner.rrf.k`, default 60). This is the first Solr-native fusion feature that maps directly to Aithena's BM25 + kNN + RRF architecture, but only once Aithena's Solr runtime includes it.

**Aithena caveat:** It is not a drop-in replacement for current hybrid search because Aithena's BM25 leg returns parent book docs while kNN returns chunk docs. Native RRF operates on Solr document IDs, so parent IDs and chunk IDs do not overlap; Combined Query also documents grouping/cursor as unsupported. A prototype must either use book-level vectors, run both legs on chunks, or keep Python-side book normalization/fusion.

**Recommendation:** Keep current app-side chunk-kNN RRF in production. Prototype Solr Combined Query RRF only behind a separate handler/flag and validate against the benchmark corpus for relevance (nDCG/judged top-k), p50/p95 latency, facets/highlights, and page-range quality before changing ranking.

**Full report:** `docs/research/solr10-hybrid-search-evaluation.md`

## Research Loop Participation (2026-06-06)

- **#1357 Phase 3 Test Readiness Planning:** Co-authored Phase 3 test scope documenting query suite validation (30 queries × 3 modes), Overseer-disabled runtime diagnostics, and int8 corpus indexing readiness. Identified blockers: PR #1670 (schema fix), #1344 (benchmark validation).
- **#1347 cuVS GPU Search Implementation Plan:** Co-authored planning for GPU-accelerated vector search infrastructure and implementation approach (documented in issue threads).
- **#1348 DocumentCategorizer Runtime/QA Validation Plan:** Co-authored runtime and QA validation approach; noted that SolrCloud `DocumentCategorizerUpdateProcessorFactory` requires labeled corpus before enabling and safe pattern is separate fields (topic_category_s, document_sentiment_s) without touching core category_s.
- **#1344 int8 Quantization Gate:** Co-signed int8 evaluation protocol; noted recall@10 and memory validation as release blockers on #1670.
- **#1343 SolrCloud Overseer Decision:** Approved decision to disable Overseer in production Solr 10 while retaining ZooKeeper HA. Documented runtime validation commands for Phase 2 testing.
- **#1349 Hybrid RRF Decision:** Decided to keep app-side RRF (current implementation) as production default until Solr Combined Query is benchmarked and proven on real corpus. SOLR-17319 adds native RRF but does not handle parent/chunk fusion correctly; prototype required before default change.
