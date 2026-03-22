# Squad Decisions

This file records architectural, operational, and technical decisions made by the Aithena squad. Decisions are proposed by squad members, discussed, and merged into this log once finalized.

## Phase 2: A/B Testing Infrastructure (2026-03-22)

### Decision: P2-1 — Test Corpus Indexing via Fanout Exchange

**Author:** Ash (Search Engineer)  
**Date:** 2026-03-22  
**Status:** IMPLEMENTED  
**Issue:** #877  

#### Context

Phase 1 infrastructure is complete: dual collections (`books` 512D, `books_e5base` 768D), dual indexers, fanout exchange. We need a way to trigger indexing of a test corpus through both pipelines and verify the results.

#### Decision

**Script Architecture**

1. **`scripts/index_test_corpus.py`** publishes document file paths directly to the `documents` fanout exchange (same mechanism as `document-lister`). This is simpler than triggering `document-lister` and more controllable for test scenarios.

2. **`scripts/verify_collections.py`** queries both Solr collections via the `/select` API. Checks: parent doc count parity, ID set equality, embedding dimensionality sampling.

3. Both scripts live in `scripts/` (not inside any service) since they're operational tools that interact with multiple services.

**Idempotency**

Re-publishing the same file paths is safe because:
- The fanout exchange delivers to both queues regardless
- Document-indexer uses the file path SHA-256 as Solr's unique key
- Solr overwrites on duplicate ID (atomic update)

**Verification Approach**

- Dimensionality check samples one chunk embedding per collection (not exhaustive). A full check would require scanning all chunks, which is expensive and unnecessary — wrong dimensions would fail at Solr indexing time.
- Empty collections pass all checks (nothing to verify yet).

#### Impact

- **Parker (document-indexer):** No changes needed — scripts use the same exchange/queue pattern.
- **Brett (infra):** Scripts require `pika` and `requests` — already available in service containers.
- **Lambert (tester):** Verification script can be integrated into CI with `--json` output and exit code checking.

---

### Decision: P2-2 — Benchmark Query Suite Design

**Author:** Ash (Search Engineer)  
**Date:** 2026-03-22  
**Status:** IMPLEMENTED  
**Issue:** #879  

#### Context

For A/B testing distiluse (512D) vs e5-base (768D), we need a standardized query suite to evaluate search quality. The benchmark must be reproducible, human-reviewable, and run against a live instance.

#### Decisions

**Query Categories**

Five categories chosen to cover the full range of real-world library search patterns:
1. **Simple keyword** (5) — baseline catalog searches
2. **Natural language** (6) — questions where semantic search should outperform BM25
3. **Multilingual** (6) — Spanish, Catalan, French queries matching the library's content mix
4. **Long/complex** (4) — queries benefiting from e5-base's 512-token context window
5. **Edge cases** (9) — single chars, stopwords, special characters, nonsense, accented text

**Comparison Metric: Jaccard Similarity of Top-10**

Jaccard over document ID sets is the primary overlap metric. It's simple, interpretable, and sufficient for human evaluation. Low-overlap queries (< 0.3) are flagged for manual review. More sophisticated metrics (nDCG, MAP) would require ground-truth relevance labels which we don't have yet.

**No input_type Handling in Benchmark Runner**

The solr-search API handles `input_type=query` injection for e5 collections internally. The benchmark runner just passes the collection name — this keeps the runner simple and avoids duplicating logic.

#### Impact

- **Parker/Brett:** The runner hits `GET /search` with `collection=` parameter. No API changes needed.
- **Team:** Run `python scripts/benchmark/run_benchmark.py` against a live instance to generate comparison data for Phase 2 evaluation.

---

### Decision: P2-3 — Comparison API Design

**Author:** Parker (Backend Developer)  
**Date:** 2026-03-22  
**Status:** IMPLEMENTED  
**Issue:** #880  

#### Decisions

**1. Endpoint is Internal (`include_in_schema=False`)**

Per PRD Phase 2 decision, comparison is API-only with no UI toggle. Hidden from OpenAPI/Swagger docs. Consumers: benchmark script (P2-2) and future admin dashboard.

**2. Reuse Existing Search Mode Helpers**

The compare endpoint delegates to `_search_keyword`, `_search_semantic`, and `_search_hybrid` through `_execute_search_for_compare`. Ensures feature parity (degradation, circuit breakers, filters) without code duplication.

**3. Parallel Collection Queries**

Both collections queried concurrently via `ThreadPoolExecutor(max_workers=2)`. Latency = max(baseline, candidate) instead of sum.

**4. Overlap Metric: Jaccard-like at Top-N**

`overlap_at_10` = |intersection| / max(|baseline|, |candidate|). Uses `max` as denominator to avoid inflating overlap when one side returns fewer results.

**5. Config via Env Vars (Not Query Params)**

Baseline/candidate collections are server-side config (`COMPARISON_BASELINE_COLLECTION`, `COMPARISON_CANDIDATE_COLLECTION`), not request parameters. Prevents arbitrary collection comparisons and keeps the API surface simple.

#### Impact

- Ash's benchmark script (P2-2) can call `/v1/search/compare` for side-by-side results with metrics.
- Dallas: no UI work needed — endpoint is API-only per PRD.

---

### Decision: P2-4 — Performance Metrics Architecture

**Author:** Lambert (QA Engineer)  
**Date:** 2026-03-22  
**Status:** IMPLEMENTED  
**Issue:** #881  

#### Decision 1: In-Memory Rolling-Window Store Over Prometheus Client

**Context:** Issue #881 required metrics collection for A/B evaluation with no new infrastructure dependencies.

**Decision:** Built a standalone `PerfMetricsStore` class using `threading.Lock` + `defaultdict` + `TimedSample` dataclass instead of using the existing Prometheus `MetricsRegistry` or adding prometheus-client.

**Rationale:**
- The existing `MetricsRegistry` (metrics.py) is Prometheus exposition-format only — adding per-collection latency percentiles would require significant refactoring
- This is temporary A/B tooling, not production monitoring — lighter is better
- Rolling-window pruning keeps memory bounded without external storage
- JSON response from `/v1/admin/metrics` is immediately consumable by scripts and dashboards

#### Decision 2: Internal Timing Keys in Search Response Dicts

**Decision:** Search mode functions (`_search_keyword`, `_search_semantic`, `_search_hybrid`) return `_solr_latency_s` and `_embedding_latency_s` keys in the response dict, stripped by the caller before returning to the client.

**Rationale:** Avoids changing function signatures or adding a separate return channel. The underscore-prefix convention signals these are internal. The caller (`search()`) pops them after recording metrics.

#### Decision 3: Admin-Auth for Metrics Endpoints

**Decision:** `GET /v1/admin/metrics` and `POST /v1/admin/metrics/reset` use `require_admin_auth` (X-API-Key), consistent with other `/v1/admin/*` endpoints.

**Rationale:** Performance data could reveal usage patterns; reset should be controlled. Follows existing admin endpoint pattern.

---

## Archive

Decisions from previous phases are available in `archive/` for historical reference.
