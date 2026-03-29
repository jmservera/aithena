---
name: "security-patterns"
description: "CI workflow security, secrets handling, security scanning, and logging security patterns"
domain: "security, ci, github-actions, logging"
confidence: "high"
source: "consolidated from ci-workflow-security, workflow-secrets-security, security-scanning-baseline, logging-security"
author: "Ripley"
created: "2026-07-25"
last_validated: "2026-07-25"
---

## Context

Apply when writing/reviewing GitHub Actions workflows, handling secrets, configuring security scanners, or implementing error logging in production services. Defense-in-depth across CI/CD and application layers.

## Pattern 1: Secrets Handling in GitHub Actions

### Rule: Use `with:` Parameters, NOT Step `env:` Blocks

❌ **Insecure — secret in env block:**
```yaml
- name: Assign issue
  env:
    TOKEN: ${{ secrets.MY_TOKEN }}
  run: gh issue edit ...
```

✅ **Secure — inline with parameter:**
```yaml
- name: Assign issue
  uses: actions/github-script@v7
  with:
    github-token: ${{ secrets.MY_TOKEN }}
    script: |
      await github.rest.issues.addAssignees({...});
```

### Additional Secret Rules
- **Always use `${{ secrets.X }}` syntax** — GitHub masking only works with this syntax
- **Never pipe secrets:** `${{ secrets.X }} | command` exposes in process list
- **Always quote expansions:** `"${{ env.VAR }}"` prevents word splitting
- **Use `::add-mask::` for sensitive output** before passing to commands that might echo
- **Token scope: least privilege** — use `GITHUB_TOKEN` for single-repo CI, fine-grained PATs for cross-repo

### Token Scope Reference

| Token | Scope | Use Case |
|-------|-------|----------|
| `GITHUB_TOKEN` | PR + repo context | CI/CD in same repo |
| Fine-grained PAT | Specific repos + perms | Dependabot, external tools |
| GitHub App token | App permissions only | Bot automation |

## Pattern 2: Bot-Condition Guards

For auto-approving copilot PRs, use `pull_request_target` with author detection:

```yaml
on:
  pull_request_target:
    types: [opened, synchronize]
jobs:
  approve:
    if: contains(fromJson('["copilot-swe-agent[bot]"]'), github.event.pull_request.user.login)
    permissions:
      actions: write
```

**Critical:** Never use `actions/checkout` on PR code in `pull_request_target` workflows. API-only operations, verified author check.

## Pattern 3: Security Scanner Configuration

### Bandit (Python SAST)
- Config: `.bandit` (centralized)
- Mode: `--exit-zero` + `continue-on-error: true` (non-blocking, SARIF upload)
- Baseline skips: B101 (pytest assert), B104 (0.0.0.0 in containers), B105/B106/B108 (test data), B603/B607 (subprocess in tests)
- Always exclude: `.venv`, `site-packages`, `node_modules`

### Checkov (IaC)
- Config: `.checkov.yml`
- Scope: Dockerfiles + GitHub Actions workflows
- CKV_GHA_7: Document exceptions for `workflow_dispatch` inputs (SLSA guideline)
- CKV_GHA_5: Pin actions to SHAs, not floating tags

### Zizmor (GitHub Actions Supply Chain)
- Config: `.zizmor.yml` (baseline exceptions)
- Focus: `template-injection`, `dangerous-triggers`, `secrets-outside-env`
- Pre-commit integration: run before committing workflow changes

### Triage Workflow
1. **CRITICAL/HIGH:** Must fix OR documented baseline exception with runtime mitigation
2. **MEDIUM/LOW:** Baseline exception acceptable if low exploitability
3. **False positive:** Dismiss with `noqa` + inline rationale comment (never suppress silently)
4. **Real findings:** Fix if trivial; otherwise document in `docs/security/baseline-exceptions.md`

## Pattern 4: Logging Security

Prevent information disclosure in production logs while preserving debugging.

### Two-Tier Exception Logging

```python
except SomeError as exc:
    logger.error("Operation failed: %s (%s)", message, type(exc).__name__)
    logger.debug("Full stack trace:", exc_info=True)
```

### Rules
- **Never use `logger.exception()` in production error paths** — exposes stack traces
- **Never use `str(exc)` at production log level** — may leak internal paths; use `type(exc).__name__`
- **Never log raw user input at INFO/ERROR level** — use document ID or hash only
- **Never use `exc_info=True` at CRITICAL/ERROR level** — reserve for DEBUG

### API Error Response Pattern
```python
try:
    result = some_operation()
except AuthError as exc:
    logger.critical("Auth failed: %s", type(exc).__name__)
    logger.debug("Auth context:", exc_info=True)
    raise HTTPException(status_code=401, detail="Invalid credentials")
```

## CI Workflow Security Review Checklist

Before merging a workflow change:
- [ ] Run `zizmor .github/workflows/*.yml` — no secrets-outside-env
- [ ] All secrets use `with:` parameters, not step-level `env:`
- [ ] Template expansions use `${{ ... }}`, not `$SHELL_VAR`
- [ ] Bot-authored PRs use `pull_request_target` + author guard
- [ ] All actions pinned to SHAs
- [ ] Token scopes match API operations
- [ ] No hardcoded credentials
- [ ] Logs don't expose secrets (test with dry-run)

## Anti-Patterns

- ❌ Using CLI flags instead of config files for scanners — centralized config is auditable
- ❌ Suppressing scanner findings without rationale — bare `noqa: S404` tells nothing
- ❌ Scanning `.venv` directories — generates hundreds of third-party false positives
- ❌ Using `logger.exception()` anywhere in auth/error paths
- ❌ Relying on "we'll filter logs later" — logs are already shipped to monitoring
- ❌ Hardcoded secrets in workflow files

## References

- `.bandit`, `.checkov.yml`, `.zizmor.yml`
- `.github/workflows/security-*.yml`
- `docs/security/baseline-exceptions.md`
- PR #313 (secrets fix), Issue #294, PR #412 (Dependabot)
- Zizmor: https://github.com/woodruffw/zizmor
- SLSA Framework: https://slsa.dev/
