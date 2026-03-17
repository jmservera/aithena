---
updated_at: 2026-03-17T22:55:00Z
focus_area: Machine migration — retro complete, 3 unreleased milestones, preparing for Docker env
active_issues:
  - pr-393: "Correlation IDs PR needs rebase + CI + merge (v1.3.0)"
  - retro-actions: "P0: Ship v1.0.1/v1.1.0/v1.2.0 retroactively before more milestone work"
  - branch-cleanup: "66 stale remote branches need deletion"
  - integration-tests: "#343 not started (v1.3.0)"
---

# What We're Focused On

**Completed milestones (NOT YET RELEASED):**
- v1.0.1: ✅ 8/8 closed — security patch
- v1.1.0: ✅ 7/7 closed — release workflow & CI/CD
- v1.2.0: ✅ 14/14 closed — frontend quality & performance

**v1.3.0 (Backend Observability & Hardening):** 6/8 closed
- PR #393 (correlation IDs) — needs rebase onto dev, CI, merge
- #343 (integration tests) — not started

**Retrospective completed** — `.squad/decisions/inbox/ripley-retro-process-gaps.md`
Major finding: 3 milestones completed without shipping releases. No CHANGELOG, no VERSION bump, no milestones closed, no branches cleaned up, no design meetings run.

**Priority on resume:**
1. P0: Retroactively release v1.0.1, v1.1.0, v1.2.0 (tags, GitHub releases, notes, close milestones, bump VERSION)
2. P1: Clean up 66 stale branches, create CHANGELOG.md
3. P1: Merge PR #393, then dispatch #343 → close v1.3.0
4. Start v1.4.0 after v1.3.0 ships

**Decision inbox (unmerged):**
- `kane-zizmor-secrets-acceptance.md`
- `ripley-retro-process-gaps.md`

**Environment:** Moving to Docker-capable machine. New env will allow local E2E testing before pushing to GitHub Actions.

**Team:** Ripley, Parker, Dallas, Ash, Lambert, Brett, Kane, Newt, Copilot, Juanma (PO)

