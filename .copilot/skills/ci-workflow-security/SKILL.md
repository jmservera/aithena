# CI Workflow Security Patterns

**Domain:** GitHub Actions CI/CD hardening, secret handling, template injection prevention, bot automation

**Maintainer:** Brett (Infrastructure Architect)

---

## Pattern 1: Secrets-Outside-Env (Zizmor Rule)

### Problem
Step-level `env:` blocks expose secrets to all commands in the step, increasing attack surface. Secrets should be passed directly to actions via `with:` parameters.

### Solution
Replace environment variable exposure with inline action parameters:

**❌ WRONG:**
```yaml
- name: Assign issue to bot
  env:
    COPILOT_ASSIGN_TOKEN: ${{ secrets.COPILOT_ASSIGN_TOKEN }}
  run: gh api ...
```

**✅ CORRECT:**
```yaml
- name: Assign issue to bot
  uses: some-action@v1
  with:
    github-token: ${{ secrets.COPILOT_ASSIGN_TOKEN }}
```

### Rationale
- Step-level `env:` variables are available to all bash commands in the step
- `with:` parameters are passed directly to the action runtime, limiting exposure
- Reduces surface for shell injection, command substitution, or log exposure

### Zizmor Rule
**secrets-outside-env** — Detects secrets in step-level `env:` blocks. Should fail pre-commit with zizmor scanner.

### Implementation
1. Run `zizmor --check .github/workflows/*.yml` before committing workflow changes
2. Fix any `secrets-outside-env` alerts by moving to action `with:` parameters
3. Validate fix: `zizmor .github/workflows/FILE.yml | grep secrets-outside-env` returns 0

---

## Pattern 2: Template Expansion Safety

### Problem
Shell variable expansion can inadvertently execute code or expose secrets. GitHub Actions context should always use the explicit template syntax.

### Solution
Always use GitHub Actions context syntax `${{ ... }}`, never raw shell variables:

**❌ WRONG:**
```yaml
env:
  VERSION: $VERSION  # shell expansion
run: |
    echo $VERSION  # expands in subprocess context
```

**❌ WRONG:**
```yaml
run: echo ${{ secrets.TOKEN }} | some-command  # piped to subprocess, visible in logs
```

**✅ CORRECT:**
```yaml
env:
  VERSION: ${{ github.ref_name }}  # GitHub Actions context
run: |
    echo "$VERSION"  # quoted in bash
```

**✅ CORRECT (for secrets):**
```yaml
run: |
    echo "::add-mask::${{ secrets.TOKEN }}"
    some-command --token "${{ secrets.TOKEN }}"
```

### Rationale
- `${{ ... }}` is evaluated by GitHub Actions runtime, not the shell
- Prevents unintended variable substitution or code injection
- `:add-mask::` syntax masks secrets in logs before they're exposed to subprocess

### Best Practices
1. **Never pipe secrets:** `${{ secrets.X }} | command` exposes in process list
2. **Always quote expansions:** `echo "${{ env.VAR }}"` prevents word splitting
3. **Use add-mask for sensitive output:** Pre-mask before passing to commands that might echo
4. **Validate with grep:** Search for `$[A-Z_]+` patterns (unquoted shell vars) in workflows

---

## Pattern 3: Bot-Condition Guards (pull_request_target)

### Problem
GitHub Actions requires manual approval for workflow runs on bot-authored PRs. This blocks automation and creates unnecessary friction.

### Solution
Use `pull_request_target` event with bot-author detection to auto-approve copilot PRs:

