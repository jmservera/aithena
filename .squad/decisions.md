# Decision: Issue Milestone Triage — 2026-06-06

**Date:** 2026-06-06T08:35:28Z  
**Author:** Newt (Product Manager)  
**Status:** Closed

## Context

All 14 open issues required milestone assignment. Two active milestones existed:
- **v2.5**: Post-release research and infrastructure work (longer cycle)
- **v2.5.1**: Active validation phase for v2.5 release (shorter cycle)

## Triage Criteria

1. **Test phases and validation** → v2.5.1: Test Phase 1, 2, 3; Performance benchmarks; Pre-release validation.
2. **Research, enhancement, and infrastructure** → v2.5: Vector quantization, GPU codecs, search improvements, admin migration, SolrCloud configuration, complexity reduction.

## Decisions

| Issue | Title | Milestone | Rationale |
|-------|-------|-----------|-----------|
| 1686 | Pre-release validation failed for pre-release | v2.5.1 | Release gate issue; active validation |
| 1452 | Reduce general complexity: Dockerfiles, scripts | v2.5 | Infrastructure enhancement; post-release |
| 1449 | Simplify GitHub Actions workflows | v2.5 | Infrastructure enhancement; post-release |
| 1357 | [v2.5] Test Phase 3 | v2.5.1 | Explicit test phase; active validation |
| 1356 | [v2.5] Test Phase 2 | v2.5.1 | Explicit test phase; already assigned |
| 1355 | [v2.5] Test Phase 1 | v2.5.1 | Explicit test phase; already assigned |
| 1354 | [v2.5] Performance benchmarks Solr 9.7 vs 10 | v2.5.1 | Validation evidence; already assigned |
| 1351 | [v2.5] Migrate admin/metrics to OpenTelemetry | v2.5 | Infrastructure enhancement |
| 1349 | [v2.5] Evaluate hybrid search improvements | v2.5 | Research track |
| 1348 | [v2.5] Prototype DocumentCategorizerUpdateProcessorFactory | v2.5 | Research track |
| 1347 | [v2.5] Add cuVS GPU codec | v2.5 | Vector quantization research |
| 1345 | [v2.5] Expose efSearchScaleFactor parameter | v2.5 | Search tuning research |
| 1344 | [v2.5] Add scalar quantization (int8) | v2.5.1 | Vector quantization; already assigned (performance gate) |
| 1343 | [v2.5] Configure SolrCloud with Overseer disabled | v2.5 | Infrastructure enhancement |

## Outcome

**All 14 open issues now have milestone assignments.** No issue remains unassigned.

**v2.5.1 focus:** 6 issues (test phases 1–3, pre-release validation, performance benchmarks, scalar quantization).  
**v2.5 focus:** 8 issues (research, infrastructure, enhancements).

## Notes

The v2.5.1 milestone now groups the active validation work needed before v2.5 release approval. The v2.5 milestone contains follow-up research and infrastructure initiatives that can proceed in parallel without blocking release validation.

Ripley should use this milestone structure to sequence implementation: v2.5.1 tests and validation gate the release; v2.5 research informs next-generation architecture decisions.

---

# Decision: OpenVINO release gates for base-image drift

**Author:** Brett (Infrastructure Architect)  
**Date:** 2026-06-05T17:02:51.834+00:00  
**Status:** Approved  
**Related:** #1662

## Decision

Keep Docker `uv sync --inexact` for the OpenVINO embeddings image, but treat it as
safe only when the built image proves the installed runtime packages satisfy the
OpenVINO extra constraints in `src/embeddings-server/pyproject.toml`.

The release gate now has two enforcement points:

1. The Docker build fails immediately after `uv sync --inexact` if installed
   `openvino`, `openvino-tokenizers`, or `optimum-intel` drift outside the
   configured constraints.
2. A PR/manual/weekly `OpenVINO Release Gate` workflow rebuilds the image with
   the latest base image and runs runtime smoke diagnostics.

## Rationale

The post-mortem for #1662 showed that lockfile validation in a clean environment
does not catch skew introduced by preserving base-image packages. Verifying inside
the built image checks the actual runtime that will be released while preserving
the build-time optimization.

## Coordination notes for Parker

Application/runtime tests can rely on `/v1/embeddings/model` for the expected
embedding dimension instead of hardcoding `768`. If Parker changes model-loading
behavior or OpenVINO dependencies, the Docker verifier and smoke script are the
infra-owned gates that should be updated with the new source-of-truth constraints.

---

# Decision: PathHierarchyTokenizer Audit — No-Op (v2.5)
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
# Scalar Quantization (int8) Evaluation Protocol — Issue #1344
**Bishop: Vector Search & Data Science Specialist**  
**Compiled**: 2026-06-06  
**Status**: Research complete; validation plan documented

---

## Executive Summary

