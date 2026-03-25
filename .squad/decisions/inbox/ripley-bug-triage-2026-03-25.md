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

---
