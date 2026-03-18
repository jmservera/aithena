---
name: "release-docs-gate-pattern"
description: "Docs-gate-the-tag pattern: Generate and merge release docs BEFORE creating version tags"
domain: "release, documentation, automation"
confidence: "high"
source: "Brett's PR #427 (Issue #363), release-docs.yml implementation"
author: "Brett"
created: "2026-07-24"
last_validated: "2026-07-24"
---

## Context

Aithena ships 4 releases in parallel (v1.4.0–v1.7.0). Each release requires:
1. Release notes (features, fixes)
2. Test report (test counts, coverage)
3. Updated admin/user manuals (screenshots, feature guide)
4. Version metadata (git tags, Docker images)

The challenge: Release docs take time to generate and review. If docs are created AFTER tagging, the version tag doesn't include the docs in history. If docs are missing, the release is incomplete.

## Pattern: Docs-Gate-The-Tag

### Core Principle

**Release docs must be merged to `dev` BEFORE creating the version tag.** This ensures:
- Release notes are part of the tagged commit history
- All 4 release artifacts are in the same commit
- Revert/audit trail includes documentation
- No "incomplete release" scenario

### Step 1: Release Checklist (Gating)

File: `.github/ISSUE_TEMPLATE/release.md`

```markdown
# Release: v{VERSION}

## Pre-Release Gate

- [ ] All milestone issues closed (check [milestone view](../../milestones) and `release:v{VERSION}` label)
- [ ] Trigger `release-docs` workflow (Actions → Release Docs → Run workflow)
  - version: `{VERSION}`
  - milestone: `v{VERSION}`
- [ ] Review generated docs PR (release notes, test report, admin/user manuals)
- [ ] Merge docs PR to `dev`
- [ ] Tag the release: `git tag -a v{VERSION} -m "Release v{VERSION}"`
- [ ] Push tag: `git push origin v{VERSION}`

## Post-Release Gate

- [ ] CI/CD `release.yml` runs (builds Docker images, pushes to GHCR, creates release asset)
- [ ] Verify GitHub Release created with tarball asset
- [ ] Announce release to users
```

**Key:** Docs PR merge is step 4 (before tag). Tagging is step 5.

### Step 2: Release-Docs Workflow

File: `.github/workflows/release-docs.yml`

**Trigger:** Manual `workflow_dispatch` with version/milestone inputs

```yaml
on:
  workflow_dispatch:
    inputs:
      version:
        description: 'Release version (e.g., 1.4.0)'
        required: true
      milestone:
        description: 'GitHub milestone (e.g., v1.4.0)'
        required: true
```

**Workflow tasks:**

1. **Generate release notes** (via Copilot CLI):
   - Query merged PRs for the milestone
   - Categorize by type (features, fixes, infrastructure)
   - Generate markdown

2. **Generate test report** (pytest/vitest summary):
   - Collect test counts from all services
   - Summarize coverage (if available)
   - Generate markdown

3. **Review manuals** (Copilot CLI):
   - Prompt Newt to review admin/user manuals
   - Suggest updates for new features
   - Generate diff/suggestions

4. **Create PR** (to `dev`):
   - Push docs to `squad/release-docs-v{VERSION}` branch
   - Create PR with docs commit
   - Auto-merge if no conflicts (or wait for review)

### Step 3: Release Notes Generation

**Pattern (via Copilot CLI):**

```bash
copilot \
  --agent squad \
  --autopilot \
  --allow-all-tools \
  --message "
  Generate release notes for v1.4.0. 
  
  Milestone: v1.4.0
  Merged PRs:
  $(gh pr list --base dev --milestone 'v1.4.0' --state closed --json number,title,labels,author)
  
  Categorize by: Features, Fixes, Infrastructure, Docs
  Format as markdown for docs/releases/v1.4.0/RELEASE_NOTES.md
  "
```

**Fallback template** (if Copilot CLI unavailable):

```markdown
# v1.4.0 Release Notes

## Features
- Feature 1 (#123)
- Feature 2 (#124)

## Fixes
- Fix 1 (#125)
- Fix 2 (#126)

## Infrastructure
- Improvement 1 (#127)

Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

### Step 4: Test Report Generation

**Pattern:**

```bash
# Collect test counts from all services
pytest --co -q > /tmp/pytest-count.txt
npm test --listTests > /tmp/vitest-count.txt

# Generate report
python3 -c "
import json
from pathlib import Path

report = {
  'generated_at': '2026-07-24T15:30:00Z',
  'services': {
    'solr-search': {'tests': 144, 'passed': 144, 'coverage': '92%'},
    'embeddings-server': {'tests': 9, 'passed': 9, 'coverage': '88%'},
    'document-indexer': {'tests': 42, 'passed': 42, 'coverage': '85%'},
    'document-lister': {'tests': 12, 'passed': 12, 'coverage': '80%'},
    'aithena-ui': {'tests': 127, 'passed': 127, 'coverage': '75%'},
    'admin': {'tests': 71, 'passed': 71, 'coverage': '88%'},
  },
  'total': {'tests': 405, 'passed': 405}
}

