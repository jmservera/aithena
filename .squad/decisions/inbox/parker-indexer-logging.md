# Decision: Production Error Logging Convention

**Date:** 2026-03-16  
**Context:** Issue #302 — Document-indexer logging security fix  
**Author:** Parker (Backend Dev)  
**Status:** Proposed

## Problem

`logger.exception()` was used in production error paths, exposing full stack traces (with internal paths and library versions) in container logs at INFO/ERROR level. This creates information disclosure risk.

## Decision

**Standard production error logging pattern:**

```python
except Exception as exc:
    logger.error("Failed to process %s: %s", resource, exc)
    logger.debug("Failed to process %s", resource, exc_info=True)
```

**Rationale:**
- `logger.error()` logs error message and exception type (suitable for production logs)
- `logger.debug()` with `exc_info=True` preserves full stack traces for troubleshooting
- DEBUG level logging can be enabled when needed without changing code
- Prevents information disclosure in default container log output

**When to use `logger.exception()`:**
- Only in truly unexpected internal errors where stack traces are always needed
- Not in expected error paths (file not found, validation failures, external service errors)

## Impact

- **document-indexer**: Fixed lines 379, 383 (PR #310)
- **Other services**: Should follow same pattern in future error handling

## References

- Issue #302
- PR #310
- Python logging best practices (avoid exception details in production logs)
