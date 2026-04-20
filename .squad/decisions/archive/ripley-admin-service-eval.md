# Ripley — Admin Service Evaluation & Recommendation

**Date:** 2025  
**Requestor:** Juanma (Product Owner)  
**Decision:** CONSOLIDATE admin functionality into aithena-ui (React) and DEPRECATE Streamlit admin service

---

## Executive Summary

The Streamlit admin dashboard (`src/admin/`) provides operations tooling for monitoring and managing the document indexing pipeline. However, **the React UI (aithena-ui) already implements functional equivalents of all core admin features**, creating redundancy. This evaluation recommends consolidating admin functionality into the main React app and gradually sunsetting the Streamlit service to reduce deployment complexity and maintenance cost.

**Impact:** Eliminates 1 Docker container, 1 build artifact, 1 authentication module to maintain, and simplifies operator UX.

---

## Current State: What Admin Does

### Streamlit Admin Service (`src/admin/`)

**Port:** 8501 (exposed via nginx at `/admin/streamlit/`)  
**Audience:** Operations / Administrators  
**Frequency:** Occasional (troubleshooting, setup)

#### Features

| Feature | Page | What It Shows |
|---------|------|---------------|
| Queue Metrics | Overview | Total, Queued, Processed, Failed document counts (from Redis) |
| RabbitMQ Status | Overview | Queue depth, messages ready, unacked (via RabbitMQ management API) |
| Document Manager | Document Manager | Tabbed view: Queued/Processed/Failed with per-doc inspection |
| Requeue Failed | Document Manager | Delete Redis entry to trigger re-indexing on next lister scan |
| Clear Processed | Document Manager | Bulk remove processed docs from Redis for re-indexing |
| System Health | System Status | Container status, version, commit, error details |

### React UI Admin (`src/aithena-ui/src/pages/AdminPage.tsx`)

**Path:** `/admin` (integrated into main app)  
**Audience:** Same operators / administrators

#### Features

| Feature | Present? | How |
|---------|----------|-----|
| Queue Metrics | ✅ Yes | Uses `/v1/admin/documents` endpoint (shows counts) |
| Document Manager | ✅ Yes | Full tabbed view (queued/processed/failed) |
| Requeue | ✅ Yes | `POST /v1/admin/documents/{id}/requeue` |
| Requeue All Failed | ✅ Yes | `POST /v1/admin/documents/requeue-failed` |
| Clear Processed | ✅ Yes | `DELETE /v1/admin/documents/processed` |
| System Health | ⚠️ Partial | StatusPage calls `/v1/admin/containers` (only system health, no queue metrics) |

---

## Architecture & Dependencies

### Admin Backend APIs (solr-search service)

All admin UIs consume these endpoints:

```
GET  /v1/admin/documents           — List documents by status
POST /v1/admin/documents/{id}/requeue     — Requeue a failed doc
POST /v1/admin/documents/requeue-failed   — Bulk requeue
DELETE /v1/admin/documents/processed      — Clear processed docs
GET  /v1/admin/containers         — System health snapshot
```

**Key insight:** The backend is UI-agnostic. Both Streamlit and React can consume these endpoints.

### Streamlit Service Stack

**Dependencies:**
- Redis (direct connection for queue state)
- RabbitMQ management API (HTTP)
- solr-search API (`/v1/admin/containers`, optional)
- JWT authentication (auth.py module)

**Docker Image:** `python:3.11-slim` + Streamlit + pandas + requests + redis  
**Build time:** ~90 seconds  
**Image size:** +60MB to total Docker Compose footprint

**Test coverage:** 
- `tests/test_auth.py`: 190 lines (JWT token generation, TTL parsing, validation)
- No tests for Streamlit pages (typical; Streamlit UI testing is manual)

---

## Redundancy Analysis

### Feature Parity

| Feature | Streamlit | React | Backend API |
|---------|-----------|-------|-------------|
| View document counts | ✅ | ✅ | ✅ |
| View individual documents | ✅ | ✅ | ✅ |
| Requeue failed doc | ✅ | ✅ | ✅ |
| Requeue all failed | ✅ | ✅ | ✅ |
| Clear processed docs | ✅ | ✅ | ✅ |
| RabbitMQ queue metrics | ✅ | ❌ | ❌ (calls mgmt API directly) |
| System health | ✅ | ✅ | ✅ |

**Missing in React:** RabbitMQ queue live metrics (messages ready, unacked). This is the **only non-trivial gap**.

### UX Considerations

**Streamlit advantages:**
- Real-time updates (WebSocket-like auto-refresh)
- Rapid prototyping (single Python file)

**React advantages:**
- Integrated with main app navigation
- Consistent styling and auth flow
- Keyboard navigation, accessibility
- Unified permission model
- Shared TypeScript types with backend

---

