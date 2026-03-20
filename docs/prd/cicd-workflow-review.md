# PRD: CI/CD Workflow Review & Consolidation

_Date:_ 2026-03-20
_Prepared by:_ Squad (Ralph — Team Lead)
_Milestone:_ v1.10.0

## 1. Problem Statement

Aithena has 16 GitHub Actions workflow files that have grown organically. A comprehensive audit reveals **duplicate test runs**, **unused workflows**, **non-blocking security scans**, and a **fragile release pipeline** that does not enforce the team's dev → main → tag release process. The pre-release validation workflow has never been run automatically. Several workflows have overlapping responsibilities, and the integration/E2E test suite has reliability issues (rate limiting, Solr cluster race conditions) that block merges to main.

## 2. Current State — Workflow Inventory

### Testing Workflows

| Workflow | Trigger | What it tests | Required? |
|----------|---------|---------------|-----------|
| **ci.yml** | push/PR to `dev` | Unit tests (6 services), Ruff lint, frontend lint+build | ✅ Yes (`all-tests-passed`) |
| **lint-frontend.yml** | push/PR to `dev` (aithena-ui paths only) | ESLint + Prettier | ❌ No (duplicate of ci.yml) |
| **dependabot-automerge.yml** | PR opened/synced (ALL branches) | Unit tests (4 services), frontend tests, stub security | ❌ No |
| **integration-test.yml** | PR to `main`, schedule (3am Mon–Fri), manual | Docker Compose E2E + Playwright | ❌ No (but blocks main merges in practice) |
| **pre-release-validation.yml** | Manual only (workflow_dispatch with milestone) | Full E2E + log analysis + auto-issue creation | ❌ No (never triggered automatically) |

### Security Workflows

| Workflow | Trigger | Tool | Blocking? |
|----------|---------|------|-----------|
| **security-bandit.yml** | push/PR to `dev` or `main` | Bandit SAST → SARIF | ❌ Non-blocking (`continue-on-error`) |
| **security-checkov.yml** | push/PR to `dev` or `main` | Checkov IaC (Dockerfiles + Actions) | ❌ Non-blocking (`soft-fail`) |
| **security-zizmor.yml** | push/PR to `dev` or `main` | zizmor supply-chain scan (Actions) | ❌ Non-blocking (`continue-on-error`) |

### Release Workflows

| Workflow | Trigger | What it does |
|----------|---------|-------------|
| **release.yml** | Tag push `v*.*.*` | Build Docker images → GHCR, create GitHub Release |
| **release-docs.yml** | Tag push `v*.*.*` or manual | Generate release docs via Copilot CLI, open PR |
| **update-screenshots.yml** | After integration-test completes on `main` | Commit Playwright screenshots to `dev` |
| **version-check.yml** | PR to `dev`/`main` (VERSION or Dockerfile changes) | Validate VERSION file + Dockerfile ARGs |

### Squad Automation

| Workflow | Trigger | What it does |
|----------|---------|-------------|
| **squad-heartbeat.yml** | Issue closed/labeled, PR closed, manual | Ralph triage: auto-label, route issues, Dependabot tracking |
| **squad-issue-assign.yml** | Issue labeled `squad:*` | Assign work to squad member + Copilot agent |
| **squad-triage.yml** | Issue labeled `squad` | Route to squad member based on keywords |
| **sync-squad-labels.yml** | Push to `team.md`, manual | Create/update repo labels from team roster |

## 3. Issues Found

### 🔴 Critical — Must Fix

#### 3.1 No Enforced Release Pipeline
The team's release process (dev → main → tag) is not enforced by any workflow. Tags were historically created on `dev` without merging to `main`. There is no automated gate that prevents releasing without passing integration tests.

**Proposed fix:** Add a required integration test check for PRs to `main`. The pre-release-validation workflow should be triggered automatically (or as a required step) during the dev → main merge process.

#### 3.2 Dependabot Auto-Merge Has No Branch Filter
`dependabot-automerge.yml` triggers on `pull_request` with no branch filter — it could auto-merge Dependabot PRs to any branch.

**Proposed fix:** Add `branches: [dev]` filter.

