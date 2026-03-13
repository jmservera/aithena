### 2026-03-13T21:05:35Z: Staggered @copilot issue routing

**By:** jmservera (via Copilot)

**What:** When routing issues to @copilot, use a staggered approach instead of labeling everything at once:
1. Identify which issues within a phase can be done in parallel (no inter-dependencies)
2. Label only that batch with `squad:copilot`
3. Wait for those PRs to be reviewed and merged
4. Then label the next batch (same phase or next phase)

**Why:** Labeling all 18 issues at once caused @copilot to work on Phase 3/4 before Phase 2 foundations existed. Results: 18 simultaneous draft PRs, dependency violations (UI built before API exists), review bottleneck, and wasted work that may need to be redone. Staggered batching respects dependency order and produces reviewable, mergeable work.

**Pattern:**
- Phase 2 batch 1: #36 (FastAPI search) — foundation, no deps
- Phase 2 batch 2: #37 (API tests), #38 (React search page) — depend on #36
- Phase 2 batch 3: #39 (facets), #40 (PDF viewer), #41 (frontend tests) — depend on #38
- Phase 3 batch 1: #42 (embeddings model), #43 (vector fields) — independent infra
- Phase 3 batch 2: #44 (chunking pipeline) — depends on #42+#43
- ...and so on
