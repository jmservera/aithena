# Release Checklist

This guide defines the canonical release process for Aithena. **All releases MUST follow this process in order.** This process prevents the failure we experienced in v1.11.0 where a tag was created on `dev` instead of on `main`, causing the Release workflow to reject the tag.

**Key Principle:** Tags must be created on `main` AFTER a PR from `dev` → `main` is merged. Never tag before the PR merges.

## Pre-Release: Preparation on `dev`

### [ ] Verify All Issues Closed in Milestone

1. Check the GitHub milestone view:
   ```bash
   gh milestone list --repo jmservera/aithena | grep "v<VERSION>"
   ```

2. Open the milestone and verify **all issues are closed**:
   ```bash
   gh issue list --repo jmservera/aithena --milestone "v<VERSION>" --state open
   ```

   If any issues are open, do NOT proceed. Return them to the PO (Juanma) for prioritization.

### [ ] Verify All Tests Pass on `dev`

Run the full test suite on your local `dev` branch:

**Frontend (aithena-ui):**
```bash
cd src/aithena-ui
npm ci
npm run lint
npm run format:check
npm run build
npm test
```

**Python Services:**
```bash
# solr-search
cd src/solr-search && uv run pytest -v --tb=short && uv run ruff check .

# document-indexer
cd src/document-indexer && uv run pytest -v --tb=short && uv run ruff check .

# document-lister
cd src/document-lister && uv run pytest -v --tb=short && uv run ruff check .

# embeddings-server
cd src/embeddings-server && uv run pytest -v --tb=short && uv run ruff check .
```

**Integration E2E Tests:**
```bash
# These run in CI, but you should verify they pass before release
# Check the "Docker Compose integration + E2E" job in the main branch CI
```

### [ ] Verify Security Reviews Completed

Review the security checklist:
- [ ] All CVEs in the milestone have been triaged (check `docs/security/baseline-exceptions.md`)
- [ ] Code scanning results (Bandit, CodeQL, checkov, zizmor) all pass on `dev`
- [ ] No new security alerts introduced in this release

Check GitHub Security tab for any open alerts blocking the release.

### [ ] Update VERSION File

1. Determine the new version following semver:
   - Patch: `v1.11.0` → `v1.11.1` (bugfixes only)
   - Minor: `v1.11.0` → `v1.12.0` (new features, backward compatible)
   - Major: `v1.11.0` → `v2.0.0` (breaking changes)

2. Update the VERSION file:
   ```bash
   echo "X.Y.Z" > VERSION
   ```

### [ ] Update CHANGELOG.md

Craft release notes summarizing:
- **Features added** (by epic/domain)
- **Bugfixes** (link to issues)
- **Security updates** (CVEs, mitigations)
- **Breaking changes** (if major version)
- **Dependencies upgraded** (major updates only)
- **Documentation** (new guides, updates)

**Template:**
```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- Feature 1 (Closes #123)
- Feature 2 (Closes #124)

### Fixed
- Bug 1 (Closes #125)
- Bug 2 (Closes #126)

### Changed
- Breaking change 1 (requires action: ...)

### Security
- CVE-YYYY-NNNNN patched: ...

### Dependencies
- Upgraded solr-search to Node.js 22

### Known Issues
- None

### Testing
- All 6 test suites pass (unit, lint, integration, E2E)
- Integration E2E verified on staging
- [Test Report](test-report-vX.Y.Z.md)

### Deployment
- No schema migrations required
- No breaking API changes
- Docker images tagged as X.Y.Z, X.Y, X (major version)
```

### [ ] Commit VERSION + CHANGELOG to `dev`

```bash
git add VERSION CHANGELOG.md
git commit -m "Release vX.Y.Z — <Title>"
git push origin dev
```

Wait for CI checks to pass on this commit (all tests must be green).

---

## Release PR: Create PR from `dev` → `main`

### [ ] Create the Release PR

```bash
gh pr create \
  --base main \
  --head dev \
  --title "Release vX.Y.Z — <Title>" \
  --body "
Releases v1.11.0 with:
- Feature 1
- Bugfix 2
- Security patch

Closes: #<issue1>, #<issue2>, ...

Release artifacts committed to dev in commit <sha>.

**Pipeline:** This PR triggers all CI checks (unit tests, lint, security scans, integration E2E). Once ALL checks pass, merge this PR. Do NOT merge if any check fails.
"
```

