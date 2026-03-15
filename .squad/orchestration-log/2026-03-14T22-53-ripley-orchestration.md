# Ripley — v0.5 Planning & Issue Verification

**Agent:** Ripley (Lead)  
**Date:** 2026-03-14T22:53  
**Task:** Verify closed Phase 3 issues, review specs, identify gaps, plan copilot assignment  
**Status:** ✅ COMPLETED

## Outcome

### Verification Completed
- ✅ All 5 closed Phase 3 issues verified as production-ready on `dev` branch
- ✅ All backend features confirmed delivered and tested

### v0.5 Scope Identified
**Issue #163** — Search mode selector in React UI (NEW GAP IDENTIFIED)
- Backend supports 3 search modes (keyword, semantic, hybrid)
- UI has no way to switch between modes
- Semantic/hybrid search invisible to users
- Scope: Add mode selector component + useSearch hook update

### Assignment to @copilot
Assigned to copilot with capability ratings:
- #41 (Frontend test coverage) — 🟢 Good fit
- #47 (Similar books UI) — 🟡 Needs review
- #163 (Search mode selector) — 🟢 Good fit

### Merge Plan
```
Batch 1 (parallel):
  #41 (tests) 
  #163 (mode selector)

Batch 2 (after Batch 1):
  #47 (similar books)
```

## Key Decisions Deferred

Merge cadence, search mode default, and scope freeze were recorded as autonomous decisions by Squad Coordinator (see `.squad/decisions/inbox/coordinator-v05-decisions.md`).

## Follow-up

All issues tracked in GitHub v0.5 milestone. Copilot can begin work immediately on Batch 1 issues.