#### 3.3 Security Scans Are Non-Blocking
All three security workflows (`bandit`, `checkov`, `zizmor`) use `continue-on-error: true` or `--soft-fail`. Findings appear in the Security tab but never prevent merges. This means a critical vulnerability could be merged without anyone noticing.

**Proposed fix:** Make Bandit a required check (it's the most actionable for Python code). Keep Checkov and zizmor as advisory but add workflow summary annotations.

### ⚠️ High Priority — Should Fix

#### 3.4 Duplicate Test Coverage
Backend unit tests run in **both** `ci.yml` and `dependabot-automerge.yml`. Frontend lint runs in **both** `ci.yml` and `lint-frontend.yml`. This wastes CI minutes and can produce confusing status check results.

| Test | ci.yml | dependabot-automerge.yml | lint-frontend.yml |
|------|--------|--------------------------|-------------------|
| document-indexer pytest | ✅ | ✅ | — |
| solr-search pytest | ✅ | ✅ | — |
| document-lister pytest | ✅ | ✅ | — |
| embeddings-server pytest | ✅ | ✅ | — |
| Frontend ESLint | ✅ | ✅ | ✅ |
| Frontend Prettier | — | ✅ | ✅ |

**Proposed fix:** Have `dependabot-automerge.yml` depend on `ci.yml` results instead of running its own tests. Remove `lint-frontend.yml` entirely (ci.yml already covers it).

#### 3.5 Pre-Release Validation Is Never Triggered Automatically
`pre-release-validation.yml` is manual-only (`workflow_dispatch`). It contains valuable features: full E2E stack testing, Docker log analysis for errors/warnings/deprecations, and automatic issue creation for findings. None of this happens automatically.

**Proposed fix:** Trigger pre-release-validation automatically on PRs to `main` (either as a required check or as part of the integration-test workflow). The log analyzer and issue creation can be conditional on the `main` branch.

#### 3.6 Integration Test Reliability Issues
The integration test has multiple reliability problems observed in CI:
- **Rate limiting (429):** Playwright tests exhaust the search rate limit (fixed in PR #623 by disabling in E2E)
- **Solr cluster race conditions:** SolrCloud nodes occasionally fail peer-sync during startup
- **Admin API key not configured:** E2E admin tests were skipped (fixed in PR #622)

**Proposed fix:** Increase Solr health check retries, add Solr readiness polling before tests, and ensure all E2E environment variables are properly configured.

#### 3.7 Overlapping Security Scans for GitHub Actions
Both `checkov` and `zizmor` scan GitHub Actions workflow files. They have different strengths (Checkov focuses on IaC best practices, zizmor on supply-chain attacks), but the overlap creates noise.

**Proposed fix:** Keep both but document their complementary roles. Consider running them in a single consolidated security workflow to reduce parallel runs.

### 🟡 Medium Priority — Nice to Have

#### 3.8 Inconsistent Python Dependency Management
`embeddings-server` uses `pip install -r requirements.txt` while all other Python services use `uv sync --frozen`. This causes different behavior in CI vs local development.

**Proposed fix:** Migrate embeddings-server to `pyproject.toml` + `uv` (tracked separately if not already planned).

#### 3.9 Large JavaScript Blocks in Workflows
Squad workflows contain 150–300+ lines of inline JavaScript (`github-script`). This is hard to test, debug, and maintain.

**Proposed fix:** Extract to reusable composite actions or standalone scripts in `.github/actions/`.

#### 3.10 Hardcoded Release Versions in Label Sync
`sync-squad-labels.yml` has hardcoded `release:v*` labels (v0.4.0 through v1.4.0). These are outdated and require manual updates.

**Proposed fix:** Generate release labels dynamically from milestones API, or remove versioned release labels entirely (milestones serve this purpose).

#### 3.11 Missing CI Tests for `admin` Service in Dependabot Workflow
`dependabot-automerge.yml` runs tests for 4 Python services but **skips `admin`**. A Dependabot update could break admin without being caught.

**Proposed fix:** Add admin to the dependabot test matrix.

## 4. Proposed Release Pipeline

### Current Process (Ad Hoc)
```
Work on dev → Merge PRs to dev → Bump VERSION on dev → Tag on dev → Manually merge dev → main
```

### Proposed Process (Enforced)
```
1. Work on dev
   └─ ci.yml runs unit tests (required)
   └─ security scans run (Bandit required, others advisory)

2. Release prep PR to dev
   └─ VERSION bump, CHANGELOG, release notes

3. PR dev → main
   └─ ci.yml runs unit tests (required)
   └─ integration-test.yml runs full E2E (required)
   └─ pre-release-validation log analysis runs (advisory, creates issues)
   └─ Copilot review comments must be addressed
   └─ If issues found → fix on dev, update PR

4. Merge dev → main
   └─ Tag v*.*.* on main
   └─ release.yml builds + publishes to GHCR
   └─ release-docs.yml generates documentation PR
   └─ update-screenshots.yml commits screenshots
```

### Key Changes
1. **Integration test becomes a required check for PRs to main** — no more bypassing with `--admin`
2. **Pre-release log analysis runs automatically** on PRs to main and creates issues for errors
3. **Tags are created on main** (not dev) after the merge
4. **VERSION stays unchanged on dev** until main release is complete

## 5. Specific Workflow Changes Required

### 5.1 `ci.yml` — No Changes
Works well as-is. Required status check for dev PRs.

### 5.2 `lint-frontend.yml` — DELETE
Redundant with ci.yml which already runs ESLint + Vitest for aithena-ui.

### 5.3 `dependabot-automerge.yml` — Refactor
- Add `branches: [dev]` filter to trigger
- Remove duplicate test jobs — use `workflow_run` or `needs` to depend on ci.yml results
- Add `admin` to test matrix
- Replace stub security check with real validation

### 5.4 `integration-test.yml` — Enhance
- Make `Docker Compose integration + E2E` a **required status check** for PRs to main
- Incorporate log analysis from pre-release-validation (optional step)
- Increase Solr startup timeout / add readiness polling
- Ensure ADMIN_API_KEY and all env vars are properly configured

### 5.5 `pre-release-validation.yml` — Integrate
- Keep as manual workflow for on-demand validation
- Extract log analysis + issue creation into a reusable action
- Integration-test.yml can call this action for PRs to main

### 5.6 `security-bandit.yml` — Make Required
- Remove `continue-on-error: true`
- Add as required status check for dev and main PRs

### 5.7 `security-checkov.yml` + `security-zizmor.yml` — Consolidate
- Consider merging into a single `security-iac.yml` workflow
- Keep as advisory (non-blocking) but add clear workflow summary

### 5.8 `release.yml` — Add Main Branch Validation
- Validate that the tag exists on the `main` branch (not just any branch)
- Fail if tag is on a branch other than main

### 5.9 Squad Workflows — Extract JavaScript
- Extract large inline JS blocks to `.github/actions/` composite actions
- Remove dead code (`routing.md` read in triage but never used)
- Update hardcoded version labels to dynamic generation

## 6. Success Criteria

1. **PRs to dev** run unit tests + Bandit (all required, ~5 min)
2. **PRs to main** run unit tests + full E2E + log analysis (~15 min, required)
3. **No duplicate test runs** across workflows for the same event
4. **Pre-release validation** runs automatically on PRs to main
5. **Tags can only be created on main** (enforced by release.yml)
6. **Security findings block merges** (Bandit required; Checkov/zizmor advisory)
7. **Release process documented** and enforced by CI gates

## 7. Out of Scope

- Migrating embeddings-server to `uv` (separate issue)
- Rewriting squad automation workflows (separate milestone)
- Adding cloud deployment workflows (on-premises only)
- Branch protection rules (managed via GitHub UI, not workflow files)

## 8. Team Review Questions

1. Should Bandit be a hard blocker, or should we allow merges with security findings and track them as issues?
2. Is the 60-minute timeout for integration tests sufficient, or should we increase it?
3. Should pre-release log analysis create issues automatically, or just report findings in the workflow summary?
4. Do we want to keep the nightly scheduled integration test (3am Mon–Fri), or is PR-triggered sufficient?
5. Should we consolidate Checkov + zizmor into one workflow, or keep them separate for clarity?