**Scalar quantization (int8) implementation** is already in place:
- `src/embeddings-server/quantization.py` — Quantization functions (none/fp16/int8 modes)
- `src/embeddings-server/tests/test_quantization.py` — Unit tests with gatekeeping
- Solr schema integration (via PR #1670) — Schema support for `ScalarQuantizedDenseVectorField bits=7`

**Issue remains open** because:
1. PR #1670 (schema fix for Solr 10) is **still open with owner hold**
2. Without PR #1670, recall@10 and memory validation cannot run (tests are skipped)
3. No live benchmarking has been executed

**Blockers identified, resolution path clear.**

---

## Evaluation Protocol

### A. Corpus Requirements

**Collection**: `books` (e5-base 768D embeddings)

**Query Suite**: `scripts/benchmark/queries.json` (30 queries × 3 modes = 90 executions)
| Category | Count | Purpose |
|----------|-------|---------|
| simple_keyword | 5 | Basic catalog keyword searches |
| natural_language | 6 | Questions benefiting from semantic understanding |
| multilingual | 6 | Spanish, Catalan, French queries |
| long_complex | 4 | Long queries testing 512-token context window |
| edge_cases | 9 | Short queries, special chars, empty results |

**Modes tested**: keyword, semantic, hybrid

**Corpus size**: Flexible (100–1000 PDFs recommended for statistical significance; test corpus available)

**Ground truth**: Not required (validation is *relative* comparison, not absolute quality)

---

### B. Exact Execution Workflow

#### Step 1: Float32 Baseline Run

```bash
# Build with float32 quantization disabled
VECTOR_QUANTIZATION=none docker compose up -d --build

# Index corpus (idempotent, safe to re-run)
python3 scripts/index_test_corpus.py --status-only

# Verify collection health
python3 scripts/verify_collections.py --verbose

# Run benchmark: semantic + hybrid modes only (keyword is identical for both)
python3 scripts/benchmark/run_benchmark.py \
  --base-url http://localhost:8080 \
  --modes semantic hybrid \
  --output results/benchmark-1344-float32.json

# Capture memory footprint
docker stats --no-stream solr solr2 solr3 > results/docker-stats-float32.txt

# Record key metadata:
# - Corpus size (total PDFs indexed)
# - Embedding count (chunks created)
# - Index size on disk (du -sh /var/solr/data/books)
```

#### Step 2: Int8 Candidate Run (Same Corpus)

```bash
# Re-build with int8 quantization enabled
VECTOR_QUANTIZATION=int8 docker compose up -d --build

# Re-index identical corpus (idempotent via Solr deduplication)
python3 scripts/index_test_corpus.py --status-only

# Verify collection health (should match float32)
python3 scripts/verify_collections.py --verbose

# Run identical benchmark
python3 scripts/benchmark/run_benchmark.py \
  --base-url http://localhost:8080 \
  --modes semantic hybrid \
  --output results/benchmark-1344-int8.json

- Issue: #1662
- Failed run: 27022717607
- Successful fix: 27026253418 (commit a8a5cb5)
- Orchestration log: `.squad/orchestration-log/2026-06-05T16-26-openvino-postmortem.md`

# Decision: Narrow pre-release auth failure classification

**Author:** Brett (Infrastructure Architect)  
**Date:** 2026-06-06T09:36:46.687+00:00  
**Status:** Approved  
**Related:** #1686

## Context

Pre-release validation run 27053636169 reported a release-blocking `security` error for `document-indexer-1`. The underlying log line was a benign thumbnail warning for a corrupt fixture PDF under a `TestAuthor` path:

`TestAuthor ... Thumbnail generation failed ... Failed to open file`

The analyzer classified it as security because the shell glob `auth*fail` matched `Author` followed later by `failed`.

## Decision

Pre-release security classification should use phrase-level authentication failure patterns, not broad substring globs. The analyzer now matches explicit phrases such as `auth failed`, `auth failure`, `auth error`, `authentication failed`, `authorization failed`, and `authorization failure`.

## Rationale

This keeps real authentication and authorization failures release-blocking while preventing benign author names, filenames, or log fields from tripping the security gate. The fix is narrower than adding an allowlist for the corrupt PDF fixture because it addresses the classifier bug without hiding future file-open or thumbnail problems.

---

# Decision: Pre-release warning policy for Solr/RabbitMQ runtime noise

**Author:** Brett (Infrastructure Architect)  
**Date:** 2026-06-06T09:36:46.687+00:00  
**Status:** Approved  
**Related:** #1695, #1696

## Context

Pre-release validation run 27058984234 reported warnings for Solr/JVM deprecations, RabbitMQ `management_metrics_collection`, Solr `solr.log.dir`, and Solr `ZkCredentialsInjector`.

## Decision

Pre-release allowlist entries should stay narrow and preserve signal:

- Fix actionable first-party configuration deprecations in Compose/scripts instead of allowlisting them. The Solr 10 `solr.log.dir` warning is actionable; Aithena should use `solr.logs.dir`.
- Keep known upstream/runtime notices as `info` only when there is no safe first-party knob for the supported topology. Current examples are Solr/JVM `sun.misc.Unsafe` terminal deprecation notices and RabbitMQ 4.0-management `management_metrics_collection` startup notices.
- Keep the Solr `Using default ZkCredentialsInjector` message in the same accepted posture as `ZkCredentialsProvider/ZkACLProvider`: acceptable only while ZooKeeper remains internal-only and Solr HTTP BasicAuth/RBAC remains enforced.
- Do not use broad allowlist patterns such as `deprecation:*deprecated*`; unrelated deprecations must continue to surface as warnings.

## Rationale

Issue #1695 mixed one actionable Solr logging configuration warning with upstream Solr/JVM and RabbitMQ runtime deprecations. Issue #1696 used the newer Solr 10 `ZkCredentialsInjector` wording for the previously accepted ZooKeeper ACL posture. Narrow rules prevent recurring pre-release issues for known noise without hiding new deprecations, authentication failures, or production hardening gaps.

---

# Decision: DocumentCategorizer stays disabled until model fixture validation

**Author:** Ash (Search Engineer)  
**Date:** 2026-06-06  
**Status:** Approved  
**Related:** #1348

## Decision

Keep Solr 10 `DocumentCategorizerUpdateProcessorFactory` disabled by default. Repository changes may include output schema fields, documentation, tests, and a non-loaded config scaffold, but active `solrconfig.xml` wiring waits for a real ONNX/vocab fixture and measured validation.

## Rationale

The processor belongs to Solr's `analysis-extras` module and requires real model artifacts in SolrCloud FileStore. Enabling the processor without those artifacts risks core load/indexing failures. Bundling model binaries or claiming accuracy without a labeled corpus would violate the #1348 research constraints.

## Follow-up

Create a dedicated fixture task to select a small multilingual ONNX classifier, upload it at runtime, index labeled documents, and measure accuracy, latency, throughput, and JVM memory before replacing manual metadata or changing ranking.

# Capture memory footprint (should be ~4× smaller)
docker stats --no-stream solr solr2 solr3 > results/docker-stats-int8.txt

# Record index size (should be ~750MB vs 3GB for float32)
```

#### Step 3: Offline Comparison (No Docker Needed)

```bash
# Run comparison tool with strict thresholds
python3 scripts/benchmark/compare_quantization.py \
  --baseline results/benchmark-1344-float32.json \
  --candidate results/benchmark-1344-int8.json \
  --top-k 10 \
  --min-recall 0.95 \
  --output results/benchmark-1344-comparison.json

# Check exit code
echo "Exit: $?"  # 0 = PASS, 1 = FAIL
```

---

### C. Comparison Tool Reference

**Location**: `scripts/benchmark/compare_quantization.py` (308 lines, fully documented)

**Inputs**:
- `--baseline` — Float32 benchmark JSON report
- `--candidate` — Int8 benchmark JSON report  
- `--top-k` — Depth to compare (default: 10)
- `--min-recall` — Per-query recall threshold (default: 0.95)
- `--output` — Optional JSON output path

**Outputs**:
1. **Console**: Human-readable summary (PASS/FAIL, metrics table)
2. **JSON file**: Full comparison data with per-query breakdowns

**Key metrics computed**:

| Metric | Definition | Source Code |
|--------|-----------|-------------|
| `recall_at_k` | Overlap of top-k result IDs between runs | Line 80: `_recall_at_k()` |
| `overlap_count` | Number of matching document IDs in top-k | Line 84 |
| `latency_delta_pct` | Percent change: (int8_ms - float32_ms) / float32_ms × 100 | Line 77: `_latency_delta_pct()` |
| `queries_below_min_recall` | List of query IDs failing threshold | Line 156 |
| `passed` (summary) | True if all queries ≥ min_recall_threshold | Line 209 |

**JSON schema** (lines 237–244):
```python
{
  "baseline_report": "path/to/float32.json",
  "candidate_report": "path/to/int8.json",
  "top_k": 10,
  "summary": {
    "total_comparisons": 60,  # (30 queries × 2 modes)
    "min_recall_threshold": 0.95,
    "by_mode": {
      "semantic": {
        "query_count": 30,
        "mean_recall_at_k": 0.97,
        "min_recall_at_k": 0.95,
        "queries_below_min_recall": [],
        "mean_latency_delta_pct": -15.2,
        "candidate_error_count": 0,
        "baseline_error_count": 0
      },
      "hybrid": { ... }
    },
    "failures": [],  # Details of any threshold violations
    "passed": true
  },
  "comparisons": [
    {
      "query_id": "sk-001",
      "mode": "semantic",
      "baseline_ids": [...],
      "candidate_ids": [...],
      "recall_at_k": 1.0,
      "overlap_count": 10,
      "baseline_latency_ms": 45.2,
      "candidate_latency_ms": 38.5,
      "latency_delta_pct": -14.8
    },
    ...
  ]
}
```

---

### D. Success Thresholds

**Release-critical gates**:

| Metric | Threshold | Rationale | Priority |
|--------|-----------|-----------|----------|
| `recall@10` (semantic) | ≥ 0.95 per query | <5% doc reranking acceptable; int8 proven in literature | P0 |
| `recall@10` (hybrid) | ≥ 0.95 per query | Hybrid includes vector component, same tolerance | P0 |
| `mean_recall@10` | ≥ 0.95 per mode | No mode should average below threshold | P0 |
| Memory reduction | 3–4× | 768D float32 (4B/dim) → int8 (1B/dim) | P0 |
| Latency change | −50% to +10% | Int8 typically *faster* due to reduced I/O; +10% max | P1 |
| Index size | < 800MB (1M vectors) | Disk footprint matches memory estimate | P1 |

**Default minimum recall**: 0.95 (defined in line 20 of `compare_quantization.py`)

**Override rationale**: Any query below 0.95 is a release blocker until:
1. Cause is identified (outlier corpus property, model limitation, etc.)
2. Documented in issue with query ID + baseline/candidate top-10 lists
3. Approved by Ripley (Lead) for known exception

---

### E. Output Artifacts

**Deliverables to attach to issue #1344**:

1. **benchmark-1344-float32.json** — Full float32 benchmark report (90 query results)
2. **benchmark-1344-int8.json** — Full int8 benchmark report (identical queries)
3. **benchmark-1344-comparison.json** — Detailed comparison with all metrics
4. **docker-stats-float32.txt** — Memory snapshot (float32 run)
5. **docker-stats-int8.txt** — Memory snapshot (int8 run)
6. **Metadata summary**:
   - Corpus: `N PDFs → M chunks`
   - Index size (bytes): float32 vs int8
   - Mean latency (ms): per mode, both runs
   - Recall summary: mean/min per mode, count of failing queries
   - Solr version confirmed (10.0.0 after PR #1670 merges)

**Example metadata comment**:
```
Corpus: 500 PDFs → 2,847 chunks (e5-base)
Index Size:
  - Float32: 2.9 GB
  - Int8:    0.73 GB (4× reduction ✓)
Latency (mean, ms):
  - Semantic (float32): 62.1 | (int8): 48.3 (−22% ✓)
  - Hybrid (float32): 68.4 | (int8): 54.1 (−21% ✓)
Recall@10:
  - Semantic: mean=0.968, min=0.960 ✓
  - Hybrid: mean=0.972, min=0.950 ✓
Conclusion: PASS — all thresholds met.
```

---

### F. Closure Checklist

Before closing issue #1344:

- [ ] **PR #1670 merged** into `dev` (Solr 10 `bits=7` support)
  - Status: Currently open; owned by Ash; pending owner signal
  - Action: Refresh for conflicts, await merge signal
  
- [ ] **Corpus indexed** with `VECTOR_QUANTIZATION=none`
  - Command: `python3 scripts/index_test_corpus.py --status-only`
  - Verification: `python3 scripts/verify_collections.py --verbose`
  
- [ ] **Float32 benchmark** executed and saved
  - File: `results/benchmark-1344-float32.json`
  - Modes: semantic, hybrid (keyword identical, can skip)
  
- [ ] **Corpus re-indexed** with `VECTOR_QUANTIZATION=int8`
  - Same documents, same collection name `books`
  - Idempotent via Solr unique key
  
- [ ] **Int8 benchmark** executed and saved
  - File: `results/benchmark-1344-int8.json`
  - Identical query set and modes
  
- [ ] **Comparison executed** with `--min-recall 0.95`
  - Command: See **Step 3** above
  - Output: `results/benchmark-1344-comparison.json`
  - Exit code verified: `echo $?` should return **0**
  
- [ ] **Memory captured** from both runs
  - Files: `docker-stats-float32.txt`, `docker-stats-int8.txt`
  - Confirms 4× reduction in Solr memory footprint
  
- [ ] **Metadata documented**
  - Corpus size (PDFs, chunks, index bytes)
  - Recall summary (mean/min per mode, pass/fail)
  - Latency deltas (pct change per mode)
  
- [ ] **Artifacts attached** to issue
  - All 5 files above uploaded/linked
  - Metadata summary posted in comment
  
- [ ] **Failing queries analyzed** (if any)
  - List query IDs below 0.95 recall
  - Document why (if applicable)
  - Escalate to Ripley if release-blocking
  
- [ ] **Issue closed** with label ✓
  - Reference: "Closes #1344"

---

## Blockers & Dependencies

### Critical Blocker: PR #1670

**Status**: OPEN, owner hold: "Do not merge from this review session"

**Why it matters**:
- Solr 10 does not support `bits=8` for scalar quantization (signed-byte only)
- PR #1670 changes schema from `bits="8"` to `bits="7"`
- Without it: schema is misconfigured, int8 benchmarking is impossible

**Current state**:
- All CI passing ✓
- No unresolved review threads ✓
- `mergeable=CONFLICTING` (needs refresh against current `dev`)
- Owner hold explicitly stated

**Unblock path**:
1. Await owner signal (lift hold)
2. Refresh PR for conflicts (rebase on current `dev`)
3. Confirm Solr 10 schema uses `bits=7` correctly
4. Merge to `dev`

**Once merged**: Tests ungated, live validation can proceed

---

## How This Closes #1344

**Issue acceptance criteria** (from issue body):

- [x] Add `ScalarQuantizedDenseVectorField` field type to schema → PR #1670 (pending merge)
- [x] Configure `bits="7"` for int8 quantization → PR #1670
- [x] Maintain `vectorDimension="768"` and `similarityFunction="cosine"` → Verified in schema configs
- [x] Create migration path from `DenseVectorField` → Implemented in indexer
- [ ] **Benchmark accuracy (cosine similarity recall@10)** ← VALIDATION STEP (this doc)
- [ ] **Document memory savings: 3GB → ~750MB for 1M vectors** ← VALIDATION STEP (docker stats)
- [ ] **Make quantization configurable (option to disable)** → Already implemented (`VECTOR_QUANTIZATION` env var)

**Validation fulfills last two acceptance criteria**, enabling closure once executed.

---

## Timeline & Effort

| Phase | Effort | Duration | Blocker |
|-------|--------|----------|---------|
| Await PR #1670 merge | — | TBD (owner-dependent) | YES |
| Float32 run (baseline) | ~10–30 min | Build + index + benchmark | No |
| Int8 run (candidate) | ~10–30 min | Re-build + re-index + benchmark | No |
| Offline comparison | <1 min | Local computation only | No |
| Documentation + closure | ~15 min | Attach artifacts, verify pass/fail | No |

**Total post-PR-#1670**: ~45–90 minutes (mostly Docker I/O and indexing time).

---

## References

### Code

| File | Purpose | Key Lines |
|------|---------|-----------|
| `src/embeddings-server/quantization.py` | Quantization modes (none/fp16/int8) | 20–45 (quantize_embedding), 48–81 (validate_quantization_quality) |
| `src/embeddings-server/tests/test_quantization.py` | Unit tests with #1670 gatekeeping | pytest.skip markers for unsupported bits |
| `scripts/benchmark/run_benchmark.py` | Benchmark runner | 321–357 (run_benchmark loop) |
| `scripts/benchmark/compare_quantization.py` | Recall/latency comparison | 87–142 (compare_reports), 229–244 (output schema) |
| `scripts/benchmark/queries.json` | 30-query test suite | 30 queries × 3 modes = 90 executions |
| `scripts/benchmark/README.md` | Complete workflow documentation | Lines 124–172 (scalar quantization validation) |

### Related Issues & PRs

- **PR #1670**: Solr 10 scalar quantization schema fix (`bits="7"`) — BLOCKER
- **PR #1680**: Solr 10 default runtime (merged) — Prerequisite complete
- **PR #1683**: Runtime/security E2E validation (merged) — Prerequisite complete
- **Issue #926**: Model benchmark (e5-base vs distiluse) — Methodology reference

### Documentation

- **Solr scalar quantization**: https://solr.apache.org/guide/solr/latest/query-guide/dense-vector-search.html#scalar-quantization
- **Benchmark methodology**: `scripts/benchmark/README.md` (this repo)
- **Quantization literature**: Typical recall@10 degradation <5% (int8 vs float32)

---

## Next Steps

1. **Await PR #1670 merge** — Unblock all validation
2. **Execute validation workflow** — Steps A–C above
3. **Attach artifacts to #1344** — All 5 deliverables
4. **Confirm all thresholds met** — recall@10 ≥ 0.95, memory 4×, latency acceptable
5. **Close issue with label ✓**

---

**Prepared by**: Bishop (Vector Search & Data Science Specialist)  
**Validation plan**: Complete and executable upon PR #1670 merge
# Research Pass: #1452 Reduce General Complexity — Remaining Items Post-PR #1706

**Date:** 2026-06-06  
**Authored by:** Brett (Infrastructure Architect)  
**Status:** PLANNING (not implementation)  
**Related:** #1452, PR #1706

---

## Summary

PR #1706 completed the first step: **buildall.sh dynamic service discovery** — replaced hard-coded Python service list with filesystem-based detection (finds services with `pyproject.toml` + `Dockerfile`).

This research pass identifies **remaining 5 complexity areas** in #1452 and decomposes them into **small, safe, low-risk follow-up PRs** scoped for single owners across Brett/Parker/Dallas/Newt.

---

## Findings: Remaining Complexity Areas (Post PR #1706)

### 1. **Dockerfile Duplication** (4 Python Services, ~260 lines total)

**Current state:**
- `src/document-indexer/Dockerfile` (62 lines)
- `src/document-lister/Dockerfile` (59 lines)
- `src/solr-search/Dockerfile` (60 lines)
- `src/embeddings-server/Dockerfile` (79 lines, uniquely complex: custom base image, OpenVINO optional)

**Commonality:**
- All 4 follow multi-stage build pattern: builder stage → runtime stage
- All 4 use `python:3.*-*` base, `astral uv` package manager, Alpine or Debian-slim
- All 4 create non-root app user (uid 1000), set `PYTHONUNBUFFERED=1`, expose health check endpoints
- All 4 run `uv sync --frozen --no-dev --no-install-project --native-tls`

**Divergence:**
- **embeddings-server:** custom base image (`ghcr.io/jmservera/embeddings-server-base`), OpenVINO optional feature, cache/model dirs
- **solr-search:** depends on `src/aithena-common/` (monorepo pattern), complex entrypoint
- **document-indexer/lister:** simpler, fewer environment variables

**Complexity cost:**
- Drift risk: Changes to best practices (security, layer optimization) require manual updates across 4 files
- Maintenance tax: Each Dockerfile change requires validation on 4 builds

**Recommendation:**
- Extract reusable base stages OR parametrized template (low-complexity first step)
- Keep embeddings-server custom base separate (justified by OpenVINO complexity)
- Do NOT attempt generic "template Dockerfile" — Docker build arg machinery is fragile; inline duplication is acceptable here

---

### 2. **Shell Script Sprawl** (18 scripts in `/scripts/`, no CLI wrapper)

**Current state:**
- Backup variants: `backup.sh`, `backup-critical.sh`, `backup-high.sh`, `backup-medium.sh`, `backup-critical-test.sh` (5 scripts)
- Restore variants: `restore.sh`, `restore-critical.sh`, `restore-high.sh`, `restore-medium.sh` (4 scripts)
- Solr export/import: `solr-export.sh`, `solr-import.sh` (2 scripts)
- Verification: `verify-backup.sh` (1 script)
- Data/benchmarks: `index_test_corpus.py`, `verify_collections.py` (2 Python utilities)
- Operational: `cleanup-ghcr.sh`, `create-release-tag.sh`, `export-images.sh`, `init-volumes.sh` (4 scripts)

**Commonality:**
- All backup/restore variants share ~80% identical logic (Solr collection export/import, RabbitMQ queue drain/restore, Redis snapshot management)
- Parameterization is via shell script naming convention (e.g., `backup-critical.sh` vs `backup-medium.sh` select different collection types)

**Complexity cost:**
- Discoverability: New users cannot easily find "how do I backup Solr?" — 5 backup scripts with unclear naming
- Maintenance: A bug fix in `backup.sh` requires manual replication to `backup-critical.sh`, `backup-high.sh`, etc.
- Silent drift: The 4 backup variants may have diverged intentionally or by accident; no single source of truth

**Recommendation:**
- Create `manage.sh` CLI wrapper with subcommands: `manage.sh backup [tier]`, `manage.sh restore [tier]`, `manage.sh export-images`, etc.
- Parametrize backup/restore by tier (default, critical, high, medium) → single script + env var
- Move Python utilities to a `scripts/util/` subdir or convert to `manage.sh backup-corpus` subcommand
- Keep existing scripts as-is for backward compatibility; do NOT delete (users may have scripts calling them)

**Risk:** LOW — CLI wrapper is additive; no breaking changes if we preserve existing script entry points.

---

### 3. **Environment File Confusion** (3 templates: `.env.example`, `.env.prod.example`, inline compose vars)

**Current state:**
- `.env.example` (193 lines): Comprehensive dev/CI template with all 50+ variables documented
- `.env.prod.example` (82 lines): Production-only subset (BOOKS_PATH, CORS, auth, RabbitMQ, Solr, VERSION/GIT_COMMIT/BUILD_DATE)
- **Inline defaults in compose services:** e.g., `solr-search/Dockerfile` hardcodes `SOLR_HOST="solr"`, `RABBITMQ_HOST="localhost"`, `REDIS_HOST="localhost"`

**Redundancy:**
- `.env.example` and `.env.prod.example` both define CORS_ORIGINS, RABBITMQ_PASS, SOLR_ADMIN_USER (overlapping)
- Production env vars are scattered: some in `.env.prod.example`, some in `docker/compose.prod.yml` inline
- Dockerfile env defaults (e.g., `ENV SOLR_HOST="solr"`) duplicate what could be in a `.env.compose.defaults`

**Clarity cost:**
- Onboarding: Docs say "copy .env.example" but prod should use ".env.prod.example" — not obvious when to use which
- Merging: If you need to migrate dev → prod, unclear which vars to preserve vs. override

**Recommendation:**
- Create single `.env.example` with clearly marked **DEV** and **PROD** sections (with a header explaining when to use which)
  - OR: Keep `.env.example` as dev; rename `.env.prod.example` → `.env.production` (simpler: just copy one of the two)
- Document in README: "Start with `.env.example` for local dev. For production, copy `.env.production` and customize."
- Move hardcoded Dockerfile ENV defaults into `.env.compose.defaults` (sourced by installer only, not checked in)
- Do NOT strip vars from `.env.example`; that template should remain comprehensive for reference.

**Risk:** MEDIUM — Need to coordinate with installer expectations (which vars does the installer depend on?). Test with fresh `python3 -m installer --reset` run.

---

### 4. **Test Infrastructure Complexity** (3 frameworks, 480-line orchestration workflow)

**Current frameworks:**
1. **Pytest (Python):** `e2e/pytest.ini`, `e2e/conftest.py`, ~10 test files in `e2e/test_*.py`, ~2000 lines
2. **Playwright (JavaScript):** `e2e/playwright/`, separate `package.json`, separate test runner, ~200 lines
3. **Stress tests (Python):** `tests/stress/`, separate `pytest.ini`, `conftest.py`, custom runner in `scripts/benchmark/`

**Orchestration complexity:**
- `.github/workflows/integration-test.yml` (480 lines): Glues all 3 together
  - Changes discovery logic: PR → check if build-relevant → run all tests
  - Topology matrix: [single-node, distributed]
  - Health checks: Custom Python inline scripts (Solr cluster verification, API readiness, etc.)
  - CI-only Docker Compose overrides: `docker-compose.github-actions.yml` generated inline (tmpfs volumes, no persistent data)
  - Test execution: Sequential `pytest → playwright → report upload`

**Fragility:**
- Integration-test workflow is **480 lines** (hard to reason about, hard to change)
- CI overrides generated inline (brittle, hard to diff, hard to version)
- Health-check logic is embedded as shell + Python one-liners (hard to unit-test, hard to reuse)
- Stress tests in separate `tests/stress/` with separate pytest.ini (unclear how/when they run)

**Recommendation (stepped approach):**
- **Phase 1 (low-risk):** Extract health-check logic into reusable `docker/health-check.sh` script (documented, testable, versionable)
- **Phase 2 (medium-risk):** Move CI Docker Compose override into `docker/compose.ci.yml` (replaces inline generation, easier to review)
- **Phase 3 (deferred):** Makefile targets for test orchestration (`make test-unit`, `make test-e2e`, `make test-stress`) — optional, used locally for dev but not required for CI
- Do NOT merge pytest/playwright into one runner (they have different dependency stacks; npm vs uv)

**Risk:** MEDIUM — Integration-test workflow is high-leverage; changes must be validated against both CI and local dev runs.

---

### 5. **Build Script Fragility** (`buildall.sh` lacks error handling for per-service failures)

**Current state (post-PR #1706):**
- `buildall.sh` now discovers services dynamically ✓
- However: No error handling if ONE service build fails
- If `docker compose up --build -d` hits a Dockerfile error, the entire command fails without clarity on which service broke

**Missing:**
- Per-service build error isolation and reporting
- Partial build recovery (e.g., rebuild just the failed service)
- Docker BuildKit native build parallelism (currently sequential by default)

**Recommendation:**
- Add `set -e` error trap to catch individual `uv sync` or `docker build` failures
- Report which service failed, with isolated logs saved to `./.test-artifacts/buildall-{service}-{timestamp}.log`
- Optional: Use `docker buildx build` for parallel native builds (more complex, deferred to v2.6+)

**Risk:** LOW — Additive error handling; no breaking changes.

---

### 6. **Documentation Scatter** (Solr topology config in 3+ places)

**Current state:**
- Solr deployment topology documented in:
  1. `.env.example` lines 149–170 (inline comments)
  2. `.env.prod.example` (no topology docs, minimal guidance)
  3. `docker/compose.single-node.yml` (overlay comments)
  4. `installer/` (code, not docs)
  5. Scattered across 67 Copilot skills (.copilot/, .squad/)

**Fragmentation cost:**
- Onboarding: Which doc to read? README doesn't link to `.env.example` topology section
- Maintenance: If topology changes, docs must be updated in 3+ places
- Single source of truth lost: Is `.env.example` authoritative, or the installer code?

**Recommendation:**
- Create `docs/deployment-topology.md` (single source of truth for Solr topology decision matrix)
- Link from README → "Deployment" section → topology guide
- Link from installer interactive prompt to guide
- Update `.env.example` comments to cross-reference: "(See docs/deployment-topology.md for details)"
- Keep inline comments in .env.example as SHORT TL;DR; reserve detailed docs for the dedicated guide

**Risk:** LOW — Documentation-only change; no code changes needed initially.

---

## Decomposed Follow-Up Plan: Safe, Small PR Slices

| # | Title | Scope | Owner | Risk | Validation | Depends On | Estimate |
|---|-------|-------|-------|------|-----------|-----------|----------|
| 1 | Extract health-check logic from integration-test.yml | Move inline health-check Python/shell into `docker/health-check.sh` (reusable, tested locally) | Brett | LOW | `bash -n docker/health-check.sh`, CI green on integration-test.yml | none | 1–2 PR cycles |
| 2 | Create `docker/compose.ci.yml` overlay | Move inline CI Docker Compose volume/tmpfs overrides from integration-test.yml workflow to versioned file | Brett | MEDIUM | `docker compose -f docker-compose.yml -f docker/compose.ci.yml config`, CI green | Health-check extraction | 2–3 PR cycles |
| 3 | Add error handling + logging to buildall.sh | Trap per-service failures, save logs to .test-artifacts/, report which service broke | Brett | LOW | `bash -n buildall.sh`, manual test on multi-service build | none | 1 PR cycle |
| 4 | Create manage.sh CLI wrapper | Parametrize 5 backup scripts + 4 restore scripts into single `manage.sh backup [tier]` + `manage.sh restore [tier]` interface | Parker | MEDIUM | `bash -n manage.sh`, smoke-test each tier variant, verify backward compat | none | 2–3 PR cycles |
| 5 | Consolidate .env files | Merge .env.prod.example into .env.example with **DEV**/**PROD** sections; update installer/README | Parker | MEDIUM | Fresh `python3 -m installer --reset`, test both dev + prod .env workflows | none | 1–2 PR cycles |
| 6 | Document Solr deployment topology | Create `docs/deployment-topology.md` as single source of truth; link from README + installer | Dallas or Newt | LOW | Review for clarity by Ripley; link check in README | none | 1 PR cycle |
| 7 | Dockerfile base stage extraction | Extract common Alpine/Debian stages from document-indexer, document-lister, solr-search (keep embeddings-server separate) | Brett | MEDIUM | `docker build` all 4 services, verify layer cache hit rates improve | none | 2–3 PR cycles (post v2.5) |

---

## Risk Ranking Summary

| Risk Level | Items | Notes |
|-----------|-------|-------|
| **LOW** | Health-check extraction, buildall error handling, docs consolidation | Additive or docs-only; low breaking change risk |
| **MEDIUM** | CI Compose overlay, manage.sh CLI, env file consolidation, Dockerfile extraction | Require careful testing; higher breaking change risk; good review gates recommended |
| **HIGH** | Test framework unification (pytest + Playwright + stress tests into single runner) | **DEFERRED** — too risky for v2.5 backlog; revisit in v2.6+ with dedicated test refactor epic |

---

## Owner Routing

- **Brett (Infra Architect):** #1, #2, #3, #7 (Docker, buildall, health checks, Compose overlays, Dockerfile refactoring)
- **Parker (Backend Dev):** #4, #5 (manage.sh CLI, env consolidation — touches installer and deployment code)
- **Dallas or Newt (Frontend Dev / Product Manager):** #6 (Docs consolidation — lightweight, good for Product context)
- **Lambert (Tester):** Optional: smoke-test suite for #1–#7 (test coverage on new tooling)

---

## Validation Strategy (Per PR)

### Health-Check Extraction (#1)
- Syntax check: `bash -n docker/health-check.sh`
- Unit test: Call `docker/health-check.sh` with mock curl (local dev)
- Integration: CI green on `integration-test.yml` using extracted script

### CI Compose Overlay (#2)
- Validate config: `docker compose -f docker-compose.yml -f docker/compose.ci.yml config >/dev/null`
- Compare generated vs. previous: Check volume tmpfs sizes match inline version
- CI green on integration-test.yml

### buildall Error Handling (#3)
- Syntax check: `bash -n buildall.sh`
- Test failure scenario: Sabotage a Dockerfile, verify buildall traps error + reports which service
- Check artifact logs: `.test-artifacts/buildall-{service}-{timestamp}.log` exists

### manage.sh CLI (#4)
- Syntax check: `bash -n manage.sh`
- Smoke test each tier: `./manage.sh backup default`, `./manage.sh backup critical`, etc.
- Verify old scripts still work: Call `/scripts/backup.sh` directly (backward compat)

### .env consolidation (#5)
- Fresh installer run: `python3 -m installer --reset`, verify .env generated correctly
- Prod workflow: Copy .env.production locally, verify solr-search + admin start with prod vars
- Diff: Check old .env.prod.example vars are present in new merged .env.example

### Solr topology docs (#6)
- Link validation: README → docs/deployment-topology.md (no 404)
- Clarity review by Ripley (2–3 min read)

### Dockerfile extraction (#7)
- Build all 4 services: `docker build src/document-indexer`, `docker build src/document-lister`, etc.
- Layer cache hits: Compare `docker build` output (with cache hit vs. without)
- Identical image output: Verify new multi-stage approach produces same binary

---

## Blockers & Dependencies

- **None immediate.** All items are post-v2.5 backlog; no release blockers.
- **Soft dependency:** #1 (health-check extraction) → #2 (CI Compose overlay) — order recommended but not mandatory
- **Coordination needed:** Parker on #4 + #5 depends on installer domain knowledge; recommend pairing with installer owner if one exists

---

## Decision: Scope of This Comment

This research pass is **PLANNING ONLY** — no code changes. Its output:
1. Identifies remaining complexity areas (not duplicative of #1452 original findings; shows progress post-PR #1706)
2. Decomposes into safe, single-owner PR slices (each 1–3 cycles)
3. Ranks risk + validation strategy
4. Routes to Brett/Parker/Dallas/Newt based on domain

**Next step:** Once #1452 is reopened or a v2.5.1 backlog milestone exists, extract these into individual GitHub issues and link them to #1452 as follow-up work.

---

## References

- Original issue: #1452
- Completed: PR #1706 (buildall service discovery)
- Config: `.squad/team.md` (routing), `.squad/agents/brett/charter.md` (Brett's domain)
- Workflows: `.github/workflows/integration-test.yml`, `buildall.sh`
- Services: `src/{document-indexer,document-lister,embeddings-server,solr-search}/Dockerfile`
- Env templates: `.env.example` (193 lines), `.env.prod.example` (82 lines)
- Scripts: `/scripts/` (18 files), `/docker/` (11 files)
# Brett — Phase 2 Infrastructure Assessment

**Date:** 2026-06-06  
**Issue:** #1356 ([v2.5] Test Phase 2)  
**Status:** Infrastructure analysis complete; fixtures deferred to v2.5.1

## Scope

Phase 2 testing requires validation of:
1. **Standalone Solr 10 (no ZooKeeper)** — true single-node, no clustering
2. **Vector quantization (int8)** — memory reduction + search quality
3. **efSearchScaleFactor tuning** — speed/quality tradeoff
4. **Production SolrCloud (Overseer disabled)** — cluster management without Overseer
5. **Failover/resilience** — deferred to v2.5.1

## Current Infrastructure State

### Compose Overlays (Existing)
- ✅ `docker-compose.yml` — base 3-node SolrCloud + 3-node ZK ensemble
- ✅ `docker/compose.single-node.yml` — disables extra nodes, keeps ZooKeeper
- ✅ `docker/compose.solr10.yml` — explicit Solr 10 runtime
- ✅ `docker/compose.e2e.yml` — CI port overrides
- ✅ `docker/compose.prod.yml` — production security + 3-node hardening

### Compose Overlays (Missing)
- ❌ `docker/compose.standalone-solr10.yml` — true no-ZK standalone Solr
- ❌ `docker/compose.overseer-disabled.yml` — Overseer disabled validation
- ⏳ `docker/compose.resilience.yml` — failover/recovery (v2.5.1 scope)

### Init Script (`docker/solr-init.sh`)
- **Current:** Hardcoded ZK_HOST requirement; all operations assume ZooKeeper
- **Needed:** Variant path for `SOLR_STANDALONE_MODE=true` (skip ZK ops, use REST API)

## Infrastructure Gaps

### Gap 1: Standalone Solr 10 (No ZooKeeper)

**What's required:**
- Remove zoo1/zoo2/zoo3 services (profile-gated)
- Single Solr node without ZK_HOST env var
- Init script adapted to skip: `solr zk cp`, `solr zk upconfig`, `/clusterStatus` validation
- Configset + collection creation via Solr REST API instead

**Compose overlay blueprint:**
```yaml
services:
  zoo1:
    profiles: ["zk-only"]
  zoo2:
    profiles: ["zk-only"]
  zoo3:
    profiles: ["zk-only"]
  
  solr:
    environment:
      - ZK_HOST=  # empty; no ZooKeeper
    depends_on: !override {}  # no ZK dependency
  
  solr2:
    profiles: ["zk-only"]
  solr3:
    profiles: ["zk-only"]
  
  solr-init:
    environment:
      - SOLR_STANDALONE_MODE=true
      - SOLR_EXPECTED_NODES=1
    depends_on: !override
      solr:
        condition: service_healthy
```

**Init script variant:**
```bash
if [ "${SOLR_STANDALONE_MODE:-false}" = "true" ]; then
  # Skip ZK auth bootstrap; Solr standalone mode has no distributed auth
  # Configset upload: curl POST /api/cluster/configs instead of solr zk upconfig
  # Collection creation: curl with waitForFinalState=true
  # Node validation: curl /admin/info/system (no /clusterStatus)
else
  # Existing ZK-based path (current code)
fi
```

**Validation:**
- Collection creation succeeds without ZooKeeper
- Search + indexing work in standalone mode
- Health checks pass without cluster quorum

---

### Gap 2: Production SolrCloud (Overseer Disabled)

**What's required:**
- Overlay sets `-DSOLR_OVERSEER_DISABLED=true` system property
- Keeps full 3-node topology (validate Overseer not needed for operations)
- Collection management still responsive (manual election, no auto-rebalancing)

**Compose overlay blueprint:**
```yaml
services:
  solr:
    environment:
      - SOLR_OPTS=-DSOLR_OVERSEER_DISABLED=true
  solr2:
    environment:
      - SOLR_OPTS=-DSOLR_OVERSEER_DISABLED=true
  solr3:
    environment:
      - SOLR_OPTS=-DSOLR_OVERSEER_DISABLED=true
```

**Validation:**
- Collections respond to `/admin/collections?action=CLUSTERSTATUS`
- No "Overseer missing" errors in logs
- Leader/replica state consistent (no auto-rebalancing, but state maintained)
- Admin API functional

---

### Gap 3: Failover & Resilience (Out of Scope for v2.5.0)

**Deferred to v2.5.1 or Phase 3.** Would require:
- Leader failure + replica promotion
- Node restart recovery
- ZK ensemble loss recovery
- Cluster healing validation

---

## Safe Runtime Commands

For Phase 2 testing diagnostics:

```bash
# General health
curl -s http://solr:8983/solr/admin/info/system | jq '.responseHeader.status'

# Standalone check (no cluster info)
curl -s http://solr:8983/solr/admin/info/properties | jq '.responseHeader'

# SolrCloud status
curl -s http://solr:8983/solr/admin/collections?action=CLUSTERSTATUS&wt=json | jq '.cluster'

# Memory usage (quantization impact)
curl -s http://solr:8983/solr/admin/info/jvm | jq '.jvm.memory.used'

# Vector field stats
curl -s http://solr:8983/solr/books/select?q=*:*&rows=0&stats=true&stats.field=embedding_byte_v | jq '.stats.stats_fields.embedding_byte_v'
```

---

## Phase 2 Test Readiness Matrix

| Scenario | Status | Blocker | Fixture |
|----------|--------|---------|---------|
| Single-node overlay validation | ✅ Active | None | `compose.single-node.yml` |
| Int8 schema + app wiring | ✅ Active | None | `managed-schema.xml`, `config.py` |
| Standalone mode startup | ⏸️ Gated | Missing fixture + #1670 + #1344 | `compose.standalone-solr10.yml` |
| Standalone full workload | ⏸️ Gated | Missing fixture + #1670 + #1344 | `compose.standalone-solr10.yml` |
| Quantization memory reduction | ⏸️ Gated | #1670 + #1344 | `compose.single-node.yml` + runtime |
| Quantization search quality | ⏸️ Gated | #1670 + #1344 | `compose.single-node.yml` + baseline |
| efSearchScaleFactor tuning | ⏸️ Gated | #1344 | `compose.single-node.yml` + runtime |
| SolrCloud Overseer disabled | ⏸️ Gated | Missing fixture | `compose.overseer-disabled.yml` |

---

## Recommendations

### For v2.5.0 Release Gate
✅ **Do NOT block Phase 2 on infrastructure fixtures.** The quantization blockers (#1670 + #1344) drive the real dependency. Fixtures are pre-work that can happen in parallel.

### For v2.5.1 Sprint (Post-Quantization)
1. Create `docker/compose.standalone-solr10.yml`
2. Adapt `docker/solr-init.sh` for `SOLR_STANDALONE_MODE` detection
3. Create `docker/compose.overseer-disabled.yml`
4. Activate all Phase 2 test scenarios

### No Code Changes Required Today
Infrastructure fixtures can be scaffolded immediately without blocking on merge or test execution:
- Compose overlays: static YAML configurations
- Init script: branching logic, no functional changes to existing paths
- Runtime validation: diagnostic curl commands (no SDK changes)

---

## Deliverables

- ✅ Infrastructure gap analysis (this document)
- ✅ Infra findings comment posted to #1356
- ✅ Safe runtime commands documented
- ✅ Fixture scaffolds ready for v2.5.1 sprint
# Decision: OpenVINO release gates for base-image drift

**Author:** Brett (Infrastructure Architect)  
**Date:** 2026-06-05T17:02:51.834+00:00  
**Status:** Proposed for Scribe merge  
**Related:** #1662

## Decision

Keep Docker `uv sync --inexact` for the OpenVINO embeddings image, but treat it as
safe only when the built image proves the installed runtime packages satisfy the
OpenVINO extra constraints in `src/embeddings-server/pyproject.toml`.

The release gate now has two enforcement points:

1. The Docker build fails immediately after `uv sync --inexact` if installed
   `openvino`, `openvino-tokenizers`, or `optimum-intel` drift outside the
   configured constraints.
2. A PR/manual/weekly `OpenVINO Release Gate` workflow rebuilds the image with
   the latest base image and runs runtime smoke diagnostics.

## Rationale

The post-mortem for #1662 showed that lockfile validation in a clean environment
does not catch skew introduced by preserving base-image packages. Verifying inside
the built image checks the actual runtime that will be released while preserving
the build-time optimization.

## Coordination notes for Parker

Application/runtime tests can rely on `/v1/embeddings/model` for the expected
embedding dimension instead of hardcoding `768`. If Parker changes model-loading
behavior or OpenVINO dependencies, the Docker verifier and smoke script are the
infra-owned gates that should be updated with the new source-of-truth constraints.
# Decision: Keep App-Side Hybrid RRF Until Solr Combined Query Is Benchmarked

**Date:** 2026-06-06
**Author:** Ash (via Copilot)
**Status:** Proposed
**Related:** #1349, SOLR-17319

## Context

Solr 10.0.0 does not include a native RRF/combined-query handler. Solr mainline after the 10.0.0 tag now includes `CombinedQuerySearchHandler` / `CombinedQueryComponent` for multi-query fusion with built-in Reciprocal Rank Fusion (RRF). This is relevant to Aithena's current BM25 + kNN + RRF hybrid search implementation.

## Proposal

Keep Aithena's current app-side hybrid search as the production default until the shipped Solr runtime includes SOLR-17319 and a dedicated prototype proves that Solr Combined Query RRF preserves or improves relevance and latency on the real corpus.

## Rationale

Aithena currently fuses parent-document BM25 results with chunk-document kNN results after normalizing chunks to book IDs in Python. Solr native RRF fuses by Solr document ID, so a naive parent BM25 + chunk kNN combined query will not reward overlap between the same book's parent and chunks. Combined Query also does not support grouping/cursors, so parent-level chunk grouping cannot be assumed inside the fusion step.

## Next Step

Prototype behind a separate Solr handler/flag and benchmark:

1. Current app-side chunk-kNN RRF.
2. Solr Combined Query RRF with parent/book-level vectors, if parent vectors are indexed.
3. Optional chunk-keyword + chunk-vector fusion with post-normalization.

Do not change default ranking without judged relevance, latency, facet/highlight, and page-range validation.
# Decision: Disable SolrCloud Overseer in production Solr 10 deployments

**Date:** 2026-06-06T16:09:02.162+00:00
**Owner:** Brett
**Related issue:** #1343

## Decision

`docker/compose.prod.yml` starts all three production Solr nodes with
`-Dsolr.cloud.overseer.enabled=false` by default. The production topology still
uses three SolrCloud nodes and a three-node ZooKeeper ensemble for HA.

## Rationale

Solr 10 supports distributed cluster-state updates without the legacy Overseer
queue. Disabling Overseer removes a collection-management bottleneck and avoids
coupling cluster operations to one busy or restarting Overseer leader, while
retaining the existing ZooKeeper-backed HA topology.

## Guardrails

- Dev/default/single-node topology is unchanged.
- Operators can temporarily set `SOLR_CLOUD_OVERSEER_ENABLED=true` for rollback.
- Runtime validation is documented in
  `tests/solrcloud-overseer-disabled-validation.sh`; failover is opt-in with
  `RUN_FAILOVER=1` because it intentionally stops a Solr node.
