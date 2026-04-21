# Session Log: OpenVINO Regression Analysis & Smoke Test

**Date:** 2026-03-31T09:10:00Z  
**Agents:** Parker, Lambert  
**Task:** Diagnose and test OpenVINO embeddings container regression (rc.3 vs rc.23)

## Summary

**Root Cause:** Dockerfile permission change (rc.23) removed `chown -R app:app /models`, leaving model directory owned by root:root. Runtime writes (OpenVINO cache, HuggingFace cache) fail with Permission denied.

**Solution:** Parker identified three fixes (preferred: create writable cache dir). Lambert designed smoke test to catch future regressions.

**Artifacts:**
- `.squad/decisions/inbox/parker-rc-comparison.md` — 160-line root cause analysis
- `.squad/decisions/inbox/lambert-ov-smoke-test.md` — Smoke test design & rationale
- `e2e/smoke-openvino-permissions.sh` — Diagnostic test script (5 checks)
- `e2e/smoke-openvino-permissions.ci.yml` — GitHub Actions CI job

**Impact:** Unblocks Dockerfile fix PR; prevents future permission regressions via automated smoke test.
