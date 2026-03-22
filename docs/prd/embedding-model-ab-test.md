# PRD: Embedding Model A/B Test — multilingual-e5-base vs distiluse

**Author:** Ripley (Lead)
**Requested by:** Juanma (jmservera)
**Date:** 2026-03-22
**Status:** DRAFT — Awaiting PO Review
**Research:** [Embedding Model Research](../research/embedding-model-research.md) (Ash, #861)

---

## 1. Overview

This PRD defines the implementation plan for an in-repo A/B test comparing the current embedding model (`distiluse-base-multilingual-cased-v2`, 128 tokens, 512D) against the recommended replacement (`multilingual-e5-base`, 512 tokens, 768D). The goal is to measure relevance improvement, resource cost, and operational feasibility before committing to a production migration.

**Why now:** The current 128-token context window constrains chunks to ~90 words, fragmenting semantic units and limiting retrieval quality. The 512-token window of e5-base enables 300+ word chunks that capture full paragraphs and complex arguments.

**Scope:** In-repo dual-collection setup. Both models run simultaneously against the same document corpus. Evaluation is human-in-the-loop (PO-driven).

---

## 2. Current State (From Codebase)

| Component | Current Value | Source |
|-----------|--------------|--------|
| **Model** | `sentence-transformers/distiluse-base-multilingual-cased-v2` | `src/embeddings-server/config/__init__.py` (`MODEL_NAME` env var) |
| **Max tokens** | 128 | Model constraint |
| **Embedding dims** | 512 | Detected at runtime via `model.get_sentence_embedding_dimension()` |
| **Chunk size** | 90 words | `src/document-indexer/document_indexer/__init__.py` (`CHUNK_SIZE` env var, default=90) |
| **Chunk overlap** | 10 words | `src/document-indexer/document_indexer/__init__.py` (`CHUNK_OVERLAP` env var, default=10) |
| **Chunking algo** | Sentence-aware word-count sliding window | `src/document-indexer/document_indexer/chunker.py` — prefers sentence boundaries |
| **Solr field type** | `knn_vector_512` (HNSW, cosine) | `src/solr/books/managed-schema.xml` line 46 |
| **Solr field** | `embedding_v` (type `knn_vector_512`) | `src/solr/books/managed-schema.xml` line 497 |
| **Solr collection** | `books` | `docker-compose.yml` — `SOLR_COLLECTION=books` |
| **Embeddings API** | `POST /v1/embeddings/` (returns vector list) | `src/embeddings-server/main.py` |
| **Embeddings timeout** | 300s | `src/document-indexer/document_indexer/embeddings.py` line 9 |
| **RabbitMQ queue** | `shortembeddings` | `docker-compose.yml` — `QUEUE_NAME=shortembeddings` |
| **Memory limits** | embeddings-server: 2GB, document-indexer: 512MB | `docker-compose.yml` deploy resources |

### 2.1 Data Flow

```
document-lister → RabbitMQ (shortembeddings) → document-indexer
  → pdfplumber (per-page text) → chunker.py (90w, 10w overlap, sentence-aware)
  → embeddings-server (distiluse, 512D) → Solr (books collection, knn_vector_512)
```

### 2.2 Key Integration Points

- **Query prefix:** Current model requires NO prefix. e5-base requires `"query: {text}"` for queries and optionally `"passage: {text}"` for passages. This affects both the embeddings-server (encoding) and solr-search (query encoding).
- **Embedding dimension:** Detected dynamically at startup (`model.get_sentence_embedding_dimension()`), but the Solr schema field type is hardcoded to 512D. A new collection needs a new field type.
- **Parent-chunk hierarchy:** Embeddings live on chunk documents, not parents. kNN queries target chunks, grouped by `parent_id_s` for book-level results. This architecture is preserved in the A/B test.

---

## 3. Target State (A/B Architecture)

```
                    ┌──────────────────────────────────────────────────┐
                    │  SolrCloud (3-node)                              │
                    │  ┌──────────────────┐  ┌──────────────────┐     │
                    │  │ books (baseline) │  │ books_e5base     │     │
                    │  │ distiluse 512D   │  │ e5-base 768D     │     │
                    │  │ 90-word chunks   │  │ 300-word chunks  │     │
                    │  │ knn_vector_512   │  │ knn_vector_768   │     │
                    │  └────────▲─────────┘  └────────▲─────────┘     │
                    └───────────┼──────────────────────┼───────────────┘
                                │                      │
              ┌─────────────────┴──┐    ┌──────────────┴──────────┐
              │ document-indexer   │    │ document-indexer-e5     │
              │ CHUNK_SIZE=90      │    │ CHUNK_SIZE=300          │
              │ CHUNK_OVERLAP=10   │    │ CHUNK_OVERLAP=50        │
              │ COLLECTION=books   │    │ COLLECTION=books_e5base │
              └────────▲───────────┘    └────────▲────────────────┘
                       │                         │
              ┌────────┴───────────┐    ┌────────┴────────────────┐
              │ embeddings-server  │    │ embeddings-server-e5   │
              │ distiluse (512D)   │    │ e5-base (768D)          │
              │ port 8080          │    │ port 8085               │
              │ 2GB RAM            │    │ 3GB RAM                 │
              └────────────────────┘    └─────────────────────────┘
                       ▲                         ▲
                       └─────────┬───────────────┘
                                 │
                    ┌────────────┴───────────┐
                    │  RabbitMQ               │
                    │  shortembeddings queue  │
                    └────────────────────────┘
```

Both indexers consume from the same RabbitMQ queue. Each indexes documents into its respective Solr collection with its own model and chunking parameters.

---

## 4. Chunking Recalculation

**PO decision context:** `CHUNK_SIZE=90` was chosen for the 128-token window (90 words × ~1.3 tokens/word ≈ 117 tokens, fitting within 128).

**New calculation for 512-token window:**
- 512 tokens ÷ ~1.3 tokens/word ≈ 393 words max
- Reserve ~12 tokens for special tokens (CLS, SEP, padding) → 385 usable words
- Apply 75% utilization target (avoid truncation edge cases) → **~290 words**
- Round to clean number: **300 words** (conservative, ~390 tokens)

**Recommended chunking for e5-base:**

| Parameter | Current (distiluse) | Proposed (e5-base) | Rationale |
|-----------|--------------------|--------------------|-----------|
| `CHUNK_SIZE` | 90 words | **300 words** | ~390 tokens, safely within 512-token window |
| `CHUNK_OVERLAP` | 10 words | **50 words** | Proportional scaling (11% → 17%), improves context continuity |

**Impact on index size:**
- Fewer chunks per book (~3.3× reduction in chunk count)
- But each vector is 768D vs 512D (+50% per vector)
- Net effect: ~55% fewer bytes in vector storage per book (fewer chunks outweighs larger dimensions)
- However, `chunk_text_t` stored text per chunk grows 3.3×

**⚠️ PO Decision Required:** Final CHUNK_SIZE and CHUNK_OVERLAP values for e5-base. The 300/50 recommendation follows the same proportional logic as the PO's original 90/10 decision for the 128-token window.

---

## 5. Phased Work Plan

### Phase 1 — Infrastructure Setup

Dependencies: None (all Phase 1 items can start in parallel after P1-1).

---

#### P1-1: Add multilingual-e5-base Support to Embeddings Server

**Assigned to:** Ash (Search Engineer)
**Effort:** 2 points (small)

**Description:**
The embeddings-server already loads the model dynamically via `MODEL_NAME` env var and detects dimensions at runtime. However, e5-base requires query/passage prefixes (`"query: {text}"` and `"passage: {text}"`) that the current API does not support. Add prefix handling to the embeddings server.

**Changes required:**
- `src/embeddings-server/main.py`: Accept optional `prefix` field in `EmbeddingsInput` request body
- `src/embeddings-server/config/__init__.py`: Add `QUERY_PREFIX` and `PASSAGE_PREFIX` env vars (default empty for backward compatibility with distiluse)
- When a prefix is configured and no explicit prefix is passed in the request, prepend automatically
- Ensure `/v1/embeddings/model` endpoint returns prefix configuration so clients know what to use

**Acceptance criteria:**
- [ ] `EmbeddingsInput` model accepts optional `prefix: str` field
- [ ] `QUERY_PREFIX` and `PASSAGE_PREFIX` env vars are supported (defaults: empty string)
- [ ] When `MODEL_NAME=intfloat/multilingual-e5-base`, queries work correctly with prefix
- [ ] Backward compatible: existing distiluse callers unaffected (no prefix = no prefix applied)
- [ ] `/v1/embeddings/model` response includes `query_prefix` and `passage_prefix` fields
- [ ] Unit tests cover prefix application and backward compatibility
- [ ] `requirements.txt` unchanged (sentence-transformers already supports e5 models)

---

#### P1-2: Create Solr Collection Schema for 768D Vectors

**Assigned to:** Ash (Search Engineer)
**Effort:** 2 points (small)

**Description:**
Create a new Solr configset and collection (`books_e5base`) that mirrors the existing `books` collection but uses a 768-dimensional vector field type. The existing `managed-schema.xml` at `src/solr/books/managed-schema.xml` defines `knn_vector_512` — the new schema needs `knn_vector_768`.

**Changes required:**
- Create `src/solr/books_e5base/` directory with a copy of the existing configset
- In the new `managed-schema.xml`:
  - Add `<fieldType name="knn_vector_768" class="solr.DenseVectorField" vectorDimension="768" similarityFunction="cosine" knnAlgorithm="hnsw"/>`
  - Change `embedding_v` and `book_embedding` fields to use `knn_vector_768` type
  - Add ADR comment referencing this PRD
- All other fields (parent/chunk hierarchy, metadata, `chunk_text_t`, etc.) remain identical
- Add collection creation to Solr init scripts or document manual creation command

**Acceptance criteria:**
- [ ] `src/solr/books_e5base/managed-schema.xml` exists with `knn_vector_768` field type
- [ ] All non-vector fields match `src/solr/books/managed-schema.xml` exactly
- [ ] `embedding_v` and `book_embedding` use `knn_vector_768`
- [ ] `solrconfig.xml` is copied (or symlinked) from existing configset
- [ ] Collection creation command documented in README or script
- [ ] YAML validation passes for any docker-compose changes

---

#### P1-3: Update Document Indexer for Dual-Model Indexing

**Assigned to:** Parker (Backend Dev)
**Effort:** 3 points (medium)

**Description:**
Configure a second instance of the document-indexer that targets the e5-base embeddings server and the `books_e5base` Solr collection. The indexer is already fully configurable via environment variables (`EMBEDDINGS_HOST`, `EMBEDDINGS_PORT`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `SOLR_COLLECTION`). No code changes needed in the indexer itself — only Docker Compose configuration.

However, the indexer must handle the e5 model's passage prefix. Two options:
- **Option A (preferred):** The embeddings-server-e5 auto-prepends `"passage: "` prefix (configured via `PASSAGE_PREFIX` env var from P1-1). Indexer sends raw text as today.
- **Option B:** Add `EMBEDDING_PREFIX` env var to the indexer to prepend before sending. Requires a small code change.

**Changes required:**
- Docker Compose: add `document-indexer-e5` service (see P1-4)
- If Option B: add `EMBEDDING_PREFIX` env var to `src/document-indexer/document_indexer/__init__.py` and apply in `embeddings.py` before sending text

**Acceptance criteria:**
- [ ] `document-indexer-e5` service definition in docker-compose with correct env vars
- [ ] `CHUNK_SIZE=300`, `CHUNK_OVERLAP=50`, `SOLR_COLLECTION=books_e5base`
- [ ] `EMBEDDINGS_HOST=embeddings-server-e5`, `EMBEDDINGS_PORT=8085`
- [ ] Same RabbitMQ queue (`shortembeddings`) — both indexers consume same documents
- [ ] Passage prefix is handled (via embeddings-server auto-prefix or indexer env var)
- [ ] Existing `document-indexer` service unchanged
- [ ] Indexer tests pass with both configurations

---

#### P1-4: Docker Compose Configuration for A/B Setup

**Assigned to:** Brett (Infra Architect)
**Effort:** 3 points (medium)

**Description:**
Add the A/B test services to `docker-compose.yml` (or a new `docker-compose.ab-test.yml` overlay). This includes the second embeddings server and second document indexer, with correct resource limits, health checks, networking, and dependency ordering.

**New services:**

```yaml
embeddings-server-e5:
  build:
    context: ./src/embeddings-server
  environment:
    - MODEL_NAME=intfloat/multilingual-e5-base
    - PORT=8085
    - QUERY_PREFIX=query:${SPACE}
    - PASSAGE_PREFIX=passage:${SPACE}
  expose:
    - "8085"
  deploy:
    resources:
      limits:
        memory: 3g          # e5-base needs ~2-3GB for encoding
      reservations:
        memory: 2g
        cpus: "2.0"         # 278M params benefits from 2 cores

document-indexer-e5:
  build:
    context: ./src/document-indexer
  environment:
    - EMBEDDINGS_HOST=embeddings-server-e5
    - EMBEDDINGS_PORT=8085
    - CHUNK_SIZE=300
    - CHUNK_OVERLAP=50
    - SOLR_COLLECTION=books_e5base
    - QUEUE_NAME=shortembeddings
  depends_on:
    embeddings-server-e5:
      condition: service_healthy
    solr:
      condition: service_healthy
    rabbitmq:
      condition: service_healthy
    redis:
      condition: service_healthy
  deploy:
    resources:
      limits:
        memory: 512m
```

**Key decisions:**
- Use a compose overlay file (`docker-compose.ab-test.yml`) to avoid polluting the production compose file. Activated with `docker compose -f docker-compose.yml -f docker-compose.ab-test.yml up`.
- Memory limit for `embeddings-server-e5`: 3GB (e5-base is 278M params, needs ~2-3GB during encoding)
- Health check for `embeddings-server-e5`: same pattern as existing (`wget` on `/health`), but `start_period: 120s` (model download + load time on first run)

**Acceptance criteria:**
- [ ] `docker-compose.ab-test.yml` overlay file created at repo root
- [ ] `embeddings-server-e5` service with correct `MODEL_NAME`, port, resource limits, health check
- [ ] `document-indexer-e5` service with correct env vars and dependency ordering
- [ ] Network aliases configured so `embeddings-server-e5` is resolvable by name
- [ ] Both new services can coexist with existing services (no port conflicts)
- [ ] YAML validation passes (`python3 -c "import yaml; yaml.safe_load(open('docker-compose.ab-test.yml'))"`)
- [ ] README or inline comments document how to activate the A/B overlay
- [ ] Total memory budget documented (existing ~6GB + new ~3.5GB = ~9.5GB)

---

#### P1-5: Add Collection Parameter to solr-search API

**Assigned to:** Parker (Backend Dev)
**Effort:** 2 points (small)

**Description:**
Extend the solr-search API to accept an optional `collection` query parameter that routes queries to a specific Solr collection. Currently, `SOLR_COLLECTION` is a fixed env var (`books`). For A/B comparison, the API needs to query either `books` or `books_e5base`.

**Changes required:**
- `src/solr-search/solr_search/search_service.py`: Accept `collection` parameter, validate against allowlist
- `src/solr-search/solr_search/config.py`: Add `ALLOWED_COLLECTIONS` env var (default: `books`)
- Query construction: replace hardcoded collection in Solr URL with parameter value
- **Security:** Allowlist validation only — never pass user-provided collection names directly to Solr

**Also needed:** When querying the e5-base collection, the search service must prepend `"query: "` to the text before sending to the embeddings server for vector encoding. The embeddings server's `/v1/embeddings/model` endpoint (enhanced in P1-1) exposes the `query_prefix` — the search service should fetch and cache this at startup.

**Acceptance criteria:**
- [ ] `/v1/search?q=...&collection=books_e5base` routes to the correct Solr collection
- [ ] Collection parameter validated against `ALLOWED_COLLECTIONS` allowlist
- [ ] Default remains `books` when no parameter provided
- [ ] Query prefix (`"query: "`) applied when targeting e5-base collection
- [ ] Error response (400) for invalid collection names
- [ ] Existing search behavior unchanged when parameter is omitted
- [ ] Unit tests cover collection routing, validation, and prefix application

---

### Phase 2 — Indexing & Benchmarking

Dependencies: All Phase 1 items must be complete.

---

#### P2-1: Index Test Corpus with Both Models

**Assigned to:** Ash (Search Engineer)
**Effort:** 3 points (medium)

**Description:**
Index a representative test corpus (100–200 books) into both Solr collections simultaneously. Ensure balanced language distribution across the four target languages (ES, FR, CA, EN). Measure and log indexing performance metrics.

**Steps:**
1. Select corpus: minimum 100 books, ~25 per language (ES, FR, CA, EN)
2. Start both indexer instances via docker-compose overlay
3. Trigger document-lister scan or manual queue population
4. Monitor both indexers until completion
5. Record metrics per collection

**Metrics to capture:**
- Documents/second per indexer (from indexer logs)
- Peak memory usage per service (`docker stats`)
- Solr index size on disk per collection (`du -sh /var/solr/data/books*`)
- Encoding latency distribution (p50, p95 from embeddings server logs)
- Total indexing time for full corpus
- Chunk count per book (compare 90-word vs 300-word)

**Acceptance criteria:**
- [ ] Both collections indexed with identical document sets
- [ ] Minimum 100 books, balanced across ES/FR/CA/EN
- [ ] Indexing metrics documented in a report (markdown or CSV)
- [ ] No indexing errors or failures in either pipeline
- [ ] Solr admin UI confirms both collections are queryable
- [ ] Index size comparison documented (baseline vs e5-base)

---

#### P2-2: Create Benchmark Query Suite

**Assigned to:** Ash (Search Engineer)
**Effort:** 2 points (small)

**Description:**
Create a standardized query suite of 50 queries across 4 categories and 4 languages for repeatable evaluation. The research report (Section 7.4) provides candidate queries — refine these based on the actual test corpus.

**Query categories (50 total):**
- **Single-keyword (10):** Simple topic queries (e.g., "Napoleon", "quantum")
- **Phrase queries (15):** Multi-word specific queries (e.g., "French Revolution causes")
- **Conceptual queries (15):** Abstract/thematic queries (e.g., "books about overcoming adversity")
- **Multilingual queries (10):** Queries in ES, FR, CA targeting specific content

**Deliverable format:**
```json
{
  "queries": [
    {
      "id": "kw-01",
      "category": "keyword",
      "language": "en",
      "text": "Napoleon",
      "expected_topics": ["French history", "military biography"],
      "notes": "Expect French history books in all languages"
    }
  ]
}
```

Store at `tests/benchmark/embedding-ab-queries.json`.

**Acceptance criteria:**
- [ ] 50 queries total: 10 keyword + 15 phrase + 15 conceptual + 10 multilingual
- [ ] At least 3 queries per target language (ES, FR, CA, EN)
- [ ] Each query has `expected_topics` for relevance grading
- [ ] Queries aligned with actual test corpus content (not hypothetical)
- [ ] JSON file committed to `tests/benchmark/`
- [ ] README in `tests/benchmark/` explains the query suite

---

#### P2-3: Build Comparison API for Side-by-Side Results

**Assigned to:** Parker (Backend Dev)
**Effort:** 3 points (medium)

**Description:**
Create an API endpoint (or script) that runs each benchmark query against both collections and returns side-by-side results for comparison. This feeds into human evaluation (Phase 3).

**Option A — API endpoint (preferred):**
Add `GET /v1/search/compare?q={query}` to solr-search that:
1. Runs the query against `books` (baseline, distiluse)
2. Runs the query against `books_e5base` (variant, e5-base)
3. Returns both result sets with scores, anonymized labels (Model A / Model B)

**Option B — CLI script:**
Python script that reads `tests/benchmark/embedding-ab-queries.json`, queries both collections via the API (using the `collection` parameter from P1-5), and writes results to a CSV/JSON report.

**Acceptance criteria:**
- [ ] Both collections queryable from a single entry point
- [ ] Results include: query text, rank, title, score, collection source
- [ ] Anonymized labeling option (for blind evaluation)
- [ ] Supports batch execution of the full 50-query suite
- [ ] Output format supports both human review (readable) and metrics computation (structured)
- [ ] Latency per query recorded in output

---

#### P2-4: Collect Performance Metrics

**Assigned to:** Lambert (Tester)
**Effort:** 2 points (small)

**Description:**
Run the benchmark query suite against both collections and collect quantitative metrics. Produce a structured report for the PO's decision gate.

**Metrics:**

| Category | Metric | How to Measure |
|----------|--------|----------------|
| **Latency** | Query response time (p50, p95, p99) | Timed API calls per query |
| **Latency** | Embedding encoding time | Embeddings server logs |
| **Resource** | Solr index size on disk | `du -sh` per collection |
| **Resource** | Embeddings server memory (peak RSS) | `docker stats` |
| **Resource** | kNN query memory (Solr JVM heap) | Solr admin metrics |
| **Quality** | Result count per query | API response |
| **Quality** | Score distribution (min/max/avg) | API response |
| **Quality** | Chunk count per book (avg) | Solr stats query |

**Acceptance criteria:**
- [ ] All 50 benchmark queries executed against both collections
- [ ] Latency report with p50/p95/p99 per collection
- [ ] Resource usage report (disk, memory, CPU)
- [ ] Metrics saved to `tests/benchmark/results/` as structured data (JSON/CSV)
- [ ] Summary report in markdown for PO review
- [ ] Comparison against success criteria from research report (Section 4.4)

---

### Phase 3 — Evaluation & Migration

Dependencies: Phase 2 complete. PO decision gate required between P2-4 and P3-2.

---

#### P3-1: Human-in-the-Loop Relevance Evaluation

**Assigned to:** Juanma (PO) — with tooling support from Parker
**Effort:** 5 points (large, ~4-6 hours of PO evaluation time)

**Description:**
The PO reviews side-by-side results from the comparison API (P2-3) and scores relevance for each query against both collections. Results are blind-labeled (Model A / Model B) to avoid bias.

**Evaluation protocol:**
1. For each of the 50 queries, review top-10 results from both collections
2. Score each result: 0 (irrelevant), 1 (partially relevant), 2 (highly relevant)
3. Record scores in a structured format (spreadsheet or JSON)
4. Compute nDCG@10, MRR, Precision@5 per collection

**Success criteria (from research report Section 4.4):**
- **Proceed** if relevance improvement ≥ 5% nDCG@10 (p < 0.05)
- **Proceed** if query latency increase ≤ 50ms at p95
- **Proceed** if index size increase ≤ 2×
- **Abort** if relevance improvement < 3%
- **Abort** if query latency > +100ms p95
- **Abort** if index size > 3× baseline

**Acceptance criteria:**
- [ ] All 50 queries evaluated (100 annotation tasks total)
- [ ] Blind evaluation (PO doesn't know which model produced which results)
- [ ] Relevance scores recorded in structured format
- [ ] nDCG@10, MRR, Precision@5 computed and documented
- [ ] Go/no-go decision documented with rationale

---

#### P3-2: Production Migration Plan

**Assigned to:** Brett (Infra Architect) + Ash (Search Engineer)
**Effort:** 3 points (medium) — only if P3-1 approves migration

**Description:**
If the A/B test succeeds (PO approves), create and execute the production migration plan. This replaces the current model with e5-base in the production pipeline.

**Migration steps:**
1. **Schema migration:** Update `src/solr/books/managed-schema.xml` to use `knn_vector_768`
2. **Full reindex:** All documents must be reindexed with the new model and chunk size (no in-place vector update possible)
3. **Service update:** Change `embeddings-server` to use `MODEL_NAME=intfloat/multilingual-e5-base` and configure prefixes
4. **Indexer update:** Change `CHUNK_SIZE=300`, `CHUNK_OVERLAP=50` in `document-indexer` service
5. **Search update:** Ensure `solr-search` applies query prefix for e5 model
6. **Cleanup:** Remove A/B overlay, `books_e5base` collection, dual services
7. **Version bump:** Update `VERSION` file for the release

**Acceptance criteria:**
- [ ] Migration plan documented with step-by-step instructions
- [ ] Rollback plan defined (see P3-3)
- [ ] Estimated downtime documented (reindexing duration for full corpus)
- [ ] Data backup procedure before migration
- [ ] Smoke test checklist for post-migration validation

---

#### P3-3: Rollback Plan

**Assigned to:** Brett (Infra Architect)
**Effort:** 1 point (trivial)

**Description:**
Document and validate the rollback procedure in case the migration causes issues in production.

**Rollback strategy:**
- The `books` collection (baseline) remains untouched during the A/B test
- If migration to e5-base fails or underperforms in production:
  1. Revert `docker-compose.yml` changes (model, chunk size, collection name)
  2. Point services back to original `books` collection
  3. No reindex needed — baseline collection is intact
- If the baseline collection was already replaced:
  1. Restore from Solr backup (BCDR procedures from v1.10.1)
  2. Reindex from document library with original configuration

**Acceptance criteria:**
- [ ] Rollback procedure documented step-by-step
- [ ] Rollback tested in development environment
- [ ] Estimated rollback time documented
- [ ] Decision tree: when to rollback vs. when to fix forward

---

## 6. Dependency Graph

```
P1-1 (embeddings prefix)
  │
  ├──→ P1-3 (indexer dual config) ──→ P1-4 (docker compose) ──→ P2-1 (index corpus)
  │                                                                      │
  └──→ P1-5 (search API collection) ──→ P2-2 (query suite) ──→ P2-3 (comparison API)
                                                                         │
                                                               P2-4 (metrics) ──→ P3-1 (PO eval)
                                                                                       │
                                                                              P3-2 (migration plan)
                                                                                       │
                                                                              P3-3 (rollback plan)

P1-2 (Solr schema) ──→ P1-4 (docker compose)
```

**Critical path:** P1-1 → P1-3 → P1-4 → P2-1 → P2-3 → P2-4 → P3-1

**Parallelizable:** P1-1 and P1-2 can start simultaneously. P1-5 can start after P1-1.

---

## 7. Effort Summary

| Item | Title | Assignee | Effort | Phase |
|------|-------|----------|--------|-------|
| P1-1 | Embeddings server e5 prefix support | Ash | 2 pts | 1 |
| P1-2 | Solr schema for 768D vectors | Ash | 2 pts | 1 |
| P1-3 | Document indexer dual-model config | Parker | 3 pts | 1 |
| P1-4 | Docker Compose A/B overlay | Brett | 3 pts | 1 |
| P1-5 | solr-search collection parameter | Parker | 2 pts | 1 |
| P2-1 | Index test corpus | Ash | 3 pts | 2 |
| P2-2 | Benchmark query suite | Ash | 2 pts | 2 |
| P2-3 | Comparison API | Parker | 3 pts | 2 |
| P2-4 | Performance metrics | Lambert | 2 pts | 2 |
| P3-1 | Human evaluation | Juanma (PO) | 5 pts | 3 |
| P3-2 | Production migration plan | Brett + Ash | 3 pts | 3 |
| P3-3 | Rollback plan | Brett | 1 pts | 3 |
| | **Total** | | **31 pts** | |

**By assignee:**
- **Ash:** P1-1, P1-2, P2-1, P2-2, P3-2 (co-owner) = 12 pts
- **Parker:** P1-3, P1-5, P2-3 = 8 pts
- **Brett:** P1-4, P3-2 (co-owner), P3-3 = 7 pts
- **Lambert:** P2-4 = 2 pts
- **Juanma:** P3-1 = 5 pts (human evaluation, not dev work)

**Note:** Dallas (Frontend) is not assigned work in this PRD. A comparison UI (frontend toggle between collections) could be added as a stretch goal, but the CLI/API-based comparison (P2-3) is sufficient for the A/B evaluation.

---

## 8. Risks & Mitigations

| # | Risk | Impact | Likelihood | Mitigation |
|---|------|--------|------------|------------|
| R1 | **e5-base encoding too slow on CPU** | Indexing backlog, slow reindexing | Medium | Memory limit at 3GB, 2 CPU cores. If still slow: batch encoding optimization, or defer to GPU support (future). Benchmark during P2-1. |
| R2 | **768D index too large for disk** | Disk exhaustion on Solr nodes | Low | Research estimates 1.5× growth. Fewer chunks (3.3× fewer) partially offsets. Monitor during P2-1. If critical: explore Solr int8 quantization (9.4+). |
| R3 | **Query latency unacceptable** | Poor UX for users | Low | Research estimates +15ms. Monitor during P2-4. If >50ms: tune HNSW params (efConstruction, maxConnections), reduce topK. |
| R4 | **Relevance improvement marginal (<3%)** | Wasted effort on A/B infrastructure | Medium | A/B infrastructure is reusable for future model tests (e5-large, BGE-M3). The overlay pattern and benchmark suite are permanent assets. |
| R5 | **RabbitMQ dual-consumer contention** | Missing documents in one collection | Medium | Both indexers on same queue means each message goes to ONE consumer (competing consumers pattern). **Must use separate queues or topic exchange.** See Open Question OQ-1. |
| R6 | **Model download on first container start** | Long startup, timeout in health check | Low | `start_period: 120s` in health check. Pre-pull model in Docker build (add to Dockerfile `RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-base'"`). |
| R7 | **Memory budget exceeded** | OOM kills, service instability | Medium | Current services ~6GB. A/B adds ~3.5GB (embeddings 3GB + indexer 0.5GB). Total ~9.5GB. Document minimum host RAM requirement (12GB recommended). |
| R8 | **Query prefix mismatch** | Silent relevance degradation | High | E5 models REQUIRE `"query: "` prefix for queries. If solr-search forgets the prefix, results will be poor but no error is raised. **Must test prefix application explicitly** (Lambert: add to P2-4 test plan). |

---

## 9. Open Questions

| # | Question | Owner | Status |
|---|----------|-------|--------|
| OQ-1 | **RabbitMQ queue topology:** Competing consumers pattern means only ONE indexer gets each message. Need either (a) separate queues with message fanout (topic exchange), or (b) publish each message twice, or (c) index sequentially (first baseline, then e5). Ash/Brett to decide. | Ash + Brett | **BLOCKING P1-3/P1-4** |
| OQ-2 | **Final CHUNK_SIZE for e5-base:** Recommend 300/50 based on proportional scaling from PO's 90/10 decision. PO to confirm or override. | Juanma | Open |
| OQ-3 | **Compose overlay vs inline:** Should A/B services go in `docker-compose.ab-test.yml` (cleaner) or inline in `docker-compose.yml` (simpler)? Brett to recommend. | Brett | Open |
| OQ-4 | **Model pre-download in Docker build:** Should the Dockerfile download the model at build time (~1.1GB added to image) or at runtime (slower first start)? Trade-off: image size vs cold-start time. | Brett | Open |
| OQ-5 | **Frontend comparison UI:** Is a minimal UI toggle needed (Dallas, ~3 pts), or is the API/CLI approach from P2-3 sufficient? | Juanma | Open |
| OQ-6 | **Hierarchical chunking (future):** The 512-token window enables parent/child chunk strategies. Should this be explored in this A/B test or deferred to a separate experiment? | Ash + Juanma | Deferred |

---

## 10. Success Criteria Summary

**From the research report (Section 4.4), endorsed by Ripley:**

| Metric | Proceed | Abort |
|--------|---------|-------|
| nDCG@10 improvement | ≥ 5% (p < 0.05) | < 3% |
| Query latency (p95) | ≤ +50ms | > +100ms |
| Index size | ≤ 2× baseline | > 3× baseline |
| Indexing throughput | ≥ 80% of baseline | N/A (tolerable) |

**Decision authority:** Juanma (PO), informed by metrics from P2-4 and relevance evaluation from P3-1.

---

## 11. Glossary

| Term | Definition |
|------|-----------|
| **distiluse** | `sentence-transformers/distiluse-base-multilingual-cased-v2` — current embedding model |
| **e5-base** | `intfloat/multilingual-e5-base` — candidate replacement model |
| **kNN** | k-Nearest Neighbors — vector similarity search algorithm |
| **HNSW** | Hierarchical Navigable Small World — approximate nearest neighbor index structure used by Solr |
| **nDCG@10** | Normalized Discounted Cumulative Gain at rank 10 — standard relevance metric |
| **MRR** | Mean Reciprocal Rank — measures how high the first relevant result appears |
| **MTEB** | Massive Text Embedding Benchmark — standard evaluation suite for embedding models |
| **RRF** | Reciprocal Rank Fusion — Aithena's method for merging keyword and semantic results |

---

**END OF PRD**
