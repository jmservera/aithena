# Decision: Phase 2 Frontend PR Overlap Resolution

**Author:** Ripley (Lead)  
**Date:** 2026-03-13T23:20  
**Status:** DECIDED

## Context

Three Phase 2 frontend PRs (#61, #62, #63) submitted by @copilot needed review after PR #72 (solr-search backend) merged. All three PRs claimed to implement Phase 2 UI work but had significant overlap and inconsistencies.

## The Problem

1. **PR #61** and **PR #62** both rewrite `App.tsx` from chat to search paradigm — direct conflict
2. **PR #63** modifies the wrong service (qdrant-search instead of solr-search)
3. All three PRs use slightly different API contracts, some incorrect

## Decision

### PR #61 — CLOSED
- Redundant with PR #62 (which is a superset)
- Clean implementation but incomplete (no facets, no pagination)
- Closing eliminates the "minimal vs full search UI" choice

### PR #62 — APPROVED ✅
- This becomes the **canonical Phase 2 search UI**
- Includes facets, filters, pagination, sorting — complete implementation
- One-line fix needed: change `limit` to `page_size` in API call
- Marked as ready for review

### PR #63 — NEEDS CHANGES ❌
- Cannot merge as-is: modifies qdrant-search (deprecated) instead of solr-search
- Must rebase on PR #62 and layer PDF viewer on top
- PdfViewer.tsx component is good — needs correct API wiring

## Rationale

**Why close #61 instead of merging both?**
- Both rewrite the same `App.tsx` file — one must win
- #62 is feature-complete for Phase 2; #61 would need a follow-up PR for facets anyway
- Simpler to merge one complete PR than sequence two partial ones

**Why reject #63's current form?**
- Phase 2 architecture (ADR-001, decisions.md) is explicitly Solr-first
- qdrant-search is Phase 1 artifact, not part of Phase 2 plan
- Mixing backends breaks the migration path and creates API inconsistency

## Impact

- **PR #62** becomes the baseline for all future Phase 2 UI work
- **PR #63** (and any other UI PRs) must rebase on #62 and add features incrementally
- Prevents fragmentation: one search UI implementation, not three competing versions

## Follow-Up

1. Monitor #62 for the one-line `limit` → `page_size` fix
2. Guide #63 author to rebase and remove qdrant-search changes
3. Future frontend PRs should reference #62 as the base branch
