# Ralph Round 3 — Conflict Recovery

**Timestamp:** 2026-05-31T17:50Z  
**Agent:** Ralph (Dependabot Orchestrator) + Copilot (Reviewer)  
**Issue:** Manifest file conflict during batch merge + manual intervention

## The Gotcha

When merging multiple dependabot branches that touched the same manifest/lockfile (package.json, pyproject.toml), naive conflict resolution with `git checkout --theirs` **CLOBBERED previously merged bumps**:

- **dep-1602's pyproject.toml:** Taking `--theirs` reverted #1601 uvicorn bump and #1596 pika bump
- **dep-1597's package.json:** Taking `--theirs` reverted #1594, #1595, #1599, #1600 npm bumps

**Result:** 6 bumps silently disappeared from batch PR #1608.

## Detection & Recovery

Copilot code reviewer caught uvicorn revert during PR review. Identified pattern: all 6 reverted bumps were from earlier merged PRs (overlapping same manifest files).

**Fix commit:** 4fd7ed3

```
chore: restore reverted bumps from earlier PRs

Re-apply bumps from #1601 (uvicorn), #1596 (pika), #1594/#1595/#1599/#1600 (npm)
which were clobbered by naive --theirs conflict resolution during batch merge.
Run local verify: 1094 backend + 841 UI tests pass.
```

### Manual Reconciliation Steps

1. Extract all 6 bumps from prior commits
2. Reapply to conflicted files (pyproject.toml, package.json)
3. Regenerate lockfiles (uv lock, npm ci)
4. Run verify.sh locally — confirm all tests pass before pushing

## Learning Captured

See `.squad/skills/dependabot-batch-merge/SKILL.md` for the recommended pattern:
- **Never** use `git checkout --theirs` for multi-branch batching
- Instead: (a) take incoming bump, (b) re-apply ALL prior bumps, (c) regenerate lockfile, or
- Better: use 3-way merge on bump entries, not file replacements
