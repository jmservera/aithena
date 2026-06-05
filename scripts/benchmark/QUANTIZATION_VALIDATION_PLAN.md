# Scalar Quantization Validation Plan for #1344

**Document:** Comprehensive validation checklist for int8 scalar quantization (post-#1670)
**Version:** 1.0
**Created:** 2026-06-05
**By:** Bishop (Vector Search & Data Science Specialist)

## Overview

This document extends the benchmark plan in the squad decisions inbox with practical checklists, environment validation, and troubleshooting guidance for the scalar quantization (int8) validation workflow.

## Pre-Benchmark Checklist

### Environment Verification

- [ ] **Docker availability:** `docker --version` and `docker compose --version` work
- [ ] **Python environment:** `python3 --version` (3.10+) and `python3 -m pip list | grep requests numpy`
- [ ] **Solr containers ready:** No prior `docker compose up` state; clean start for repeatable benchmarks
- [ ] **Disk space:** ~20 GB free (for float32 collection, int8 collection, results, logs)
- [ ] **Network:** localhost:8983 (Solr) and localhost:8080 (solr-search API) not in use
- [ ] **Git state:** On a branch post-#1670 (schema has `bits="7"` or `bits="4"` for Solr 10)

### Corpus Availability

- [ ] **Test corpus location:** Verify `BASE_PATH` environment variable or default location
  - Default: `~/booklibrary` or configured in `.env`
  - Minimum: 1,000 documents; recommended: 1,000–2,000
  - Check: `python3 scripts/index_test_corpus.py --status-only` to preview

### Benchmark Suite

- [ ] **Query suite present:** `scripts/benchmark/queries.json` exists (30 queries across 5 categories)
  - Categories: simple_keyword (5), natural_language (6), multilingual (6), long_complex (4), edge_cases (9)
  - Check: `jq '.queries | length' scripts/benchmark/queries.json`

### Solr Schema

- [ ] **Schema updated for Solr 10 int8:**
  - Check: `grep 'ScalarQuantizedDenseVectorField' src/solr/books/managed-schema.xml | grep 'bits="7"'`
  - For Solr 9: `grep 'DenseVectorField vectorEncoding="BYTE"' src/solr/books/managed-schema.xml`
  - If neither found: **BLOCKER** — #1670 not applied; schema validation failed

### Comparison Tool

- [ ] **Comparator script present:** `scripts/benchmark/compare_quantization.py` exists and is executable
  - Check: `python3 scripts/benchmark/compare_quantization.py --help` (should show usage)

---

## Phase 1: Float32 Baseline Execution

### Setup

```bash
# Terminal 1: Start services
export VECTOR_QUANTIZATION=none
docker compose down -v  # Clean state
docker compose up -d --build

# Wait for Solr readiness (check health endpoint)
for i in {1..30}; do
  curl -s http://localhost:8983/solr/books/select?q=*:* | jq '.response.numFound' && break
  sleep 2
done
```

- [ ] Solr accessible at `http://localhost:8983`
- [ ] solr-search API accessible at `http://localhost:8080/search`
- [ ] No error logs in `docker compose logs solr | tail -20`

### Indexing & Verification

```bash
# Terminal 1: Index corpus
python3 scripts/index_test_corpus.py

# Monitor progress (in another terminal, optional)
watch -n 5 'curl -s http://localhost:8983/solr/books/select?q=*:* | jq ".response.numFound"'

# Wait for indexing to complete (check logs)
docker compose logs document-indexer | tail -20
```

- [ ] No RabbitMQ publishing errors
- [ ] document-indexer completes (look for "Done" or "Processed X documents")
- [ ] Final document count matches expected (e.g., 2,000 docs for a 2K corpus)

```bash
# Verify collection integrity
python3 scripts/verify_collections.py --verbose
```

- [ ] Parent documents present (count > 0)
- [ ] Chunk documents present (count > 0)
- [ ] Embedding dimensionality: **768 (e5-base)**
- [ ] No degraded or missing embeddings
- [ ] Exit code: 0

### Benchmark Run

```bash
# Create results directory
mkdir -p results

# Run benchmark (semantic + hybrid modes only; keyword unaffected by quantization)
python3 scripts/benchmark/run_benchmark.py \
  --base-url http://localhost:8080 \
  --modes semantic hybrid \
  --output results/benchmark-1344-float32.json

# Check for completion
echo "Exit code: $?"
```

- [ ] Benchmark completes without hanging (typically 2–5 min for 30 queries)
- [ ] Exit code: 0
- [ ] Output file exists: `results/benchmark-1344-float32.json`
- [ ] File is valid JSON: `jq '.' results/benchmark-1344-float32.json | head -5`

```bash
# Verify results structure
jq '.summary.semantic | keys' results/benchmark-1344-float32.json
jq '.summary.hybrid | keys' results/benchmark-1344-float32.json
jq '.results | length' results/benchmark-1344-float32.json  # Should be 60 (30 queries × 2 modes)
jq '[.results[] | select(.error != null)] | length' results/benchmark-1344-float32.json  # Should be 0
```

- [ ] Semantic mode summary has: `mean_latency_ms`, `median_latency_ms`, `p95_latency_ms`, `mean_results_count`
- [ ] Hybrid mode summary has same fields
- [ ] 60 total results (30 queries × 2 modes)
- [ ] 0 errors

### Memory Snapshot

```bash
# Capture memory at steady state (after indexing, before shutdown)
docker stats --no-stream solr solr2 solr3 > results/memory-1344-float32.txt 2>&1 || true
cat results/memory-1344-float32.txt
```

- [ ] File exists and contains `CONTAINER`, `MEM USAGE`, `LIMIT` columns
- [ ] Solr memory (e.g., "3.2 GB / 4.0 GB" for ~1M vectors in float32)
- [ ] Record this value for comparison

### Cleanup for Phase 2

```bash
# Stop services (do NOT delete volumes yet, for reference)
docker compose down
```

- [ ] Containers stopped
- [ ] Volumes persist (for manual inspection if needed)

---

## Phase 2: int8 Candidate Execution

### Setup (Same as Phase 1, Different Environment)

```bash
# Terminal 1: Start services with int8 quantization
export VECTOR_QUANTIZATION=int8
docker compose down -v  # Clean state (important: clear old volumes for fresh indexing)
docker compose up -d --build

# Wait for Solr readiness
for i in {1..30}; do
  curl -s http://localhost:8983/solr/books/select?q=*:* | jq '.response.numFound' && break
  sleep 2
done
```

- [ ] Solr accessible at `http://localhost:8983`
- [ ] solr-search API accessible at `http://localhost:8080/search`
- [ ] Schema has int8 quantization field type (`ScalarQuantizedDenseVectorField bits="7"` or equivalent)

### Indexing & Verification

```bash
# Index the SAME corpus (idempotent; indexer routes to embedding_byte_v)
python3 scripts/index_test_corpus.py

# Verify collection with int8 vectors
python3 scripts/verify_collections.py --verbose
```

- [ ] Document count matches Phase 1 (same corpus)
- [ ] Embedding field type is now `knn_vector_768_byte` (or similar int8 field)
- [ ] No indexing errors
- [ ] Exit code: 0

### Benchmark Run

```bash
# Run the SAME benchmark queries (order must match Phase 1)
python3 scripts/benchmark/run_benchmark.py \
  --base-url http://localhost:8080 \
  --modes semantic hybrid \
  --output results/benchmark-1344-int8.json

# Verify completion
echo "Exit code: $?"
```

- [ ] Benchmark completes without hanging
- [ ] Exit code: 0
- [ ] Output file exists: `results/benchmark-1344-int8.json`
- [ ] File is valid JSON: `jq '.' results/benchmark-1344-int8.json | head -5`

```bash
# Verify results structure matches Phase 1
jq '.results | length' results/benchmark-1344-int8.json  # Should be 60
jq '[.results[] | select(.error != null)] | length' results/benchmark-1344-int8.json  # Should be 0
```

- [ ] 60 total results
- [ ] 0 errors
- [ ] Query IDs match Phase 1 (spot-check: `jq '.results[0].query_id' results/benchmark-1344-{float32,int8}.json`)

### Memory Snapshot

```bash
# Capture int8 memory (should be ~4× less than float32)
docker stats --no-stream solr solr2 solr3 > results/memory-1344-int8.txt 2>&1 || true
cat results/memory-1344-int8.txt
```

- [ ] File exists and contains memory stats
- [ ] int8 memory usage ≤50% of float32 (target: 25% for 4× reduction)
- [ ] Example: if float32 was 3.2 GB, int8 should be ≤800 MB

### Cleanup

```bash
docker compose down
```

- [ ] Containers stopped

---

## Phase 3: Offline Comparison

### Run Comparator

```bash
# Generate comparison report (no Docker/Solr required)
python3 scripts/benchmark/compare_quantization.py \
  --baseline results/benchmark-1344-float32.json \
  --candidate results/benchmark-1344-int8.json \
  --top-k 10 \
  --min-recall 0.95 \
  --output results/benchmark-1344-quantization-comparison.json

echo "Exit code: $?"
```

- [ ] Comparator completes
- [ ] Exit code: 0
- [ ] Output file exists: `results/benchmark-1344-quantization-comparison.json`

### Analyze Results

```bash
# View summary
jq '.summary' results/benchmark-1344-quantization-comparison.json

# Per-mode breakdown
jq '.modes' results/benchmark-1344-quantization-comparison.json

# Check for failures
jq '.failures | length' results/benchmark-1344-quantization-comparison.json
jq '.failures[] | {query_id, mode, recall_at_k}' results/benchmark-1344-quantization-comparison.json
```

- [ ] Summary shows `total_comparisons`, `mean_recall_at_k`, `median_recall_at_k`, `min_recall_at_k`
- [ ] **Mean recall ≥0.95** (PASS criterion)
- [ ] Semantic mode recall (baseline for accuracy-critical search)
- [ ] Hybrid mode recall (combined BM25 + vector rerank)

```bash
# Latency analysis
jq '.comparisons[] | {query_id, mode, latency_delta_pct}' results/benchmark-1344-quantization-comparison.json | head -20

# Median latency delta
jq '[.comparisons[].latency_delta_pct | select(. != null)] | (min, max, .[length/2 | floor])' results/benchmark-1344-quantization-comparison.json
```

- [ ] Latency delta: ≤+10% acceptable (int8 slightly slower OK)
- [ ] Flag if >+15%

---

## Pass/Fail Determination

### ✅ PASS Criteria (Release Ready)

```bash
# Check recall automatically
jq '.summary.mean_recall_at_k >= 0.95' results/benchmark-1344-quantization-comparison.json
```

- [ ] **Recall@10:** Mean ≥0.95 across all 30 queries
- [ ] **Per-mode:** Semantic and hybrid ≥0.95
- [ ] **Errors:** 0 index/search errors in Phase 1 and Phase 2
- [ ] **Memory:** int8 ≤50% of float32 (or ≥4× reduction)

### ⚠️ WARNING (Manual Review)

```bash
# Check latency anomalies
jq '.comparisons[] | select(.latency_delta_pct > 15 or .latency_delta_pct < -5)' results/benchmark-1344-quantization-comparison.json
```

- [ ] Latency delta >+15%: re-run with larger corpus or investigate query complexity
- [ ] Latency negative: int8 faster than float32 (possible hardware variance; acceptable)

### ❌ BLOCKER (Escalate)

```bash
# Check for recall failures
jq '.comparisons[] | select(.recall_at_k < 0.85)' results/benchmark-1344-quantization-comparison.json
```

- [ ] Any query < 0.85 recall: **Manual review required**
  - Capture query ID, query text, top-10 doc IDs from both runs
  - Assess semantic relevance manually (did int8 quantization hide relevant results?)
  - Escalate to Ripley and Ash

---

## Troubleshooting

### Solr Init Fails

**Symptom:** `curl http://localhost:8983/solr/books/select?q=*:*` returns 404

**Debug:**
```bash
docker compose logs solr | tail -50  # Check Solr startup
docker compose logs --follow solr
```

**Fixes:**
- Ensure `src/solr/books/managed-schema.xml` is correct (check #1670 changes)
- Confirm `docker-compose.yml` uses `solr10` image (not solr9)
- Clear volumes: `docker compose down -v && docker compose up -d --build`

### Indexing Hangs

**Symptom:** `index_test_corpus.py` runs but document count doesn't increase

**Debug:**
```bash
docker compose logs document-indexer | tail -50
docker compose logs rabbitmq | tail -50
curl -s http://localhost:8983/solr/books/select?q=*:* | jq '.response.numFound'  # Check manually
```

**Fixes:**
- RabbitMQ or document-indexer may not be running; check health
- Verify `VECTOR_QUANTIZATION` env var set correctly
- Check embeddings-server logs for model loading errors

### Benchmark API Returns 404

**Symptom:** `python3 scripts/benchmark/run_benchmark.py` fails with "Connection refused"

**Debug:**
```bash
curl -v http://localhost:8080/search?q=test  # Check solr-search API
docker compose logs solr-search | tail -20
```

**Fixes:**
- solr-search service may not be ready; wait 30s and retry
- Confirm `--base-url http://localhost:8080` is correct
- Check firewall (unlikely in local Docker)

### Recall < 0.95 (Concerning)

**Symptom:** Comparison report shows `mean_recall_at_k: 0.88`

**Root cause analysis:**
```bash
# Identify failing queries
jq '.comparisons[] | select(.recall_at_k < 0.95) | {query_id, query, mode, recall_at_k}' results/benchmark-1344-quantization-comparison.json

# Check if specific modes are problematic
jq '.comparisons | group_by(.mode) | map({mode: .[0].mode, mean_recall: (map(.recall_at_k | select(. != null)) | add / length)})' results/benchmark-1344-quantization-comparison.json
```

**Next steps:**
- If semantic mode <<hybrid mode: consider if vector quantization is appropriate for this embedding model
- If specific queries fail: re-index with `VECTOR_QUANTIZATION=none` and re-run just that query; compare top-10 IDs
- Escalate to Ripley/Ash if consensus is that int8 is unsuitable

### Memory Usage Not Reduced

**Symptom:** int8 memory ≈ float32 memory (no 4× reduction)

**Debug:**
```bash
docker stats --no-stream solr solr2 solr3
# Check embedded collection size
curl -s http://localhost:8983/solr/admin/collections?action=CLUSTERSTATUS | jq '.cluster.collections.books'
```

**Possible causes:**
- Solr cache/buffer not releasing (normal overhead ~300–500 MB)
- Query cache or facet cache still holding float32 vectors
- int8 field type not actually used; check if indexer wrote to wrong field

**Fix:**
- Ensure `embedding_byte_v` field is populated: `curl -s 'http://localhost:8983/solr/books/select?q=*:*&rows=1&fl=embedding_byte_v' | jq '.response.docs[0].embedding_byte_v | length'` (should be ~768 integers)

---

## Deliverables Checklist

Before attaching to #1344:

- [ ] `results/benchmark-1344-float32.json` (valid JSON, 60 results, 0 errors)
- [ ] `results/benchmark-1344-int8.json` (valid JSON, 60 results, 0 errors, matching query IDs)
- [ ] `results/benchmark-1344-quantization-comparison.json` (valid JSON, recall summary, latency delta)
- [ ] `results/memory-1344-float32.txt` (memory stats from Phase 1)
- [ ] `results/memory-1344-int8.txt` (memory stats from Phase 2)
- [ ] **Manual summary:** (text or Markdown)
  - Corpus size: X documents, Y MB text
  - Recall@10: mean X%, min Y% (semantic/hybrid breakdown)
  - Memory reduction: Z× (e.g., 3.2 GB → 800 MB = 4×)
  - Latency delta: median +X%, range [Y%, Z%]
  - Pass/fail decision with justification
  - Any failed queries and root cause

---

## References

- Bishop decision: `.squad/decisions/inbox/bishop-1344-benchmark-execution-plan.md`
- Benchmark README: `scripts/benchmark/README.md` (updated post-#1671)
- Comparator source: `scripts/benchmark/compare_quantization.py`
- Benchmark tests: `scripts/benchmark/tests/test_compare_quantization.py`
- Schema: `src/solr/books/managed-schema.xml` (post-#1670)

---

**Status:** Ready to execute post-#1670 merge | **Author:** Bishop | **Version:** 1.0
