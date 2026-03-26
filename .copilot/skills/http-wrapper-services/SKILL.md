---
name: "http-wrapper-services"
description: "Build thin, well-typed FastAPI wrappers around complex infrastructure (Solr, embeddings servers)"
domain: "api, fastapi, backend, architecture"
confidence: "high"
source: "earned — solr-search, embeddings-server, and status/stats endpoints follow this pattern consistently (v0.4–v0.5)"
author: "Ripley"
created: "2026-03-14T23:45"
last_validated: "2026-03-14T23:45"
---

## Context

When building backend services in aithena, complex infrastructure (Solr, embeddings servers, monitoring endpoints) should be wrapped in thin, well-typed FastAPI layers. This pattern emerges across `solr-search/`, `embeddings-server/`, and all `/v1/*` health/stats endpoints.

## Problem

Raw Solr HTTP responses are verbose, untyped, and require significant client-side parsing. Direct embeddings server calls lack standardization. Building this parsing logic in React components violates the Clean Architecture principle (presentation layer should never know infrastructure shape).

## Solution

Build a **typed HTTP wrapper service** with three layers:

### Layer 1: Domain Models (Plain Python dataclasses)

Define response shapes that the frontend actually needs, not what Solr returns:

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class SearchResult:
    """User-facing search result — never contains Solr schema details."""
    id: str
    title: str
    author: str
    snippet: str  # Pre-extracted, sanitized snippet
    page_number: int | None
    year: int | None

@dataclass
class SearchResponse:
    total_count: int
    results: list[SearchResult]
    facets: dict[str, dict[str, int]]
```

### Layer 2: Application Service (query builder + parsing)

Handle all Solr integration logic in one place:

```python
# search_service.py — application layer
def search(q: str, page: int = 1, page_size: int = 20) -> SearchResponse:
    """Query Solr and return typed response."""
    solr_params = {
        "q": q,
        "start": (page - 1) * page_size,
        "rows": page_size,
        "defType": "edismax",
        "qf": "title_t^3 author_t^2 content",
    }
    
    raw_response = requests.get(
        f"{SOLR_URL}/select", 
        params=solr_params
    ).json()
    
    # Parse Solr response into domain models
    results = [
        SearchResult(
            id=doc["id"],
            title=doc.get("title_s", "Unknown"),
            snippet=extract_highlight(raw_response["highlighting"].get(doc["id"], ""))
        )
        for doc in raw_response["response"]["docs"]
    ]
    
    return SearchResponse(
        total_count=raw_response["response"]["numFound"],
        results=results,
        facets=parse_facets(raw_response.get("facet_counts", {}))
    )
```

### Layer 3: Presentation (FastAPI routes)

Routes are pure HTTP handlers — no Solr logic here:

```python
# main.py — presentation layer
@app.get("/v1/search/", response_model=SearchResponse)
def search_handler(q: str, page: int = 1, page_size: int = 20):
    """HTTP endpoint."""
    return search_service.search(q, page, page_size)
```

### Frontend Never Touches Infrastructure

The React component receives `SearchResponse` (typed dict), not raw Solr:

```typescript
// Frontend: completely decoupled from Solr schema
export interface SearchResult {
  id: string;
  title: string;
  author: string;
  snippet: string;
  page_number: number | null;
}

// This is the only backend knowledge needed
const response = await fetch(`/v1/search/?q=${q}`);
const results: SearchResult[] = response.results;
```

## Patterns Observed in aithena

### ✅ solr-search/search_service.py
- `FACET_FIELDS`, `SOLR_FIELD_LIST`, `SORT_FIELDS` constants centralize Solr schema knowledge
- `build_filter_queries()` abstracts filter parsing → Solr fq params
- `parse_response()` normalizes raw Solr into domain models
- Tests validate transformation logic independently (e.g., `test_parse_stats_returns_document_count`)

### ✅ solr-search/main.py
- Routes are thin wrappers: `search()` → `search_service.search()` → response serialization
- All error handling at the HTTP layer (status codes, error schemas)
- No Solr logic leaks into route handlers

### ✅ /v1/status/ endpoint (stats + indexing)
- Domain models: `ServiceHealth`, `CollectionStats`, `IndexingStatus`
- Application service: `get_service_health()`, `get_collection_stats()`
- Presentation: routes call services, return typed responses

### ✅ embeddings-server/main.py
- Wraps `sentence-transformers` library
- `/v1/embeddings/` returns standardized `EmbeddingResponse` (list of floats)
- Model details abstracted: frontend doesn't know it's distiluse or Jina

### ❌ Anti-Pattern: Leaking Infrastructure
- Don't expose raw Solr response in FastAPI response_model
- Don't let React components `import solr_response_schema`
- Don't hardcode field names in route handlers (use constants)

## Testing Strategy

Each layer is independently testable:

```python
# Test domain models (ensure they're serializable)
def test_search_result_json_serialization():
    r = SearchResult(...); json.dumps(asdict(r))

# Test application service (mock Solr, validate parsing)
def test_search_parses_solr_facets():
    raw = {"facet_counts": {...}}
    result = search_service._parse_facets(raw)
    assert result == {...}

# Test presentation (mock service, validate HTTP)
def test_search_endpoint_returns_200():
    response = client.get("/v1/search/?q=test")
    assert response.status_code == 200
```

## Migration Path for Existing Services

If a service has Solr logic scattered across routes:

1. **Extract domain models** from the responses you want to expose
2. **Create `search_service.py`** and move all parsing there
3. **Update routes** to call the service
4. **Add unit tests** to service layer (mock Solr HTTP)
5. **Verify frontend** works with the new typed responses

Example: `embeddings-server/` → needs refactor to separate model loading (infrastructure) from the HTTP endpoint (presentation).

## References

- `solr-search/search_service.py` — canonical example
- `solr-search/main.py` — route layer example
- `.squad/skills/tdd-clean-code/SKILL.md` — clean architecture principles
- `aithena-ui/src/api.ts` — frontend (never touches Solr directly)
