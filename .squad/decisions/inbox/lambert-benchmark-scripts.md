# Decision: Benchmark scripts simplified from A/B comparison to single-collection

**Author:** Lambert (Test Engineer)
**Date:** 2026-03-25
**Status:** IMPLEMENTED
**PR:** #985 (Closes #968)

## Context

PR #964 migrated to e5-base as the sole embedding model, removing the distiluse model and `books_e5base` collection. The benchmark scripts still contained the full A/B comparison framework.

## Decision

Rather than keeping the A/B comparison infrastructure with only one collection, the scripts were simplified:

- `run_benchmark.py` now benchmarks a single collection (default: `books`) across search modes, reporting latency and result metrics per mode/category. The A/B comparison classes (`QueryComparison`, `jaccard_similarity`, `compare_results`) were removed.
- `verify_collections.py` is now a single-collection health checker (docs present, chunks present, 768D embeddings).
- `index_test_corpus.py` references a single indexer pipeline.

## Impact

- **All team members:** Scripts in `scripts/benchmark/` and `scripts/` now target the single `books` collection. No more `books_e5base` references anywhere.
- **Future A/B testing:** If a new model comparison is needed, the old comparison code can be recovered from git history (commit before #985).
- **CI:** No CI pipeline changes needed — the scripts are run manually.