## Maintenance Cost

### Ongoing Obligations

**Per-service cost:**
1. Build: One fewer `docker build` step
2. Test: Streamlit testing is mostly manual (no unit tests for pages); removing it doesn't reduce test suite
3. Security: JWT auth module stays (could be generic), but Streamlit-specific security review steps vanish
4. Deployment: One fewer container to version, tag, and push
5. Documentation: One fewer service in admin manual

**Estimated reduction:** ~5–10% of deployment pipeline complexity

### Risk of Keeping Both

- **Inconsistency risk:** Operators confused about which admin UI to use (both at different URLs)
- **Auth divergence:** Two separate auth implementations (JWT in Streamlit, standard React auth in UI)
- **Bug duplication:** A bug in queue display shows in both systems; fixing requires two fixes
- **Image bloat:** +60MB per deployment cycle (Streamlit deps in production image)

---

## Recommendation

### Decision: CONSOLIDATE → DEPRECATE

**Phase 1 (Immediate):**
1. ✅ React AdminPage already functional for core use cases
2. Enhance React AdminPage to include **RabbitMQ queue metrics**
   - Option A: Add `GET /v1/admin/rabbitmq-queue` endpoint in solr-search
   - Option B: Call RabbitMQ management API directly from React with CORS headers
   - Effort: ~2–3 hours for React dev
3. Mark Streamlit admin as deprecated in documentation

**Phase 2 (v0.8 release, ~2–3 weeks):**
1. Remove `streamlit-admin` from `docker-compose.yml`
2. Redirect `/admin/streamlit/` in nginx to `/admin` with a notice
3. Remove `src/admin/` directory entirely
4. Update admin-manual.md to reference React UI only

**Fallback:** If issues with React implementation arise (e.g., RabbitMQ API CORS), keep Streamlit admin in `docker/compose.dev-ports.yml` as a developer-only tool (not in production builds).

---

## Trade-off Analysis

### Pros of Consolidation

| Pro | Impact |
|-----|--------|
| Eliminates 1 Docker container | Faster deploy, smaller footprint |
| Single UI to maintain | Fewer bugs, faster fixes |
| Unified auth & permissions | Clearer security model |
| Reduced image bloat | 60MB smaller production image |
| Better operator UX | One URL, consistent styling |
| Cleaner codebase | One fewer service to document |

### Cons (& Mitigation)

| Con | Mitigation |
|-----|-----------|
| Requires React dev for RabbitMQ metrics | Already have strong React team (Eva, Sofia) |
| Loses Streamlit's rapid prototyping | UI is stable; no further rapid iteration expected |
| Auth module won't be reused | Not a limitation; JWT logic is Streamlit-specific |
| If React implementation fails | Keep Streamlit in docker/compose.dev-ports.yml temporarily |

---

## Implementation Checklist

- [ ] **Week 1:** React dev adds RabbitMQ metrics to AdminPage
  - [ ] New API endpoint or direct mgmt API call
  - [ ] Metrics card showing messages ready / unacked
  - [ ] Test with local Docker Compose stack
- [ ] **Week 2:** Remove Streamlit from main compose
  - [ ] Delete `/src/admin/`
  - [ ] Update `docker-compose.yml`
  - [ ] Update `docs/admin-manual.md`
  - [ ] Update nginx.conf (redirect `/admin/streamlit/` → `/admin`)
- [ ] **Week 3:** v0.8 release
  - [ ] Test full E2E workflow with React admin only
  - [ ] Update release notes

---

## Decision Record

**Approved by:** Ripley (Lead)  
**Effective:** Immediately  
**Status:** In Planning (Phase 1 starts after approval)  
**Supersedes:** None  
**See also:** Issue #202 (admin containers endpoint), #51 (original Streamlit admin work)

---

## Appendix: Architecture Diagram (Current)

```
Operators
   ├─ `/admin/streamlit/` ──→ streamlit-admin (8501) ┐
   │                                                    │
   └─ `/admin` ──────────────┬────→ React (aithena-ui) │
                             │                          │
                   Both call APIs in solr-search ◄──────┘
                       ├─ /v1/admin/documents
                       ├─ /v1/admin/containers
                       └─ (+ requeue, clear endpoints)
                             │
                       ┌──────┴──────┐
                       ▼             ▼
                     Redis      RabbitMQ mgmt
```

**After consolidation:**

```
Operators
   └─ `/admin` ──────→ React AdminPage (aithena-ui)
                             │
                       Calls solr-search APIs
                       ├─ /v1/admin/documents
                       ├─ /v1/admin/containers
                       ├─ /v1/admin/rabbitmq-queue (NEW)
                       └─ (+ requeue, clear endpoints)
                             │
                       ┌──────┴──────┐
                       ▼             ▼
                     Redis      RabbitMQ mgmt
```
