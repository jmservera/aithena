# Lambert — History

## Core Context

Lambert owns test strategy, regression coverage, release validation, and QA evidence across pytest, Vitest, Playwright, and stress tooling.

- Stable quality posture: solr-search coverage stays around 91%+, document-indexer targets >=80%, and main has little reported flakiness.
- Release reporting should keep unit, integration, E2E, and stress counts separate; historic totals differ because suites are counted differently.
- Cross-endpoint tests catch more regressions than isolated mocks (register→login, delete→login-fails, update→list-reflects).
- Reuse `E2E_API_TOKEN` in CI/local E2E before password login to avoid rate-limit noise.
- Solr readiness validation should wait for ACTIVE replicas and verify real endpoints like `/v1/search`, not only cluster status.

## Active Patterns

- Audit existing coverage before adding tests to avoid duplicate assertions.
- Use `object.__setattr__` when patching frozen settings/dataclasses in tests.
- Restore `os.environ` before final `importlib.reload(config)` so module-level settings are not left stale.
- Prefer accessible/i18n-safe selectors over raw text for UI assertions.
- For data-dependent Playwright cases, skip explicitly with annotations instead of inventing fake evidence.

## Recent Learnings

### 2026-06-13T15:31:32.692+00:00 — #1745 Test infrastructure documentation
- Consolidated fragmented testing guidance into `docs/testing/README.md` as the single source of truth for prerequisites, commands, framework usage, CI expectations, debugging, and common gotchas.
- Key documented patterns include rate-limiter reset, Solr readiness polling, circuit-breaker constructor shape, i18n selectors, PDF viewer sequencing, and E2E token reuse.

### 2026-06-07T08:10:57.944+00:00 — Evidence gate support (#1344, #1354)
- Do not close quantization or Solr-version benchmark issues from tooling-only checks.
- Required close-out evidence is same-host, same-corpus benchmark output with recall/memory metadata, failed query IDs, and measured Solr samples.

### 2026-06-06T22:00:15.185+00:00 — Quantization / benchmark test quality review
- Optional int8 support is acceptable when docs clearly state that live recall/memory evidence is still pending.
- Phase 2 live checks must fail loudly when the fixture is wrong-shaped or unreachable; benchmark gates should report unsupported comparisons instead of implying claims.

### 2026-06-05 — OpenVINO smoke-test prevention (#1662)
- Smoke tests prove runtime boot/respond behavior, but not intermediate build-state correctness.
- Any service using `uv sync --inexact` should add a build-time version verification step so dependency drift fails the image build early.
