---
name: "smoke-testing"
description: "Local smoke test cycle: Docker infra up → health wait → Vite dev → Playwright validate → cleanup"
domain: "testing, e2e, playwright"
confidence: "medium"
source: "earned — Lambert's Playwright smoke tests across Sessions 2–3"
author: "Ripley"
created: "2026-03-14"
last_validated: "2026-03-14"
---

## Context

Use when validating that the full aithena stack works end-to-end locally. The smoke test proves: services start, API responds, UI renders, search returns results, and PDFs open.

## Patterns

### 1. Infrastructure up + health wait

```bash
docker compose up -d --build
# Wait for SolrCloud + collection
until curl -fsS http://localhost:8983/solr/books/admin/ping?distrib=true 2>/dev/null | grep -q OK; do sleep 5; done
# Wait for search API
until curl -fsS http://localhost:8080/v1/health 2>/dev/null; do sleep 3; done
# Wait for indexing (check numFound > 0)
until [ "$(curl -s 'http://localhost:8080/v1/search/?q=*&limit=1' | python3 -c 'import sys,json; print(json.load(sys.stdin).get("total",0))')" -gt 0 ]; do sleep 10; done
```

### 2. Start UI dev server

```bash
cd aithena-ui
npm install --legacy-peer-deps
npm run dev &
# Wait for Vite
until curl -fsS http://localhost:5173 2>/dev/null; do sleep 2; done
```

### 3. Run Playwright validation

```bash
cd e2e
npx playwright test --project=chromium
```

Key assertions:
- Page loads at `http://localhost:5173`
- Search input is visible
- Search for a known term returns results (`numFound > 0`)
- Facets render (author, category, language)
- PDF viewer opens on result click

### 4. Capture artifacts

Save screenshots and network logs to `e2e/artifacts/`, not the repo root.

### 5. Cleanup

```bash
docker compose down
kill %1  # Vite dev server
```

## Anti-Patterns

- **Don't commit smoke artifacts to repo root** — use `e2e/artifacts/` and `.gitignore` them
- **Don't skip the health wait** — Solr collection creation is async; hitting `/search` too early returns 502
- **Don't assume `docker compose up` starts all services** — `document-indexer` may stay in `Created` state; verify with `docker compose ps`
- **Don't test against empty Solr** — wait for `numFound > 0` before running UI assertions

## References

- `.squad/agents/lambert/history.md` — smoke test sessions
- `e2e/` — Playwright test directory
- `docker-compose.yml` — full stack definition
