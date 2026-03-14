# Retro — v0.3.0 Stabilize Core (Post-Phase 2/3)

**By:** Ripley (Lead)
**Date:** 2026-03-14
**Scope:** Sessions 1–3, Phase 1–3 work

---

## What Went Well

1. **Pipeline bugs caught and fixed fast.** Parker found the lister scan bug (`DOCUMENT_WILDCARD=.pdf` matching nothing) and the indexer `save_state()` `file_path` collision in the same session — both root causes of the "pipeline looks idle" symptom. Lambert's smoke test against the real library mount confirmed the fixes.

2. **Smoke tests with Playwright caught real issues.** Lambert's Playwright runs caught the `/v1/` API prefix mismatch (UI calling `/v1/search/` while backend exposed `/search`) before users could. The smoke cycle — docker compose up → wait-for-health → Vite dev → Playwright validate — became a repeatable pattern.

3. **Parallel work model scaled.** @copilot delivered 14 PRs from the P4 spec while the squad worked locally on Phases 1–3. Ripley triaged and merged 6 safe PRs in one session, held 8 for phase sequencing.

4. **Skills system paid off.** The `solrcloud-docker-operations` skill guided Brett's SolrCloud bootstrap and admin ingress work. The `path-metadata-heuristics` skill kept Parker's indexer changes consistent with the library's real folder conventions.

5. **Milestone cadence established.** Five milestones (v0.3.0–v1.0.0) with a pause-log-reskill-tag-merge cycle keeps the team focused and prevents brownfield drift.

6. **Branching strategy prevented further UI breakage.** Moving to a `dev` integration branch stopped uncoordinated merges to the feature branch from breaking the UI again.

---

## What Didn't Go Well

1. **UI broke from uncoordinated PR merges.** Before the `dev` branch existed, merged frontend PRs (chat-era removal + search rewrite) left the UI non-functional. No integration test gate caught it.

2. **Stale branches / conflicts were a recurring time sink.** All 14 @copilot PRs targeted the wrong branch (`jmservera/solrstreamlitui` instead of `dev`). PR #138 had merge conflicts. Manual retargeting was needed across all PRs.

3. **Smoke test artifacts committed to repo root.** PNG screenshots, markdown snapshots, and network logs landed in the repo root instead of a dedicated `e2e/` or `.smoke/` directory. Needs cleanup.

4. **Collection bootstrap was a critical missing piece.** The `books` collection didn't auto-create on `docker compose up`. Lambert had to manually run `solr zk upconfig` + `collections?action=CREATE` before `/search` stopped returning 502. This blocked every smoke test until fixed.

5. **document-indexer didn't start automatically.** Compose left `document-indexer` in `Created` state while `document-lister` was already queueing. Manual `docker compose up -d document-indexer` was needed.

---

## Key Learnings

1. **Hybrid dev workflow (Docker infra + local code) is essential.** Running Solr/ZooKeeper/Redis/RabbitMQ in Docker while developing Python/TypeScript locally with hot reload is the productive path. Full-Docker dev is too slow for iteration.

2. **Must validate UI build before merging frontend PRs.** `npm run build` must pass as a merge gate. Dallas proved this when the post-merge UI was broken but `npm run build && npm run lint` would have caught it.

3. **API contract mismatches (`/v1/` prefix) cost significant debugging time.** The frontend assumed `/v1/search/`, the backend exposed `/search`. Parker added `/v1/` aliases, but this should have been a single source of truth from the start.

4. **Page-level search needs app-side extraction.** Solr Tika loses page boundaries during extraction. The v0.5.0 plan correctly uses app-side PDF parsing to preserve page numbers before sending to Solr.

5. **`solr-init` container pattern works for bootstrap.** Brett's init container that uploads configsets and creates the collection on first run solved the manual bootstrap problem.

6. **`--legacy-peer-deps` is required for aithena-ui.** Vite 8.0.0 conflicts with `@vitejs/plugin-react@4.7.0` peer requirements. This needs to be documented and eventually resolved.

7. **FastAPI 0.99.1 + Starlette 0.27.0 requires `httpx<0.28`.** Parker discovered this during CI integration test setup. TestClient compatibility constraint.

---

## Action Items

| # | Action | Owner | Target |
|---|--------|-------|--------|
| 1 | Create `smoke-testing` skill | Ripley | This retro |
| 2 | Create `api-contract-alignment` skill | Ripley | This retro |
| 3 | Create `pr-integration-gate` skill | Ripley | This retro |
| 4 | Update `solrcloud-docker-operations` confidence → high | Ripley | This retro |
| 5 | Update `path-metadata-heuristics` confidence → high | Ripley | This retro |
| 6 | Clean smoke artifacts from repo root | Dallas | v0.4.0 |
| 7 | Add `npm run build` gate to CI for `aithena-ui/` | Parker/Lambert | v0.4.0 |
| 8 | Document `--legacy-peer-deps` requirement | Dallas | v0.4.0 |
