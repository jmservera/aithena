# Security Baseline Exceptions

This document tracks security findings that have been accepted as baseline exceptions with documented risk assessment and mitigation.

## CVE-2024-23342 — ecdsa Timing Side-Channel (Dependabot #118)

**Status:** ACCEPTED RISK  
**Severity:** HIGH (CVSS 7.4)  
**Affected Service:** solr-search  
**Dependency Chain:** python-jose[cryptography] → ecdsa 0.19.1  

### Vulnerability Details
The `ecdsa` Python package (pure Python ECDSA implementation) is vulnerable to CVE-2024-23342, a timing side-channel attack (Minerva attack) that could allow private key recovery through careful measurement of signature generation timing.

### Why No Patch Available
- **No fixed version exists** — The ecdsa maintainers have explicitly stated that constant-time/side-channel-resistant cryptography is not feasible in pure Python
- **Project recommendation** — The ecdsa project's security policy advises against using this package for production security-critical operations
- **Vulnerable range:** >= 0 (all versions, including 0.19.1)

### Mitigation
1. **Runtime backend selection:** solr-search uses `python-jose[cryptography]`, which prefers the `pyca/cryptography` backend (OpenSSL-backed, side-channel hardened) over the pure Python `ecdsa` package
2. **ecdsa is fallback only:** The ecdsa package is installed as a fallback dependency but is **not used at runtime** when the cryptography backend is available
3. **Verification:** The `cryptography` package is explicitly declared in `pyproject.toml` via `python-jose[cryptography]>=3.3.0`

### Risk Assessment
- **Exploitability:** LOW — Attacker would need to observe many JWT signing operations with precise timing measurements
- **Impact:** HIGH — If exploited, could lead to JWT secret key compromise
- **Likelihood:** LOW — Runtime uses cryptography backend, not ecdsa
- **Residual Risk:** ACCEPTABLE for current use case

### Planned Remediation
- **Target:** v1.1.0 milestone (P1)
- **Action:** Replace `python-jose` with `PyJWT` library, which does not require ecdsa as a dependency
- **Issue:** #TBD (to be created)
- **Justification:** This is a larger refactor requiring auth code changes and testing; deferring to avoid blocking v1.0.1 security fixes

### References
- **CVE:** CVE-2024-23342
- **Dependabot Alert:** #118
- **GHSA:** GHSA-wj6h-64fc-37mp
- **NVD:** https://nvd.nist.gov/vuln/detail/CVE-2024-23342
- **ecdsa Security Policy:** https://github.com/tlsfuzzer/python-ecdsa/blob/master/SECURITY.md

---

**Reviewed by:** Kane (Security Engineer)  
**Date:** 2026-03-16  
**Next Review:** v1.1.0 planning (estimated 2026-04)
