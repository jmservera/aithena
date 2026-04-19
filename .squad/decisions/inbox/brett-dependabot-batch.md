# Decision: Dependabot Batch Merge Workflow

**Author:** Brett (Infra Architect)  
**Date:** 2026-04-19  
**Status:** Proposed

## Problem

The existing `dependabot-automerge.yml` workflow had two issues:

1. **Bug:** Author login filter checked `dependabot[bot]` but the correct value from `gh pr list --json author` is `app/dependabot`. This meant zero PRs ever matched — 38 PRs piled up.
2. **Structural:** The `workflow_run` trigger processes PRs one at a time. Each merge changes `dev`, requiring the next PR to rebase before CI can run. With 35+ PRs, this creates a multi-hour sequential pipeline.

## Solution

### Fix 1: Author login (1-line fix)

Changed `select(.author.login == "dependabot[bot]")` to `select(.author.login == "app/dependabot")` in `dependabot-automerge.yml`. This restores the single-PR auto-merge flow for future PRs.

### Fix 2: New batch merge workflow (`dependabot-batch-merge.yml`)

A new workflow that consolidates multiple dependabot PRs into a single merge:

**Architecture:**
- **Trigger:** Manual dispatch (with dry-run option) + weekly schedule (Monday 06:00 UTC)
- **Phase 1 — Collect:** Find all open dependabot PRs targeting `dev`, filter out major version bumps
- **Phase 2 — Consolidate:** Create `dependabot/batch-YYYY-MM-DD` branch from `dev`, merge each PR branch sequentially with lockfile conflict resolution
- **Phase 3 — Test:** Run the full CI suite (`ci.yml`) on the consolidated branch
- **Phase 4 — PR:** Open a single PR to `dev` with summary table of all included updates
- **Phase 5 — Cleanup:** Close original dependabot PRs with back-reference comment

**Key design decisions:**
- **Major bumps excluded:** Filtered out during collection; these require manual review per existing team policy
- **Lockfile conflict resolution:** For Python services using uv, runs `uv lock` to regenerate. For npm (aithena-ui), runs `npm install --package-lock-only`
- **VERSION bump:** Patch version incremented only when changes exist (e.g., 1.18.1 → 1.18.2)
- **No `--admin` flag:** All operations use standard `GITHUB_TOKEN` permissions
- **Security patterns preserved:** All actions pinned by SHA, minimal permissions per job, `read-all` default
- **Dry-run mode:** `workflow_dispatch` input to preview eligible PRs without creating branches

## Alternatives Considered

1. **Fix auto-merge only, no batch workflow:** Would work for future PRs but doesn't solve the backlog problem efficiently. Sequential rebase-and-merge of 35 PRs would take 6+ hours of CI time.
2. **GitHub's native dependabot grouped updates:** Dependabot supports `groups` in config, but it creates grouped PRs at PR-creation time — it cannot retroactively group existing PRs.
3. **Third-party batch merge actions:** Evaluated but rejected for security (SHA-pinning policy) and because our lockfile regeneration needs are project-specific.

## Impact

- Reduces CI runner time by ~80% when processing multiple dependabot PRs (1 CI run vs N)
- Single review point for batch updates
- Preserves the existing single-PR auto-merge flow for day-to-day updates
- Both workflows can coexist: auto-merge handles new PRs promptly, batch-merge handles backlogs