Note the PR number (e.g., #854).

### [ ] Wait for ALL CI Checks to Pass

The release PR will trigger:
1. **Unit Tests** — all 6 test suites
2. **Linting** — ruff (Python), ESLint (TypeScript)
3. **Security Scans** — Bandit, CodeQL, checkov, zizmor
4. **Integration + E2E** — full Docker Compose stack with browser tests

**Status checks required by main branch protection:**
- `All tests passed` ✅
- `Python lint (ruff)` ✅
- `Docker Compose integration + E2E` ✅

You can monitor progress here:
```bash
gh pr view <number> --web  # Opens the PR in browser
gh pr checks <number>      # Shows check status
```

### [ ] Fix Any Failing Checks

If a check fails:
1. Identify the failure (read the check log)
2. Create a follow-up commit on `dev`:
   ```bash
   git fetch origin dev && git checkout dev
   # Fix the issue (e.g., failing test, lint error)
   git add <files>
   git commit -m "Fix <check name> for vX.Y.Z release"
   git push origin dev
   ```
3. The PR will automatically update and re-run checks
4. Repeat until all checks pass

**Do NOT merge with failing checks.** Branch protection enforces this.

### [ ] Merge the Release PR

Once all CI checks pass:

```bash
gh pr merge <number> --merge
```

Use `--merge` to create a **merge commit** (not squash). This preserves the release history and makes the commit graph easier to follow.

**Why merge, not squash?**
- Merge commits show the release boundary clearly
- Squash loses the intermediate development history
- Easier to bisect or revert an entire release

---

## Tag & Release: Create Tag on `main`

### [ ] Fetch Latest `main` and Verify Release Commit

After the PR merges, fetch the latest main and verify the release commit is there:

```bash
git fetch origin main
git log origin/main --oneline -5
```

Verify the top commit is the merge commit "Merge pull request #<number> from dev".

### [ ] Create Annotated Tag on `main`

```bash
git tag -a vX.Y.Z \
  -m "Release vX.Y.Z — <Title>

See CHANGELOG.md for details.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>" \
  origin/main
```

**Important:**
- Tag must be **on `origin/main`** (or checked-out main, same commit)
- Tag name format: **`vX.Y.Z`** (semver with `v` prefix)
- Use **annotated tags** (`-a`), not lightweight tags
- Include co-author trailer in tag message (GitHub convention)

### [ ] Push the Tag

```bash
git push origin vX.Y.Z
```

This triggers the **Release workflow** (`.github/workflows/release.yml`).

### [ ] Monitor the Release Workflow

The Release workflow will:
1. **Validate tag** — Check that `vX.Y.Z` is valid semver
2. **Validate tag is on main** — Check that the commit is reachable from main
3. **Build Docker images** — Build all 6 services and push to GHCR
4. **Package release** — Create tarball + SHA256 checksum
5. **Create GitHub release** — Publish release with artifacts

Monitor the workflow:

```bash
gh run list --workflow release.yml --limit 1
gh run view <run_id> --log
```

Or open in browser:
```bash
gh workflow view release.yml --web
```

### [ ] Verify Release Assets

Once the workflow completes successfully:

```bash
gh release view vX.Y.Z
```

You should see:
- Release title: `Release vX.Y.Z — <Title>`
- Release body: Auto-generated notes from commit history
- Assets:
  - `aithena-vX.Y.Z-release.tar.gz` (production package)
  - `aithena-vX.Y.Z-release.tar.gz.sha256` (checksum)

---

## Post-Release: Verify and Communicate

### [ ] Verify Docker Images Published to GHCR

Check that all 6 images were pushed to GitHub Container Registry:

```bash
gh api /orgs/jmservera/packages?package_type=container
```

Look for:
- `aithena-admin` — tagged `vX.Y.Z`, `X.Y`, `X`, `latest`
- `aithena-aithena-ui` — tagged `vX.Y.Z`, `X.Y`, `X`, `latest`
- `aithena-document-indexer` — tagged `vX.Y.Z`, `X.Y`, `X`, `latest`
- `aithena-document-lister` — tagged `vX.Y.Z`, `X.Y`, `X`, `latest`
- `aithena-embeddings-server` — tagged `vX.Y.Z`, `X.Y`, `X`, `latest`
- `aithena-solr-search` — tagged `vX.Y.Z`, `X.Y`, `X`, `latest`

Or view them in the GitHub UI: https://github.com/organizations/jmservera/packages?repo_name=aithena&ecosystem=container

### [ ] Close the Milestone

Mark the milestone as released:

```bash
# Get the milestone ID
gh api repos/jmservera/aithena/milestones | \
  python3 -c "import sys, json; m = [x for x in json.load(sys.stdin) if x['title'] == 'vX.Y.Z']; print(m[0]['number'] if m else '')"

# Close it (replace {id} with the number from above)
gh api -X PATCH repos/jmservera/aithena/milestones/{id} \
  -f state=closed
```

### [ ] Update Squad Identity

Update the squad's running status:

```bash
cat > .squad/identity/now.md <<'EOF'
# Now

**Latest Release:** vX.Y.Z (released YYYY-MM-DD)

**Current Milestone:** vX.Y.Z+1 (in progress)

**Bottleneck:** None

**Key Metrics:**
- Tests: All 6 suites passing
- Coverage: NN%
- Security: 0 critical alerts

**Last Sync:** YYYY-MM-DD
EOF

git add .squad/identity/now.md
git commit -m "Update identity: post-release vX.Y.Z"
git push origin dev
```

### [ ] Communicate Release

- [ ] Notify Juanma (PO) that release is live
- [ ] Post release summary to team channel
- [ ] Link to GitHub release and CHANGELOG
- [ ] Highlight breaking changes or important notes
- [ ] Share production deployment instructions (if needed)

---

## ⚠️ Common Mistakes to Avoid

### ❌ DO NOT: Create tags on `dev`

Tags must be on `main` AFTER the PR merges.

**What happens if you do:**
```bash
git tag vX.Y.Z dev
git push origin vX.Y.Z
# Release workflow rejects the tag: "ahead_by != 0"
# Tag is orphaned, you must delete it
```

**Fix:**
```bash
git tag -d vX.Y.Z
git push origin --delete vX.Y.Z
# Then follow this guide correctly
```

### ❌ DO NOT: Push directly to `main`

Main has branch protection. Use a PR.

**What happens if you do:**
```bash
git push origin dev:main
# ERROR: GitHub rejects the push (force push disabled)
```

**Fix:**
Use the PR process (see "Release PR" section above).

### ❌ DO NOT: Create the GitHub release manually

The Release workflow does this automatically with proper artifacts.

**What happens if you do:**
- Release is created without the tarball + checksum
- Operators can't download a production package
- You'll need to delete it and re-run the workflow

**Fix:**
Delete the manual release. Let the workflow create it.

### ❌ DO NOT: Tag before the PR merges

The tag validation checks that the commit is reachable from `main`.

**What happens if you do:**
```bash
# On dev branch, about to merge PR:
git tag vX.Y.Z HEAD  # Tags the dev commit
git push origin vX.Y.Z
# Release workflow fails: "Tag not on main"
```

**Fix:**
Delete the tag, merge the PR, then tag the merge commit on `main`.

### ❌ DO NOT: Squash-merge the release PR

Use a regular merge to preserve commit history.

**Why?**
- Squash loses the intermediate commits
- Release history becomes harder to follow
- `git bisect` becomes less useful
- Team can't see the work that went into the release

**Correct:**
```bash
gh pr merge <number> --merge
```

---

## Troubleshooting

### Release workflow fails: "Tag not reachable from main"

**Cause:** Tag was created on a commit not merged to `main` (usually `dev`).

**Fix:**
```bash
# Delete the stale tag
git tag -d vX.Y.Z
git push origin --delete vX.Y.Z

# Wait for the dev → main PR to merge
# Then create the tag on main:
git fetch origin main
git tag -a vX.Y.Z -m "..." origin/main
git push origin vX.Y.Z
```

### Docker image build fails in Release workflow

**Cause:** A Dockerfile has a syntax error or missing dependency.

**Fix:**
1. Run `buildall.sh` locally to reproduce the error
2. Fix the Dockerfile on `dev`
3. Create a follow-up commit and push to `dev`
4. The PR will re-run CI checks
5. Once fixed, merge the PR and re-tag

### GitHub release not created with artifacts

**Cause:** `package-release` job failed or `github-release` job didn't download artifacts.

**Fix:**
1. Check the Release workflow logs for the specific step failure
2. Fix the underlying issue (usually a missing file or script error)
3. Delete the stale tag and release:
   ```bash
   git push origin --delete vX.Y.Z
   gh release delete vX.Y.Z
   ```
4. Fix the code on `dev`
5. Re-run the entire release process

---

## Related Documentation

- **Release workflow definition:** `.github/workflows/release.yml`
- **Pre-release validation:** `.github/workflows/pre-release-validation.yml`
- **Docker images:** Each service has a `src/<service>/Dockerfile`
- **Build process:** `buildall.sh`
- **Security baseline:** `docs/security/baseline-exceptions.md`
- **Deployment guide:** `docs/deployment/production.md`

---

## Version History

| Date | Release | Release Lead | Notes |
|------|---------|--------------|-------|
| 2026-03-22 | v1.10.1 | Ripley | Added gate review; BCDR + metadata editing |
| 2026-03-21 | v1.10.0 | Ripley | User collections + book metadata; 4-wave execution |
| 2026-03-20 | v1.9.0 | Newt | User management + RBAC |
| 2026-03-15 | v1.8.0 | Dallas | UI/UX redesign + Lucide icons |
| 2026-02-28 | v1.7.1 | Parker | Tech debt milestone |
| ... | ... | ... | ... |

---

**Last Updated:** 2026-03-22 by Ripley (Lead)

**Process Validation:** Follow this checklist exactly. Deviations cause release failures. If you discover a gap in this document, update it after the release.

