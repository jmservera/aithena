# Decision: release-screenshots artifact in integration-test workflow

**Author:** Brett (Infrastructure Architect)
**Date:** 2026-07-25
**PR:** #536
**Issue:** #531

## Context

The screenshot pipeline decision (already in `decisions.md`) specifies a separate `release-screenshots` artifact uploaded from the integration-test workflow. This is step 2 of 5 in the implementation order.

## Decision

Added two new steps to `integration-test.yml` (after the existing Playwright artifact upload):

1. **Extract release screenshots** — copies all `.png` from `test-results/` to `/tmp/release-screenshots/`
2. **Upload release screenshots** — uploads as `release-screenshots` artifact, 90-day retention

Both steps run with `if: always()`. No `${{ }}` in `run:` blocks (zizmor compliant).

## Impact

- **Downstream consumers:** `update-screenshots.yml` (step 3, not yet created) will use `workflow_run` trigger to download this artifact and commit PNGs to `docs/screenshots/` on `dev`
- **Existing artifacts:** `playwright-e2e-results` unchanged (still 30-day retention, still contains full test-results + report)
- **Storage cost:** ~500 KB additional artifact per integration test run
- **Runtime cost:** ~10 seconds (find + copy + upload)

## Team members affected

- **Newt** (release docs): Screenshots will be available in-repo once step 3 ships
- **Lambert** (CI/testing): Workflow change — review appreciated