print(json.dumps(report, indent=2))
" > docs/releases/v1.4.0/TEST_REPORT.json
```

### Step 5: Create Release PR

**After all docs generated:**

```bash
git checkout -b squad/release-docs-v1.4.0
git add docs/
git commit -m "docs: v1.4.0 release documentation — Features & Fixes"
git push origin squad/release-docs-v1.4.0

gh pr create \
  --base dev \
  --title "docs: v1.4.0 release documentation" \
  --body "Release notes, test report, manual updates for v1.4.0. 
  
  Milestone: v1.4.0
  
  To merge and tag:
  1. Approve this PR (after review)
  2. Merge to dev
  3. Create tag: git tag -a v1.4.0
  4. Push tag to trigger release.yml
  "
```

**Merge strategy:** Allow auto-merge or require maintainer approval based on change scope.

### Step 6: Gate the Tag

**Only after docs PR merged:**

```bash
git checkout dev
git pull origin dev
git tag -a v1.4.0 -m "Release v1.4.0"
git push origin v1.4.0
```

**This triggers release.yml:**
- Builds Docker images with version metadata
- Pushes to GHCR
- Creates GitHub Release with tarball asset

### Step 7: Verify Release Completeness

**Checklist:**

- [ ] Docs PR merged to `dev` (includes release notes, test report, manuals)
- [ ] Git tag created with `v{VERSION}` format
- [ ] GitHub Release created automatically (via release.yml)
- [ ] Release asset contains docker-compose.prod.yml, .env.prod.example, deployment guide
- [ ] Docker images tagged with version in GHCR
- [ ] `/version` endpoints return correct version metadata

## Anti-Patterns & Pitfalls

### ❌ Tag-First, Docs-Later

**Problem:** Tag created, release.yml runs and publishes images. Then docs are created. Docs become separate commit with no tag association.

**Fix:** Always gate docs → tag sequence. Enforce in release checklist.

### ❌ Incomplete Release Notes

**Problem:** Release notes missing features or fixes. Users confused about what shipped.

**Fix:** Query milestone issues/PRs, categorize, review before merging docs PR.

### ❌ Stale Manual Screenshots

**Problem:** Admin/user manual has screenshots from v1.2.0. v1.3.0 ships with new UI, but manuals not updated.

**Fix:** Include manual review step in release-docs workflow. Assign to Newt (doc author) with explicit prompt to update screenshots.

### ❌ Test Counts Incorrect

**Problem:** Release notes claim "127 tests passed" but actual count is 120. Users distrust release quality.

**Fix:** Generate test report from actual test run output (pytest, vitest), not hardcoded numbers.

## Real-World Timeline from Aithena

```
2026-03-15 v0.7.0 — versioning infrastructure shipped
2026-03-17 Release pattern implemented (issue #363, PR #427)

2026-05-10 v1.4.0 Release Gate
  - 2:00 PM: Trigger release-docs workflow
  - 2:15 PM: Release notes + test report generated
  - 2:30 PM: Newt reviews manuals, suggests updates
  - 2:45 PM: Merge docs PR #445
  - 3:00 PM: Create tag v1.4.0
  - 3:10 PM: release.yml builds images, pushes GHCR
  - 3:30 PM: GitHub Release created with tarball asset
  - 4:00 PM: Users deploy via `docker-compose.prod.yml` from release asset

2026-06-15 v1.5.0 (same pattern, faster)
  - Release-docs now cached, generation takes 10 min
  
2026-07-10 v1.6.0 (parallel with v1.5.0 hotfixes)
  - Multiple release gates happening simultaneously
  - Ralph (heartbeat) detects stale release PRs, notifies team
```

## Validation Checklist

- [ ] Release checklist issue created from template
- [ ] All milestone issues closed before starting
- [ ] release-docs workflow triggered manually
- [ ] Release notes generated (features/fixes/infra categories)
- [ ] Test report generated (actual test counts)
- [ ] Admin/user manuals reviewed and updated
- [ ] Docs PR created and merged to `dev` BEFORE tag
- [ ] Version tag created after docs PR merge
- [ ] release.yml triggered (via tag push)
- [ ] GitHub Release created with tarball asset
- [ ] `/version` endpoints return correct metadata

## References

- `.github/ISSUE_TEMPLATE/release.md`: Release checklist
- `.github/workflows/release-docs.yml`: Docs generation automation
- `.github/workflows/release.yml`: Tag-triggered build/push
- Issue #363: Release packaging strategy
- PR #427: Release packaging implementation
- `docs/admin-manual.md`, `docs/user-manual.md`: Release documentation
