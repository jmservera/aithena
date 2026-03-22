# Lambert — P2-4 Performance Metrics Decisions

## Decision: In-memory rolling-window store over Prometheus client

**Context:** Issue #881 required metrics collection for A/B evaluation with no new infrastructure dependencies.

**Decision:** Built a standalone `PerfMetricsStore` class using `threading.Lock` + `defaultdict` + `TimedSample` dataclass instead of using the existing Prometheus `MetricsRegistry` or adding prometheus-client.

**Rationale:**
- The existing `MetricsRegistry` (metrics.py) is Prometheus exposition-format only — adding per-collection latency percentiles would require significant refactoring
- This is temporary A/B tooling, not production monitoring — lighter is better
- Rolling-window pruning keeps memory bounded without external storage
- JSON response from `/v1/admin/metrics` is immediately consumable by scripts and dashboards

## Decision: Internal timing keys in search response dicts

**Decision:** Search mode functions (`_search_keyword`, `_search_semantic`, `_search_hybrid`) return `_solr_latency_s` and `_embedding_latency_s` keys in the response dict, stripped by the caller before returning to the client.

**Rationale:** Avoids changing function signatures or adding a separate return channel. The underscore-prefix convention signals these are internal. The caller (`search()`) pops them after recording metrics.

## Decision: Admin-auth for metrics endpoints

**Decision:** `GET /v1/admin/metrics` and `POST /v1/admin/metrics/reset` use `require_admin_auth` (X-API-Key), consistent with other `/v1/admin/*` endpoints.

**Rationale:** Performance data could reveal usage patterns; reset should be controlled. Follows existing admin endpoint pattern.
