# Orchestration Log: Brett (Infrastructure Architect) — Screenshot Pipeline Review

**Timestamp:** 2026-03-18T22:41Z  
**Agent:** Brett  
**Role:** Infrastructure Architect  
**Task:** Review integration-test workflow for screenshot pipeline  
**Mode:** Background  
**Status:** Completed ✅

---

## Outcome

**Decision filed:** `.squad/decisions/inbox/brett-screenshot-pipeline.md`

### Selected Approach: Option B — `workflow_run`-Triggered Screenshot Commit Workflow

---

## Architecture Overview

```
Integration Test (existing)
  ├── Builds Docker Compose stack
  ├── Runs Playwright → screenshots in test-results/
  ├── Uploads artifact: playwright-e2e-results (existing)
  └── Uploads artifact: release-screenshots (NEW, screenshots only)
        │
        ▼  (workflow_run trigger, on success)
Update Screenshots (NEW workflow)
  ├── Downloads release-screenshots artifact
  ├── Commits to docs/screenshots/ on dev
  └── Done (~2 min)
        │
        ▼  (already in repo when release happens)
Release-Docs (existing)
  ├── Checks out dev (screenshots already there)
  ├── Copilot CLI (Newt) can reference docs/screenshots/
  └── Screenshots included in release docs PR
```

---

## Implementation Plan

### 1. Changes to `integration-test.yml`
- Extract release screenshots (4 PNGs) after test run
- Upload separate `release-screenshots` artifact (~500 KB, 90 days retention)
- Runs only on success, minimal overhead (+10 seconds)

### 2. New Workflow: `.github/workflows/update-screenshots.yml`
- Triggered by `workflow_run` when Integration Test completes successfully
- Downloads screenshots artifact, commits to `docs/screenshots/` on `dev`
- Branch filter: Only commits when integration test ran against `main`
- Idempotent: Avoids empty commits when screenshots unchanged
- Runtime: ~2 minutes

### 3. Repo Setup
- Create `docs/screenshots/.gitkeep` (pre-create directory)
- Add `docs/screenshots/README.md` documenting auto-generation

### 4. Optional Enhancement
- Update `release-docs.yml` to mention screenshot locations in Copilot CLI prompt

---

## Options Evaluated

### Option A: Integration test commits directly
- **Rejected** — Widens attack surface (needs write access), creates commit noise on every scheduled run

### Option B: `workflow_run`-triggered workflow ✅ SELECTED
- Clean separation of concerns
- Integration test stays read-only
- Only runs on success
- Lightweight (~2 min)

### Option C: Release-docs builds and screenshots from scratch
- **Rejected** — Duplicates 60-min Docker build cycle, violates DRY

### Option D: Release-docs downloads artifact cross-workflow via API
- **Rejected** — Fragile (artifact expiry after 30 days), Option B strictly better

---

## Cost/Performance Analysis

### Runtime Impact
- Integration test: +10 seconds (copy 4 PNGs + upload artifact)
- New workflow: ~2 minutes total (ultra-lightweight)
- Release-docs: No additional runtime

### Artifact Storage
- Current: `playwright-e2e-results` artifact (unchanged, ~50–200 MB, 30 days)
- New: `release-screenshots` artifact (~500 KB, 90 days)
- Committed screenshots: ~500 KB in git (updated infrequently)

### Docker Build Optimization (Separate Initiative)
- BuildKit layer caching: Expected savings 10–15 min
- Pre-built base images: Expected savings 5–10 min
- **Recommendation:** File separate issue (ties into v1.7.1 Docker optimization spec)

---

## Security Considerations

- **Integration test stays read-only** — No permissions change needed
- **New workflow has `contents: write`** — Required for git push, scoped to `workflow_run` event (safe from fork-based attacks)
- **Direct push to `dev`** — Auto-generated PNGs only (no code)

---

## Implementation Order

1. Create `docs/screenshots/` directory with README
2. Add screenshot extraction + upload step to `integration-test.yml`
3. Create `update-screenshots.yml` workflow
4. Update Copilot CLI prompt in `release-docs.yml` (optional)
5. Verify end-to-end via manual integration test trigger

---

## References

- Full decision: `brett-screenshot-pipeline.md`
- Related: Newt's screenshot strategy (`newt-screenshot-strategy.md`)
- Integration test workflow: `.github/workflows/integration-test.yml`
- Screenshot spec: `e2e/playwright/tests/screenshots.spec.ts`
