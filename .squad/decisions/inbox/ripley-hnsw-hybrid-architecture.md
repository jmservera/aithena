# Decision: HNSW vs Hybrid-Rerank Dual Architecture

**Author:** Ripley (Lead)
**Date:** 2025-07-25
**Status:** Proposed
**Scope:** System-wide (Solr schema, search API, UI, Docker)

## Context

HNSW vector indexes consume 9–28 GB RAM for 9M page vectors. Some deployments (dev, small machines, cost-constrained) cannot afford this. We need a second deployment mode that eliminates HNSW but retains semantic capability via application-side vector reranking.

## Decision

Introduce `SEARCH_ARCHITECTURE` env var with two modes:

1. **`hnsw`** (default) — current behavior, all three search modes available
2. **`hybrid-rerank`** — no HNSW index, BM25 retrieval + app-side cosine reranking

Key design choices:
- **Explicit configuration** over auto-detection (clearer, debuggable)
- **Same `embedding_v` field name**, schema type changes at init time (Option B)
- **RRF fusion for hybrid-rerank** (consistent with HNSW hybrid)
- **`/v1/capabilities` endpoint** for UI to discover available modes
- **Semantic search disabled** in hybrid-rerank (returns 400)
- **Similar-books disabled** in hybrid-rerank (returns 501)

## Trade-offs

| Dimension | HNSW | Hybrid-Rerank |
|-----------|------|---------------|
| RAM | 9–28 GB | ~0 GB (for HNSW) |
| Semantic recall | Full kNN coverage | Bounded by BM25 top-N |
| Cross-lingual | Strong | Weak |
| Latency | Comparable | Comparable |
| Complexity | Current | +1 code path |

## Risks

- Mode switching requires full reindex (documented as maintenance operation)
- Rerank quality ceiling — BM25 misses purely semantic matches
- Network overhead: ~600 KB per query for 200 stored vectors

## Implementation Order

Phase 1 (Foundation) → Phase 2 (Search Path) → Phase 3 (UI + Docker) → Phase 4 (Validation)

Full analysis: `.squad/analysis/hnsw-vs-hybrid-architecture.md`

## Affected Teams

Parker (config/API), Ash (schema/search), Dallas (UI), Brett (Docker), Lambert (testing)
