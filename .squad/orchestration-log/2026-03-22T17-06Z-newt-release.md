# 2026-03-22T17:06Z — Newt Release Orchestration

**Milestone:** v1.12.1 Release  
**Status:** COMPLETE

## Accomplishments

- **v1.12.1 shipped** to production
  - VERSION file bumped to 1.12.1
  - CHANGELOG.md updated with all 18 issues (11 from v1.12.0 A/B infrastructure + 7 from v1.12.1 polish)
  - Git tag `v1.12.1` created on main branch
  - GitHub Release published with release notes

- **PRs merged to complete release:**
  - PR #927 (version bump + CHANGELOG) → dev
  - PR #929 (dev→main merge for release)
  - All changes backported to production via main branch merge

## Metrics

- **Issues resolved:** 18 total (v1.12.0 + v1.12.1)
- **Release timeline:** Consolidated into single v1.12.1 release point
- **Branch protection:** dev branch protected; version bump required PR flow

## Next Gates

- v1.14.0 (A/B Testing Evaluation UI) now gated on embeddings evaluation results
- If e5-base model benchmarks show negligible loss, skip v1.14.0 entirely
- Otherwise, proceed with A/B UI only if quality differences require human judgment

## Process Notes

- Integration tests in CI remain flaky (embeddings-server health check)
- Main branch merges may require admin override or manual owner intervention due to branch protection
