# Orchestration Log: Ripley (Lead)

**Date:** 2026-03-19T12:48Z  
**Agent:** Ripley  
**Task:** Design pre-release integration test process

## Outcome

✅ **COMPLETED** — Full process design documented and ready for implementation.

**Deliverable:** Pre-release validation workflow proposal + e2e log analyzer design.

## Design Summary

### New Workflow: `pre-release-validation.yml`

**Trigger:** Manual (`workflow_dispatch`)  
**Inputs:** Milestone name (e.g., "v1.8"), release tag (e.g., "v1.8.0")

**Pipeline:**
1. Run full integration test suite (Playwright e2e tests)
2. Run Python service tests (all 4 backends)
3. Analyze test logs for 9 finding categories:
   - **Flaky tests** — high retry counts
   - **Slow tests** — >5 second test duration
   - **Browser crashes** — Playwright quit unexpectedly
   - **Service restarts** — container crash loops
   - **Dependency timeouts** — Redis, RabbitMQ, Solr unavailable
   - **Permission errors** — EACCES on file operations
   - **Memory pressure** — OOM kills, heap exhaustion
   - **Database deadlocks** — SQLite lock contention
   - **Port conflicts** — Address already in use

4. Auto-create GitHub issues based on finding severity:
   - **🔴 FAILURE** → Issue template `pre-release-failure-CATEGORY.md`
   - **🟡 WARNING** → Issue template `pre-release-warning-CATEGORY.md`
   - **🟢 SUCCESS** → Single success summary issue

### Log Analyzer Design

Tool: `e2e/pre-release-check.sh` (Bash + regex)

**Categories analyzed:**
- Test runner output (pytest, Vitest logs)
- Docker Compose logs (solr-search, embeddings-server, etc.)
- Browser logs (Playwright stderr)
- System logs (dmesg excerpt for OOM, permission errors)

**Output:**
- Summary JSON (category counts, severity distribution)
- Per-category detail files (examples of each finding)
- Pass/fail exit code

## Issue Templates

Created 11 issue templates in `.github/ISSUE_TEMPLATE/`:
- `pre-release-failure-flaky-tests.md`
- `pre-release-failure-browser-crash.md`
- `pre-release-failure-service-restart.md`
- ... (8 total failure categories)
- `pre-release-warning-slow-tests.md`
- `pre-release-warning-dependency-timeout.md`
- ... (4 total warning categories)
- `pre-release-success.md`

Each template includes:
- Reproduction steps
- Expected vs. actual
- Suggested fix approach
- Links to logs/artifacts

## Impact & Next Steps

### Phase 2: Implementation

1. **@brett** — Create `pre-release-validation.yml` workflow skeleton in `.github/workflows/`
2. **@ripley** — Implement `e2e/pre-release-check.sh` log analyzer
3. **Integration** — Validate with mock test run (pass + fail scenarios)

### Phase 3: Release Process

Before any release:
1. Run `pre-release-validation.yml` manually
2. Review auto-created issues
3. Merge passing PRs, escalate failures to sprint
4. Tag + release only after 🟢 SUCCESS

### Who Benefits

- **Release lead** (Newt): Confidence that pre-release suite passed
- **Team** (all): Automatic discovery of flaky tests, performance regressions
- **Future oncalls**: Reduced post-release rollback risk

## Design Rationale

- **9 categories:** Covers most common dev-to-prod failure modes (not exhaustive)
- **Issue auto-creation:** Forces visibility; bypasses "we'll look at logs later" pattern
- **Failure vs. warning tier:** Non-blocking warnings don't prevent release; blockers must be fixed
- **Manual trigger:** Intentional — prevents CI spam; release lead decides when to validate

## Issues Created

#543 — Track implementation progress (assigned to @brett + @ripley for phases 2–3)
