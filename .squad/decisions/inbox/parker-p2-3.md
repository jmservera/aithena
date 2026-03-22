# P2-3: Comparison API Design Decisions

**Date:** 2026-03-22
**Author:** Parker (Backend Dev)
**Issue:** #880

## Decisions

### 1. Endpoint is internal (`include_in_schema=False`)
Per PRD Phase 2 decision, comparison is API-only with no UI toggle. Hidden from OpenAPI/Swagger docs. Consumers: benchmark script (P2-2) and future admin dashboard.

### 2. Reuse existing search mode helpers
The compare endpoint delegates to `_search_keyword`, `_search_semantic`, and `_search_hybrid` through `_execute_search_for_compare`. Ensures feature parity (degradation, circuit breakers, filters) without code duplication.

### 3. Parallel collection queries
Both collections queried concurrently via `ThreadPoolExecutor(max_workers=2)`. Latency = max(baseline, candidate) instead of sum.

### 4. Overlap metric: Jaccard-like at top-N
`overlap_at_10` = |intersection| / max(|baseline|, |candidate|). Uses `max` as denominator to avoid inflating overlap when one side returns fewer results.

### 5. Config via env vars (not query params)
Baseline/candidate collections are server-side config (`COMPARISON_BASELINE_COLLECTION`, `COMPARISON_CANDIDATE_COLLECTION`), not request parameters. Prevents arbitrary collection comparisons and keeps the API surface simple.

## Impact
- Ash's benchmark script (P2-2) can call `/v1/search/compare` for side-by-side results with metrics.
- Dallas: no UI work needed — endpoint is API-only per PRD.
