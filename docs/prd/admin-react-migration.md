# PRD: Admin Portal Migration — Streamlit to React (v2.0)

| Field | Value |
|---|---|
| **Author** | Newt (Product Manager) |
| **Requested by** | Juanma (jmservera) |
| **Status** | Draft |
| **Target release** | v2.0 |
| **Last updated** | 2025-07-18 |

---

## 1. Executive Summary

The Aithena admin portal (`src/admin/`) is a Streamlit (Python) application whose features are being progressively migrated into the React UI. The `streamlit-admin` Docker Compose service has been removed and nginx redirects `/admin/streamlit` → `/admin`, but the `src/admin/` source tree is retained as reference for migration. The main user-facing search UI (`src/aithena-ui/`) was migrated to React + Vite in earlier releases and now includes a growing set of admin-oriented pages (document manager, backup dashboard, user management). This creates a **split-brain admin experience**: some admin features exist only in the legacy Streamlit code while others are already in React.

This PRD proposes a **full migration of all Streamlit admin features into the existing React application** for v2.0, unifying the tech stack, eliminating the standalone Streamlit service, and enabling shared components, consistent UX, and a single auth system.

### Key Benefits

- **Unified tech stack**: One frontend framework (React + TypeScript + Vite) for all UI surfaces
- **Shared component library**: Reuse existing React components (tables, metrics cards, error states, loading spinners, modals) across user and admin pages
- **Single auth system**: JWT-based auth with role-based access control already in aithena-ui — no separate basic auth or cookie SSO passthrough needed
- **Eliminated Docker socket dependency**: The Streamlit log viewer mounts `/var/run/docker.sock` — a security concern flagged in review. The React version will use a proper API-based log streaming endpoint
- **Reduced deployment footprint**: Complete removal of the `streamlit-admin` container and `src/admin/` source tree from the Docker Compose stack
- **Better accessibility**: The React UI already has `eslint-plugin-jsx-a11y`, keyboard navigation patterns, and ARIA roles; Streamlit's accessibility story is limited

---

## 2. Background & Problem Statement

### Current State

The admin portal was introduced in early releases as a Streamlit app for quick operator tooling. It has grown to 7 pages across 4 navigation groups:

| Group | Pages |
|---|---|
| Overview | Dashboard |
| Documents | Document Manager |
| Indexing | Reindex Library, Indexing Status |
| System | System Status, Log Viewer, Infrastructure |

The Streamlit admin communicates **directly** with Redis, RabbitMQ Management API, Docker daemon, and the `solr-search` FastAPI backend. It has its own auth system (JWT with environment variables `AUTH_JWT_SECRET`, `AUTH_ADMIN_USERNAME`, `AUTH_ADMIN_PASSWORD`), separate from the main app's database-backed auth.

### Problems

1. **Duplicate tech stacks**: Python/Streamlit admin alongside React/TypeScript main UI increases cognitive load, build complexity, and CI time.

2. **Split auth systems**: The Streamlit admin uses env-var credentials with its own JWT; the main app uses SQLite-backed users with role-based access. SSO passthrough via cookie was added as a workaround (v1.15.0), but it's a bridge — not a solution.

3. **Direct infrastructure access**: The admin talks directly to Redis (`redis-py`), RabbitMQ (HTTP management API), and Docker (`docker-py` with socket mount). This creates tight coupling, security surface, and makes the admin impossible to run outside the Docker network.

4. **Security concern — Docker socket**: The log viewer requires mounting `/var/run/docker.sock:ro` into the admin container. Even read-only, this grants significant host Docker daemon access. This was flagged during PR review; a configuration gate (e.g., an `ENABLE_LOG_VIEWER` flag defaulting to `false`) is a desired mitigation but is not currently enforced in the Streamlit `src/admin/src/pages/log_viewer.py`.

5. **Partial React migration already in progress**: `aithena-ui` already has an `/admin` page (document manager with queued/processed/failed tabs), `/admin/users` (user management), and `/admin/backups` (backup dashboard). The Streamlit pages duplicate some of this functionality with inconsistent UX.

6. **Accessibility gaps**: Streamlit generates its own DOM; we have limited control over ARIA roles, keyboard navigation, and screen reader support. The React app already enforces `jsx-a11y` rules.

---

## 3. Goals & Non-Goals

### Goals (In Scope for v2.0)

- **G1**: Migrate all 7 Streamlit admin pages to React routes within `aithena-ui`
- **G2**: Eliminate direct Redis/RabbitMQ/Docker access from the frontend — all data flows through `solr-search` API endpoints
- **G3**: Remove the Streamlit admin service from `docker-compose.yml`
- **G4**: Unify auth — admin pages use the existing React auth context with `role === 'admin'` guard
- **G5**: Achieve feature parity with the Streamlit admin (no regression in admin capabilities)
- **G6**: Replace Docker socket log viewer with API-based log streaming
- **G7**: Update admin manual and user manual to reflect the unified admin experience
- **G8**: Maintain or improve the existing 81 admin test count (unit + integration)

### Non-Goals (Deferred)

