# Orchestration: Brett (Infra) — Create update-screenshots.yml (#532)

**Date:** 2026-03-19  
**Agent:** Brett (Infrastructure Engineer)  
**Issue:** #532  
**Mode:** background  
**Outcome:** PR #537

## Task

Create `update-screenshots.yml` workflow triggered by release-screenshots artifact completion. Download artifact, extract PNGs, commit to `docs/screenshots/` on dev branch.

## Expected Outcome

- PR #537 created and ready for review
- Workflow file: `.github/workflows/update-screenshots.yml`
- Trigger: on workflow_run (release-screenshots artifact upload completion)
- Downloads release-screenshots artifact
- Extracts PNGs to docs/screenshots/
- Commits changes to dev branch with bot identity
- Commit message references release version + artifact ID
- Rate limiting: max 1 run per 2 hours to avoid thrashing

## Dependencies

- **Blocks:** Newt #533 (PM manual updates require screenshots in docs/)
- **Depends on:** Brett #531 (artifact generation must exist)

## Status

- QUEUED: Awaiting agent execution
