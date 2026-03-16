# Decision: Stack Trace Logging Security Pattern

**Date:** 2026-03-16  
**Author:** Parker (Backend Dev)  
**Context:** Issue #299 — embeddings-server exc_info exposure

## Decision

All Python services must use a two-tier logging pattern for exceptions:

1. **CRITICAL/ERROR level** — User-facing, production-safe:
   ```python
   logger.critical("Operation failed: %s (%s)", exc, type(exc).__name__)
   ```

2. **DEBUG level** — Stack trace for troubleshooting only:
   ```python
   logger.debug("Full stack trace:", exc_info=True)
   ```

## Rationale

Production logs (INFO/WARNING level) should NOT expose:
- Internal file paths and directory structure
- Library versions (dependency fingerprinting)
- Environment configuration details
- Variable values in exception frames

Stack traces are valuable for debugging but constitute information disclosure in production environments.

## Scope

Applies to:
- solr-search
- document-indexer
- document-lister
- embeddings-server
- admin (Streamlit)

All critical/error exception handlers should be reviewed and updated to follow this pattern.

## Implementation

Fixed in embeddings-server (PR #314). Recommend audit of other services in future milestone.

## Related

- Security best practice: least-privilege logging
- Complements existing Bandit (S) ruff rules
