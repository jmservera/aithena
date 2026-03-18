---
name: "dependabot-triage-routing"
description: "Classify and route Dependabot PRs to team members based on dependency type"
domain: "automation, ci, dependencies"
confidence: "high"
source: "Brett's PR #486 (Issue #483) and #485 (Issue #470)"
author: "Brett"
created: "2026-07-24"
last_validated: "2026-07-24"
---

## Context

Dependabot generates many PRs (patch/minor updates, security fixes). Triage routing ensures the right team member reviews each:
- **Brett (Infrastructure):** Docker, deployment, buildtools
- **Kane (Security):** crypto, auth, security packages
- **Parker (Backend):** Python dependencies
- **Dallas (Frontend):** Node.js, React, Vite
- **Lambert (Testing):** Test frameworks, CI tooling

## Pattern: Detect and Classify Dependabot PRs

### Step 1: Detection

Dependabot PRs are detected by:
- **Label:** `dependabot:manual-review` (when auto-merge fails or CI checks fail)
- **Author:** `dependabot[bot]` or `app/dependabot` in the PR author field
- **Branch:** `dependabot/{ecosystem}/{package-manager}/{package-name}` format
- **Stale:** `7+ days old` with `dependabot[bot]` author (likely abandoned or blocked)
- **CI failure:** PR has failed check runs (via Checks API)

### Step 2: Extract Dependency Name

**Primary method — PR title parsing:**

All Dependabot PR titles follow format: `"Bump {package} from {old-version} to {new-version}"`

```javascript
const match = prTitle.match(/^Bump\s+(\S+)\s+from\s+\S+\s+to\s+\S+/);
const depName = match ? match[1] : null;
```

**Secondary method — Branch name parsing:**

Branch format: `dependabot/{ecosystem}/{package-manager}/{package-name}`

```javascript
const depName = prBranch.split('/')[3];  // last segment after 'dependabot/{ecosystem}/{manager}/'
```

**Tertiary method — Changed files analysis:**

If title/branch parsing fails, scan changed files:
- `requirements.txt` changes → Python
- `package.json` changes → JavaScript/Node.js
- `Dockerfile` changes → Base images, system packages
- `.github/workflows/*.yml` → GitHub Actions
- `docker-compose.yml` → Infrastructure dependencies

### Step 3: Route by Dependency Type

**Routing table (in priority order):**

| Dependency | Pattern | Owner | Reason |
|------------|---------|-------|--------|
| cryptography, PyJWT, jwt | crypto, auth, jwt, signing | Kane | Security-sensitive |
| ecdsa, pycryptodome | crypto backends | Kane | Authentication foundation |
| requests, urllib3 | HTTP client security | Kane | Network security |
| docker, docker-compose | Docker versioning | Brett | Infrastructure |
| Python base images | `FROM python:*` in Dockerfile | Brett | Infrastructure dependency |
| Node.js base images | `FROM node:*` in Dockerfile | Dallas | Frontend infrastructure |
| Alpine base images | `FROM alpine:*` in Dockerfile | Brett | Infrastructure dependency |
| pytest, pytest-cov | Python test frameworks | Lambert | Testing infrastructure |
| vitest, jest, testing-library | Node.js test frameworks | Lambert | Testing infrastructure |
| Ruff, mypy, black | Python linting/formatting | Parker | Code quality (backend-adjacent) |
| ESLint, Prettier | JavaScript linting | Dallas | Code quality (frontend) |
| uv, pip-tools | Python package managers | Brett | Build infrastructure |
| Vite, Webpack | Frontend bundlers | Dallas | Build infrastructure |
| FastAPI, Flask, Django | Python web frameworks | Parker | Backend framework |
| React, Vue, Angular | Frontend frameworks | Dallas | Frontend framework |
| SQLAlchemy, psycopg2 | Database libraries | Parker | Backend persistence |
| Requests, httpx | Python HTTP clients | Parker | Backend networking |

**Logic:**

1. Extract dep name from PR title
2. Look up in routing table
3. If exact match found → assign to Owner
4. If no match, use keyword search on changed files
5. If still ambiguous, assign to Brett (infrastructure owner) for classification

### Step 4: Handle Auto-Merge vs Manual Review

**Auto-merge candidate (CI passes, no conflicts):**
- Patch versions (1.2.3 → 1.2.4)
- Minor versions with green CI (1.2.3 → 1.3.0)
- All dependencies except major version bumps

**Manual review required (label: `dependabot:manual-review`):**
- Major version bumps (1.x → 2.x)
- CI check failures
- Merge conflicts
- Security/auth packages (always manual)
- Dependencies on critical path (always manual for first bump)

