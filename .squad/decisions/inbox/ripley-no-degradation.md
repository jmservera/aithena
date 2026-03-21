# Decision: No Silent Degradation Rule (R6)

**Author:** Ripley (Lead)
**Date:** 2026-03-20
**Status:** APPROVED
**Source:** v1.10.0 Wave 0/1 Retrospective — Action Item R6

## Context

PR #700 proposed silently degrading semantic search to keyword search when kNN failed. This would have masked two real bugs (field name mismatch + URI too large) and permanently degraded search quality without any user-visible indication. PO rejected the PR.

## Rule

**Error handlers must NOT silently change search mode or drop results.**

### Required behavior when an error occurs in a search/data path:

1. **Log a WARNING-level message** with the error details and context
2. **Return a clear indication to the user/API consumer** — e.g., an error field in the response, an HTTP error status, or a user-visible message
3. **Never silently fall back** to a degraded mode (e.g., semantic → keyword, full results → partial results)

### Approval required

Any error handler that changes user-visible behavior (search mode, result count, result quality) requires **explicit approval from the Lead or PO** before implementation. This must be documented as a squad decision.

### Examples

**❌ Prohibited:**
```python
try:
    results = knn_search(query)
except Exception:
    results = keyword_search(query)  # silent degradation
```

**✅ Required:**
```python
try:
    results = knn_search(query)
except Exception as e:
    logger.warning("kNN search failed: %s — returning error to client", e)
    raise SearchError("Semantic search unavailable", cause=e)
```

## Impact

All agents implementing error handling in search or data paths. Existing degradation code must be reviewed for compliance.
