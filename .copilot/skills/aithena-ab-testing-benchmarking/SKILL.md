---
name: "aithena-ab-testing-benchmarking"
description: "A/B testing framework for embedding models in Aithena using dual Solr collections, query benchmarking, and result comparison"
domain: "search, embeddings, evaluation, benchmarking"
confidence: "high"
source: "earned — E5-base model research and dual-collection A/B testing implementation (Phase 1-2, issues #873-#879)"
author: "Ash"
created: "2026-07-21"
last_validated: "2026-07-21"
---

## Context

Apply this skill when:
- Evaluating alternative embedding models for semantic search
- Setting up parallel Solr collections for A/B testing
- Creating benchmark query suites and comparison metrics
- Implementing result ranking and overlap analysis

This skill consolidates the dual-collection architecture with benchmarking tooling for comparing model quality, latency, and index size.

## Patterns

### 1. Dual-Collection Architecture

**Setup:**
- Base collection: `{name}` (e.g., `books`) with legacy/current model (512D)
- Test collection: `{name}_{tag}` (e.g., `books_e5base`) with alternative model (768D)
- Two separate configsets with shared non-vector config (analyzers, stopwords, synonyms, langid chains)
- Two embeddings-server instances (different `MODEL_NAME`, different ports) or environment-switched single instance

**Configset sharing strategy:**
- Copy base configset to new configset directory
- Modify ONLY the vector field type definitions (`knn_vector_512` → `knn_vector_768`)
- Keep all other config identical: analyzers (ICU, multilingual), stopwords, synonyms, copyFields, update chains
- This ensures query behavior parity except for embedding dimensions

**Schema field requirements:**
- Vector fields: `embedding_v` (chunk-level), `book_embedding` (parent-level)
- Both must exist in both configsets but with different dimensions per model
- All metadata fields (`title_s`, `author_s`, etc.) identical across collections
- Parent/chunk document structure identical

**Solr init script pattern:**
```bash
# Inside solr-init container
if ! solr zk ls /configs -z $ZK_HOST | grep -q "^$SOLR_COLLECTION$"; then
  solr create_collection -c $SOLR_COLLECTION -d $SOLR_COLLECTION
fi
```
This is idempotent — the `grep -q` check prevents duplicate creates on container restart.

**Collection creation order:**
- Create base collection first
- Create test collection with same topology (numShards, replicationFactor)

### 2. Query Benchmarking Suite

**Query set design (30-50 queries across categories):**
- **Keyword**: 5-10 simple BM25-friendly queries (e.g., "Spanish books", "author:Hemingway")
- **Natural language**: 5-10 conversational queries (e.g., "What books about medieval history?")
- **Multilingual**: 5-10 queries in ES/FR/CA/EN (tests language-specific embeddings)
- **Long/complex**: 5-10 multi-clause queries (e.g., "books by female authors from 19th century about nature")
- **Edge cases**: 5-10 boundary conditions (e.g., empty string, special characters, single words)

**Query metadata:**
```json
{
  "queries": [
    {
      "id": "kw1",
      "category": "keyword",
      "query_text": "Spanish books",
      "expected_model_advantage": "semantic",
      "notes": "Tests basic multilingual retrieval"
    }
  ]
}
```

**Execution pattern:**
1. Load query set from JSON
2. For each query, call solr-search API twice:
   - Once with `collection=base`
   - Once with `collection=base_tag`
3. Collect: top-K results, scores, response latency, API errors
4. Compute: Jaccard similarity (set overlap), rank correlation, latency delta

**API contract (solr-search):**
- `?q=<text>&collection=<name>&mode=<semantic|keyword|hybrid>&limit=20`
- E5 collections automatically get `input_type=query` injection (handled by `is_e5_collection()` check in API)
- Returns: `results[{id, title, author, score}]`, `latency_ms`, `collection`

### 3. Result Comparison Metrics

**Jaccard Similarity (set overlap at top-K):**
```
Jaccard(A, B) = |A ∩ B| / |A ∪ B|
```
- 1.0 = identical top-K
- 0.5 = 50% overlap
- 0.0 = completely different
- Interpretation: Low Jaccard (<0.3) queries are the most interesting for human review — they show where models disagree most

**Rank Correlation (NDCG, MRR alternative):**
- Not required for Aithena (human evaluation is sufficient)
- Optional: compute Spearman correlation of score rankings between collections

**Latency percentiles:**
- Measure p50, p95, p99 query latency per collection
- Success threshold: ≤50ms increase at p95 for production worthiness

**Index size comparison:**
```bash
# Query Solr stats API
curl 'http://solr:8983/solr/books/admin/luke?wt=json&numTerms=0' | jq '.index.sizeInBytes'
curl 'http://solr:8983/solr/books_e5base/admin/luke?wt=json&numTerms=0' | jq '.index.sizeInBytes'
```
- Success threshold: ≤2× baseline for production worthiness

### 4. A/B Test Success Criteria (Aithena baseline)

**Quality improvement:**
- Relevance: ≥5% nDCG@10 at p < 0.05 (statistical significance)
- Human evaluation: minimum 3 relevance judges, κ > 0.6 inter-rater agreement

