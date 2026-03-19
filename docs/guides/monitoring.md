# Monitoring

`solr-search` exposes Prometheus-compatible metrics at `/v1/metrics` using the plain-text exposition format. The endpoint keeps request counters and latency histograms in memory, so counter values reset when the service restarts.

## Scrape configuration

```yaml
scrape_configs:
  - job_name: aithena-search
    metrics_path: /v1/metrics
    static_configs:
      - targets:
          - solr-search:8080
```

## Exported metrics

- `aithena_search_requests_total{mode="keyword|semantic|hybrid"}`
- `aithena_search_latency_seconds_bucket{mode=...}` plus `_sum` and `_count`
- `aithena_indexing_queue_depth`
- `aithena_indexing_failures_total`
- `aithena_embeddings_available`
- `aithena_solr_live_nodes`

## Recommended alert thresholds

Tune thresholds after observing production baselines, but these defaults are a good starting point for the current single-service deployment.

```yaml
groups:
  - name: aithena-search
    rules:
      - alert: AithenaIndexingQueueDepthHigh
        expr: aithena_indexing_queue_depth > 100
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: Aithena indexing backlog is growing
          description: More than 100 documents have remained queued for 15 minutes.

      - alert: AithenaIndexingQueueDepthCritical
        expr: aithena_indexing_queue_depth > 500
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: Aithena indexing backlog is critically high
          description: More than 500 documents are queued and indexing throughput is likely impaired.

      - alert: AithenaSearchLatencyP95High
        expr: histogram_quantile(0.95, sum by (le, mode) (rate(aithena_search_latency_seconds_bucket[5m]))) > 1.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: Aithena search latency p95 is elevated
          description: Search p95 latency has exceeded 1.5 seconds for at least 10 minutes.

      - alert: AithenaEmbeddingsUnavailable
        expr: aithena_embeddings_available == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: Embeddings service is unavailable
          description: The embeddings service has been unavailable for 5 minutes, so semantic and hybrid search will degrade.

      - alert: AithenaSolrLiveNodesLow
        expr: aithena_solr_live_nodes < 3
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: Solr cluster has lost a live node
          description: Fewer than 3 Solr live nodes are reported by CLUSTERSTATUS.
```

## Operational notes

- `aithena_indexing_failures_total` is derived from Redis failed keys observed by the API process and is monotonic only for the lifetime of the process.
- `aithena_indexing_queue_depth` reflects queued documents tracked in Redis state, not RabbitMQ message depth.
- Consider adding a dashboard panel split by `mode` for latency and request volume so degraded semantic or hybrid search is visible immediately.
