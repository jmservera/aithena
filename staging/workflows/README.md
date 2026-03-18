# Staging Workflows

This directory contains GitHub Action workflows that are **not yet deployed** to `.github/workflows/`.

## Why Staging?

Due to OAuth token scope limitations in GitHub Codespaces, workflows cannot be pushed directly to `.github/workflows/` from this environment. Instead, they are created in `staging/workflows/` and must be manually moved to activate them.

## Current Staged Workflows

### `release-docs.yml` — Automated Release Documentation

**Purpose**: Automatically generate release documentation when a version tag is pushed.

**Triggers**:
- Tag push matching `v*.*.*` (e.g., `v1.8.0`)
- Manual workflow_dispatch with version input

**What it does**:
1. Collects release context (merged PRs, closed issues, CHANGELOG, CI results)
2. Uses GitHub Copilot CLI to generate comprehensive release notes
3. Creates `docs/releases/v{version}-release-notes.md`
4. Opens a PR for human review before merging

**How to deploy**:
```bash
# From repository root
mv staging/workflows/release-docs.yml .github/workflows/release-docs.yml
git add .github/workflows/release-docs.yml
git commit -m "feat: add automated release documentation workflow"
git push origin main
```

**Configuration required**:
- No additional secrets needed (uses `GITHUB_TOKEN`)
- Milestone names must match version format: `v1.8.0`, `v1.9.0`, etc.
- PRs should be labeled with milestone labels for accurate collection

**Testing the workflow**:
```bash
# Manual trigger
gh workflow run release-docs.yml -f version=1.8.0

# Or push a tag
git tag v1.8.0
git push origin v1.8.0
```

**Dependencies**:
- GitHub CLI (`gh`) — pre-installed on ubuntu-latest runners
- Copilot CLI (optional, falls back to template if unavailable)
- jq (pre-installed)

## Action Pinning Convention

All GitHub Actions in this repository are pinned to **commit SHAs** (not floating tags like `@v4`) for security and reproducibility. Example:

```yaml
- uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd  # v6.0.2
```

When updating actions, find the SHA for the desired version tag:
```bash
# Example: Find SHA for actions/checkout@v6.0.2
gh api repos/actions/checkout/git/ref/tags/v6.0.2 --jq '.object.sha'
```

## Workflow Design Principles

All workflows in this repository follow these conventions:

1. **Minimal Permissions**: Use `permissions:` to grant only what's needed
2. **Concurrency Control**: Use `concurrency:` to prevent duplicate runs
3. **Timeout Protection**: Set `timeout-minutes:` on all jobs
4. **SHA Pinning**: Pin all actions to commit SHAs with version comments
5. **Fail Fast**: No `continue-on-error` unless explicitly justified
6. **Copilot Co-author**: Include `Co-authored-by: Copilot <...>` in commit messages

## Related Documentation

- [CI/CD Overview](../../docs/development/ci-cd.md) (if exists)
- [Release Process](../../docs/development/release-process.md) (if exists)
- [Squad Team Decisions](../../.squad/decisions.md)

## Questions?

- Check existing workflows in `.github/workflows/` for patterns
- See Brett's charter: `.squad/agents/brett/charter.md`
- Ask in issue #523 (the feature request for this workflow)
