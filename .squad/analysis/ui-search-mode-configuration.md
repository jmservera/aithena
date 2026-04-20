# UI Search Mode Configuration — Analysis & Design Proposal

**Author:** Dallas (Frontend Dev)  
**Date:** 2025-07-23  
**Status:** Proposal  
**Requested by:** jmservera (Juanma)

---

## 1. Current UI Audit

### 1.1 Search Mode Selector — Location & UI Pattern

The search mode is rendered as a **segmented button group** (three buttons in a horizontal bar) in `SearchPage.tsx` (line 484–501). The buttons are wrapped in a `<div class="mode-selector">` with `role="group"` and each button uses `aria-pressed` for accessibility.

```
┌──────────────────────────────────────────────────┐
│  [Keyword]  [Semantic]  [Hybrid]                 │
│   ^^^^^^^^                                        │
│   active (highlighted with --color-primary)       │
└──────────────────────────────────────────────────┘
```

The three modes are defined as a static constant array:

```tsx
const MODE_OPTIONS: { value: SearchMode; labelId: string; titleId: string }[] = [
  { value: 'keyword',  labelId: 'search.modeKeyword',  titleId: 'search.modeKeywordTitle'  },
  { value: 'semantic', labelId: 'search.modeSemantic', titleId: 'search.modeSemanticTitle' },
  { value: 'hybrid',   labelId: 'search.modeHybrid',   titleId: 'search.modeHybridTitle'   },
];
```

**Default mode:** `keyword` (defined in `useSearchState.ts` line 46).

### 1.2 How the UI Calls the Search API

The search hook (`hooks/search.ts`) builds a request to `GET /v1/search?q=...&mode=...&limit=...&page=...&sort=...&fq_*=...`.

Key observations:
- The `mode` parameter is sent as a plain string: `keyword`, `semantic`, or `hybrid`.
- On a 400 response for non-keyword modes, the UI shows a helpful fallback error: *"Semantic search is unavailable. Embeddings may not be indexed yet."* (line 116–122).
- The search state is fully URL-driven (`useSearchState.ts`): mode is read from `?mode=` param, validated against `VALID_MODES`, and falls back to `keyword` if invalid.

### 1.3 Existing "Available Modes" or Capabilities Concept

**There is none.** The mode list is entirely hardcoded in the frontend. There is:
- No `GET /api/capabilities` call
- No feature flag system
- No A/B testing framework
- No environment-variable-driven mode filtering

The only dynamic behavior is the 400-error fallback for semantic/hybrid when embeddings aren't indexed.

### 1.4 Mode-Specific UI Elements

| Element | Location | Mode-specific behavior |
|---------|----------|----------------------|
| **Mode selector buttons** | SearchPage header | Static 3-button group, no disabling |
| **Mode badge** | Results count area | Colored pill showing active mode (keyword=gray, semantic=teal, hybrid=amber) |
| **FacetPanel** | Left sidebar | Shows "Facets are only available in keyword mode" message when `mode === 'semantic'`; hidden facets for semantic mode |
| **SimilarBooks** | Below results | Always uses vector similarity — independent of search mode |

---

## 2. Design Proposal for Hybrid-Rerank Mode

### 2.1 Recommended Approach: Hide Unavailable + Capabilities API

**Option (a) — Hide "Semantic" entirely** when the backend reports it's unavailable.

**Rationale:**
- Users don't need to know about HNSW vs rerank architecture
- Showing a grayed-out option creates confusion ("why can't I use this?")
- Simpler UX: users only see what works

### 2.2 Text-Based Mockups

#### HNSW Mode (current behavior, no changes)

```
┌─ Search ────────────────────────────────────────────────────┐
│                                                              │
│  [ 🔍 Search for books...                    ] [Search]      │
│                                                              │
│  [Keyword]  [Semantic]  [Hybrid]                             │
│   ^^^^^^^^                                                    │
│                                                              │
│  42 results for "machine learning"  ● keyword                │
│  Sort: Relevance ▾    Per page: 10 ▾                         │
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                     │
│  │ Result 1 │ │ Result 2 │ │ Result 3 │                     │
│  └──────────┘ └──────────┘ └──────────┘                     │
└──────────────────────────────────────────────────────────────┘
```

