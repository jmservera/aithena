# Decision: Admin Portal React Migration Architecture

**Date**: 2025-07-18
**Author**: Newt (Product Manager)
**Status**: Proposed
**Requested by**: Juanma (jmservera)

## Context

The admin portal (`src/admin/`) is a standalone Streamlit (Python) app with 7 pages. The React UI (`src/aithena-ui/`) already has 3 admin pages (`/admin`, `/admin/users`, `/admin/backups`). For v2.0, we need to decide how to unify these.

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
