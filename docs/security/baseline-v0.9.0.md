# Security Baseline — v0.9.0 (Python Dependency Re-baseline)

**Document Version:** 1.0  
**Date:** 2026-03-15  
**Author:** Kane (Security Engineer)  
**Scope:** Python dependency security audit and re-baseline — all active services

## Purpose

This document supersedes the Python dependency portion of the v0.6.0 baseline. It retires stale Mend/Dependabot alerts targeting obsolete manifests (Python 3.7 wheels, removed `qdrant-*` services, pre-`uv` transitive resolutions) and establishes a current, actionable security status for the Python 3.11 production stack.

## Active Service Inventory

| Service | Runtime | Manifest | Locked |
|---------|---------|---------|--------|
| `solr-search` | Python 3.11 | `pyproject.toml` + `requirements.txt` (fallback) | `uv.lock` ✅ |
| `document-indexer` | Python 3.11 | `pyproject.toml` + `requirements.txt` (fallback) | `uv.lock` ✅ |
| `document-lister` | Python 3.11 | `pyproject.toml` | `uv.lock` ✅ |
| `admin` (Streamlit) | Python 3.11 | `pyproject.toml` + `src/requirements.txt` (fallback) | `uv.lock` ✅ | **Removed** — replaced by React admin |
| `embeddings-server` | Python 3.11 | `requirements.txt` only | ❌ no lockfile |

**Retired services (no longer in repo):**  
`qdrant-search/`, `llama-server/` — all Mend alerts referencing these paths are retired as stale.

## Audit Methodology

All manifests audited with `pip-audit` (version 2.10.0) against the PyPA advisory database. Lock files regenerated with `uv lock` after version floor updates.

```bash
pip-audit -r <service>/requirements.txt -f json
pip-audit --requirement <service>/pyproject.toml -f json
```

---

## Vulnerabilities Fixed in This Baseline

### 1. FastAPI / Starlette — solr-search

| CVE / ID | Package | Old Version | Fixed Version | Severity |
|----------|---------|-------------|---------------|----------|
| PYSEC-2024-38 | `fastapi` | 0.99.1 | ≥ 0.115.0 (locked: 0.135.1) | HIGH |
| CVE-2024-47874 | `starlette` (transitive) | 0.27.0 | ≥ 0.40.0 (locked: 0.52.1) | HIGH |
| CVE-2025-54121 | `starlette` (transitive) | 0.27.0 | ≥ 0.47.2 (locked: 0.52.1) | HIGH |

**Fix applied:** `src/solr-search/pyproject.toml`  
- `fastapi[all]` pinned from `==0.99.1` → minimum floor `>=0.115.0,<1`  
- `uvicorn[standard]` pinned from `==0.23.1` → minimum floor `>=0.30.0,<1`  
- `python-multipart` floor raised from `>=0.0.6` → `>=0.0.7` (required by fastapi ≥0.115)  
- Dev constraint `httpx<0.28` removed (updated to `>=0.27`)

`src/solr-search/requirements.txt` (fallback) updated to match.  
`uv.lock` regenerated: fastapi 0.135.1, starlette 0.52.1, uvicorn 0.41.0.  
**All 93 existing tests pass.**

---

### 2. pdfminer-six — document-indexer

| CVE / ID | Package | Old Version | Fixed Version | Severity |
|----------|---------|-------------|---------------|----------|
| CVE-2025-64512 | `pdfminer-six` (transitive via pdfplumber) | 20221105 | ≥ 20251107 | HIGH |
| CVE-2025-70559 | `pdfminer-six` (transitive via pdfplumber) | 20221105 | ≥ 20251230 | HIGH |

**Fix applied:** `src/document-indexer/pyproject.toml`  
- `pdfplumber` pinned from `==0.10.0` → minimum floor `>=0.11.9,<1`

`src/document-indexer/requirements.txt` (fallback) updated to match.  
`uv.lock` regenerated: pdfplumber 0.11.9, pdfminer-six 20251230.  
**All 91 existing tests pass (4 skipped — require maintainer file system).**

---

### 3. Pillow — admin (Streamlit) — **SERVICE REMOVED**

> **Note:** The Streamlit admin service has been removed from the codebase. The findings below are historical.

| CVE / ID | Package | Old Version | Fixed Version | Severity |
|----------|---------|-------------|---------------|----------|
| CVE-2026-25990 | `pillow` (transitive via streamlit) | 10.4.0 | ≥ 12.1.1 | HIGH |

**Fix applied:** `src/admin/pyproject.toml`  
- `streamlit` pinned from `==1.37.0` → minimum floor `>=1.51.0,<2`  
  (streamlit ≥1.51.0 ships with `pillow<13,>=7.1.0`, resolving to 12.1.1 as of this baseline)  
- Added explicit `pillow>=12.1.1` direct dependency to enforce the security floor at the manifest level, independent of streamlit's internal constraint

`src/admin/src/requirements.txt` (fallback) updated to match.  
`uv.lock` regenerated: streamlit 1.55.0, pillow 12.1.1.

---

## Accepted / Deferred Findings

