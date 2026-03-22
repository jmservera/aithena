# Decision: Benchmark Query Suite Design (P2-2)

**Author:** Ash (Search Engineer)
**Date:** 2026-07-21
**Status:** IMPLEMENTED
**Issue:** #879

## Context

For A/B testing distiluse (512D) vs e5-base (768D), we need a standardized query suite to evaluate search quality. The benchmark must be reproducible, human-reviewable, and run against a live instance.

## Decisions

### Query categories
Five categories chosen to cover the full range of real-world library search patterns:
1. **Simple keyword** (5) — baseline catalog searches
2. **Natural language** (6) — questions where semantic search should outperform BM25
3. **Multilingual** (6) — Spanish, Catalan, French queries matching the library's content mix
4. **Long/complex** (4) — queries benefiting from e5-base's 512-token context window
5. **Edge cases** (9) — single chars, stopwords, special characters, nonsense, accented text

### Comparison metric: Jaccard similarity of top-10
Jaccard over document ID sets is the primary overlap metric. It's simple, interpretable, and sufficient for human evaluation. Low-overlap queries (< 0.3) are flagged for manual review. More sophisticated metrics (nDCG, MAP) would require ground-truth relevance labels which we don't have yet.

### No input_type handling in benchmark runner
The solr-search API handles `input_type=query` injection for e5 collections internally. The benchmark runner just passes the collection name — this keeps the runner simple and avoids duplicating logic.

## Impact

- **Parker/Brett:** The runner hits `GET /search` with `collection=` parameter. No API changes needed.
- **Team:** Run `python scripts/benchmark/run_benchmark.py` against a live instance to generate comparison data for Phase 2 evaluation.
