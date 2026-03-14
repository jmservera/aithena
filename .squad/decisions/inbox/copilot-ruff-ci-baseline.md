### 2026-03-14T08:38: Ruff CI introduced as non-blocking baseline
**By:** Lambert (via Copilot)
**What:** Added root Ruff configuration plus a `python-lint` GitHub Actions job using `astral-sh/ruff-action@v3`, with each Ruff step marked `continue-on-error: true` until the backlog item for cleanup lands.
**Why:** Issue #91 requires visibility for current lint/format debt in CI now, without blocking merges before the repository-wide fixes in LINT-5.
