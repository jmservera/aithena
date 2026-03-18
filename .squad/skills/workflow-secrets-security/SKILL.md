---
name: "workflow-secrets-security"
description: "GitHub Actions secrets best practices: inline params vs env blocks, zizmor compliance"
domain: "security, ci, github-actions"
confidence: "high"
source: "Brett's PR #313 (Issue #294), zizmor security scanning, squad-issue-assign.yml fixes"
author: "Brett"
created: "2026-07-24"
last_validated: "2026-07-24"
---

## Context

GitHub Actions workflows often need secrets (tokens, credentials, API keys). The way secrets are passed and used affects security:
- **Leaked secrets** in environment or step context
- **Accidental exposure** in logs
- **Escalated privileges** when secrets available to unintended commands

This skill captures patterns from aithena's workflow security hardening (zizmor + code review).

## Pattern: Pass Secrets Securely

### Rule 1: Use Inline `with:` Parameters (NOT Step `env:`)

**❌ INSECURE — Step-level env block:**

```yaml
- name: Assign issue to copilot
  env:
    COPILOT_ASSIGN_TOKEN: ${{ secrets.COPILOT_ASSIGN_TOKEN }}
  run: |
    gh issue edit ${{ github.event.issue.number }} \
      --add-assignee copilot-swe-agent[bot]
    # Problem: Secret available to ALL commands in this step
    # An attacker can inject: echo $COPILOT_ASSIGN_TOKEN > /tmp/steal.txt
```

> **Note:** Step-level `env:` is not always insecure — if the step has no untrusted shell
> eval and has a documented `.zizmor.yml` exception (e.g., internal workflows like
> `squad-heartbeat.yml`), it can be acceptable. Prefer `with:` when possible; if `env:`
> must be used, minimize scope and document the exception.

**✅ SECURE — Inline with parameter:**

```yaml
- name: Assign issue to copilot
  uses: octokit/gh-action-paginate-issues@v2  # Example action
  with:
    github-token: ${{ secrets.COPILOT_ASSIGN_TOKEN }}
  # Secret passed directly to action; not exposed to step environment
```

Or use action input mapping:

```yaml
- name: Assign issue to copilot
  uses: actions/github-script@60a0d83039c74a4aee543508d2ffcb1c3799cdea # v7.0.1
  with:
    github-token: ${{ secrets.COPILOT_ASSIGN_TOKEN }}
    script: |
      // Secret injected by action runtime, not shell env
      // (github context has token available securely)
```

### Rule 2: Never Use Shell Variable Expansion for Secrets

**❌ INSECURE — Shell expansion:**

```yaml
- name: Deploy to AWS
  run: |
    aws configure set aws_access_key_id $AWS_ACCESS_KEY
    aws configure set aws_secret_access_key $AWS_SECRET_KEY
    # If `set -x` is enabled, logs show: aws_secret_access_key=sk-1234...
```

**✅ SECURE — Inline CLI parameters:**

```yaml
- name: Deploy to AWS
  run: |
    aws configure set aws_access_key_id ${{ secrets.AWS_ACCESS_KEY }}
    aws configure set aws_secret_access_key ${{ secrets.AWS_SECRET_KEY }}
  # GitHub masks ${{ secrets.X }} in logs automatically
```

Or pass as file:

```yaml
- name: Deploy to AWS
  run: |
    echo "${{ secrets.AWS_CREDENTIALS }}" > ~/.aws/credentials
    chmod 600 ~/.aws/credentials
    aws s3 ls
  # File contains secret, not exposed in shell
```

### Rule 3: Always Use `${{ secrets.X }}` Syntax

**❌ INSECURE — Environment variable reference:**

```yaml
env:
  MY_SECRET: my-secret-value  # Hardcoded!
```

**❌ INSECURE — Indirect reference:**

```yaml
env:
  SECRET_REF: $SECRET_NAME  # Shell expansion, not GitHub secret
```

**✅ SECURE — Template expansion:**

```yaml
env:
  MY_SECRET: ${{ secrets.MY_SECRET }}  # GitHub secret, automatically masked
```

