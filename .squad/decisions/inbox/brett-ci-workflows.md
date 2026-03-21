# Decision: CI Workflow Design for BCDR and Stress Tests

**Author:** Brett (Infrastructure Architect)  
**Date:** 2026-07-25  
**Context:** Issues #682, #684 / PR #799  
**Status:** PROPOSED  

## Decision

Two new CI workflows added — both designed for CI environments **without Docker daemon access**:

1. **monthly-restore-drill.yml** — Validates restore scripts via `bash -n` syntax checking + `DRY_RUN=1` orchestrator execution against a mock backup directory. Creates a GitHub issue automatically on failure.

2. **stress-tests.yml** — Uses `--collect-only` (dry-run) to validate test infrastructure, always runs Locust smoke tests (no stack needed), and optionally runs full tests when `dry_run: false` (requires live stack on self-hosted runners).

## Rationale

- CI runners don't have Docker, so both workflows validate _scripts and test infrastructure_ rather than running live services.
- The restore drill uses exit code semantics: 0=pass, 2=warnings (acceptable), 1=fail.
- The stress workflow's nightly schedule is commented out per PRD §10 — enable after stabilisation.
- `workflow_dispatch` inputs make both workflows useful for on-demand validation.

## Impact

- **Lambert:** Stress test CI runs will surface collection errors early.
- **Brett:** Restore drill catches script regressions monthly.
- **All:** No PR-blocking — both are manual/scheduled only.