#### Hybrid-Rerank Mode (semantic hidden)

```
┌─ Search ────────────────────────────────────────────────────┐
│                                                              │
│  [ 🔍 Search for books...                    ] [Search]      │
│                                                              │
│  [Keyword]  [Hybrid]                                         │
│              ^^^^^^^^                                         │
│              (default in this mode)                           │
│                                                              │
│  42 results for "machine learning"  ● hybrid                 │
│  Sort: Relevance ▾    Per page: 10 ▾                         │
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                     │
│  │ Result 1 │ │ Result 2 │ │ Result 3 │                     │
│  └──────────┘ └──────────┘ └──────────┘                     │
└──────────────────────────────────────────────────────────────┘
```

### 2.3 Architecture Indicator (Admin Only)

Regular users should **not** see the architecture mode. Admin users can see it on the existing **Admin → Infrastructure** page as a new "Search Architecture" card:

```
┌─ Admin › Infrastructure ──────────────────────────┐
│                                                    │
│  ┌─────────────────────────────────┐               │
│  │ 🔍 Search Architecture          │               │
│  │                                  │               │
│  │  Mode:    hybrid-rerank          │               │
│  │  Modes:   keyword, hybrid        │               │
│  │  HNSW:    not available          │               │
│  └─────────────────────────────────┘               │
│                                                    │
│  (existing service cards below...)                 │
└────────────────────────────────────────────────────┘
```

---

## 3. Capabilities API Integration

### 3.1 Proposed API Contract

```
GET /api/capabilities
→ 200 OK
{
  "search_modes": ["keyword", "hybrid"],
  "default_mode": "hybrid",
  "architecture": "hybrid-rerank",
  "features": {
    "hnsw_index": false,
    "vector_reranking": true,
    "facets": true,
    "similar_books": false
  }
}
```

For HNSW mode:
```json
{
  "search_modes": ["keyword", "semantic", "hybrid"],
  "default_mode": "keyword",
  "architecture": "hnsw",
  "features": {
    "hnsw_index": true,
    "vector_reranking": false,
    "facets": true,
    "similar_books": true
  }
}
```

### 3.2 Frontend Integration Plan

#### New: `useCapabilities` hook

```tsx
// hooks/useCapabilities.ts
interface Capabilities {
  searchModes: SearchMode[];
  defaultMode: SearchMode;
  architecture: string;
  features: {
    hnswIndex: boolean;
    vectorReranking: boolean;
    facets: boolean;
    similarBooks: boolean;
  };
}

function useCapabilities(): {
  capabilities: Capabilities | null;
  loading: boolean;
  error: string | null;
}
```

- Fetches `GET /api/capabilities` once at app startup
- Caches in React context (`CapabilitiesContext`) so all components can access it
- Refetches on visibility change (`document.visibilitychange`) to handle deployment switches
- Returns sensible defaults while loading (all modes available = current behavior)

#### New: `CapabilitiesContext`

```tsx
// contexts/CapabilitiesContext.tsx
<CapabilitiesProvider>
  {/* wraps entire app in App.tsx */}
  <App />
</CapabilitiesProvider>
```

#### Changes to Existing Components

| File | Change |
|------|--------|
| `hooks/search.ts` | `SearchMode` type stays the same. No changes needed — the mode param is already a string. |
| `hooks/useSearchState.ts` | `VALID_MODES` becomes dynamic: read from `CapabilitiesContext`. If URL has an invalid mode, fall back to `capabilities.defaultMode` instead of hardcoded `'keyword'`. |
| `pages/SearchPage.tsx` | Filter `MODE_OPTIONS` array by `capabilities.searchModes`. Only render available modes. |
| `Components/FacetPanel.tsx` | No change needed — already handles mode-specific behavior. |
| `Components/SimilarBooks.tsx` | Check `capabilities.features.similarBooks` — hide the section if false (no HNSW = no kNN for similar books). |
| `pages/AdminInfrastructurePage.tsx` | Add "Search Architecture" card using capabilities data. |

### 3.3 Loading Strategy