**Why?** GitHub's secret masking only works on `${{ secrets.X }}` syntax. Direct env vars or shell expansion bypass masking.

### Rule 4: Secret Masking is Automatic, But Limited

**What GitHub masks:**
- Exact secret value in logs (if it appears as string)
- `${{ secrets.X }}` references in console output

**What GitHub DOES NOT mask:**
- Partial secret (if leaked as substring)
- Secret in structured output (JSON, XML) if not detected
- Secret in error messages from tools

**Mitigation:** Treat all secrets as sensitive; audit logs after deployment.

### Rule 5: Scope Secrets to Specific Actions

**Pattern — Isolate secret to single action:**

```yaml
- name: Approve workflow
  uses: actions/github-script@60a0d83039c74a4aee543508d2ffcb1c3799cdea # v7.0.1
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    script: |
      // Action provides github context with token
      // Secret never exposed to shell
      await github.rest.actions.approveWorkflowRun({
        owner: context.repo.owner,
        repo: context.repo.repo,
        run_id: runId
      });
```

**Anti-pattern — Pass secret to bash:**

```yaml
- name: Deploy
  run: |
    # Secret available to bash, risky
    ./deploy.sh "${{ secrets.DEPLOY_KEY }}"
```

**Mitigation:**

```yaml
- name: Deploy
  uses: my-deploy-action@v1
  with:
    deploy-key: ${{ secrets.DEPLOY_KEY }}
  # Action handles secret securely (hopefully)
```

### Rule 6: Token Scope Principle (Least Privilege)

**Different tokens have different scopes:**

| Token | Scope | Use Case |
|-------|-------|----------|
| `${{ secrets.GITHUB_TOKEN }}` | PR + repo context | CI/CD in same repo |
| `PAT (classic)` | All repos, full control | Cross-repo access, longer-lived |
| `PAT (fine-grained)` | Specific repos + permissions | Dependabot, external tools |
| `GitHub App token` | App permissions only | Bot automation |

**Pattern — Use GITHUB_TOKEN for single-repo CI:**

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: read
    steps:
      - uses: actions/checkout@v4
      - run: npm test
      # Default GITHUB_TOKEN used; scoped to this repo
```

**Pattern — Use PAT for cross-repo or long-lived access:**

```yaml
jobs:
  sync-labels:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Sync labels to other repos
        env:
          LABEL_SYNC_TOKEN: ${{ secrets.LABEL_SYNC_PAT }}
        run: |
          # ❌ WRONG: env block exposes secret
          python3 sync_labels.py
```

**Fix:**

```yaml
- name: Sync labels
  uses: actions/github-script@60a0d83039c74a4aee543508d2ffcb1c3799cdea # v7.0.1
  with:
    github-token: ${{ secrets.LABEL_SYNC_PAT }}
    script: |
      // Better: Use GitHub API via actions/github-script
      const octokit = github.getOctokit(process.env.GITHUB_TOKEN);
```

### Rule 7: Secrets in Workflow Files

**What GitHub scans for:**

- `${{ secrets.X }}` in workflow YAML
- Hard-coded values that look like secrets (AWS keys, tokens, PII)

**Limitation:** GitHub doesn't scan public/private repository content for embedded secrets (only workflow files).

**Mitigation:**

- Use git-secrets or Talisman pre-commit hooks
- Scan Dockerfiles, Python files, config files separately (checkov, truffleHog)
- Never commit secrets; use environment variables or secret stores

### Rule 8: Zizmor Scanning (IaC Security)

**Zizmor flags:**

| Rule | Problem | Fix |
|------|---------|-----|
| secrets-outside-env | Secret in `env:` block | Move to `with:` parameter |
| hardcoded-credentials | Hard-coded token | Use `secrets.X` |
| pull_request_target injection | PR code executed with token | Guard with copilot author check |
| workflow_dispatch validation | User input affects build | Validate inputs, document exceptions |

**Pattern — Zizmor compliant workflow:**

```yaml
name: Approve Workflow
on:
  pull_request:  # Use pull_request, NOT pull_request_target (secrets not exposed to fork code)
    types: [opened, synchronize]

