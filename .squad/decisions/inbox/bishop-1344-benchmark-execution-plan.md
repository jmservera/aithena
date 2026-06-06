# Decision: Scalar Quantization (int8) Benchmark Execution Plan #1344

**Author:** Bishop (Vector Search & Data Science Specialist)
**Date:** 2026-06-05
**Status:** Proposed
**Blocked on:** #1670 (Solr 10 `bits="7"` schema fix)
**Related:** #1344, #1669, #1671

## Summary

This document specifies the precise benchmark execution plan for validating scalar quantization (int8) vector reduction, including data sizes, recall thresholds, memory metrics, and pass/fail criteria. The plan is ready to execute post-#1670 merge without code changes; it requires only Docker and shell commands.

## Prerequisites

1. **Schema:** Target runtime must contain Solr 10 `ScalarQuantizedDenseVectorField bits="7"` (from #1670) or bits="4" equivalent for int8 quantization. Solr 9 compatibility rewrite to `DenseVectorField vectorEncoding="BYTE"` must remain functional.
2. **Tooling:** 
   - `python3` with `requests`, `numpy` available
   - `docker compose` and `docker stats`
   - `jq` for JSON parsing (optional, for manual inspection)
3. **Branch state:** #1671 merged (benchmark comparator); #1670 merged (schema fix)

## Benchmark Corpus

**Requirement:** Same representative corpus indexed twice (once per quantization mode), approximately:
- **Corpus size:** 1,000–2,000 representative documents (~5–10 MB text content total)
- **Target:** Mix of multilingual content (Spanish, Catalan, French, English) to reflect production diversity
- **Indexing time:** ~2–5 minutes per mode (float32 then int8) on modern hardware

**Rationale:** Corpus must be large enough to stress vector memory (~750 MB for 1M vectors in float32, ~187 MB in int8) but small enough to complete benchmark in reasonable time. 30-query suite (from `scripts/benchmark/queries.json`) ensures consistent measurement across runs.

## Validation Workflow

### Phase 1: Float32 Reference Benchmark (Baseline)

**Goal:** Capture float32 performance as ground truth for recall comparison.

**Commands:**
```bash
# 1. Spin up services with float32 (default/no quantization)
VECTOR_QUANTIZATION=none docker compose up -d --build

# 2. Wait for Solr to be ready (typically 15–30s after compose up)
curl -s http://localhost:8983/solr/books/select?q=*:* | jq '.response.numFound' | head -1

# 3. Index the corpus (idempotent; safe to rerun)
python3 scripts/index_test_corpus.py

# 4. Verify collection health
python3 scripts/verify_collections.py --verbose

# 5. Run benchmark suite (semantic + hybrid modes, no keyword—not affected by quantization)
python3 scripts/benchmark/run_benchmark.py \
  --base-url http://localhost:8080 \
  --modes semantic hybrid \
  --output results/benchmark-1344-float32.json

# 6. Capture Solr memory footprint (solr and solr2, solr3 if in a cluster)
docker stats --no-stream solr solr2 solr3 > results/memory-1344-float32.txt 2>&1 || echo "Single-node or unavailable"
```

**Expected output:**
- `results/benchmark-1344-float32.json` with `"modes_tested": ["semantic", "hybrid"]`
- `results/memory-1344-float32.txt` showing MEM/LIMIT for each container
- **Pass criterion:** All 30 queries complete (0 errors); no query latency > 5s

### Phase 2: int8/Scalar Quantization Candidate Benchmark

**Goal:** Measure recall@10 and latency delta under int8 constraints; compare to float32.

**Commands:**
```bash
# 1. Re-spin with int8 quantization enabled
VECTOR_QUANTIZATION=int8 docker compose up -d --build

# 2. Wait for Solr (same as before)
curl -s http://localhost:8983/solr/books/select?q=*:* | jq '.response.numFound' | head -1

# 3. Re-index the SAME corpus (idempotent; indexer routes to embedding_byte_v)
python3 scripts/index_test_corpus.py

# 4. Verify collection health with int8 vectors
python3 scripts/verify_collections.py --verbose

# 5. Run the same benchmark suite (no reordering of queries; must match corpus)
python3 scripts/benchmark/run_benchmark.py \
  --base-url http://localhost:8080 \
  --modes semantic hybrid \
  --output results/benchmark-1344-int8.json

# 6. Capture memory footprint (int8 vectors should consume ~4× less memory)
docker stats --no-stream solr solr2 solr3 > results/memory-1344-int8.txt 2>&1 || echo "Single-node or unavailable"
```

**Expected output:**
- `results/benchmark-1344-int8.json` with same structure
- `results/memory-1344-int8.txt` showing reduced LIMIT/MEM
- **Pass criterion:** All 30 queries complete (0 errors); median latency delta < ±10% (int8 slightly slower is acceptable)

### Phase 3: Offline Comparison & Analysis

**Goal:** Compare recall@10 and latency; generate pass/fail report.

**Commands:**
```bash
# 1. Run the offline comparator (no Solr/Docker required)
python3 scripts/benchmark/compare_quantization.py \
  --baseline results/benchmark-1344-float32.json \
  --candidate results/benchmark-1344-int8.json \
  --top-k 10 \
  --min-recall 0.95 \
  --output results/benchmark-1344-quantization-comparison.json

# 2. Inspect results
jq '.' results/benchmark-1344-quantization-comparison.json | head -100

# 3. Check failure summary (if any)
jq '.failures' results/benchmark-1344-quantization-comparison.json
```

**Expected output:**
- `results/benchmark-1344-quantization-comparison.json` JSON report with per-query recall and latency metrics
- Summary section showing:
  - Overall recall@10 (target: ≥0.95, i.e., ≥95% of top-10 documents match)
  - Median latency delta (acceptable: -5% to +10%)
  - Per-mode and per-category breakdown

## Pass/Fail Criteria

### Release Blocker (MUST PASS)
1. **Recall@10:** Semantic and hybrid modes must maintain **≥0.95 (95%)** recall across all 30 queries
   - Individual query failures below 0.95 trigger manual review; not auto-fail
   - **If any query < 0.85 recall:** blocker; escalate to Ripley and Ash
2. **Errors:** 0 index or search errors during Phase 1 and Phase 2
3. **Memory:** int8 collection must use ≤50% of float32 memory (target: 4× reduction = 25% of float32 baseline)

### Warning (SHOULD PASS)
1. **Latency:** int8 queries may be up to +10% slower than float32 (due to byte unpacking); flag if > +15%
2. **Corpus coverage:** Ensure indexed document count matches between Phase 1 and Phase 2

### Manual Review (If Failures Occur)
- Query ID + mode failing recall: capture top-10 document IDs from both runs and compare semantic relevance
- Latency anomalies: re-run with larger corpus if single-corpus variance > 20%
- Memory underestimate: if int8 > 50% of float32, audit Solr config for cache/buffer misconfiguration

## Data Sizes & Thresholds

| Metric | Float32 | int8 | Target Ratio |
|--------|---------|------|--------------|
| Bytes per vector | 4 bytes × 768 dims = 3,072 B | 1 byte × 768 dims = 768 B | 1:4 |
| ~1M vectors memory | ~3 GB (+ Solr overhead) | ~750 MB (+ overhead) | 1:4× |
| Corpus size | ~1K–2K docs | Same as float32 | n/a |
| Query suite | 30 queries (10 per category) | Same 30 queries | n/a |
| Recall threshold | 1.0 (reference) | ≥0.95 | 95% agreement |
| Latency delta | 0 ms (reference) | ±5–10% | tolerance |

## Deliverables

After benchmark completion, attach to #1344:
1. **Float32 report:** `results/benchmark-1344-float32.json` (full benchmark data)
2. **int8 report:** `results/benchmark-1344-int8.json` (full benchmark data)
3. **Comparison report:** `results/benchmark-1344-quantization-comparison.json` (recall@10, latency delta, summary)
4. **Memory logs:** 
   - `results/memory-1344-float32.txt` (Solr stats: `docker stats --no-stream`)
   - `results/memory-1344-int8.txt` (Solr stats: same command, int8 run)
5. **Corpus metadata:**
   - Document count (from `verify_collections.py --verbose`)
   - Total text size (approximate; from indexing logs)
   - Any query failures and root cause analysis

## Blocker Resolution

### Current State
- #1670 is **held by directive** (not merged)
- Current schema has `bits="8"` (incompatible with Solr 10; will fail at runtime on Solr 10)
- **Action:** Await Ripley directive or #1670 approval; this plan assumes #1670 is merged

### Post-#1670 Merge
- Schema will have `bits="7"` for Solr 10, Solr 9 compat rewrite to `DenseVectorField vectorEncoding="BYTE"`
- This plan is executable with no further code changes
- Only requirement: updated Docker compose and schema files from #1670

## Notes

- **Idempotency:** `index_test_corpus.py` deduplicates by Solr unique key; safe to re-run
- **No hardcoding:** Corpus path, Solr URL, and query file are configurable in benchmark scripts
- **Offline comparison:** `compare_quantization.py` requires no Solr/Docker; suitable for CI pipelines
- **Parallel runs not supported:** Each phase uses the same Solr collection; must be sequential
- **Memory measurement:** `docker stats` captures live memory; run after indexing stabilizes (~1 min)

## Acceptance

This plan is approved by Bishop as a complete, self-contained validation strategy for #1344 scalar quantization, subject to #1670 schema fix merging.

---

**Next steps for squad:**
1. Merge #1670 (or equivalent `bits="7"` fix)
2. Execute Phases 1–3 per this plan
3. Attach reports to #1344 for release validation
