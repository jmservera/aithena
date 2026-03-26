---
name: "api-contract-alignment"
description: "Keep frontend/backend API contracts in sync to prevent path mismatches"
domain: "api, frontend, backend"
confidence: "high"
source: "earned — /v1/ prefix validated and working across Phase 2–3 (7+ copilot PRs, 0 contract mismatches)"
author: "Ripley"
created: "2026-03-14"
last_validated: "2026-03-14T23:45"
---

## Context

Use when adding or modifying API endpoints in `solr-search/` or consuming them in `aithena-ui/`. The `/v1/search/` vs `/search` mismatch cost multiple debugging sessions.

## Patterns

### 1. Single source of truth for API paths

The backend (`solr-search/main.py`) defines canonical routes. The frontend must derive paths from the same prefix constant.

**Backend convention:**
```python
API_PREFIX = "/v1"
app.include_router(router, prefix=API_PREFIX)
```

**Frontend convention (`aithena-ui/src/api.ts`):**
```typescript
const API_PREFIX = "/v1";
export const searchUrl = (params: string) => `${baseUrl}${API_PREFIX}/search/?${params}`;
```

### 2. Verify contract on both sides after changes

After changing any API route:
```bash
# Backend: confirm routes
cd solr-search && python3 -c "from main import app; print([r.path for r in app.routes])"
# Frontend: search for API calls
grep -rn '/v1/' aithena-ui/src/
```

### 3. Use the nginx proxy as the integration point

In production, nginx proxies `/v1/` to `solr-search:8080`. In dev, Vite proxies `/v1` to `http://localhost:8080`. Both must agree on the prefix.

**Vite proxy (`vite.config.ts`):**
```typescript
proxy: {
  '/v1': { target: 'http://localhost:8080' },
  '/documents': { target: 'http://localhost:8080' }
}
```

### 4. API versioning discipline

- All public endpoints live under `/v1/`
- Health and info endpoints: `/v1/health`, `/v1/info`
- Search endpoints: `/v1/search/`, `/v1/facets/`
- Document endpoints: `/v1/documents/{token}`
- Never expose unversioned public routes

## Anti-Patterns

- **Don't hardcode full URLs in frontend components** — use the shared `api.ts` module
- **Don't add backend routes without the version prefix** — breaks nginx and Vite proxy rules
- **Don't change route paths without grep-checking both frontend and backend**
- **Don't rely on `VITE_API_URL` env var alone** — it broke in production when set to `"."`

## References

- `solr-search/main.py` — backend routes
- `aithena-ui/src/api.ts` — frontend URL builder
- `aithena-ui/vite.config.ts` — dev proxy config
- `nginx/` — production proxy config
