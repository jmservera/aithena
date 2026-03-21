# Decision: Branch Hygiene Rule (R1)

**Author:** Ripley (Lead)
**Date:** 2026-03-20
**Status:** APPROVED
**Source:** v1.10.0 Wave 0/1 Retrospective — Action Item R1

## Context

During Wave 0, multiple cross-branch contamination incidents occurred: auth cookie changes leaked into unrelated PRs, backup script files appeared on wrong branches, and documentation commits landed on incorrect branches. Root cause: agents created branches from a polluted local working tree instead of clean `origin/dev`.

## Rule

**All agents must follow this exact sequence when creating a new branch:**

```bash
git fetch origin
git status              # must show clean working tree
git checkout -b <branch-name> origin/dev
```

### Prohibited

- `git checkout -b <branch> dev` — local `dev` may be stale or dirty
- `git checkout -b <branch>` — branches from current HEAD, which may contain other agents' work
- Creating a branch with uncommitted changes in the working tree

### Enforcement

- Agents must verify `git status` shows a clean working tree before branching
- PR reviewers should check `git diff --stat origin/dev` for unrelated files
- If contamination is detected, the branch must be recreated from `origin/dev`

## Impact

All squad agents. This rule is non-negotiable — no exceptions.
