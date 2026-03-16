# Decision: ecdsa CVE-2024-23342 Baseline Exception

**Date:** 2026-03-17  
**Decided by:** Kane (Security Engineer)  
**Context:** Issue #290, Dependabot alert #118  
**Status:** Approved (baseline exception)

## Decision

Accept CVE-2024-23342 (ecdsa Minerva timing attack, CVSS 7.4 HIGH) as a **baseline exception** with documented mitigation, rather than attempting to fix via dependency upgrade or immediate JWT library replacement.

## Context

### Vulnerability
- **Package:** `ecdsa` 0.19.1 (pure Python ECDSA implementation)
- **CVE:** CVE-2024-23342
- **Attack:** Timing side-channel attack allowing private key recovery via signature timing measurements
- **Severity:** HIGH (CVSS 7.4)
- **Affected Service:** solr-search (via `python-jose[cryptography]` transitive dependency)

### Investigation Results
1. **No patched version exists** — All ecdsa versions (>= 0) are vulnerable. Maintainers state constant-time crypto is impossible in pure Python.
2. **Upgrade attempted** — Ran `uv lock --upgrade-package ecdsa`, confirmed 0.19.1 is latest version.
3. **Runtime mitigation verified** — solr-search uses `python-jose[cryptography]`, which prefers `pyca/cryptography` backend (OpenSSL-backed, side-channel hardened) over ecdsa.
4. **Dependency analysis** — ecdsa is installed as a fallback but should not be used at runtime when cryptography is available.

## Options Considered

### Option 1: Accept Baseline Exception (SELECTED)
- **Pros:** Unblocks v1.0.1 security milestone, runtime is protected via cryptography backend, acceptable residual risk
- **Cons:** Vulnerability remains in dependency tree (scanner alerts continue)
- **Risk:** LOW exploitability, mitigated by runtime backend selection

### Option 2: Replace python-jose with PyJWT
- **Pros:** Eliminates ecdsa dependency entirely, PyJWT is actively maintained
- **Cons:** Requires auth code refactor (auth.py, tests), larger scope than P0 dependency fix, delays v1.0.1
- **Risk:** Implementation risk, testing burden, timeline impact

### Option 3: Remove JWT Authentication
- **Pros:** Eliminates vulnerability completely
- **Cons:** Breaks authentication feature (not viable)
- **Risk:** N/A (not feasible)

## Rationale

1. **No upgrade path exists** — The vulnerability cannot be fixed by upgrading ecdsa (no patched version available).
2. **Runtime mitigation is effective** — The cryptography backend (OpenSSL) is side-channel hardened and is the active backend at runtime.
3. **Exploitability is low** — Requires precise timing measurements of many JWT signing operations, difficult to execute remotely.
4. **Scope management** — Replacing python-jose is a significant refactor that should not block the v1.0.1 security milestone.
5. **Planned remediation** — This is a deferred fix, not ignored; v1.1.0 migration to PyJWT will eliminate the dependency.

## Implementation

1. **Documentation:** Created `docs/security/baseline-exceptions.md` with full risk assessment (PR #309)
2. **PR:** Squad branch `squad/290-fix-ecdsa-vulnerability` → dev (documentation only)
3. **Follow-up:** Create issue for python-jose → PyJWT migration (P1, v1.1.0 milestone)
4. **Dependabot:** Alert #118 will be resolved as "accepted risk" after PR merge

## Impact

- **Teams:** Security (Kane), Backend (Parker if PyJWT migration assigned)
- **Timeline:** Unblocks v1.0.1 milestone, defers full fix to v1.1.0
- **Users:** No user-facing impact (runtime already uses safe backend)
- **CI/CD:** Dependabot alerts will continue until python-jose replacement

## Acceptance Criteria

- [x] Baseline exception documented with risk assessment
- [x] Runtime mitigation verified (cryptography backend in use)
- [x] PR created and reviewed
- [ ] Follow-up issue created for v1.1.0 PyJWT migration (post-merge action)

## References

- **Issue:** #290
- **PR:** #309
- **Dependabot Alert:** #118
- **CVE:** CVE-2024-23342
- **GHSA:** GHSA-wj6h-64fc-37mp
- **Documentation:** `docs/security/baseline-exceptions.md`
