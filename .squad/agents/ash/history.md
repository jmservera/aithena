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