- **NG1**: Real-time WebSocket log streaming (v2.0 will use polling; WebSocket can follow in v2.1)
- **NG2**: Advanced RBAC beyond admin/user/viewer roles (current role model is sufficient)
- **NG3**: Multi-tenant admin (Aithena is single-tenant on-premises)
- **NG4**: Mobile-optimized admin layout (responsive is fine; dedicated mobile admin is not required)
- **NG5**: Admin page i18n (admin pages will be English-only initially; i18n framework is in place for future)

---

## 4. Current Feature Inventory

### 4.1 Dashboard (`pages/dashboard.py`)

| Feature | Current Implementation | Data Source |
|---|---|---|
| Document count metrics (total, queued, processed, failed) | 4 `st.metric` cards | Direct Redis: `redis.keys(f"/{QUEUE_NAME}/*")`, then JSON parse each value |
| RabbitMQ queue metrics (ready, unacked, total messages) | 3 `st.metric` cards | RabbitMQ Management API: `GET /api/queues/%2F/{QUEUE_NAME}` |
| Connection status display | Caption with Redis host/port and RabbitMQ URL | Config env vars |

### 4.2 Document Manager (`pages/document_lister.py`)

| Feature | Current Implementation | Data Source |
|---|---|---|
| Tabbed view (Queued / Processed / Failed) | `st.tabs` with count badges | Direct Redis: key scan + JSON parse |
| Queued documents table | `st.dataframe` with path, timestamp, last_modified | Redis |
| Processed documents table | `st.dataframe` with path, title, author, year, category, page_count, timestamp | Redis |
| Clear All processed | Bulk `redis.delete()` with confirmation dialog | Direct Redis write |
| Failed documents with error details | `st.expander` per document showing error, timestamp, last_modified | Redis |
| Requeue single failed document | `redis.delete(key)` — lister re-discovers on next scan | Direct Redis write |
| Requeue All failed | Bulk requeue with success message | Direct Redis write |

**Note**: The React `/admin` page already implements an equivalent document manager via `GET /v1/admin/documents`, `POST /v1/admin/documents/{id}/requeue`, `POST /v1/admin/documents/requeue-failed`, and `DELETE /v1/admin/documents/processed`. This is the most complete migration already done.

### 4.3 Reindex Library (`pages/reindex.py`)

| Feature | Current Implementation | Data Source |
|---|---|---|
| Reindex explanation text | Markdown describing the 4-step process | Static content |
| Confirmation dialog | Two-step: button → warning → confirm/cancel | UI state |
| Trigger reindex | `POST {SOLR_SEARCH_URL}/v1/admin/reindex?collection=books` | `solr-search` API (already exists) |
| Result display | Success message with collection name, Redis cleared count | API response |
| Admin API key support | `X-API-Key` header when `ADMIN_API_KEY` is set | Config env var |

### 4.4 Indexing Status (`pages/indexing_status.py`)

| Feature | Current Implementation | Data Source |
|---|---|---|
| Summary metrics (total files, queued, processing, done, pages indexed, chunks indexed) | 6 `st.metric` cards | Direct Redis: full key scan with JSON parse |
| Status filter dropdown | `st.selectbox` with All/Queued/Processing/Done/Failed | UI state |
| Currently processing section | Per-document cards showing text/embed progress, page/chunk counts | Redis (status = "processing") |
| Full document table | `st.dataframe` with status, path, title, text_indexed, embedding_indexed, page_count, chunk_count, error, error_stage, timestamp | Redis |
| Status classification | `classify_document()` logic: failed → processed → processing (has `text_indexed`/`solr_id`) → queued | Redis JSON state |

**Note**: The React app already has an `IndexingStatus` component at `/status`, but it uses the existing status API, not the detailed per-document Redis state. The v2.0 migration needs a new API endpoint.

### 4.5 System Status (`pages/system_status.py`)

| Feature | Current Implementation | Data Source |
|---|---|---|
| Container status overview (total, healthy, need attention) | 3 `st.metric` cards | `GET {SOLR_SEARCH_URL}/v1/admin/containers` (already exists) |
| Application services group | Cards with status emoji, version, commit hash | API response, ordered by `APP_SERVICE_ORDER` |
| Infrastructure services group | Cards with status emoji, version, commit hash | API response, ordered by `INFRA_SERVICE_ORDER` |
| Auto-refresh (30s TTL cache) | `@st.cache_data(ttl=30)` | Streamlit caching |
| Timestamp formatting | ISO 8601 → human-readable | Client-side formatting |

### 4.6 Log Viewer (`pages/log_viewer.py`)

| Feature | Current Implementation | Data Source |
|---|---|---|
| Security gate | None in Streamlit; planned `ENABLE_LOG_VIEWER` env var gate for React (default: false) | Config (planned) |
| Docker dependency check | `docker` Python package import check | Runtime |
| Docker connection test | `docker.from_env().ping()` | Docker socket (`/var/run/docker.sock:ro`) |
| Service selector | `st.selectbox` with running aithena containers | Docker SDK: `client.containers.list()` |
| Tail lines control | `st.select_slider` (50/100/200/500/1000) | UI state |
| Log display | `st.code(log_text, language="log")` | Docker SDK: `container.logs(tail=N, timestamps=True)` |
| Auto-refresh | Checkbox + `time.sleep(30)` + `st.rerun()` | Streamlit polling |

