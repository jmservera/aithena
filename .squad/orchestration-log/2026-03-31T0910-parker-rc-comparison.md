# Orchestration Log: Parker RC Comparison Analysis

**Timestamp:** 2026-03-31T09:10:00Z  
**Agent:** Parker (Backend Dev)  
**Task:** Deep comparison of OpenVINO embeddings container rc.3 vs rc.23  
**Outcome:** ✅ Complete

## Work Completed

### Root Cause Identified
The regression is caused by a **Dockerfile change that removed `chown` from `/models`**:
- **rc.3:** `RUN chown -R app:app /app /models` (all files owned by app:app)
- **rc.23:** `RUN chown -R app:app /app && chmod -R a+rX /models` (only /app chown'd; /models stays root:root)

### Permission Regression Details
- `/models/` ownership changed from `app:app 755` → `root:root 755`
- All model files and subdirectories ownership changed to root:root
- Result: Any runtime write to `/models` fails with "Permission denied"
- OpenVINO and HuggingFace caching at runtime will fail in rc.23

### Analysis Scope
Compared 10 dimensions between rc.3 and rc.23:
1. ✅ File permissions (PRIMARY FINDING)
2. ✅ Process user (identical)
3. ✅ Dockerfile layers (root cause)
4. ✅ Directory ownership (regression)
5. ✅ Python code (model_utils.py improvements, not cause of regression)
6. ✅ Model cache state (neither has pre-built cache)
7. ✅ Python packages (all identical versions)
8. ✅ Writable directories (32+ in rc.3, zero in rc.23 under /models)
9. ✅ Environment variables (identical)
10. ✅ Dockerfile analysis (explained the rationale: avoid 5GB layer duplication)

## Deliverables

**Decision File:** `.squad/decisions/inbox/parker-rc-comparison.md`
- 160 lines of detailed findings
- Root cause summary with contributing factors
- Three recommended fixes (with rationale)

## Recommended Fixes (in priority order)
1. **Create a writable cache directory** — targeted, no bloat
2. **Make only directory inodes writable** — avoid full chown
3. **Revert to full chown** — simplest, acceptable if layer size OK

## Impact

This analysis provides the root cause documentation for:
- PR targeting the embeddings-server Dockerfile fix
- Lambert's OpenVINO smoke test validation
- Future permission-related regressions