### 4. py 1.11.0 — PYSEC-2022-42969 (ACCEPTED — Low Risk)

| ID | Package | Version | Severity | Disposition |
|----|---------|---------|----------|-------------|
| PYSEC-2022-42969 | `py` (transitive via `retry==0.9.2`) | 1.11.0 | LOW | **Accepted** |

**Affected services:** `document-indexer`, `document-lister`

**Vulnerability description:** `py.path.local` in `py ≤1.11.0` contains a ReDoS (Regular Expression Denial of Service) vulnerability reachable via malformed Subversion repository URLs passed to `py.path.svnwc.SvnWC`.

**Why this is accepted:**  
- `retry==0.9.2` pulls in `py` only as a dependency of its `decorator` utilities — no Subversion path handling is ever invoked in this codebase.  
- No `svn://` URLs, no `py.path.svnwc`, no `SvnWC` usage anywhere in the repository.  
- `py` 1.11.0 is the last and only release; the project was archived. No patched version exists.

**Mitigation:**  
Replace `retry==0.9.2` with `tenacity` (actively maintained, no `py` dependency) in a follow-up issue. Tracked as a **follow-up below**.

---

## Retired Stale Alerts

The following Mend/Dependabot alert classes are retired because they target manifests or services that no longer exist in this repository:

| Alert Category | Reason for Retirement |
|---------------|----------------------|
| Any alert referencing `qdrant-search/` | Service removed; directory does not exist |
| Any alert referencing `llama-server/` | Service removed; directory does not exist |
| Any alert referencing Python 3.7 wheels | Stack is Python 3.11+; 3.7 wheels never ship |
| Any alert referencing `requirements.txt` in `qdrant-search/` or `llama-server/` | Files do not exist |
| Pre-`uv` transitive resolutions (non-deterministic) | All services now use `uv.lock` for deterministic resolution |

---

## Post-Baseline Dependency Status

After all fixes, `pip-audit` reports the following status per service:

| Service | Manifest Scanned | Direct Vulns | Transitive Vulns | Status |
|---------|-----------------|--------------|-----------------|--------|
| `solr-search` | `pyproject.toml` + lock | 0 | 0 | ✅ Clean |
| `document-indexer` | `pyproject.toml` + lock | 0 | 0 | ✅ Clean |
| `document-lister` | `pyproject.toml` + lock | 0 | 1 (py, accepted) | ⚠️ Accepted |
| `admin` | `pyproject.toml` + lock | 0 | 0 | ✅ Clean |
| `embeddings-server` | `requirements.txt` | 0 | 0 | ✅ Clean |
| `e2e` | `requirements.txt` | 0 | 0 | ✅ Clean |

---

## Follow-Up Issues

The following issues should be created for the v0.9.0 / v1.0.0 roadmap:

| Priority | Issue | Affected Service | Description |
|----------|-------|-----------------|-------------|
| LOW | Replace `retry` with `tenacity` | `document-indexer`, `document-lister` | `retry==0.9.2` pulls in abandoned `py` package (PYSEC-2022-42969). Replace with `tenacity>=9.0` which has no such dependency. Requires code-level migration of `@retry` decorators. |
| LOW | Add `pip-audit` to CI pipeline | All Python services | Integrate `pip-audit` as a blocking CI check to catch new dependency CVEs before merge. |
| LOW | Add `uv.lock` to `embeddings-server` | `embeddings-server` | Only service without a lockfile. Add `pyproject.toml` + `uv.lock` to make the dependency set reproducible and auditable. |

---

## Changes Summary

| File | Change |
|------|--------|
| `src/solr-search/pyproject.toml` | `fastapi[all]` `==0.99.1` → `>=0.115.0,<1`; `uvicorn[standard]` `==0.23.1` → `>=0.30.0,<1`; `python-multipart` `>=0.0.6` → `>=0.0.7`; `httpx<0.28` → `>=0.27` |
| `src/solr-search/requirements.txt` | Same as above (fallback file) |
| `src/solr-search/uv.lock` | Regenerated: fastapi 0.135.1, starlette 0.52.1, uvicorn 0.41.0 |
| `src/document-indexer/pyproject.toml` | `pdfplumber` `==0.10.0` → `>=0.11.9,<1` |
| `src/document-indexer/requirements.txt` | Same as above (fallback file) |
| `src/document-indexer/uv.lock` | Regenerated: pdfplumber 0.11.9, pdfminer-six 20251230 |
| `src/admin/pyproject.toml` | `streamlit` `==1.37.0` → `>=1.51.0,<2`; added `pillow>=12.1.1` |
| `src/admin/src/requirements.txt` | `streamlit` `==1.37.0` → `>=1.51.0,<2`; added `pillow>=12.1.1` (fallback file) |
| `src/admin/uv.lock` | Regenerated: streamlit 1.55.0, pillow 12.1.1 |
| `src/solr-search/Dockerfile` | Changed install from `uv pip install --system -r pyproject.toml` → `uv sync --frozen --no-dev --no-install-project`; added `ENV PATH="/app/.venv/bin:${PATH}"` so production image is built from the reviewed lockfile |