**⚠️ Security concern**: This is the primary blocker for the React migration. Docker socket access must be replaced with an API endpoint.

### 4.7 Infrastructure (`pages/infrastructure.py`)

| Feature | Current Implementation | Data Source |
|---|---|---|
| Solr Admin link | Card with external link to `SOLR_ADMIN_URL` (default: `/admin/solr/`) | Config env var |
| RabbitMQ Management link | Card with external link to `RABBITMQ_ADMIN_URL` (default: `/admin/rabbitmq/`) | Config env var |
| Connection details table | Redis host:port, RabbitMQ management URL | Config env vars |

---

## 5. Target Architecture

### 5.1 Recommended Approach: Integrated Routes in aithena-ui

**Decision**: The React admin portal will be **integrated into the existing `aithena-ui` application** as admin-only routes, not deployed as a separate application.

**Rationale**:
- `aithena-ui` already has admin routes (`/admin`, `/admin/users`, `/admin/backups`) with `AdminRoute` role guards
- Shared auth context (`AuthContext`) and API layer (`api.ts` / `apiFetch`) are already in place
- The `TabNav` component already shows an Admin tab for authenticated users
- A separate app would duplicate auth, routing, theming, and i18n infrastructure
- Single build artifact simplifies deployment (one nginx container serves everything)

### 5.2 Route Structure

```
/admin                    → Admin Dashboard (migrated from Streamlit dashboard.py)
/admin/documents          → Document Manager (enhance existing /admin page)
/admin/reindex            → Reindex Library (new)
/admin/indexing-status    → Indexing Status (new)
/admin/system-status      → System Status (new)
/admin/logs               → Log Viewer (new — API-based)
/admin/infrastructure     → Infrastructure Links (new)
/admin/users              → User Management (already exists)
/admin/backups            → Backup Dashboard (already exists)
```

All `/admin/*` routes are protected by the existing `AdminRoute` component which checks `user?.role === 'admin'`.

### 5.3 Admin Sub-Navigation

Replace the current single Admin tab with a sidebar or sub-tab navigation within the admin section:

```
Admin
├── Dashboard         (overview metrics)
├── Documents         (document triage)
├── Indexing
│   ├── Reindex       (trigger full reindex)
│   └── Status        (per-document progress)
├── System
│   ├── Status        (container health)
│   ├── Logs          (service log viewer)
│   └── Infrastructure (links to Solr/RabbitMQ UIs)
├── Users             (already exists)
└── Backups           (already exists)
```

### 5.4 Component Architecture

```
src/
├── pages/
│   ├── admin/
│   │   ├── AdminDashboardPage.tsx      ← Dashboard metrics
│   │   ├── AdminDocumentsPage.tsx      ← Refactored from current AdminPage.tsx
│   │   ├── AdminReindexPage.tsx        ← Reindex with confirmation
│   │   ├── AdminIndexingStatusPage.tsx ← Per-document indexing status
│   │   ├── AdminSystemStatusPage.tsx   ← Container health cards
│   │   ├── AdminLogViewerPage.tsx      ← API-based log viewer
│   │   ├── AdminInfraPage.tsx          ← Infrastructure links
│   │   └── AdminLayout.tsx             ← Shared admin layout with sub-nav
│   ├── UserManagementPage.tsx          ← Already exists
│   └── BackupDashboardPage.tsx         ← Already exists
├── hooks/
│   ├── admin.ts                        ← Existing (documents API)
│   ├── useAdminDashboard.ts            ← New: dashboard metrics
│   ├── useAdminIndexingStatus.ts       ← New: per-document status
│   ├── useAdminSystemStatus.ts         ← New: container status
│   ├── useAdminLogs.ts                 ← New: log streaming
│   └── useAdminReindex.ts              ← New: reindex trigger
├── Components/
│   ├── admin/
│   │   ├── AdminSidebar.tsx            ← Admin sub-navigation
│   │   ├── MetricCard.tsx              ← Reusable metric display
│   │   ├── ContainerStatusCard.tsx     ← Container health card
│   │   ├── LogViewer.tsx               ← Log display with controls
│   │   └── ReindexConfirmDialog.tsx    ← Reindex confirmation
```

---

## 6. Functional Requirements

### FR-1: Admin Dashboard

**Replaces**: `dashboard.py`

| Requirement | Acceptance Criteria |
|---|---|
| Display document count metrics (total, queued, processed, failed) | Four metric cards visible on page load, data from `GET /v1/admin/documents` (counts already returned) |
| Display RabbitMQ queue metrics (ready, unacked, total) | Three metric cards; data from new `GET /v1/admin/queue-status` endpoint |
| Show connection context | Display Redis and RabbitMQ endpoint info (read from status API, not hardcoded) |
| Manual refresh | Refresh button reloads all metrics |
| Auto-refresh | Optional toggle with 30-second polling interval |
| Error handling | Show error banners if API calls fail; degrade gracefully per section |