permissions:
  actions: write  # Explicit, minimal scope

# ⚠️ WARNING: If pull_request_target is required (e.g., label-based workflows needing write access),
# NEVER checkout PR HEAD, never run PR code, use strict permissions, and document justification.

jobs:
  approve:
    runs-on: ubuntu-latest
    steps:
      - name: Check if copilot author
        id: check
        run: |
          author="${{ github.event.pull_request.user.login }}"
          if [[ "$author" == "copilot"* ]]; then
            echo "is_copilot=true" >> $GITHUB_OUTPUT
          fi
      
      - name: Approve workflow
        if: steps.check.outputs.is_copilot == 'true'
        uses: actions/github-script@60a0d83039c74a4aee543508d2ffcb1c3799cdea # v7.0.1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          script: |
            // GitHub token (not custom secret) + guarded by copilot check
            await github.rest.actions.approveWorkflowRun({...});
```

## Real-World Examples from Aithena

### Example 1: squad-issue-assign.yml (Fixed in PR #313)

**Before (insecure):**

```yaml
- name: Assign issue to squad
  env:
    COPILOT_ASSIGN_TOKEN: ${{ secrets.COPILOT_ASSIGN_TOKEN }}
  run: |
    gh issue edit $issue_number --add-assignee copilot-swe-agent[bot]
```

**After (secure):**

```yaml
- name: Assign issue to squad
  uses: actions/github-script@60a0d83039c74a4aee543508d2ffcb1c3799cdea # v7.0.1
  with:
    github-token: ${{ secrets.COPILOT_ASSIGN_TOKEN }}
    script: |
      await github.rest.issues.addAssignees({
        owner: context.repo.owner,
        repo: context.repo.repo,
        issue_number: context.issue.number,
        assignees: ['copilot-swe-agent[bot]']
      });
```

**Improvement:** Secret no longer exposed to bash; action handles it securely.

### Example 2: release-docs.yml (Copilot CLI Integration)

**Pattern — Secure token passing to CLI:**

```yaml
- name: Generate release notes
  run: |
    copilot \
      --agent squad \
      --autopilot \
      --message "Generate release notes for ${{ github.event.inputs.version }}"
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  # ✅ GITHUB_TOKEN only accessible to copilot CLI (not exported)
```

### Example 3: dependabot-automerge.yml (Robust Error Handling)

```yaml
- name: Auto-merge dependabot PR
  uses: actions/github-script@60a0d83039c74a4aee543508d2ffcb1c3799cdea # v7.0.1
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    script: |
      try {
        await github.rest.pulls.merge({
          owner: context.repo.owner,
          repo: context.repo.repo,
          pull_number: context.issue.number
        });
      } catch (error) {
        // Handle merge failure, label PR, post comment
        await github.rest.issues.addLabels({
          owner: context.repo.owner,
          repo: context.repo.repo,
          issue_number: context.issue.number,
          labels: ['dependabot:manual-review']
        });
      }
  # Error handling prevents secret exposure in fallback
```

## Validation Checklist

- [ ] All secrets use `${{ secrets.X }}` syntax
- [ ] No secrets in step-level `env:` blocks
- [ ] No hard-coded credentials or tokens
- [ ] Actions receive secrets via `with:` parameters
- [ ] Zizmor passes (if enabled)
- [ ] Pull_request_target workflows guard on author
- [ ] Token permissions are minimal (least privilege)
- [ ] Logs don't expose secrets (test with dry-run)
- [ ] PATs are fine-grained (not classic) where possible
- [ ] Secret rotation plan in place (if long-lived tokens)

## References

- GitHub Actions secrets docs: https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions
- Zizmor: https://github.com/woodruffw/zizmor (scan GitHub Actions for security issues)
- Issue #294: Fix secrets-outside-env in squad-issue-assign.yml
- PR #313: Implementation of secure secret passing
- `.github/workflows/zizmor.yml`: Automated security scanning
- `.checkov.yml`: IaC security exceptions
