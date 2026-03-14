# Round 6 — Merges + Triage (2026-03-14T18:30:00Z)

## Summary

Two PRs merged to `dev`. Nine issues triaged and relabeled. Three new @copilot PRs retargeted from default branch to `dev` branch. Root cause identified: repo default branch is `jmservera/solrstreamlitui`, not `dev`.

## PRs Merged to `dev`

| # | Title | Branch | Mode | Result |
|---|-------|--------|------|--------|
| #142 | UV docs | `feat/uv-docs` | Squash | ✅ Merged by Coordinator |
| #137 | Return page numbers in search results | `feature/page-ranges` | Squash | ✅ Rebased (64 tests pass), merged by Parker |

## Issues Triaged (9 total)

**Closed (Issue + PR):** #96, #134

**Reassigned to @copilot (3 issues):**
- #139 — Clean up smoke test artifacts (🟢 simplest — file deletion only)
- #95 — LINT-4: Replace pylint/black with ruff (🟢 single directory)
- #100 — LINT-6: Run eslint + prettier auto-fix (🟢 single directory)

**Assigned to squad members (6 issues):**
- #99 (Parker) — LINT-5: Multi-directory ruff auto-fix
- #114 (Parker) — P4: Add /v1/status/ endpoint
- #135 (Dallas) — Open PDF viewer at specific page
- #122 (Dallas) — P4: Build Status tab (blocked on #120, #114)
- #121 (Dallas) — P4: Build Stats tab (blocked on #120)
- #92 (Brett) — UV-8: Update buildall.sh and CI (blocked on UV-1…UV-7)

**Triage method:** Ripley removed all stale `squad:*` and `go:needs-research` labels, then applied fresh routing per team capabilities.

## PRs Retargeted to `dev`

| # | Title | Author | From | To | Method | Result |
|---|-------|--------|------|----|----|--------|
| #146 | N/A | @copilot | `jmservera/solrstreamlitui` (default) | `dev` | `gh pr edit --base dev` | ✅ Retargeted |
| #147 | N/A | @copilot | `jmservera/solrstreamlitui` (default) | `dev` | `gh pr edit --base dev` | ✅ Retargeted |
| #148 | N/A | @copilot | `jmservera/solrstreamlitui` (default) | `dev` | `gh pr edit --base dev` | ✅ Retargeted |

## Root Cause: Default Branch Mismatch

**Finding:** @copilot consistently targets the repo's default branch (`jmservera/solrstreamlitui`) regardless of `copilot-instructions.md` branch rules.

**Why:** GitHub's REST API defaults to the repository's default branch when creating PRs if no explicit base is specified.

**Impact:** Manual retargeting required until default branch is changed to `dev`.

**Recommendation:** Update repository settings: default branch → `dev`.

## Decisions Recorded

- **Decision:** Merge decision inbox into `decisions.md`
- **Status:** Pending scribe commit

## Next Phase

- @copilot begins batch 1 (3 sequential issues: #139, #95, #100)
- Parker assigns to #99, #114
- Dallas assigns to #135, #122, #121
- Brett holds #92 pending UV-1…UV-7 completion
- Coordinator changes repo default branch to `dev`