### FR-2: Document Manager

**Enhances**: Existing `/admin` page (already migrated)

| Requirement | Acceptance Criteria |
|---|---|
| All existing functionality preserved | Queued/Processed/Failed tabs, requeue, clear all — already working |
| Add document search/filter | Text filter to search documents by path (new enhancement) |
| Add pagination | Support pagination for large libraries (>1000 documents) |
| Display additional metadata | Show `page_count`, `chunk_count` for processed documents (extend existing table) |

### FR-3: Reindex Library

**Replaces**: `reindex.py`

| Requirement | Acceptance Criteria |
|---|---|
| Explain what reindex does | Informational text describing the 4-step process |
| Two-step confirmation | Button → confirmation dialog (using existing `ConfirmDialog` component) with warning about search downtime |
| Trigger reindex | `POST /v1/admin/reindex?collection=books` (endpoint already exists) |
| Display result | Show success/failure with collection name and Redis cleared count |
| Disable during active reindex | Button disabled while request is in-flight; show spinner |
| Auth | Requires admin role (existing `AdminRoute` guard) |

### FR-4: Indexing Status

**Replaces**: `indexing_status.py`

| Requirement | Acceptance Criteria |
|---|---|
| Summary metrics | Six metric cards: total files, queued, processing, done, pages indexed, chunks indexed |
| Status filter | Dropdown or button group to filter by status (All/Queued/Processing/Done/Failed) |
| Currently processing section | Highlighted section showing in-progress documents with text/embed progress indicators |
| Full document table | Sortable, filterable table with status, path, title, text_indexed, embedding_indexed, page_count, chunk_count, error, timestamp |
| Refresh | Manual refresh button + optional auto-refresh toggle |
| Data source | New `GET /v1/admin/indexing-status` API endpoint (see API Requirements) |

### FR-5: System Status

**Replaces**: `system_status.py`

| Requirement | Acceptance Criteria |
|---|---|
| Container overview metrics | Total, healthy, needs attention — three metric cards |
| Application services section | Cards for each app service (solr-search, embeddings-server, document-indexer, document-lister, admin, aithena-ui) with status, version, commit |
| Infrastructure services section | Cards for each infra service (solr, redis, rabbitmq, nginx, zookeeper) with status |
| Consistent ordering | Services ordered by defined priority (app services first, then infra) |
| Status colors | Green for up/healthy, red for down, orange for unknown |
| Refresh | Manual refresh + 30-second stale indicator |
| Data source | `GET /v1/admin/containers` (already exists) |

### FR-6: Log Viewer

**Replaces**: `log_viewer.py` — **without Docker socket dependency**

| Requirement | Acceptance Criteria |
|---|---|
| Service selector | Dropdown listing all running aithena services |
| Tail lines control | Selector for 50/100/200/500/1000 lines |
| Log display | Monospace code block with timestamps, line-wrapping, and scroll-to-bottom |
| Auto-refresh | Optional toggle with configurable interval (10s/30s/60s) |
| Text search | Ctrl+F or inline filter to search within displayed logs |
| No Docker socket | Logs fetched via `GET /v1/admin/logs/{service}?tail={n}` API endpoint |
| Graceful degradation | If log API is unavailable, show informational message (not an error) |

### FR-7: Infrastructure Links

**Replaces**: `infrastructure.py`

| Requirement | Acceptance Criteria |
|---|---|
| Solr Admin link | Card with icon and link to Solr admin console (URL from API or config) |
| RabbitMQ Management link | Card with icon and link to RabbitMQ console (URL from API or config) |
| Redis Commander link | Card with icon and link to Redis Commander UI |
| Connection details | Table showing service endpoints (informational) |
| External link behavior | Links open in new tab with `rel="noopener noreferrer"` |

**Note**: The existing React `AdminPage.tsx` already has an `InfrastructureLinks` component with Solr and RabbitMQ cards. This can be extracted and reused.

---

## 7. Non-Functional Requirements

### NFR-1: Performance

| Requirement | Target |
|---|---|
| Admin dashboard load time | < 2 seconds for all metrics on a local Docker Compose stack |
| Document table render | Handle 5,000+ documents without UI freeze (virtual scrolling or pagination) |
| Log viewer render | Handle 1,000 lines without scroll jank |
| Bundle size impact | Admin pages lazy-loaded; no impact on initial search page load |

### NFR-2: Accessibility

| Requirement | Standard |
|---|---|
| WCAG 2.1 Level AA | All admin pages pass `axe-core` automated checks |
| Keyboard navigation | All interactive elements reachable via Tab; admin sub-nav supports arrow keys |
| Screen reader support | Proper ARIA labels on metric cards, status indicators, tables |
| Color contrast | Status colors (green/red/orange) meet 4.5:1 contrast ratio |
| Focus management | Focus moves to main content on route change (existing `App.tsx` pattern) |

### NFR-3: Authentication & Authorization

