# Orchestration Log: Brett — Dependabot Automerge Fix & Batch Workflow (2026-04-19T07:50Z)

**Agent:** Brett (Infra Architect)  
**Task:** Fix automerge bug + design & implement batch merge workflow  
**Status:** ✅ Completed (PR #1413 opened)  
**Output:** 2 new workflows + 1 bug fix  

## Problem Analysis

### Bug: Automerge Workflow Author Filter
- **Issue:** `dependabot-automerge.yml` filtered PRs by `author.login == "dependabot[bot]"`
- **Reality:** GitHub API returns `author.login == "app/dependabot"` for dependabot PRs
- **Impact:** 0 PRs matched; 38 dependabot PRs accumulated without action
- **Fix:** 1-line change to correct author login string

### Structural Limitation
- **Sequential merge pattern:** `workflow_run` trigger fires per PR; each merge rebases subsequent PRs
- **Scaling problem:** 35+ PRs = 6+ hours of sequential CI runs (each rebase adds 5-10 min)
- **Solution:** New batch workflow consolidates multiple PRs into single merge & CI run

## Deliverables (PR #1413)

### 1. Fixed `dependabot-automerge.yml`
- Changed: `select(.author.login == "dependabot[bot]")` → `select(.author.login == "app/dependabot")`
- Effect: Restores single-PR auto-merge for future dependabot PRs
- Scope: Applies only to Patch/Minor version bumps per triage criteria

### 2. New `dependabot-batch-merge.yml`
**Architecture:**
- **Trigger:** Manual dispatch (with dry-run option) + weekly schedule (Monday 06:00 UTC)
- **Collection Phase:** Find all open dependabot PRs on `dev`, exclude major version bumps
- **Consolidation Phase:** Create `dependabot/batch-YYYY-MM-DD` branch, merge sequentially with lockfile regeneration
  - Python services (uv): Run `uv lock` to regenerate lockfiles
  - aithena-ui (npm): Run `npm install --package-lock-only`
- **Testing Phase:** Run full `ci.yml` on consolidated branch
- **PR Phase:** Open single PR to `dev` with summary table of all included updates
- **Cleanup Phase:** Close original dependabot PRs with back-reference comment

**Key Design Decisions:**
- **Major bumps excluded:** Filtered out during collection (requires manual review per team policy)
- **Version bump:** Patch version incremented only when changes exist
- **No `--admin` flag:** All operations use standard `GITHUB_TOKEN` permissions
- **Security:** All actions pinned by SHA, minimal permissions per job, `read-all` default
- **Dry-run mode:** Workflow dispatch input to preview eligible PRs without creating branches

### 3. New `close-dependabot-batch.yml`
Separate workflow for post-merge cleanup:
- Triggered after batch PR merges to `dev`
- Closes original dependabot PRs with back-reference comment
- Prevents duplicate PRs in final cleanup

## Quality Gate Validation (Rubber Duck Review)

**4 Critical Issues Found & Fixed:**
1. ✅ Broken CI job reference → corrected to proper trigger job name
2. ✅ Premature PR closing → moved cleanup to post-merge workflow
3. ✅ Unsafe version regex → fixed to exclude pre-release versions in patch filter
4. ✅ Shell word-splitting → added proper quoting in merge loop

All fixes applied before merge.

## Alternatives Considered & Rejected

| Option | Pros | Cons | Status |
|--------|------|------|--------|
| Fix auto-merge only (no batch) | Simple, minimal changes | Doesn't solve 35-PR backlog efficiently (6+ hrs) | ❌ Rejected |
| GitHub dependabot `groups` config | Native feature, retroactive grouping | Only works at PR-creation time, can't group existing PRs | ❌ Rejected |
| Third-party batch merge actions | Pre-built solution | Security (SHA-pinning policy), project-specific lockfile needs | ❌ Rejected |
| **New batch workflow (selected)** | Solves both problems, coexists with auto-merge, project-specific | More complex initially | ✅ Chosen |

## Impact & Next Steps

**Impact:**
- CI runner time reduction: ~80% when processing multiple dependabot PRs (1 CI run vs N)
- Single review point for batch updates
- Auto-merge continues for day-to-day new PRs
- Both workflows coexist: auto-merge handles continuous PRs; batch-merge handles backlogs

**Next Steps:**
1. Review & merge PR #1413 to `dev`
2. Run batch workflow (manual dispatch or wait for Monday schedule)
3. Merge consolidated batch PR to `dev`
4. Monitor future dependabot PRs for auto-merge success

**Backlog Status (as of merge):**
- 35 PRs ready to merge (batch workflow)
- 2 PRs on hold pending manual testing (#1390, #1401)
- 1 PR closed (#1393, pre-release)

