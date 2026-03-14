### Code Scanning Alerts — GitHub API Findings
**Date:** 2026-03-14
**Author:** Kane (Security Engineer)

#### Summary
- Code scanning: 3 open alerts (medium: 3; no critical/high)
- Dependabot: 4 open alerts (critical: 2, high: 1, medium: 1)
- Secret scanning: not accessible — API returned `404 Secret scanning is disabled on this repository`
- Tool breakdown: CodeQL (3)
- Cross-reference: no overlap with prior Bandit triage; current GitHub alerts are workflow-permission hardening and dependency vulnerabilities, while prior Bandit findings were dominated by third-party `.venv` noise

#### Open Code Scanning Alerts
| # | Rule | Severity | File | Line | Description |
|---|------|----------|------|------|-------------|
| 7 | `actions/missing-workflow-permissions` | medium | `.github/workflows/ci.yml` | 18 | Workflow does not contain permissions |
| 8 | `actions/missing-workflow-permissions` | medium | `.github/workflows/ci.yml` | 41 | Workflow does not contain permissions |
| 9 | `actions/missing-workflow-permissions` | medium | `.github/workflows/ci.yml` | 68 | Workflow does not contain permissions |

#### Critical/High Code Scanning Alerts (require action)
No critical or high-severity code scanning alerts are currently open.

#### Dependabot Critical/High Snapshot
| # | Package | Severity | Location | Vulnerable Range | First Patched | Summary |
|---|---------|----------|----------|------------------|---------------|---------|
| 40 | `qdrant-client` | critical | `qdrant-search/requirements.txt` | `< 1.9.0` | `1.9.0` | qdrant input validation failure |
| 41 | `qdrant-client` | critical | `qdrant-clean/requirements.txt` | `< 1.9.0` | `1.9.0` | qdrant input validation failure |
| 44 | `braces` | high | `aithena-ui/package-lock.json` (transitive via `micromatch`) | `< 3.0.3` | `3.0.3` | Uncontrolled resource consumption in braces |

#### Additional Dependabot Context
| # | Package | Severity | Location | Vulnerable Range | First Patched | Summary |
|---|---------|----------|----------|------------------|---------------|---------|
| 43 | `azure-identity` | medium | `document-lister/requirements.txt` | `< 1.16.1` | `1.16.1` | Azure Identity Libraries and Microsoft Authentication Library Elevation of Privilege Vulnerability |

#### Recommended Actions
1. Add explicit least-privilege `permissions:` to `.github/workflows/ci.yml` at workflow or job scope so each CI job only gets the token scopes it needs; this should clear all three open CodeQL alerts.
2. Upgrade `qdrant-client` to `>=1.9.0` in both `qdrant-search/requirements.txt` and `qdrant-clean/requirements.txt`; these are the highest-risk open findings because they are critical and affect request validation.
3. Refresh `aithena-ui` dependencies/lockfile so `braces` resolves to `3.0.3+` (likely via updated transitive packages such as `micromatch`/`fast-glob`); verify the lockfile no longer pins `braces` `3.0.2`.
4. Upgrade `azure-identity` in `document-lister/requirements.txt` to `>=1.16.1` after validating compatibility with the current Azure SDK usage.
5. Enable secret scanning if repository policy allows it; current API response indicates the feature is disabled, so exposed-secret coverage is absent.
