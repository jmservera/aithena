# Orchestration Log: Lambert Smoke Test Design

**Timestamp:** 2026-03-31T09:10:00Z  
**Agent:** Lambert (Tester)  
**Task:** Design and create OpenVINO permissions smoke test  
**Outcome:** ✅ Complete

## Work Completed

### Smoke Test Design
Created a dedicated smoke test suite for OpenVINO embeddings container permissions validation:

**Test Coverage (5 checks):**
1. Model directory exists and is readable
2. model_cache is writable for app user (uid 1000)
3. UID audit (verify container runs as app user)
4. Health endpoint liveness with BACKEND=openvino DEVICE=cpu
5. Embedding inference returns correct 768-dim vectors

### Deliverables

**Script:** `e2e/smoke-openvino-permissions.sh`
- Shell script with 5 diagnostic checks
- Captures container user, directory permissions, API responses
- Provides clear pass/fail output for CI/CD integration

**CI Job Snippet:** `e2e/smoke-openvino-permissions.ci.yml`
- GitHub Actions workflow job definition
- Runs in parallel with existing smoke tests (~3-4 min runtime)
- Auto-creates GitHub Issue on failure with root cause documentation
- Requires `issues: write` permission on pre-release workflow

**Decision File:** `.squad/decisions/inbox/lambert-ov-smoke-test.md`
- Rationale: Catches silent permission regressions early
- Impact: Reduces MTTR — auto-issue with root cause = immediately actionable fix

## Integration Points

- **Existing Smoke Tests:** Runs in parallel (no bloat to matrix)
- **Pre-release Workflow:** Requires adding to `pre-release.yml`
- **Permission Regression:** Immediately catches if Dockerfile chown is removed
- **Parker's Analysis:** Auto-issue will reference root cause findings

## Next Steps for Team

1. Add `e2e/smoke-openvino-permissions.ci.yml` job to `.github/workflows/pre-release.yml`
2. Grant `issues: write` permission on pre-release workflow
3. After Dockerfile fix is deployed, this test validates the fix works