**Performance constraints:**
- Query latency: ≤50ms p95 increase (UX requirement)
- Indexing throughput: ≥80% baseline rate
- Index size: ≤2× baseline (disk capacity constraint)

**Go/no-go decision:**
- All three constraints must be satisfied
- Quality gain must be statistically significant, not anecdotal

### 5. Document Indexing for A/B Test Corpus

**Fanout exchange pattern:**
- RabbitMQ `documents` exchange with two binding queues (one per indexer)
- Single publish to `documents` reaches both indexer pipelines
- Both indexers process same document paths, compute embeddings independently
- Idempotency: Solr unique key dedup (both collections have same parent `id` = SHA-256 of path)

**Verification pattern:**
```bash
# Verify both collections received same parent docs
python scripts/verify_collections.py --mode=count
# Expected: parent count identical, embedding dimensionality different (512D vs 768D)
```

**Script design principles:**
- Lazy dependency imports must be top-level for mockability (not inside functions)
- Always use `-parent_id_s:[* TO *]` to filter parents (chunks have `parent_id_s` field)
- Dry-run mode for planning (`--dry-run` flag)
- JSON output for CI/CD integration

### 6. Model-Specific Integration (E5-Base Example)

**E5 model requirements:**
- Requires prefix: `"query: "` for query embedding, `"passage: "` for document embedding
- 768-dimension vectors (2.2× larger than 512D)
- 512-token context window → ~400 words/chunk recommended
- MTEB score: 61.5 (competitive with SOTA)

**E5 integration in embeddings-server:**
- Model family detection: substring match (`"e5" in model_name.lower()`)
- Prefix application: internal to server, transparent via `input_type` parameter
- API response includes `model_family` and `requires_prefix` metadata
- Caller pattern: pass `input_type="query"` or `"passage"`, server applies prefix automatically

**Solr-search API E5 handling:**
```python
def is_e5_collection(collection_name: str) -> bool:
    return "e5" in collection_name.lower()

# Inside search handler
input_type = "query" if is_e5_collection(collection) else "passage"
# API calls embeddings-server with input_type parameter
```

## Anti-Patterns

- **Don't evaluate only one model** — always maintain a known-good baseline for comparison
- **Don't rely on automated metrics alone** — human evaluation catches relevance nuances that Jaccard/MRR miss
- **Don't assume test collection indexes faster** — measure actual throughput; higher dimensions may increase time
- **Don't share collection data volumes in Docker** — each collection needs its own replica storage
- **Don't skip verification of collection parity** — embedding dimensionality differences must be intentional, not accidental
- **Don't hard-code model-specific logic in callers** — keep prefixing, dimension handling internal to embeddings-server
- **Don't evaluate on production traffic only** — benchmark suite ensures reproducible, controlled queries

## Examples

### Example: Set up dual collections for e5-base A/B test
```bash
# 1. Copy configset
cp -r src/solr/books src/solr/books_e5base

# 2. Edit schema in books_e5base
# Replace <fieldType name="knn_vector_512"> with <fieldType name="knn_vector_768">
# Update <field name="embedding_v" type="knn_vector_768" />
# Update <field name="book_embedding" type="knn_vector_768" />

# 3. Start dual embeddings servers
# Server 1: MODEL_NAME=distiluse-base-multilingual-cased-v2:8001
# Server 2: MODEL_NAME=intfloat/multilingual-e5-base:8002

# 4. Collections auto-created by solr-init
docker compose up solr-init
```

### Example: Run benchmark suite
```bash
python scripts/benchmark/run_benchmark.py \
  --collection1 books \
  --collection2 books_e5base \
  --queries scripts/benchmark/queries.json \
  --output results/benchmark-e5-vs-distiluse.json

# Output includes:
# - Per-query results: jaccard, latency delta, model advantage
# - Aggregated metrics: avg latency, index size, p95 latency
# - Low-overlap queries (<0.3 jaccard) flagged for manual review
```

### Example: Verify test corpus indexed correctly
```bash
python scripts/verify_collections.py \
  --solr-url http://localhost:8983 \
  --collection1 books \
  --collection2 books_e5base \
  --mode parity

# Output: "✓ 10242 parent docs in books, 10242 in books_e5base"
#         "✓ 512D embeddings in books, 768D in books_e5base"
#         "✓ All parent IDs present in both collections"
```

## References

- `src/solr/` — Dual configsets (`books/` and `books_e5base/`)
- `src/solr-search/main.py` — `is_e5_collection()` integration, collection parameter handling
- `src/embeddings-server/model_utils.py` — `detect_model_family()`, `apply_prefix()`
- `scripts/benchmark/queries.json` — Query suite definition
- `scripts/benchmark/run_benchmark.py` — Benchmark runner
- `scripts/verify_collections.py` — Collection parity verification
- `docs/research/embedding-model-research.md` — E5-base selection rationale
- `.squad/skills/embedding-model-selection/SKILL.md` — Model evaluation methodology
- `.squad/skills/solr-parent-chunk-model/SKILL.md` — Data model correctness patterns
