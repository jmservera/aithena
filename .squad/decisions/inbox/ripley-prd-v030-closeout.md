# PRD: v0.3.0 — Stabilize Core (Close-Out)

**Author:** Ripley (Lead)
**Date:** 2026-03-14
**Status:** PROPOSED
**Milestone:** v0.3.0 — Stabilize Core

---

## Goal

Close v0.3.0 by completing the 6 remaining stabilization issues. These are cleanup, lint, and documentation tasks — no new features.

## Current State

- **Open:** 6 issues
- **Closed:** 0 issues (all work done but issues not formally closed via PRs)
- **Merged PRs supporting v0.3.0:** #115 (qdrant removal), #117 (ruff CI), #116/#129/#130/#131 (UV migrations)

## Remaining Issues

| # | Title | Owner | Effort | Status |
|---|-------|-------|--------|--------|
| #139 | Clean up smoke test artifacts from repo root | Dallas | S | PR #140 DRAFT |
| #100 | LINT-6: eslint + prettier auto-fix on aithena-ui | Dallas | S | Not started |
| #99 | LINT-5: ruff auto-fix across all Python services | Lambert | S | Not started |
| #96 | DOC-1: Document uv migration and dev setup in README | Dallas | S | Not started |
| #95 | LINT-4: Replace pylint/black with ruff in document-lister | Ripley | S | Not started |
| #92 | UV-8: Update buildall.sh and CI for uv | Dallas | S | Not started |

## Dependencies

None — all 6 issues are independent and can be worked in parallel.

## Acceptance Criteria

1. All smoke test artifacts (`.png`, `.md` snapshots, `.txt` logs) removed from repo root; `.gitignore` updated
2. `ruff check --fix` and `ruff format` pass cleanly across all Python services
3. `eslint` and `prettier` pass cleanly on `aithena-ui/`
4. `document-lister/` uses ruff instead of pylint/black (pyproject.toml updated, old configs removed)
5. `buildall.sh` uses `uv` for builds; CI workflows use `uv pip install`
6. README documents: prerequisites (Docker, uv, Node 20+), dev setup, `docker compose up`, running tests

## TDD Notes

These are cleanup/config tasks, not feature work. TDD applies only to #95 (verify ruff replaces pylint — run `ruff check` and confirm zero errors).

## Close-Out Criteria

When all 6 issues have merged PRs on `dev`:
1. Run full CI suite (all green)
2. Tag `v0.3.0`
3. Merge `dev` → `main`
4. Create GitHub Release
5. Scribe logs session
