---
name: "ci-pr-gates"
description: "CI gate patterns, PR integration checks, branch protection handling, milestone review gates, and release validation"
domain: "ci, quality, release-management"
confidence: "high"
source: "consolidated from ci-gate-pattern, pr-integration-gate, branch-protection-strict-mode, milestone-gate-review, release-gate"
author: "Ripley"
created: "2026-07-25"
last_validated: "2026-07-25"
---

## Context

Apply when designing CI workflows, reviewing PRs, handling branch protection, auditing milestones, or validating releases. Covers the full gate lifecycle from PR creation through release approval.

## Pattern 1: Tiered CI Merge Gates

### Tier 1 — Auto-Merge (Low Risk)
**Trigger:** Dependabot patch/minor updates

- Gate on trusted actors: `if: github.actor == 'dependabot[bot]'`
- Checkout with explicit SHA: `ref: ${{ github.event.pull_request.head.sha }}`
- Disable credential persistence: `persist-credentials: false`
- All unit tests + linting must pass across all services
- Auto-merge via `actions/github-script` with squash strategy
- Label: `dependabot:auto-merge`

### Tier 2 — Manual Review (Medium Risk)
**Trigger:** Major version bumps, breaking changes

- Label: `dependabot:manual-review`
- Reviewer checks changelog, test coverage, rollback plan
- Approval required before merge

### Tier 3 — Security Scan (High Risk)
**Trigger:** Changes to auth, crypto, secrets, serialization

- Static security scanning (Bandit, npm audit)
- No new HIGH/CRITICAL vulnerabilities without baseline exception
- Security lead review required

### `pull_request_target` Safety Checklist
- [ ] Gate on trusted actors only
- [ ] Explicit SHA checkout (never branch name)
- [ ] Disabled credential persistence
- [ ] No arbitrary code from PR
- [ ] Concurrency controlled

## Pattern 2: PR Integration Checks

Before merging any PR to `dev`:

**Frontend PRs** (`aithena-ui/`):
```bash
cd src/aithena-ui && npm install --legacy-peer-deps && npm run build && npm run lint
```

**Backend PRs** (Python services):
```bash
cd src/{service} && uv run pytest --tb=short -q
```

**Infrastructure PRs** (compose, nginx):
```bash
docker compose config --quiet
```

Until CI covers all paths, the reviewing agent must run these manually.

## Pattern 3: Branch Protection Strict Mode

When branch protection requires "up to date before merging":

- **Use `gh pr merge --admin --merge`** to bypass "branch is not up to date" after checks pass
- **Merge in dependency order** — if PR B depends on PR A, merge A first
- **Expect cascading BEHIND states** — normal after merging PR 1 of N
- **Retry with 5–10s delays** between sequential merges
- **Batch independent PRs** with `--admin` to avoid waiting for CI re-runs

```bash
for pr in 101 102 103 104 105 106 107; do
  gh pr merge $pr --admin --merge
  sleep 5
done
```

**Warning:** `--admin` bypasses ALL protection rules — only use when checks passed and reviews approved.

## Pattern 4: Milestone Gate Review

Before closing a milestone, audit every merged issue:

**Security checks:**
- Scan for `# noqa: S608` (SQL injection suppression) — justify each instance
- Look for dynamic SQL construction, auth bypass paths
- Verify input validation on public endpoints

**Performance checks:**
- Flag sequential batch operations on >100 items
- Check for N+1 query patterns
- Verify Redis uses `scan_iter()`/`mget()`, not `KEYS`/per-key loops
- Look for missing pagination on list endpoints

**Architecture checks:**
- New endpoints follow existing patterns (FastAPI, Pydantic)
- New config uses dataclass-based `config.py` with env vars
- Docker health checks in `docker-compose.yml`, not Dockerfiles

**Verdict:** APPROVE or BLOCK with specific findings.

## Pattern 5: Release Gate (Dev → Main)

**Owner:** Newt (PM) — no release without explicit approval.

### Quality Gate
1. ✅ Milestone clear: 0 open issues (check BOTH milestone AND issue labels)
2. ✅ All tests pass: `uv run pytest -v` per service + `npx vitest run` for frontend
3. ✅ Frontend builds clean: `npm run build`
4. ✅ Docker Compose validates: `python3 -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"`

### Documentation Gate (REQUIRED — blocks release)
5. ✅ Release notes: `docs/release-notes/vX.Y.Z.md`
6. ✅ Test report: `docs/test-reports/vX.Y.Z.md`
7. ✅ User manual updated
8. ✅ Admin manual updated
9. ✅ CHANGELOG.md updated (Keep a Changelog format)
10. ✅ README.md current

### Test Count Baseline
Typical range: **467–628 tests total**. Significant drops are red flags.

## Anti-Patterns

- ❌ Using `pull_request_target` without actor guards
- ❌ Checking out branch name instead of SHA
- ❌ Auto-merging major version bumps
- ❌ Merging frontend PRs without `npm run build`
- ❌ Skipping `--legacy-peer-deps` for npm install
- ❌ Approving release without docs committed
- ❌ Merging dev→main without Newt's sign-off
- ❌ Rubber-stamping milestone reviews — read the diffs
- ❌ Blocking milestone gate on style issues (save for PR review)
- ❌ Rebasing each PR onto updated base when using `--admin` merge

## References

- `.github/workflows/ci.yml`, `.github/workflows/dependabot-automerge.yml`
- PR #412 (Dependabot auto-merge), PR #432 (v1.4.0)
- `docs/security/baseline-exceptions.md`
