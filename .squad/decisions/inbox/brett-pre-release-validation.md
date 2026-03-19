# Decision: Pre-release Validation Workflow

**Author:** Brett (Infrastructure Architect)
**Date:** 2026-07-25
**Status:** IMPLEMENTED
**PR:** #544 (Closes #542)

## Context

The team needed an automated pre-release check that builds the full Docker Compose stack, runs E2E tests, and scans container logs for issues before tagging a release. Ripley's design proposal outlined 9 finding categories and a two-job workflow pattern.

## Decision

Implemented two artifacts:

1. **`e2e/pre-release-check.sh`** — POSIX-compatible log analyzer that scans Docker Compose logs for 9 categories: crash/fatal, deprecation, version mismatch, slow startup, connection retries, security, memory pressure, configuration, and dependency issues. Outputs a JSON array of findings. Exit code 0=clean, 1=errors, 2=warnings.

2. **`.github/workflows/pre-release-validation.yml`** — `workflow_dispatch` workflow with `milestone` input. Two jobs: `build-and-test` (build stack, run E2E, gather logs, run analyzer) and `create-issues` (create GitHub issues based on findings). On errors: single issue. On warnings: one issue per category routed to the responsible squad member.

## Category → Squad Routing

| Category | Squad Member | Rationale |
|---|---|---|
| crash, security | squad:kane | Security domain |
| deprecation, dependency, slow_startup, memory, config, version | squad:brett | Infrastructure domain |
| connection | squad:parker | Backend domain |

## Impact

- **Release process:** Trigger this workflow before tagging any release to catch container-level issues
- **All team members:** May receive auto-created issues from findings
- **CI:** Adds ~30-60 min workflow run (full stack build + E2E + analysis)
- **Existing workflows:** No changes to `integration-test.yml`; patterns reused but not modified
