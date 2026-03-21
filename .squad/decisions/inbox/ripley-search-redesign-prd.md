# Decision: Search Results Redesign PRD — Phasing & Scope

**Author:** Ripley (Lead)  
**Date:** 2026-03-21  
**Status:** PROPOSED — Awaiting PO approval  
**PRD:** `docs/prd/search-results-redesign.md`  
**Issues:** #796 (chunking strategy), #797 (PRD review), PR #798

## Context

Juanma requested 4 improvements to the search experience for v1.11.0. Code research revealed that the vector search text preview (R1) is nearly complete — chunk text is stored in Solr but not returned in the API.

## Decisions

### 1. Phasing: 3-wave delivery

- **Wave 1 (S+M):** R1 (chunk text preview) + R2 (PDF viewer improvements) — quick wins, no backend architecture changes
- **Wave 2 (L):** R3 (similar books + book detail view) — main frontend deliverable, depends on R2
- **Wave 3 or v1.12.0 (XL):** R4 (thumbnails) — deferred due to infrastructure dependencies

### 2. Chunking strategy requires PO decision before R1

Issue #796 assigned to Juanma. Current defaults (400 words / 50 overlap) may exceed the embedding model's token limit. Quality of text previews depends on good chunking parameters.

### 3. Similar books will be decoupled from PDF viewer state

The current z-index/overlay issue makes similar books unusable when PDF is open. R3 introduces a standalone BookDetailView that shows similar books without requiring the PDF viewer to be open.

## Impact

- **All frontend agents (Dallas):** BookDetailView is a new component — design review needed
- **Backend agents (Parker, Ash):** R1 is small (add field to list, update normalizer). R4 needs architecture discussion.
- **Milestone planning (Newt):** v1.11.0 milestone created. 4 requirements, 3 waves.