```yaml
name: Auto-Approve Copilot Workflow Runs

on:
  pull_request_target:
    types: [opened, synchronize]

jobs:
  approve:
    runs-on: ubuntu-latest
    if: contains(fromJson('["copilot-swe-agent[bot]","app/copilot-swe-agent","copilot-swe-agent"]'), github.event.pull_request.user.login)
    permissions:
      actions: write
    steps:
      - name: Wait for workflow runs
        run: sleep 15
        
      - name: Approve workflow runs
        uses: actions/github-script@v7
        with:
          script: |
            const runs = await github.rest.actions.listWorkflowRunsForRepo({
              owner: context.repo.owner,
              repo: context.repo.repo,
              head_sha: context.payload.pull_request.head.sha,
              status: 'action_required'
            });
            for (const run of runs.data.workflow_runs) {
              await github.rest.actions.approveWorkflowRun({
                owner: context.repo.owner,
                repo: context.repo.repo,
                run_id: run.id
              });
            }
```

### Key Details
- **Event:** `pull_request_target` — runs in trusted base-branch context, no approval needed
- **Author check:** `contains(fromJson(['copilot-swe-agent[bot]', ...]), github.event.pull_request.user.login)`
- **Wait time:** 15 seconds allows GitHub Actions to create run records
- **API endpoint:** `github.rest.actions.approveWorkflowRun({ owner, repo, run_id })`
- **Permissions:** `actions: write` required for approval API

### Rationale
- `pull_request_target` runs trusted code from base branch (no checkout of PR code)
- API-only operations (no shell execution, no code checkout)
- Verified author check prevents approving unrelated bot PRs
- Eliminates the approval chicken-and-egg problem for copilot automation

### Security Considerations
- Never use `actions/checkout` on PR code in pull_request_target workflows
- Only query/approve workflow runs for verified bot authors
- Keep the author list up-to-date as copilot bot IDs evolve

---

## Pattern 4: Zizmor Pre-Commit Hook Integration

### Setup
Add to `.pre-commit-config.yaml`:

```yaml
- repo: https://github.com/neilkuan/zizmor
  rev: v0.2.3  # pin to stable version
  hooks:
    - id: zizmor
      types: [yaml]
      files: ^\.github/workflows/
      args: ['--check']
```

### CI Integration
Add to `ci.yml` (or dedicated security workflow):

```yaml
- name: Zizmor GitHub Actions security scan
  run: |
    pip install zizmor
    zizmor --check .github/workflows/*.yml
```

### Rules to Enforce
- `secrets-outside-env` — Detect secrets in step-level env blocks
- `node-runtime` — Deprecated Node.js versions in actions
- `action-reference` — Actions must be pinned to SHAs, not floating tags
- `hardcoded-secrets` — Scan for common secret patterns

### False Positives & Exemptions
Document any exemptions in `.zizmor.yml`:

```yaml
# .zizmor.yml
disable:
  # Acceptable risks
  - rule: node-runtime
    path: .github/workflows/legacy-compat.yml
    reason: "Legacy action requires Node.js 16 until replacement available"
```

---

## Pattern 5: API Fallback Patterns (Token Scope Validation)

### Problem
GitHub API endpoints have varying token scope requirements. The low-level Git Data API requires `workflow` scope to modify `.github/workflows/*` files, even when the higher-level Contents API would work.

### Solution
**Always validate token scope before making API calls:**

```yaml
- name: Check token scope for Git Data API
  id: scope-check
  run: |
    TOKEN="${{ secrets.GITHUB_TOKEN }}"
    # Try a light operation to validate scope
    if gh api repos/{owner}/{repo}/git/trees/HEAD 2>/dev/null; then
      echo "scope=full" >> $GITHUB_OUTPUT
    else
      echo "scope=limited" >> $GITHUB_OUTPUT
    fi

- name: Update workflow file (fallback on scope error)
  if: steps.scope-check.outputs.scope == 'full'
  run: |
    # Use Git Data API with full token
    gh api repos/{owner}/{repo}/contents/.github/workflows/file.yml \
      --method PUT \
      --input=payload.json
      
- name: Update workflow file (fallback method)
  if: steps.scope-check.outputs.scope == 'limited'
  run: |
    # Fallback: use git command or skip update
    echo "Warning: Token scope insufficient for Git Data API. Skipping workflow update."
```

