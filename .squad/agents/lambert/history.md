# Lambert — History

## Core Context

Lambert owns tests, release validation evidence, regression coverage, CI gate confidence, and QA framing.

**Current testing posture:** the repo has grown past roughly 1.3k collectable tests across pytest, Vitest, Playwright, and stress suites, with solr-search coverage around 91%+. Report counts by suite, not as one blended number, because unit/integration/E2E/stress totals are often rolled up differently.

## Key Patterns

- **Audit coverage before adding tests.** Search existing assertions first so new work closes a gap instead of duplicating signal.
- **Cross-endpoint flows beat isolated mocks.** Register→login, delete→login-fails, update→list-reflects, and search→detail flows catch more regressions than isolated unit-only checks.
- **After manifest or lockfile conflicts, rerun full verification.** `git checkout --theirs` can silently drop earlier dependency bumps.
- **Be precise about auth expectations.** Wrong role should return 403; unauthenticated should return 401.
- **Use fixture-safe mutation for frozen settings.** `object.__setattr__` and disciplined env restore/reload patterns prevent cleanup from testing stale module state.
- **Playwright should discover through live read-only endpoints where possible.** Skip data-dependent cases explicitly instead of manufacturing fake confidence.
- **Reuse `E2E_API_TOKEN` in CI before password login.** It reduces rate-limit flakes and keeps setup closer to production behavior.
- **Name tests after exact assertions.** Distinguish metadata URL validation from file retrieval, semantic fallback from strict semantic, and delete-then-reindex from plain delete.
- **UI/API contracts matter more than internal implementation details.** Test page ranges, highlights, badges, and selectors instead of chunk internals the UI does not own.
- **Live Solr runtime checks should be opt-in and honest.** Preflight/static validation is useful, but performance, recall, memory, and version claims need real paired evidence.
- **Benchmark evidence gates are strict.** Same host, same corpus, expected Solr/version metadata, failed-query IDs, and measured memory samples are required before closing search-performance issues.
- **Local Docker + Playwright/integration validation is preferred when feasible.** Report local evidence explicitly in PRs.

## Useful Edge Cases

- `RateLimiter(max_requests=0)` must still allow repeated uploads.
- `CircuitOpenError` tests need the real constructor shape.
- Similar-books chunk IDs resolve through `parent_id_s`; bad chunks or missing parents should 404.
- `CollectionBadge` and other i18n UI need semantic selectors, not brittle raw text checks.
- Restore validation should exercise the real search API, not just cluster-status endpoints.

## Skill References

- `.squad/skills/pytest-aithena-patterns/SKILL.md`
- `.squad/skills/playwright-e2e-aithena/SKILL.md`
- `.squad/skills/vitest-testing-patterns/SKILL.md`
- `.squad/skills/e2e-auth-reuse/SKILL.md`
- `.squad/skills/ci-pr-gates/SKILL.md`
