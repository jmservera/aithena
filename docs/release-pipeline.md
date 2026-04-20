# Release Pipeline

This document describes the enforced release pipeline for Aithena. All releases follow a strict `dev → main → tag` flow to ensure quality gates are met before any production release.

## Pipeline Stages

```
┌─────────┐     ┌──────────────┐     ┌─────────────┐     ┌───────────┐
│  dev    │────▶│ PR: dev→main │────▶│  main       │────▶│  Tag      │
│ branch  │     │              │     │  branch     │     │  vX.Y.Z   │
└─────────┘     └──────────────┘     └─────────────┘     └───────────┘
     │                 │                                       │
 ci.yml           ci.yml +                               release.yml
 (unit tests)    integration-test.yml                  (build + publish)
                 (full E2E tests)
```

### Stage 1: Development on `dev`

All feature work happens on branches created from `dev`.

- **Branch naming:** `squad/{issue-number}-{kebab-case-slug}` or `copilot/{slug}`
- **CI trigger:** Push to `dev` and PRs targeting `dev` run **ci.yml**
- **ci.yml checks:**
  - Change detection (skips tests for docs-only changes)
  - Unit tests for all six services (document-indexer, solr-search, aithena-ui, admin, document-lister, embeddings-server)
  - Python lint (ruff)
  - Gate job: `All tests passed` (required status check)

### Stage 2: Release Preparation PR to `dev`

Before merging to `main`, a release prep PR is created on `dev`:

1. Bump the `VERSION` file to the target release version
2. Update `CHANGELOG.md` with the release notes
3. Ensure all milestone issues are closed
4. This PR goes through the standard ci.yml checks

### Stage 3: PR from `dev` to `main`

When `dev` is ready for release, a PR is opened from `dev` → `main`.

- **CI trigger:** PRs targeting `main` run **integration-test.yml**
- **integration-test.yml checks:**
  - Full Docker Compose build of all services
  - Playwright end-to-end tests against the running stack
  - Release screenshots captured as artifacts
- **ci.yml** also runs (unit tests + lint)
- Both workflows must pass before the PR can be merged

### Stage 4: Tag on `main` → Release

After the PR is merged to `main`, a semver tag is created on `main`:

```bash
git checkout main
git pull origin main
git tag v1.2.3
git push origin v1.2.3
```

- **CI trigger:** Tag push matching `v*.*.*` runs **release.yml**
- **release.yml performs:**
  1. **Tag format validation** — must match `vX.Y.Z` (stable semver, no pre-release)
  2. **Main branch validation** — verifies the tagged commit is reachable from `main` via the GitHub API. Tags on any other branch (e.g., `dev`, feature branches) are **rejected**
  3. **Docker image build and push** — all six service images pushed to GitHub Container Registry (ghcr.io) with semver tags
  4. **Release package** — production Docker Compose config, installer scripts, and documentation packaged as a tarball with SHA256 checksum
  5. **GitHub Release** — created with auto-generated notes and the release package attached

## Enforcement Rules

### Tags must be on `main`

The release workflow validates that the tagged commit exists on the `main` branch. If a tag is pushed on any other branch, the workflow fails with:

```
::error::Tag vX.Y.Z points to a commit that is N commit(s) ahead of main.
::error::Release tags must only be created on the main branch.
```

This prevents accidental releases from `dev` or feature branches.

### Integration tests required for `main`

PRs targeting `main` trigger the integration-test workflow, which runs the full E2E suite. This must be configured as a required status check in GitHub branch protection settings — PRs cannot be merged to `main` without passing integration tests.

### No direct pushes to `main`

Branch protection rules require PRs for all changes to `main`. Direct pushes are blocked.

## Pre-Release (RC) Builds

Before merging `dev` into `main`, you can build release candidate images to validate the upcoming release. The pre-release workflow builds all six service containers with an RC tag (e.g., `1.16.0-rc.1`) and pushes them to GHCR for local testing.

- **Trigger:** `workflow_dispatch` on the `dev` branch with a `version` input
- **RC numbering:** Auto-increments from existing tags, or set explicitly
- **Testing:** Pull RC images locally with `docker/compose.prod.yml` and run validation

See [Pre-Release Testing](pre-release-testing.md) for the full step-by-step workflow.

## Quick Reference

| Action | Branch | Workflow | Required? |
|--------|--------|----------|-----------|
| Push/PR to `dev` | `dev` | ci.yml (unit tests + lint) | ✅ Yes |
| Pre-release RC build | `dev` | pre-release.yml (manual trigger) | 🔶 Recommended |
| PR to `main` | `main` | ci.yml + integration-test.yml | ✅ Yes |
| Tag `vX.Y.Z` on `main` | `main` | release.yml (build + publish) | ✅ Yes |
| Tag on non-`main` branch | any | release.yml → **FAILS** | ❌ Blocked |

## Related Files

- `.github/workflows/ci.yml` — Unit tests and lint
- `.github/workflows/integration-test.yml` — E2E integration tests
- `.github/workflows/release.yml` — Release build and publish
- `.github/workflows/pre-release.yml` — RC image builds for pre-release validation
- `.github/workflows/build-containers.yml` — Reusable container build workflow
- `.github/workflows/pre-release-validation.yml` — Manual pre-release checks
- `VERSION` — Source of truth for the current version
- `CHANGELOG.md` — Release notes history
- `docs/pre-release-testing.md` — Pre-release testing workflow guide
