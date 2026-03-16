# Orchestration Log: v1 Restructure Research & Planning
**Agent:** Ripley (Lead)  
**Session:** 2026-03-16T12:00Z  
**Task:** Research src/ restructure plan for #222

## Outcome
✅ **COMPLETE** — Produced comprehensive decision document with implementation map, path reference inventory, and risk assessment.

### Deliverables
- `.squad/decisions/inbox/ripley-src-restructure-plan.md` — 351 lines, covers:
  - Executive summary and current directory inventory
  - 9 services moving to `src/`, edge case reasoning for `installer/` staying at root
  - Detailed implementation map: 50-60 line edits across 10 files
  - Per-file breakdown (Docker Compose, buildall.sh, workflows, ruff.toml, docs)
  - Appendix with line-by-line changes
  - Risk assessment, rollback plan, testing strategy
  - Implementation sequence (5 phases)

### Status Changes
- Issue #222 → ✅ `go:yes` — decision document ready for implementation
- Issues #223, #224, #225 → ✅ `go:yes` — unblocked, validation tasks now clear

### GitHub Labels
Added `go:yes` label to orchestrated issues as per squad decision-flow conventions.

---

## Notes for Squad

**Plan quality:** Comprehensive, all edge cases identified (installer directory rationale, Dockerfile context paths, uv project resolution, `sys.path` no-change guarantee).

**Expected implementation time:** 2-3 hours (Parker to execute Phase 2-3 moves + path updates).

**Rollback:** Simple git mv reversals if any path breaks CI/CD.
