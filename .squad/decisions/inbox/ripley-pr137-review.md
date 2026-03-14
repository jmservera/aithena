# Decision: PR #137 — Page ranges in search results

**Date:** 2026-03-14
**Author:** Ripley (Lead)
**Status:** Approved

## Context

PR #137 adds `pages` field to search API results, exposing chunk-level page ranges (`page_start_i` / `page_end_i` from Solr) as `[start, end]` or `null` for full-doc hits.

## Decision

Approved as-is. The change is purely additive — a new `pages` field on the response object. The UI `BookResult` TypeScript type does **not** need updating until the frontend wires up page-range display; the backend already returns several untyped fields (`score`, `file_size`, `folder_path`) that the UI ignores.

## Rationale

- Correct edge-case handling (both fields, one field, neither)
- Comprehensive test coverage (5 unit + 2 integration)
- No breaking API changes
- Targets `dev` branch as required
