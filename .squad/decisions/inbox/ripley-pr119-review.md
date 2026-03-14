# Ripley — PR #119 Review (Status Endpoint)

**Date:** 2026-07-14
**PR:** #119 "Add GET /v1/status/ endpoint to solr-search"
**Author:** @copilot
**Issue:** #114
**Verdict:** ❌ NEEDS CHANGES — scope bloat, performance issues

## Decision

PR #119 requested changes for two categories of issues:

### Scope
The PR touches 108 files but the issue (#114) only requires `solr-search/` changes. The branch includes ~500 lines of unrelated frontend code (react-router-dom, TabNav, 4 page components, App.tsx rewrite) — this is the UI router architecture from rejected PR #128 re-introduced into a backend PR. Also deletes a squad decision file. Must rebase on dev and strip UI changes.

### Implementation
The status endpoint design is correct (response shape, graceful degradation, TCP health checks, test coverage), but:
1. `r.keys()` is a blocking O(N) Redis operation — must use `scan_iter()`
2. Individual `r.get()` per key — must use `mget()` or pipeline
3. Creates new Redis connection per request — should use a connection pool
4. Solr status always returns `"ok"` even when unreachable — should reflect actual health

## Pattern Reinforcement

This is another instance of the stale-branch + scope-creep pattern. The copilot agent branched from an old commit, manually synced files (creating a 108-file diff), and bundled unrelated UI work into a backend PR. Detection signal: check the `--stat` for changes outside the expected service directory.