### Token Scope Rules
1. **Contents API** (read/write files) — requires `contents` scope
2. **Git Data API** (refs, trees, commits) — requires `workflow` scope when targeting `.github/workflows/*`
3. **Actions API** (runs, artifacts, approval) — requires `actions` scope
4. **Workflows API** (dispatch, manage) — requires `workflows` scope

### Recommendation
Use GitHub App tokens with fine-grained permissions instead of classic PATs:
- App tokens support per-resource scopes
- No user-level permission inheritance
- Easier to audit and revoke
- Better for bot automation

---

## Checkov + GitHub Actions (CKV_GHA Rules)

### CKV_GHA_7: workflow_dispatch Inputs
**Rule:** Workflow dispatch inputs should be empty (SLSA security guideline — outputs must not depend on user input).

**Rationale:** If user parameters affect build outputs, reproducibility and supply chain integrity are compromised.

**Exception Pattern (Document in `.checkov.yml`):**
```yaml
- resource: .github/workflows/release-docs.yml
  code_block:
    - 17  # Input definition line
  comment: |
    Exception: release-docs is documentation automation (not build/release pipeline).
    Inputs (version, milestone) are validated with regex; protected by maintainer-only access.
    Does not affect build artifacts or supply chain.
```

### Other GitHub Actions Rules
- **CKV_GHA_5:** Pinned actions (use SHAs, not floating tags like `@v1`)
- **CKV_GHA_6:** Avoid hardcoded GitHub token usage
- **CKV_GHA_2:** Restrict concurrency (prevent cancellation of running jobs)

---

## Examples from Aithena Project

### Example 1: copilot-approve-runs.yml
**File:** `.github/workflows/copilot-approve-runs.yml`

**Pattern:** Auto-approve workflow runs on copilot-swe-agent PRs using pull_request_target guard.

### Example 2: squad-issue-assign.yml (Fixed)
**File:** `.github/workflows/squad-issue-assign.yml`

**Pattern:** Removed `env: COPILOT_ASSIGN_TOKEN`, now passes token directly via `github-token` parameter (PR #313).

### Example 3: security-checkov.yml
**File:** `.github/workflows/security-checkov.yml`

**Pattern:** Checkov IaC scanning with soft_fail (non-blocking), path filtering, SARIF integration.
- Exception flags in `.checkov.yml` for context-specific rules (CKV_DOCKER_2, CKV_DOCKER_3)
- Runs on path changes: Dockerfiles, workflows, docker-compose files

### Example 4: release-docs.yml
**File:** `.github/workflows/release-docs.yml`

**Pattern:** Template expansion safety — uses `${{ github.ref_name }}` instead of shell vars; Copilot CLI invocation with fallback template generation.
- CKV_GHA_7 exception documented for `version` and `milestone` inputs

---

## Checklist: CI Workflow Security Review

Before merging a workflow change:
- [ ] Run `zizmor .github/workflows/*.yml` — no secrets-outside-env
- [ ] Verify all secrets use `with:` parameters, not step-level `env:`
- [ ] Check template expansions use `${{ ... }}`, not `$SHELL_VAR`
- [ ] If bot-authored PR: use `pull_request_target` + author guard
- [ ] All actions pinned to SHAs (verify with `gh workflow view <file> --json content`)
- [ ] Token scopes match API operations (check `.checkov.yml` exceptions)
- [ ] No hardcoded credentials in workflow files
- [ ] Concurrency settings prevent job cancellation (if applicable)
- [ ] SARIF/Code Scanning integration configured (if security scanning)

---

## References
- **Zizmor:** https://github.com/neilkuan/zizmor (GitHub Actions security scanner)
- **Checkov CKV_GHA:** https://www.checkov.io/4.Integrations/GitHub%20Actions
- **SLSA Framework:** https://slsa.dev/ (supply chain security)
- **GitHub Actions Best Practices:** https://docs.github.com/en/actions/security-guides
