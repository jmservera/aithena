---
name: "pr-integration-gate"
description: "Required build/test checks before merging PRs to dev"
domain: "ci, workflow, quality"
confidence: "high"
source: "earned — 7 consecutive copilot PRs (Phase 2–3) with zero build/test failures in dev merges"
author: "Ripley"
created: "2026-03-14"
last_validated: "2026-03-14T23:45"
---

## Context

Use when reviewing or merging any PR to `dev`. The UI broke in Session 2 because frontend PRs were merged without verifying the build. This skill defines the minimum gates.

## Patterns

### 1. Frontend PRs (changes in `aithena-ui/`)

Before merge, verify:
```bash
cd aithena-ui
npm install --legacy-peer-deps
npm run build    # Must exit 0
npm run lint     # Must exit 0
```

If the PR adds dependencies, also verify `package-lock.json` is committed and consistent.

### 2. Backend PRs (changes in `solr-search/`, `document-indexer/`, `document-lister/`)

Before merge, verify:
```bash
cd <service>
python3 -m pytest tests/ -q    # Must exit 0
python3 -m compileall .        # Must exit 0
```

For `solr-search`, also run integration tests:
```bash
python3 -m pytest tests/test_integration.py -q
```

### 3. Infrastructure PRs (changes in `docker-compose.yml`, `nginx/`, `solr/`)

Before merge, verify:
```bash
docker compose config --quiet   # Must exit 0
```

For nginx changes:
```bash
docker run --rm -v $(pwd)/nginx:/etc/nginx/conf.d:ro nginx:alpine nginx -t
```

### 4. CI automation (target state)

These gates should be enforced by `.github/workflows/ci.yml`:
- Frontend: `npm run build && npm run lint` on PRs touching `aithena-ui/`
- Backend: `pytest` on PRs touching Python services
- Infra: `docker compose config` on PRs touching compose/nginx

Until CI covers all paths, the reviewing agent must run these manually.

## Anti-Patterns

- **Don't merge frontend PRs without `npm run build`** — TypeScript errors and missing imports only surface at build time
- **Don't skip `--legacy-peer-deps`** — Vite 8 + plugin-react 4.7 peer conflict will fail a plain `npm install`
- **Don't merge backend PRs without `pytest`** — the `save_state()` TypeError was catchable by existing tests
- **Don't assume CI covers everything** — check what the workflow actually tests before relying on green checks

## References

- `.github/workflows/ci.yml` — current CI config
- `.squad/skills/squad-pr-workflow/SKILL.md` — branch and PR conventions
- `.squad/agents/dallas/history.md` — UI breakage incident