| Requirement | Implementation |
|---|---|
| Admin role required | All `/admin/*` routes wrapped in `AdminRoute` component |
| JWT token auth | Use existing `apiFetch` with Bearer token — no separate auth system |
| Session persistence | Use existing localStorage/sessionStorage token management |
| Token expiry | Handled by existing `AuthContext` validation flow |
| Remove Streamlit auth | Delete `AUTH_JWT_SECRET`, `AUTH_ADMIN_USERNAME`, `AUTH_ADMIN_PASSWORD` env vars from admin service |

### NFR-4: Security

| Requirement | Implementation |
|---|---|
| No Docker socket | Log viewer must NOT require Docker socket mount |
| No direct Redis access | All Redis data accessed through `solr-search` API endpoints |
| No direct RabbitMQ access | Queue metrics exposed through `solr-search` API endpoint |
| API key deprecation | Remove `ADMIN_API_KEY` / `X-API-Key` header — use JWT auth exclusively |
| CSP headers | Admin pages follow same Content Security Policy as main UI |

### NFR-5: Testing

| Requirement | Target |
|---|---|
| Unit test coverage | ≥ 80% for new admin pages and hooks |
| Component tests | Each admin page has at least one render test and one interaction test |
| Integration tests | API hooks tested with MSW (Mock Service Worker) or similar |
| Accessibility tests | Each page tested with `@axe-core/react` |
| Regression | Existing 81 Streamlit admin tests replaced with equivalent React tests |

---

## 8. API Requirements

The following new API endpoints must be added to `solr-search` (FastAPI backend) to support the React admin portal. Existing endpoints are noted.

### 8.1 Existing Endpoints (No Changes Needed)

| Endpoint | Method | Purpose |
|---|---|---|
| `/v1/admin/documents` | GET | List all documents with status counts |
| `/v1/admin/documents/{doc_id}/requeue` | POST | Requeue a single failed document |
| `/v1/admin/documents/requeue-failed` | POST | Requeue all failed documents |
| `/v1/admin/documents/processed` | DELETE | Clear all processed documents |
| `/v1/admin/reindex` | POST | Trigger full reindex |
| `/v1/admin/containers` | GET | Container status (version, health) |
| `/v1/admin/metrics` | GET | Performance metrics |
| `/v1/admin/backups/*` | Various | Backup and restore operations |
| `/v1/admin/documents/{doc_id}/metadata` | PATCH | Edit document metadata |
| `/v1/admin/documents/batch/metadata` | PATCH | Batch metadata edit |

### 8.2 New Endpoints Required

#### `GET /v1/admin/queue-status`

Returns RabbitMQ queue metrics for the dashboard.

```json
{
  "queue_name": "shortembeddings",
  "messages_ready": 0,
  "messages_unacknowledged": 0,
  "messages_total": 0,
  "status": "ok"
}
```

**Implementation**: Move the RabbitMQ Management API call from `dashboard.py` into `solr-search`. The backend already has access to `RABBITMQ_HOST`, `RABBITMQ_MGMT_PORT`, `RABBITMQ_USER`, `RABBITMQ_PASS`.

#### `GET /v1/admin/indexing-status`

Returns detailed per-document indexing status with summary metrics.

```json
{
  "summary": {
    "total": 150,
    "queued": 10,
    "processing": 3,
    "processed": 130,
    "failed": 7,
    "total_pages": 45000,
    "total_chunks": 120000
  },
  "documents": [
    {
      "id": "/shortembeddings/path/to/book.pdf",
      "status": "processing",
      "path": "/path/to/book.pdf",
      "title": "Book Title",
      "text_indexed": true,
      "embedding_indexed": false,
      "page_count": 300,
      "chunk_count": 0,
      "error": null,
      "error_stage": null,
      "timestamp": "2025-07-18T10:00:00Z"
    }
  ]
}
```

**Implementation**: Port the `classify_document()` / `load_all_documents()` / `build_status_dataframe()` logic from `indexing_status.py` into a new FastAPI endpoint. The `solr-search` backend already connects to Redis for document operations.

**Query parameters**: `?status=queued|processing|processed|failed` for server-side filtering, `?page=1&per_page=100` for pagination.

#### `GET /v1/admin/logs/{service_name}`

Returns recent log lines for a container, without requiring Docker socket access from the frontend.

```json
{
  "service": "document-indexer",
  "lines": [
    "2025-07-18T10:00:01Z INFO  Starting document processing...",
    "2025-07-18T10:00:02Z INFO  Processing /data/documents/book1.pdf"
  ],
  "total_lines": 100,
  "available_services": ["solr-search", "embeddings-server", "document-indexer", "document-lister"]
}
```

**Implementation options** (in order of preference):

1. **Docker SDK in backend**: Move Docker socket mount to `solr-search` container instead of admin. The backend is a trusted service with API authentication — this is more defensible than exposing the socket directly to the Streamlit admin UI, even though it is protected by JWT/cookie-based auth.

2. **Docker API over HTTP**: Configure Docker daemon to expose the API over a Unix socket or TCP to `solr-search` only, with network-level isolation.

