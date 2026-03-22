# Code Review: EXCHANGE_NAME Environment Variable Fix

**By:** Code Review Team  
**Items:** PR #886, PR #885  
**Status:** ISSUE FOUND & FIXED before merge  
**Timestamp:** 2026-03-22T12:08:51Z

## Finding

During code review, reviewers identified that `EXCHANGE_NAME` environment variable was missing from the `docker-compose.yml` entries for both indexers and the producer.

## Issue Details

- **Service:** document-lister, document-indexer, document-indexer-e5
- **Missing:** `EXCHANGE_NAME` env var definition (required for runtime configuration)
- **Default:** Code had defaults (`"documents"`), but env var not exposed in docker-compose
- **Impact:** Services would use hardcoded string instead of configuration-driven value; made environment override impossible

## Resolution

Added `EXCHANGE_NAME=documents` to the environment section of:
1. **document-lister**
2. **document-indexer** (baseline)
3. **document-indexer-e5** (A/B candidate)

All three services now explicitly declare the exchange name in their docker-compose configuration, enabling:
- Per-environment customization (dev, staging, prod)
- Clear audit trail (env vars visible in compose file)
- Easy rollback or testing of alternative exchange names

## Status

✅ **FIXED before merge** — No technical debt introduced. Both PR #886 and #885 merged with full env var coverage.

## Process Note

This demonstrates the value of code review for infrastructure-as-code. Env var omissions are easy to miss in code inspection alone but critical for production deployments.
