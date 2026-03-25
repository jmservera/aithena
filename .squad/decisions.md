# Squad Decisions

---

> 📦 Older decisions archived to decisions-archive.md

# Decision: User directive — No A/B comparison for v1.14.0

**Author:** Juanma (Project Owner)  
**Date:** 2026-03-23T09:05Z  
**Status:** CLOSED (v1.14.0 milestone)  
**Impact:** All A/B evaluation issues (#900-918) closed as "not planned"

## Directive

"We are not going to have a side by side comparer as we already decided to move to the new model directly." The e5-base benchmark showed clear superiority. The stack moves directly to multilingual-e5-base via PR #964.

## Context

A/B testing infrastructure was prepared for user-facing comparison of distiluse-base vs multilingual-e5-base embeddings. However, internal benchmarks demonstrated e5-base superiority across all metrics, eliminating the need for end-user A/B evaluation.

## Decision

- Close all v1.14.0 A/B evaluation issues (#900-918) as "not planned"
- Mark v1.14.0 milestone complete
- Proceed with e5-base deployment via #964 (no dual-model production stack)
- Dual-model infrastructure remains available for future testing/rollback scenarios

---


---

## Decision: Thumbnail Volume Permission Handling

**Author:** Brett (Infrastructure Architect)
**Date:** 2026-03-24
**Status:** Implemented (PR #1090)
**Context:** Issue #1089

### Problem

Pre-release log analyzer flags `Permission denied: '/data/thumbnails/'` errors from document-indexer as security findings. These are caused by missing directory ownership in the Dockerfile — the named volume is root-owned but the container runs as UID 1000.

### Decision

1. **Allowlist rule:** `security:*permission denied*/data/thumbnails/*=ignore` — thumbnail generation is non-critical; indexing succeeds without thumbnails
2. **Dockerfile fix:** `RUN mkdir -p /data/thumbnails && chown app:app /data/thumbnails` — named volumes inherit image layer permissions on first creation

### Rationale

- Thumbnail failures don't block document indexing (non-critical feature)
- The Dockerfile fix is the correct infrastructure-level approach for named volume permissions
- The allowlist provides defense-in-depth for CI environments where volumes may not initialize cleanly

### Impact

- Unblocks v1.15.0 release (PR #1088)
- Pattern applies to any future service that writes to named volumes as non-root

---

# User directive: review PR comments before merging

**Date:** 2026-03-24T21:55:00Z  
**Author:** Juanma (via Copilot)  
**Status:** Proposed

## Context
PR #1095 was merged with 8 unaddressed review comments. The user has requested that this must not happen again.

## Decision
Always review PR comments before merging. Never merge a PR with unresolved review threads.

## Rationale
Ensuring all review comments are addressed before merging prevents regressions, maintains code quality, and respects reviewer feedback, aligning with the user's explicit request after the PR #1095 incident.

---

# Decision: Admin Portal React Migration Architecture

**Date**: 2025-07-18
**Author**: Newt (Product Manager)
**Status**: Proposed
**Requested by**: Juanma (jmservera)

## Context

The admin portal (`src/admin/`) was originally a standalone Streamlit (Python) app with 7 pages. The `streamlit-admin` Compose service has since been removed and nginx redirects `/admin/streamlit` → `/admin`, but the `src/admin/` source tree is retained as reference. The React UI (`src/aithena-ui/`) already has 3 admin pages (`/admin`, `/admin/users`, `/admin/backups`). For v2.0, we need to complete the migration of all remaining Streamlit admin features into React.

## Decision

**Integrate admin pages into the existing `aithena-ui` React application** as `/admin/*` routes, rather than building a separate React admin application.

## Rationale

1. **Infrastructure already exists**: `AdminRoute` component, `AuthContext`, `apiFetch` API layer, admin hooks, and tab navigation are all in place.
2. **No duplication**: A separate app would duplicate auth, routing, theming, i18n, and build tooling.
3. **Single deployment artifact**: One nginx container serves everything — simpler ops.
4. **Lazy loading**: Admin pages are code-split, so they don't affect search page performance.
5. **Precedent**: The existing `/admin`, `/admin/users`, and `/admin/backups` pages already follow this pattern.

## Implications

- Admin pages share the same build pipeline, test suite, and deployment as the main UI
- An `AdminLayout.tsx` component with sidebar sub-navigation will wrap all admin routes
- Four new backend API endpoints are required in `solr-search` (queue-status, indexing-status, logs, infrastructure)
- Docker socket mount moves from Streamlit container to `solr-search` backend (for log API)
- The Streamlit `streamlit-admin` service is removed from Docker Compose in v2.0

## Alternatives Considered

1. **Separate React app** (`admin-ui/`): More isolation but duplicates auth/routing/theming. Rejected.
2. **Micro-frontend**: Over-engineered for a single-tenant on-premises app. Rejected.
3. **Keep Streamlit**: Maintains tech stack split and Docker socket security concern. Rejected.

## Full PRD

See `docs/prd/admin-react-migration.md` for the complete Product Requirements Document including feature inventory, API requirements, migration phases, and success metrics.
---

# Decision: Thumbnail URL Prefix in Search API

**Author:** Parker (Backend Dev)  
**Date:** 2026-03-25  
**Status:** Implemented (PR #1139)  
**Context:** Issue #1137

## Problem

Thumbnail URLs stored in Solr are relative paths (e.g., `folder/book.pdf.thumb.jpg`). The search API returned these as-is, but the frontend uses them directly in `<img src>`. Without a `/thumbnails/` prefix, the browser resolved them as relative URLs against the current page, hitting the SPA catch-all instead of the nginx static-file location block.

## Decision

The search API now prefixes relative thumbnail paths with `/thumbnails/` via `_thumbnail_url()` in `search_service.py`. Absolute URLs (http/https) and already-prefixed paths (starting with `/`) are passed through unchanged.

## Rationale

- The backend is the right place to apply URL prefixes because it knows the routing scheme
- The frontend should receive ready-to-use URLs without needing path manipulation
- Preserving absolute URLs ensures backward compatibility with any externally-hosted thumbnails
- The nginx location block `^/thumbnails/(.+\.thumb\.jpg)$` expects this prefix

## Impact

- All search, books, and similar-books responses now return `/thumbnails/`-prefixed URLs
- Frontend components (`BookCard`, `BookDetailView`) work without changes
- nginx correctly routes to `/data/thumbnails/` filesystem path

---

# Decision: Bug Triage for v1.16.0 (2026-03-25)

**Author:** Ripley (Project Lead)  
**Date:** 2026-03-25T15:30Z  
**Requested by:** Juanma (jmservera)  
**Status:** DECIDED

## Context

Three new bugs submitted for triage with no assigned milestones:
- #1137 — Thumbnails not loaded in UI (squad:parker)
- #1138 — Admin dashboard queued/processed/failed list not paged (squad:dallas)
- #1136 — RabbitMQ deprecation warning (squad:lambert)

## Decision

All three bugs assigned to **v1.16.0 milestone**.

### Priority Ranking (for Ralph's backlog)

1. **#1137 (Thumbnails)** — Parker | Medium severity | Low–Medium effort
   - User-visible feature broken; nginx route or volume mount issue
   - Investigate static `/thumbnails` serving; verify Docker volume creation

2. **#1138 (Admin pagination)** — Dallas | Medium severity | Low effort
   - Scales with data size; missing React pagination component
   - **Note:** Streamlit admin deprecated in v2.0; consider deferred if v2.0 React migration imminent

3. **#1136 (RabbitMQ warning)** — Lambert (investigation) → Parker (fix) | Low severity | Very Low effort
   - Log noise only; blocks future RabbitMQ upgrades
   - Add `deprecated_features.permit.management_metrics_collection` config before next patch release

### Label Actions

- Removed `go:needs-research` from all three (clear enough to implement immediately)
- Preserved squad routing: Parker (backend), Dallas (frontend), Lambert (testing)

## Rationale

- **User impact ordering:** Visible bugs before warnings
- **#1137 first:** Broken feature, direct user impact
- **#1138 second:** Unscalable UX, but Streamlit admin EOL in v2.0 (risk: low-ROI effort if timeline tight)
- **#1136 last:** No functional impact; maintenance task

## Risk

#1138 (admin paging) may be low-ROI if v2.0 React migration happens soon. Recommend Ralph check with Newt on admin-react-migration timeline before committing.
