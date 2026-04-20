# Decision: UI Search Mode Configuration for Dual Architecture Support

**Author:** Dallas (Frontend Dev)  
**Date:** 2025-07-23  
**Status:** Proposed

## Summary

The UI currently hardcodes three search modes (keyword, semantic, hybrid). To support the new hybrid-rerank architecture (which lacks HNSW and thus cannot do pure semantic search), the frontend needs to dynamically discover available search modes from the backend.

## Decision

1. **Capabilities API:** The frontend will call `GET /api/capabilities` at startup to learn which search modes are available and what the default mode should be.
2. **Hide unavailable modes:** When semantic search is unavailable, hide the button entirely (don't gray it out — users don't need to know about missing architecture).
3. **Dynamic defaults:** The default search mode comes from the capabilities API (`defaultMode`). In HNSW mode: `keyword`. In hybrid-rerank mode: `hybrid`.
4. **URL fallback:** If a bookmarked URL contains `mode=semantic` but semantic isn't available, silently fall back to the default mode.
5. **SimilarBooks gating:** Hide the SimilarBooks component when `capabilities.features.similarBooks` is false (no HNSW = no kNN).
6. **Admin visibility only:** Architecture mode info is shown on the Admin Infrastructure page, not to regular users.
7. **Graceful degradation:** If the capabilities endpoint fails, show all modes (current behavior) and let search API 400 errors handle unavailability as they do today.

## Rationale

- Users care about "search works" not "which index technology is active"
- Hiding vs graying out avoids confusion and support questions
- Capabilities API is the industry-standard pattern for runtime feature discovery
- Non-blocking fetch means no UX degradation on slow/failed capability checks

## Impact

- **Frontend:** New `CapabilitiesContext`, `useCapabilities` hook; updates to SearchPage, useSearchState, SimilarBooks, AdminInfrastructurePage
- **Backend (Parker):** Needs to implement `GET /api/capabilities`
- **i18n:** ~4-6 new keys across 4 locales
- **Tests:** New test files for capabilities hook and mode filtering