**Auto-merge workflow logic:**

```javascript
if (isDependabot && hasAutoMergeLabel && allChecksPass) {
  // Auto-merge
  github.rest.pulls.merge({ owner, repo, pull_number, merge_method: 'squash' });
  removeLabel('dependabot:manual-review');
} else if (isDependabot && !allChecksPass) {
  // Mark for manual review
  addLabel('dependabot:manual-review');
  createComment('CI failed; requires manual review');
  removeLabel('dependabot:auto-merge');
}
```

### Step 5: Heartbeat Integration (Ralph)

The squad heartbeat (Ralph) detects and triages Dependabot PRs:

```javascript
// In ralph-heartbeat workflow

// 1. Find Dependabot PRs needing triage
const prQuery = `label:dependabot:manual-review OR (author:dependabot[bot] updated:<2026-07-17 -label:squad:*)`;
const prs = await github.rest.search.issuesAndPullRequests({ q: prQuery });

// 2. For each PR, classify and route
for (const pr of prs) {
  const owner = classifyDependabot(pr.title, pr.head.ref, changedFiles);
  
  // 3. Apply label
  await github.rest.issues.addLabels({
    owner, repo, issue_number: pr.number,
    labels: [`squad:${owner}`]
  });
  
  // 4. Post triage comment
  await github.rest.issues.createComment({
    owner, repo, issue_number: pr.number,
    body: `🔄 Ralph — Auto-Triage\n\nClassified as ${depType} (routed to squad:${owner})\n\n${reviewGuidance}`
  });
}
```

**Existing triage detection (preserved, not modified):**
- Squad issue assignment (via `squad-issue-assign.yml`)
- Copilot auto-assignment (PR author detection)
- Regular heartbeat runs (10-minute cycle)

### Step 6: Prevention of Re-Triage

Once a PR is triaged (has any `squad:*` label), Ralph skips it:

```javascript
const isAlreadyTriaged = pr.labels.some(l => l.name.startsWith('squad:'));
if (isAlreadyTriaged) {
  continue;  // Skip, don't re-process
}
```

## Real-World Examples from Aithena

### Example 1: Patch Update (Auto-Merge)

```
PR Title: "Bump ruff from 0.3.5 to 0.3.6"
Branch: dependabot/pip/ruff
Changed files: pyproject.toml, uv.lock
Classification: Python linting/code-quality
Owner: Parker
CI Status: ✅ All checks pass
Action: Auto-merge (squash) + keep label (info only)
```

### Example 2: Major Version Bump (Manual Review)

```
PR Title: "Bump cryptography from 41.x to 42.0"
Branch: dependabot/pip/cryptography
Changed files: requirements.txt, uv.lock, tests/
Classification: Cryptography (auth/crypto)
Owner: Kane
CI Status: ✅ Green, but major version
Action: Label dependabot:manual-review + route squad:kane
```

### Example 3: CI Failure (Manual Review)

```
PR Title: "Bump pytest from 7.4.0 to 8.0.0"
Branch: dependabot/pip/pytest
Changed files: pyproject.toml, uv.lock
Classification: Test framework
Owner: Lambert
CI Status: ❌ Document-indexer tests fail
Action: Label dependabot:manual-review + route squad:lambert + post explanation
```

### Example 4: Abandoned PR (Stale Triage)

```
PR Title: "Bump node from 20.x to 22.x"
Branch: dependabot/dockerfile/node
Changed files: src/aithena-ui/Dockerfile
Created: 7+ days ago
CI Status: ✅ Passing
Classification: Frontend base image
Owner: Dallas
Action: Post heartbeat comment "Hi Dallas, this PR has been open 7+ days and is passing CI. Ready to merge?"
```

## Validation Checklist

- [ ] Dependabot PR detected (author or label)
- [ ] Dependency name extracted (title parsing works)
- [ ] Routing table lookup successful
- [ ] Team member exists and has active charter
- [ ] Label applied (`squad:{member}`)
- [ ] Comment posted with classification reasoning
- [ ] Existing triaged PRs skipped (avoid re-processing)
- [ ] Auto-merge PRs have explicit `dependabot:auto-merge` label before merging
- [ ] Failed CI routes to manual review (label + comment)

## References

- Issue #483: Heartbeat Dependabot detection
- Issue #470: Dependabot auto-merge CI improvements
- PR #486: Heartbeat detection + routing implementation
- PR #485: Dependabot auto-merge workflow
- `.squad/agents/ralph/charter.md`: Heartbeat agent responsibilities
