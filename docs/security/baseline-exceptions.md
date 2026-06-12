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

---

## CVE-2025-3000 — PyTorch `torch.jit.script` Memory Corruption (Dependabot #205)

**Status:** ACCEPTED RISK  
**Severity:** LOW (GitHub Advisory; CVSS v4 1.9)  
**Affected Service:** embeddings-server  
**Dependency Chain:** sentence-transformers 5.3.0 → torch 2.11.0  

### Vulnerability Details
PyTorch is vulnerable to memory corruption in the `torch.jit.script` function. GitHub tracks this as GHSA-rrmf-rvhw-rf47 / CVE-2025-3000 for `torch<=2.12.0`.

### Why No Patch Available
- **No fixed version exists** — Dependabot reports `first_patched_version: null`
- **Current lockfile version:** `src/embeddings-server/uv.lock` resolves torch 2.11.0
- **Vulnerable range:** `<=2.12.0`

### Mitigation
1. **No JIT/TorchScript entry point:** embeddings-server code does not import `torch` directly and repository search found no `torch.jit.script` or TorchScript usage.
2. **Text-only API surface:** `/v1/embeddings/` accepts text and passes it to `SentenceTransformer.encode`; clients cannot submit Python functions, TorchScript code, or model artifacts through the service API.
3. **Pinned offline model runtime:** The container defaults to `MODEL_NAME=intfloat/multilingual-e5-base` with `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`, so runtime does not fetch attacker-controlled model code.
4. **Container hardening:** The embeddings server runs as the non-root `app` user in the Docker image.

### Risk Assessment
- **Exploitability:** LOW — Practical exploitation would require local/trusted control over Python code or model artifacts that invoke `torch.jit.script`, not ordinary embeddings API access
- **Impact:** LOW — Advisory impact is local memory corruption with low confidentiality, integrity, and availability impact
- **Likelihood:** LOW — The service does not use the vulnerable API and runs a pinned offline model
- **Residual Risk:** ACCEPTABLE until PyTorch publishes a patched release

### Planned Remediation
- **Action:** Reopen and upgrade torch when a patched version is published.
- **Guardrail:** Reassess before adding TorchScript/JIT features or accepting untrusted model files/code in embeddings-server.

### References
- **CVE:** CVE-2025-3000
- **Dependabot Alert:** #205
- **GHSA:** GHSA-rrmf-rvhw-rf47
- **NVD:** https://nvd.nist.gov/vuln/detail/CVE-2025-3000
- **PyTorch issue:** https://github.com/pytorch/pytorch/issues/149623
