# Decision: e5 Migration Review Outcomes

**Date:** 2026-03-23
**Author:** Ripley (Lead)
**Status:** DECIDED

## Context

PR #964 migrates from distiluse to multilingual-e5-base. Review identified leftover A/B infrastructure and a timeout mismatch.

## Decisions

1. **scripts/benchmark/ cleanup** — The entire `scripts/benchmark/` directory, `scripts/index_test_corpus.py`, and `scripts/verify_collections.py` reference the removed `books_e5base` collection and `distiluse` model. These should be updated or archived in a **follow-up issue**, not this PR. The benchmark tooling is useful post-migration but needs to target the single `books` collection.

2. **Compare endpoint** — `/v1/search/compare` now defaults both baseline and candidate to `"books"`, making it a no-op. Keep it (it's `include_in_schema=False`) but open a follow-up issue to either repurpose it for future A/B tests or remove it.

3. **README update required** — README.md still references `distiluse-base-multilingual-cased-v2`. Must be updated as part of this migration.

4. **Admin reindex timeout** — The Streamlit admin page uses `timeout=60` but the API endpoint allows up to 120s for Solr deletion. The admin client may timeout before the API completes on large collections.
