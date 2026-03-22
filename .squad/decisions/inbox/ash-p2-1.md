# Decision: P2-1 — Test Corpus Indexing via Fanout Exchange

**Author:** Ash (Search Engineer)
**Date:** 2026-07-21
**Status:** PROPOSED
**Issue:** #877

## Context

Phase 1 infrastructure is complete: dual collections (`books` 512D, `books_e5base` 768D), dual indexers, fanout exchange. We need a way to trigger indexing of a test corpus through both pipelines and verify the results.

## Decision

### Script Architecture

1. **`scripts/index_test_corpus.py`** publishes document file paths directly to the `documents` fanout exchange (same mechanism as `document-lister`). This is simpler than triggering `document-lister` and more controllable for test scenarios.

2. **`scripts/verify_collections.py`** queries both Solr collections via the `/select` API. Checks: parent doc count parity, ID set equality, embedding dimensionality sampling.

3. Both scripts live in `scripts/` (not inside any service) since they're operational tools that interact with multiple services.

### Idempotency

Re-publishing the same file paths is safe because:
- The fanout exchange delivers to both queues regardless
- Document-indexer uses the file path SHA-256 as Solr's unique key
- Solr overwrites on duplicate ID (atomic update)

### Verification Approach

- Dimensionality check samples one chunk embedding per collection (not exhaustive). A full check would require scanning all chunks, which is expensive and unnecessary — wrong dimensions would fail at Solr indexing time.
- Empty collections pass all checks (nothing to verify yet).

## Impact

- **Parker (document-indexer):** No changes needed — scripts use the same exchange/queue pattern.
- **Brett (infra):** Scripts require `pika` and `requests` — already available in service containers.
- **Lambert (tester):** Verification script can be integrated into CI with `--json` output and exit code checking.
