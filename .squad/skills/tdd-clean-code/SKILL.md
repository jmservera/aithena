---
name: "tdd-clean-code"
description: "TDD red-green-refactor cycle and Clean Code/Architecture principles for aithena"
domain: "development-process"
confidence: "high"
source: "user directive — jmservera mandated TDD + Clean Code/Architecture for all development"
author: "Ripley"
created: "2026-03-14"
last_validated: "2026-03-14"
---

## TDD: Red → Green → Refactor

Every feature, bugfix, and refactor follows this cycle:

### 1. RED — Write a failing test first
- Write the **smallest test** that describes the desired behavior
- Run it — it **must fail** (if it passes, the test is wrong or the feature already exists)
- The test defines the interface contract before implementation exists

### 2. GREEN — Make it pass with minimal code
- Write the **simplest code** that makes the test pass
- No optimization, no abstraction, no cleanup — just make it green
- Resist the urge to write more than what the test requires

### 3. REFACTOR — Clean up while tests stay green
- Remove duplication, improve naming, extract functions
- Apply Clean Code principles (below)
- Run tests after every change — they must stay green
- This is where architecture emerges

### Cycle Rules
- **Never write production code without a failing test**
- **Never write more than one failing test at a time**
- **Never refactor while tests are red**
- Keep cycles short: 2-10 minutes per RED→GREEN→REFACTOR

---

## Clean Code Principles

### Naming
- Names reveal intent: `get_service_health()` not `get_data()`
- Functions: verb phrases (`calculate_stats`, `parse_facets`, `build_solr_params`)
- Variables: noun phrases (`document_count`, `author_facets`, `search_results`)
- Booleans: question form (`is_indexed`, `has_embedding`, `can_access`)
- No abbreviations except universally understood ones (URL, HTTP, PDF, API)

### Functions
- **Small:** ≤20 lines, one level of abstraction
- **Single Responsibility:** does one thing, does it well
- **No side effects:** a function named `get_stats()` must not modify state
- **Command-Query Separation:** functions either do something OR return something, not both
- **≤3 parameters:** if more, group into a dataclass/TypedDict

### Error Handling
- Use exceptions for exceptional cases, not flow control
- Fail fast: validate inputs at boundaries (API routes, CLI entry points)
- Never catch generic `Exception` unless re-raising
- Always log errors with context (what failed, what was the input)

---

## Clean Architecture — Aithena

### Backend (Python/FastAPI)

```
Presentation (main.py)
    ↓ calls
Application (search_service.py, status_service.py)
    ↓ calls
Domain (models, validation, business rules)
    ↓ uses
Infrastructure (Solr HTTP, RabbitMQ, Redis, filesystem)
```

**Rules:**
- Dependencies point **inward** (infrastructure → domain, never domain → infrastructure)
- `main.py` only handles HTTP concerns (routes, status codes, serialization)
- Service modules contain business logic (filtering, aggregation, validation)
- Infrastructure is injected or imported at the edge, never deep in business logic
- Domain models are plain Python dataclasses, no framework dependencies

**Example — Adding a new endpoint:**
```python
# 1. Domain model (no dependencies)
@dataclass
class ServiceHealth:
    name: str
    status: Literal["up", "down", "degraded"]
    response_time_ms: float

# 2. Application service (depends on domain, injected infra)
def get_status(solr_url: str, rabbitmq_url: str) -> list[ServiceHealth]:
    results = []
    results.append(check_solr(solr_url))
    results.append(check_rabbitmq(rabbitmq_url))
    return results

# 3. Presentation (depends on application)
@app.get("/v1/status/")
def status():
    return get_status(settings.solr_url, settings.rabbitmq_url)
```

### Frontend (React/TypeScript)

```
Pages (SearchPage, LibraryPage)
    ↓ uses
Components (BookCard, FacetPanel)
    ↓ uses
Hooks (useSearch, useLibrary)
    ↓ calls
API (api.ts — typed fetch wrappers)
```

**Rules:**
- Pages compose components and wire hooks — minimal logic
- Components are **presentational**: receive props, render UI, emit callbacks
- Hooks manage **state + side effects**: fetch data, manage loading/error
- `api.ts` is the **only** module that makes HTTP calls
- Components never call `fetch()` directly

**Example — Adding a new tab:**
```typescript
// 1. API layer (typed fetch)
export async function fetchStats(): Promise<StatsData> {
  const res = await fetch(`${API_BASE}/v1/stats/`);
  if (!res.ok) throw new Error(`Stats failed: ${res.status}`);
  return res.json();
}

// 2. Hook (state management)
export function useStats() {
  const [stats, setStats] = useState<StatsData | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { fetchStats().then(setStats).finally(() => setLoading(false)); }, []);
  return { stats, loading };
}

// 3. Page (composition)
export function StatsPage() {
  const { stats, loading } = useStats();
  if (loading) return <Spinner />;
  return <StatsTable data={stats} />;
}
```

---

## Test Structure

### Python (pytest) — Arrange / Act / Assert

```python
def test_parse_stats_returns_document_count():
    # Arrange
    solr_response = {"response": {"numFound": 42}}

    # Act
    result = parse_stats(solr_response)

    # Assert
    assert result.total_books == 42
```

### TypeScript (Vitest) — Given / When / Then

```typescript
test('BookCard renders title and author', () => {
  // Given
  const book = { title: 'Don Quixote', author: 'Cervantes', year: 1605 };

  // When
  render(<BookCard book={book} />);

  // Then
  expect(screen.getByText('Don Quixote')).toBeInTheDocument();
  expect(screen.getByText('Cervantes')).toBeInTheDocument();
});
```

### What to test
- **Happy path:** normal input → expected output
- **Edge cases:** empty input, null, missing fields, boundary values
- **Error cases:** network failure, invalid data, timeout
- **Security:** XSS in search results, path traversal, injection

### What NOT to test
- Framework internals (don't test that React renders a `<div>`)
- Implementation details (don't test internal state, test behavior)
- Third-party libraries (mock them, don't test them)

---

## Anti-Patterns to Avoid

### Testing Anti-Patterns
- ❌ **Test after:** writing tests after implementation loses the design benefit of TDD
- ❌ **Testing implementation:** `expect(hook.state.internalCache).toBe(...)` — test behavior, not internals
- ❌ **Brittle selectors:** `getByTestId('div-3-inner')` — use `getByRole`, `getByText`
- ❌ **Giant test files:** one 500-line test file — split by behavior/feature
- ❌ **Mocking everything:** if you mock the thing you're testing, the test is worthless

### Code Anti-Patterns
- ❌ **God function:** one function that queries Solr, transforms data, and formats HTML
- ❌ **Stringly typed:** using `status: str` when `status: Literal["up", "down"]` is available
- ❌ **Hidden dependencies:** importing `settings` deep inside a function instead of passing as parameter
- ❌ **Comments instead of names:** `x = get_data()  # get the status` → `status = get_service_health()`
- ❌ **Premature abstraction:** creating a `BaseService` class for one service
- ❌ **Dead code:** commented-out blocks, unused imports, unreachable branches

### Architecture Anti-Patterns
- ❌ **Circular dependencies:** component imports hook, hook imports component
- ❌ **Leaking infrastructure:** Solr response shape in React components
- ❌ **Fat controllers:** all logic in `main.py` route handlers
- ❌ **Anemic services:** service functions that just pass through to infrastructure