```
App mounts
  → CapabilitiesProvider fetches /api/capabilities
  → While loading: render UI with all modes (optimistic, avoids flash)
  → On success: filter to available modes
  → On error: keep all modes (graceful degradation, let search API return 400s as today)
```

This is a **non-blocking** load — users can start typing immediately.

---

## 4. UX Considerations

### 4.1 User-Centric Naming

Most users don't care about HNSW vs rerank. The mode names should stay **user-friendly**:

| Mode | HNSW label | Hybrid-rerank label | Tooltip (title) |
|------|-----------|---------------------|-----------------|
| keyword | Keyword | Keyword | Traditional keyword search |
| semantic | Semantic | *(hidden)* | — |
| hybrid | Hybrid | Hybrid | Combined keyword + AI-powered search |

The hybrid tooltip can change subtly — "Combined keyword + semantic search" → "Combined keyword + AI-powered search" — but this is optional. The user-facing label stays "Hybrid" in both architectures.

### 4.2 Default Mode

**Recommendation:** Default to `hybrid` in hybrid-rerank mode, keep `keyword` default in HNSW mode.

Rationale: In hybrid-rerank mode, hybrid is the "best" search experience (BM25 + vector reranking). In HNSW mode, keyword is the safest default (always works even if embeddings aren't indexed yet).

The `defaultMode` field from the capabilities API drives this.

### 4.3 Bookmarked Semantic URLs in Hybrid-Rerank Mode

**Scenario:** User bookmarks `/search?q=react&mode=semantic`, then the deployment switches to hybrid-rerank.

**Handling:**
1. `useSearchState` validates `mode` against `capabilities.searchModes`
2. If `semantic` is not in the available list → fall back to `capabilities.defaultMode` (hybrid)
3. No error shown — the URL is silently corrected via `replace` navigation
4. Search executes normally with the fallback mode

This is the same pattern already used for invalid URL params (line 64–67 in `useSearchState.ts`).

### 4.4 SimilarBooks Behavior

In hybrid-rerank mode (no HNSW), the SimilarBooks component should be hidden because kNN similarity requires the HNSW index. The `capabilities.features.similarBooks` flag controls this.

---

## 5. A/B Testing Implications

**Finding:** There is no A/B testing framework in the codebase. No feature flags, experiments, or split-test infrastructure exists.

**Recommendation for future:** If A/B testing is needed to compare HNSW vs hybrid-rerank performance:
- The capabilities API already distinguishes architectures
- Analytics events should include `architecture` in their payload
- The backend controls which architecture serves each request — the frontend just adapts
- No frontend A/B framework is needed; the architecture is a deployment-level decision

---

## 6. Implementation Plan (Estimated)

| Step | Files | Effort |
|------|-------|--------|
| 1. Create `useCapabilities` hook + `CapabilitiesContext` | 2 new files | Small |
| 2. Wire into `App.tsx` | 1 file edit | Trivial |
| 3. Update `useSearchState` to use dynamic modes/defaults | 1 file edit | Small |
| 4. Filter `MODE_OPTIONS` in SearchPage | 1 file edit | Trivial |
| 5. Gate `SimilarBooks` on capabilities | 1 file edit | Trivial |
| 6. Add architecture card to Admin Infrastructure | 1 file edit | Small |
| 7. Add i18n keys for new strings (4 locales) | 4 file edits | Small |
| 8. Tests for new hook, context, and mode filtering | ~3-5 new test files | Medium |

**Total estimate:** ~2-3 days of focused frontend work, assuming the backend `/api/capabilities` endpoint is already available.

---

## 7. Open Questions for Team

1. **Parker (Backend):** Can you implement `GET /api/capabilities`? The contract is in section 3.1.
2. **Ash (Solr):** In hybrid-rerank mode, does the existing `/v1/search?mode=hybrid` endpoint automatically use reranking, or does it need a new mode value like `hybrid-rerank`?
3. **Ripley (Lead):** Should we add the architecture to analytics events now, or defer?
4. **SimilarBooks:** In hybrid-rerank mode, is there any fallback for similar books (e.g., BM25-based "related books"), or should we hide it entirely?