3. **Log file mount**: Mount a shared volume with container log files (e.g., Docker's JSON log driver output). Backend reads files directly — no Docker SDK needed.

4. **`docker compose logs` wrapper**: Backend executes `docker compose logs --tail N {service}` as a subprocess. Simple but requires Docker CLI in the backend container.

**Recommended**: Option 1 (Docker SDK in backend). It centralizes the security surface in one service that already has admin auth, and the socket mount is standard for monitoring sidecars.

**Query parameters**: `?tail=100` (default 100, max 5000), `?since=2025-07-18T00:00:00Z` (optional)

#### `GET /v1/admin/infrastructure`

Returns infrastructure connection details and management UI URLs.

```json
{
  "services": [
    {
      "name": "solr",
      "admin_url": "/admin/solr/",
      "description": "Full-text search engine"
    },
    {
      "name": "rabbitmq",
      "admin_url": "/admin/rabbitmq/",
      "description": "Message queue management"
    },
    {
      "name": "redis-commander",
      "admin_url": "/admin/redis/",
      "description": "Redis inspection tool"
    }
  ],
  "connections": {
    "redis": "redis:6379",
    "rabbitmq_mgmt": "http://rabbitmq:15672",
    "solr": "http://solr:8983"
  }
}
```

**Implementation**: Simple endpoint returning configuration-based infrastructure metadata. Alternatively, this could be a static config embedded in the frontend build — but an API endpoint allows the values to reflect actual runtime configuration.

---

## 9. Migration Strategy

### Phase 1: API Foundation (Pre-v2.0 — can start in v1.16.x)

**Goal**: Build the backend API endpoints needed by the React admin, without changing the frontend yet.

| Task | Effort | Dependencies |
|---|---|---|
| Implement `GET /v1/admin/queue-status` | Small | RabbitMQ config already in `solr-search` |
| Implement `GET /v1/admin/indexing-status` | Medium | Port `classify_document()` logic from Streamlit |
| Implement `GET /v1/admin/logs/{service}` | Medium-Large | Docker SDK integration in `solr-search` |
| Implement `GET /v1/admin/infrastructure` | Small | Config-based |
| Add API tests for all new endpoints | Medium | Test fixtures |
| Add pagination to `GET /v1/admin/documents` | Small | Existing endpoint enhancement |

**Gate**: All new API endpoints are tested and deployed. Streamlit admin still runs in parallel.

### Phase 2: React Admin Pages (v2.0-alpha)

**Goal**: Build all React admin pages, running in parallel with Streamlit for validation.

| Task | Priority | Effort | Dependencies |
|---|---|---|---|
| `AdminLayout.tsx` + `AdminSidebar.tsx` (sub-navigation) | P0 | Medium | None |
| `AdminDashboardPage.tsx` (dashboard metrics) | P0 | Medium | Phase 1 APIs |
| `AdminReindexPage.tsx` (reindex with confirmation) | P0 | Small | Existing API |
| `AdminIndexingStatusPage.tsx` (per-document status) | P0 | Large | Phase 1 indexing-status API |
| `AdminSystemStatusPage.tsx` (container health) | P1 | Medium | Existing containers API |
| `AdminLogViewerPage.tsx` (API-based logs) | P1 | Large | Phase 1 logs API |
| `AdminInfraPage.tsx` (infrastructure links) | P2 | Small | Phase 1 infrastructure API |
| Refactor existing `AdminPage.tsx` → `AdminDocumentsPage.tsx` | P1 | Small | Route restructure |
| Move `UserManagementPage` and `BackupDashboardPage` under admin layout | P1 | Small | Route restructure |

**Gate**: All pages render correctly, all API calls succeed, manual QA passes on each page.

### Phase 3: Testing & QA (v2.0-beta)

**Goal**: Comprehensive testing, side-by-side validation against Streamlit.

| Task | Effort |
|---|---|
| Unit tests for all new hooks and components | Large |
| Accessibility audit (axe-core + manual keyboard testing) | Medium |
| Side-by-side comparison: React vs. Streamlit for each page | Medium |
| Performance testing with 5,000+ documents | Small |
| E2E tests for critical admin flows (reindex, requeue, clear) | Medium |
| Update admin manual with new screenshots and navigation | Medium |

**Gate**: Feature parity confirmed. Test count ≥ 81 (Streamlit baseline). No accessibility violations.

### Phase 4: Cutover & Cleanup (v2.0-rc → v2.0)

**Goal**: Remove Streamlit, clean up Docker Compose, finalize documentation.

| Task | Effort |
|---|---|
| Remove `streamlit-admin` service from `docker-compose.yml` | Small |
| Remove `src/admin/` directory | Small |
| Remove Streamlit-specific env vars (`AUTH_JWT_SECRET`, `AUTH_ADMIN_USERNAME`, `AUTH_ADMIN_PASSWORD`, `ENABLE_LOG_VIEWER`) | Small |
| Remove Docker socket mount from compose | Small |
| Update `.env` template and installer | Small |
| Update CHANGELOG.md with migration notes | Small |
| Final release validation (Newt release gate) | Medium |

**Gate**: Full stack starts cleanly without Streamlit. All admin features accessible via React. Docs updated. Release gate passed.

---

## 10. Risks & Mitigations

| # | Risk | Severity | Likelihood | Mitigation |
|---|---|---|---|---|
| R1 | **Docker socket replacement** — No clean way to stream container logs without socket access | High | Medium | Multiple fallback options (see API Requirements §8.2). Start with Docker SDK in backend (Option 1). If unacceptable, use log file mount (Option 3). Worst case: defer log viewer to v2.1. |
| R2 | **Redis direct access removal** — Indexing status relies on scanning all Redis keys, which may be slow for large libraries | Medium | Medium | Add server-side pagination and caching to the new API endpoint. The backend already connects to Redis — no new coupling. |
| R3 | **Feature parity gaps** — Streamlit widgets (data_editor, select_slider) have no direct React equivalent | Low | Low | All Streamlit widgets used in admin pages have standard HTML/React equivalents. No exotic widgets are used. |
| R4 | **Bundle size increase** — Adding 7 admin pages increases the JS bundle | Low | High (will happen) | All admin pages are lazy-loaded (`React.lazy` + `Suspense`). Only admin users pay the download cost, and only for the specific page they visit. |
| R5 | **Parallel running complexity** — Running both Streamlit and React admin during migration may confuse operators | Medium | Medium | Clear documentation during beta. Add a banner to Streamlit admin: "This admin portal is being replaced. Use the new admin at /admin." |
| R6 | **RabbitMQ Management API credentials in backend** — Backend doesn't currently call RabbitMQ Management API | Low | Low | Credentials (`RABBITMQ_USER`, `RABBITMQ_PASS`) are already available as env vars in the Docker network. Add to `solr-search` environment. |
| R7 | **Lost Streamlit auto-refresh** — Streamlit's `st.rerun()` + `time.sleep()` pattern gives "live" feel | Low | Medium | Implement React polling hooks with `setInterval`. Consider `useSyncExternalStore` or React Query's `refetchInterval` for cleaner implementation. |

---

## 11. Success Metrics

### 11.1 Migration Completeness

| Metric | Target | Measurement |
|---|---|---|
| Streamlit pages migrated | 7/7 | Feature checklist (Section 4 inventory) |
| Legacy Streamlit artifacts removed | Yes | `src/admin/` directory deleted; Streamlit admin CI job removed; docs contain no references to the Streamlit admin UI |
| Docker socket removed from browser-facing services | Yes | No `/var/run/docker.sock` mount in any browser-facing compose service (backend-only mount is acceptable) |
| Separate auth system removed | Yes | No `AUTH_JWT_SECRET` / `AUTH_ADMIN_USERNAME` / `AUTH_ADMIN_PASSWORD` env vars |

### 11.2 Quality Gates

| Metric | Target | Measurement |
|---|---|---|
| Admin test count | ≥ 116 (v1.15.0 baseline) | `vitest run` count for admin-related test files (React) must equal or exceed the current combined Streamlit+React admin test count |
| Admin test coverage | ≥ 80% | `vitest --coverage` for `pages/admin/` and `hooks/admin*` |
| Accessibility violations | 0 (critical/serious) | `axe-core` automated audit |
| Admin page load time | < 2s on local Docker stack | Manual measurement + Lighthouse |

### 11.3 Operational Validation

| Metric | Target | Measurement |
|---|---|---|
| Dashboard shows correct document counts | Matches Redis state | Manual comparison during QA |
| Reindex completes successfully | Solr collection rebuilt | Trigger reindex via React, verify search works after |
| Log viewer shows real logs | Container logs visible without Docker socket on frontend | API-based retrieval verified |
| All infrastructure links work | Solr Admin, RabbitMQ Management accessible | Click-through test |
| Admin manual updated | All screenshots reflect React admin | Documentation review |

---

## 12. Timeline

### Milestone Plan

```
Phase 1: API Foundation
├── New backend endpoints (queue-status, indexing-status, logs, infrastructure)
├── API tests
├── Can ship incrementally in v1.16.x / v1.17.x
└── GATE: All endpoints tested and deployed

Phase 2: React Admin Pages
├── Admin layout + sub-navigation
├── Dashboard, Reindex, Indexing Status, System Status, Log Viewer, Infrastructure
├── Route restructure (existing admin pages moved under layout)
└── GATE: All pages render, all API calls work

Phase 3: Testing & QA
├── Unit + component + accessibility tests
├── Side-by-side validation vs. Streamlit
├── Performance testing (5,000+ docs)
├── Admin manual update
└── GATE: Feature parity, tests ≥ 81, zero a11y violations

Phase 4: Cutover & Cleanup
├── Remove Streamlit service and code
├── Remove Docker socket mount
├── Remove legacy env vars
├── Update installer and .env template
├── Release validation (Newt release gate)
└── GATE: Clean stack, docs updated, v2.0 shipped
```

### Dependencies Between Phases

- **Phase 2 depends on Phase 1**: React pages need API endpoints to be available
- **Phase 3 depends on Phase 2**: Can't test pages that don't exist yet
- **Phase 4 depends on Phase 3**: Can't remove Streamlit until parity is confirmed
- **Phase 1 can start immediately**: Backend work has no frontend dependency

### Effort Estimates

| Phase | Estimated Effort | Parallelizable |
|---|---|---|
| Phase 1: API Foundation | 3–5 days | Backend dev can work independently |
| Phase 2: React Admin Pages | 5–8 days | Frontend dev can start as Phase 1 endpoints land |
| Phase 3: Testing & QA | 3–5 days | Test writing + manual QA can overlap |
| Phase 4: Cutover & Cleanup | 1–2 days | Requires Phase 3 sign-off |
| **Total** | **12–20 days** | Phases 1 & 2 partially overlap |

---

## Appendix A: Environment Variable Changes

### Removed (v2.0)

| Variable | Service | Reason |
|---|---|---|
| `AUTH_JWT_SECRET` | streamlit-admin | Streamlit service removed; React uses main app auth |
| `AUTH_ADMIN_USERNAME` | streamlit-admin | Replaced by database-backed user management |
| `AUTH_ADMIN_PASSWORD` | streamlit-admin | Replaced by database-backed user management |
| `AUTH_ENABLED` | streamlit-admin | Always enabled in React (role-based) |
| `AUTH_JWT_TTL` | streamlit-admin | Managed by main app auth |
| `AUTH_COOKIE_NAME` | streamlit-admin | No longer needed |
| `ENABLE_LOG_VIEWER` | streamlit-admin | Log viewer always available via API (no socket) |
| `ADMIN_API_KEY` | streamlit-admin | Replaced by JWT auth |

### Added/Modified (v2.0)

| Variable | Service | Purpose |
|---|---|---|
| `RABBITMQ_MGMT_PORT` | solr-search | RabbitMQ Management API port (for queue-status endpoint) |
| `RABBITMQ_MGMT_PATH_PREFIX` | solr-search | RabbitMQ path prefix (if proxied) |

---

## Appendix B: Streamlit → React Component Mapping

| Streamlit Widget | React Equivalent | Notes |
|---|---|---|
| `st.metric()` | `MetricCard` component | Already partially exists in `AdminPage.tsx` |
| `st.dataframe()` | HTML `<table>` + sorting | Match existing `admin-table` CSS class pattern |
| `st.tabs()` | Tab components with `role="tablist"` | Already implemented in `AdminPage.tsx` |
| `st.expander()` | `<details>/<summary>` or collapsible component | Standard HTML |
| `st.selectbox()` | `<select>` or custom dropdown | Standard HTML |
| `st.select_slider()` | `<input type="range">` or button group | Discrete values → button group preferred |
| `st.code()` | `<pre><code>` block | Standard HTML with monospace font |
| `st.button()` | `<button>` | Standard HTML |
| `st.spinner()` | `LoadingSpinner` component | Already exists in aithena-ui |
| `st.container(border=True)` | `<div className="card">` | CSS class |
| `st.columns()` | CSS Grid or Flexbox | Standard CSS |
| `st.sidebar` | `AdminSidebar` component | New component for admin sub-navigation |
| `st.cache_data(ttl=30)` | React hook with `useEffect` + `setInterval` | Or React Query's stale-while-revalidate |
| `st.session_state` | React `useState` / `useContext` | Standard React state management |
| `st.rerun()` | State update triggers re-render | Natural in React |

---

## Appendix C: CHANGELOG Entry (v2.0)

```markdown
## [2.0.0] — TBD

### Added
- Admin dashboard with document and queue metrics in React UI
- Reindex Library page with two-step confirmation dialog
- Detailed indexing status page with per-document progress tracking
- System status page with container health cards
- API-based log viewer (no Docker socket required)
- Infrastructure links page for Solr, RabbitMQ, and Redis UIs
- Admin sub-navigation sidebar for organized admin pages
- New API endpoints: /v1/admin/queue-status, /v1/admin/indexing-status, /v1/admin/logs/{service}, /v1/admin/infrastructure

### Changed
- Admin portal fully integrated into React UI (was standalone Streamlit app)
- All admin operations routed through solr-search API (no direct Redis/RabbitMQ/Docker access from frontend)
- Admin authentication unified with main app (JWT + role-based access control)
- Document Manager page refactored with admin layout and sub-navigation

### Removed
- Streamlit admin service (`streamlit-admin` container)
- Docker socket mount (`/var/run/docker.sock`) for admin container
- Standalone admin auth system (AUTH_JWT_SECRET, AUTH_ADMIN_USERNAME, AUTH_ADMIN_PASSWORD env vars)
- ADMIN_API_KEY / X-API-Key authentication method
- ENABLE_LOG_VIEWER environment variable (log viewer always available via API)

### Security
- Eliminated Docker socket exposure from admin frontend
- All admin data flows through authenticated API endpoints
- Removed direct Redis and RabbitMQ access from browser-facing services
```
