# PR Triage & Prioritization — 2026-07-14

**Author:** Ripley (Lead)
**Status:** EXECUTED

## Merged

- **#55** — E2E test harness (Phase 4, approved, clean merge)
- **#101** — Dependabot: Bump esbuild, vite, @vitejs/plugin-react
- **#102** — Dependabot: Bump js-yaml 4.1.0 → 4.1.1

## Priority Order for Remaining Work

1. **#63 (Phase 2, HIGH)** — PDF viewer panel. Assigned @copilot. Surgical extraction: only PdfViewer.tsx + integration.
2. **#68 (Phase 3, HIGH)** — Hybrid search modes. Assigned @copilot. Keystone for Phase 3.
3. **#69 (Phase 3, MEDIUM)** — Similar books endpoint. Assigned @copilot. BLOCKED on #68.
4. **#56 (Phase 4, LOW)** — Docker hardening. Assigned @copilot, low priority.

## Closed (not worth fixing)

- **#70** — Similar books UI. Built on old chat UI (pre-PR #62). Needs full rewrite, not rebase.
- **#58** — PDF upload endpoint. Targets qdrant-search/, architecturally wrong. Needs fresh implementation.
- **#59** — PDF upload UI. Built on old chat UI. Needs full rewrite after upload endpoint exists.

## Rationale

PRs built on the old chat UI (before PR #62 rewrote to search paradigm) cannot be meaningfully rebased — the component tree is completely different. PRs targeting qdrant-search/ instead of solr-search/ are architecturally misaligned per ADR-001/ADR-003. Both classes should be re-created from scratch when their phase is prioritized.

PRs that only need conflict resolution in existing solr-search/ or aithena-ui/ files (#63, #68, #69, #56) are worth fixing because the core logic is sound.
