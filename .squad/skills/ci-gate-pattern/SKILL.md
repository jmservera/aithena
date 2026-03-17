---
name: "ci-gate-pattern"
description: "Phase-gated CI workflow: auto-merge low-risk updates, manual review for major changes"
domain: "ci, automation, security"
confidence: "high"
source: "extracted from Brett's PR #412 (Dependabot auto-merge) security review and Ripley's v1.1.0 release workflow"
author: "Ripley"
created: "2026-03-18"
last_validated: "2026-03-18"
---

## Context

Use this pattern when designing CI workflows that must balance automation efficiency with security guarantees. Aithena uses this for Dependabot auto-merge (patch/minor) and manual review gates (major/breaking).

## Pattern: Tiered Merge Gates

### Tier 1: Auto-Merge (Low Risk)
**Trigger:** Dependabot patch/minor updates, non-breaking dependency changes

**Guards:**
```yaml
on:
  pull_request_target:
    if: github.actor == 'dependabot[bot]'
```

**Checkout Safety:**
```yaml
- uses: actions/checkout@v4
  with:
    ref: ${{ github.event.pull_request.head.sha }}  # Explicit SHA, not branch
    persist-credentials: false                       # Disable token leakage
```

**Tests Required:**
- All unit tests pass (all 6 services: 4 Python + frontend + admin)
- Linting passes (ruff, eslint)
- No new high/critical vulnerabilities introduced

**Auto-Merge Action:**
```yaml
- uses: actions/github-script@v7
  if: success()  # All tests passed
  with:
    script: |
      github.rest.pulls.merge({
        owner: context.repo.owner,
        repo: context.repo.repo,
        pull_number: context.issue.number,
        merge_method: 'squash'
      })
```

**Labeling:**
- `dependabot:auto-merge` — for tracking automated merges
- `dependencies` — standard Dependabot label

---

### Tier 2: Manual Review Gate (Medium Risk)
**Trigger:** Dependabot minor-to-major upgrades, breaking changes, new major versions

**Process:**
1. PR opens with `dependabot:manual-review` label
2. All tests must pass (same as Tier 1)
3. Assigned human reviewer (usually Parker for backend, Dallas for infra, Brett for tooling)
4. Reviewer checks:
   - **Changelog:** Any breaking changes? Deprecated APIs? Migration steps?
   - **Test coverage:** Are we testing the new behavior?
   - **Rollback plan:** If this breaks production, how do we revert?
5. Approval is required before merge

**Labeling:**
- `dependabot:manual-review` — signals human needed
- `breaking-change` — if applicable
- Milestone assigned — if scheduled for next release

---

### Tier 3: Security Scan Gate (High Risk)
**Trigger:** Code changes + dependency updates affecting security surface (auth, crypto, secrets, serialization)

**Guards:**
1. Static security scanning (Bandit for Python, npm audit for frontend)
2. Dependency vulnerability database check (GitHub security alerts)
3. Security team review (Kane) required

**Criteria:**
- No new HIGH/CRITICAL vulnerabilities without baseline exception
- All CVEs have documented mitigation or scheduled fix
- No new code patterns introducing injection, XSS, auth bypass

**Baseline Exceptions Pattern:**
- Exception **requires** documented risk assessment (e.g., `docs/security/baseline-exceptions.md`)
- Exception **must have** follow-up issue for permanent fix in next milestone
- Exception **must be** approved by security lead (Kane)

---

## Safety Checklist for `pull_request_target`

`pull_request_target` runs workflow code with elevated permissions. Use only if:

- [ ] **Gate on trusted actors only** — `if: github.actor == 'dependabot[bot]'` (or other trusted account)
- [ ] **Explicit SHA checkout** — use `github.event.pull_request.head.sha`, never branch name
- [ ] **Disabled credential persistence** — `persist-credentials: false`
- [ ] **No arbitrary code from PR** — don't run PR scripts or install PR-specified dependencies
- [ ] **Concurrency controlled** — prevent race conditions with concurrency limits

---

## Anti-Patterns

### ❌ Using pull_request_target without guards
```yaml
on:
  pull_request_target:  # DANGER: any PR can run code!
```
Use `pull_request_target` only with explicit actor gates.

### ❌ Checking out branch name instead of SHA
```yaml
- uses: actions/checkout@v4
  with:
    ref: ${{ github.head_ref }}  # DANGER: can be force-pushed mid-workflow
```
Always use explicit SHA: `github.event.pull_request.head.sha`

### ❌ Auto-merging major version bumps
Major versions almost always have breaking changes. Force human review.

### ❌ Skipping tests for "simple" dependency updates
Transitive vulnerabilities can sneak in. Always run full test suite.

---

## Example: Aithena Dependabot Auto-Merge Workflow

See `.github/workflows/dependabot-auto-merge.yml` (PR #412).

**Key features:**
- Patch + minor: auto-merge after tests pass
- Major + breaking: manual review required
- All 6 test suites run in parallel
- Concurrency limit prevents queue explosion

**Limitations (as of 2026-03-18):**
- Does NOT test `src/admin` (Streamlit app has no test suite)
- Security scan is placeholder; should add `npm audit` + `pip-audit`

---

## Integration with Release Gate

This CI pattern feeds into the release gate (`.squad/skills/release-gate/`):

1. **Dev branch must be green:** All CI gates pass before considering merge to main
2. **Dependency baseline updated:** Before release, run `uv lock`, commit updated lockfiles
3. **Baseline exceptions documented:** Any accepted CVEs must be in release notes

---

## References

- **PR #412:** Dependabot auto-merge workflow implementation
- **Issue #290:** ecdsa CVE baseline exception (example of security gate decision)
- **Docs:** `docs/security/baseline-exceptions.md`
- **GitHub Actions:** https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#pull_request_target
