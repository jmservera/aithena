# Session Log: Similar Books Fix & Release

**Date:** 2026-03-28  
**Milestone:** v1.17.0  
**Status:** COMPLETE

## Summary

Fixed critical bug where similar books endpoint failed when called with chunk IDs from semantic search results. Root cause: semantic search returns chunk document IDs, but the endpoint expected parent book IDs. Added transparent chunk ID resolution and data enrichment so the endpoint works seamlessly.

## Outcome

- **PR #1262** (dev): Backend fix + frontend data enrichment → MERGED
- **PR #1263** (main): Merge dev to main → MERGED
- **v1.17.0** tag created, GitHub release published
- **Release workflow** triggered (containers publishing to GHCR)
- **1022 backend + 600 frontend tests** passing
- **Zero regressions**

## Team Work

- **Parker:** Backend resilience (chunk ID detection + parent ID extraction)
- **Dallas:** Frontend coordination (SearchPage, BookDetailView, types)
- **Lambert:** Comprehensive test coverage (9 new tests + E2E validation)

## Decisions Recorded

- `parker-similar-books-chunk-id.md` — Chunk ID handling pattern and rationale
