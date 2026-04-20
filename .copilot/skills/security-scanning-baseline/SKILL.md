---
name: "security-scanning-baseline"
description: "Configure and triage Bandit, Checkov, and zizmor security scanners with baseline exceptions for aithena"
domain: "security, SAST, IaC scanning, supply chain"
confidence: "high"
source: "earned — Kane implemented SEC-1 through SEC-5, triaged all findings through v1.10.0"
author: "Kane"
created: "2026-07-25"
last_validated: "2026-07-25"
---

## Context

Aithena runs three security scanners in CI, all non-blocking with SARIF upload to GitHub Code Scanning. This skill covers configuration, baseline exceptions, and triage workflow.

## Scanner Configuration

### Bandit (Python SAST)
- **Config:** `.bandit` (centralized, not CLI flags)
- **Workflow:** `.github/workflows/security-scanning.yml` (bandit-scan job)
- **Mode:** `--exit-zero` + `continue-on-error: true` (non-blocking)
- **Output:** SARIF → GitHub Code Scanning + artifact (30-day retention)
- **Permissions:** `security-events: write`

**Baseline skip rules (`.bandit`):**
| Rule | Reason |
|------|--------|
| B101 | pytest assert statements |
| B104 | 0.0.0.0 binding in containers (intentional) |
| B105/B106/B108 | Test data false positives |
| B603/B607 | subprocess in tests (list args, no shell=True) |

**Exclusions:** `.venv`, `site-packages`, `node_modules` — always exclude to avoid third-party noise.

### Checkov (IaC)
- **Config:** `.checkov.yml`
- **Workflow:** `.github/workflows/security-scanning.yml` (checkov-scan job)
- **Scope:** Dockerfiles + GitHub Actions workflows
- **Limitation:** Cannot scan `docker-compose.yml` — use manual IaC checklist in OWASP ZAP guide instead

### Zizmor (GitHub Actions Supply Chain)
- **Config:** `.zizmor.yml` (baseline exceptions)
- **Workflow:** `.github/workflows/security-scanning.yml` (zizmor-scan job)
- **Action:** `zizmorcore/zizmor-action@v0.1.1`
- **Triggers:** Push/PR to dev/main, path filter: `.github/workflows/**`
- **Focus:** template-injection, dangerous-triggers, secrets-outside-env

## Triage Workflow

### Step 1: Classify Severity
| Severity | Action |
|----------|--------|
| CRITICAL/HIGH | Must fix OR documented baseline exception with runtime mitigation |
| MEDIUM/LOW | Baseline exception acceptable if low exploitability |
| False positive | Dismiss with `noqa` + inline rationale comment |

### Step 2: For False Positives
Add inline suppression with rationale:
```python
import subprocess  # noqa: S404 — used for git operations with list args, never shell=True
```
**Key:** The comment IS the documentation. Never suppress silently.

### Step 3: For Real Findings
1. Fix if trivial (even false positives — defense-in-depth principle)
2. If no fix available, document in `docs/security/baseline-exceptions.md`:
   - CVE ID, severity, affected package, dependency chain
   - Runtime mitigation (e.g., "cryptography backend used, not pure-Python ecdsa")
   - Deferred fix plan (e.g., "replace python-jose with PyJWT in v1.1.0")

### Step 4: For Stale Alerts
Code Scanning doesn't re-scan automatically after fixes merge. To close stale alerts:
- Push a commit to trigger re-scan
- Or manually trigger the security workflow

## Anti-Patterns
- **Don't use CLI flags instead of config files** — centralized config is auditable and maintainable
- **Don't suppress without rationale** — bare `noqa: S404` tells future reviewers nothing
- **Don't ignore false positives entirely** — apply defense-in-depth fix if trivial (e.g., removing exception chaining costs nothing)
- **Don't scan .venv directories** — generates hundreds of third-party findings that drown real issues

## Scope
Applies to: all CI security workflows, all Python services, all Dockerfiles
Files: `.bandit`, `.checkov.yml`, `.zizmor.yml`, `.github/workflows/security-*.yml`, `docs/security/baseline-exceptions.md`
