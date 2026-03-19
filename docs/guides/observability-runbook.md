# Observability Runbook

Operational guide for monitoring, debugging, and troubleshooting the Aithena platform. This runbook is written for operators who need to diagnose issues quickly and restore service health.

> **Prerequisites:** Shell access to the Docker Compose host, `docker compose`, `curl`, and `jq` installed.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Service Map & Ports](#service-map--ports)
3. [Log Analysis](#log-analysis)
4. [Health Check Reference](#health-check-reference)
5. [Key API Endpoints for Debugging](#key-api-endpoints-for-debugging)
6. [Debugging Workflows](#debugging-workflows)
7. [Common Failure Scenarios](#common-failure-scenarios)
8. [Performance Investigation](#performance-investigation)
9. [Prometheus Metrics Reference](#prometheus-metrics-reference)
10. [Quick Reference Card](#quick-reference-card)

---

## Architecture Overview

Aithena is a multi-service document search platform. Documents flow through an ingestion pipeline and become searchable via keyword, semantic, or hybrid search.

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────┐
│  document-   │────▶│   RabbitMQ    │────▶│  document-   │────▶│ Solr │
│  lister      │     │  (queue)     │     │  indexer      │     │ (3x) │
│  (scanner)   │     └──────────────┘     │              │     └──────┘
└─────────────┘                           │              │
                                          │   ┌──────────┤
                                          │   │embeddings│
                                          │   │ server   │
                                          │   └──────────┘
                                          └──────────────┘

┌───────┐     ┌───────┐     ┌────────────┐     ┌──────┐
│ nginx │────▶│aithena│────▶│ solr-search │────▶│ Solr │
│ (:80) │     │  -ui  │     │  (FastAPI)  │     │      │
└───────┘     └───────┘     │             │     └──────┘
                            │   ┌─────┐   │
                            │   │Redis│   │
                            │   └─────┘   │
                            └─────────────┘

┌──────────────┐     ┌──────────────┐
│  streamlit-  │     │    redis-    │
│  admin       │     │  commander   │
└──────────────┘     └──────────────┘
```

**Data flow — Ingestion pipeline:**

1. **document-lister** scans `/data/documents/` for PDFs every `POLL_INTERVAL` seconds (default: 60)
2. Checks Redis for document state (new, modified, already processed)
3. Enqueues new/modified file paths to the `shortembeddings` RabbitMQ queue
4. **document-indexer** consumes from the queue with `prefetch_count=1`
5. Phase 1: Extracts full text via Solr Tika (`/update/extract`)
6. Phase 2: Chunks text, generates embeddings via **embeddings-server**, indexes chunks to Solr
7. Document state is tracked in Redis throughout (queued → text_indexed → processed, or → failed)

**Data flow — Search:**

1. User query hits **nginx** → **aithena-ui** → **solr-search** (FastAPI)
2. solr-search queries **Solr** (keyword), **embeddings-server** + Solr kNN (semantic), or both (hybrid RRF)
3. Results returned through the chain; **Redis** caches indexing state used by the status API

---

## Service Map & Ports

| Service | Internal Port | External Port (dev) | Technology | Purpose |
|---------|--------------|--------------------:|------------|---------|
| **nginx** | 80, 443 | 80, 443 | Nginx 1.15 | Reverse proxy, TLS, auth gateway |
| **solr-search** | 8080 | 8080 | FastAPI (Python) | Search API, admin API, auth |
| **aithena-ui** | 80 | — | Static frontend | Search UI |
| **streamlit-admin** | 8501 | 8501 | Streamlit (Python) | Admin dashboard |
| **document-lister** | — | — | Python worker | Filesystem scanner, queue producer |
| **document-indexer** | — | — | Python worker | Queue consumer, PDF indexer |
| **embeddings-server** | 8080 | 8085 | FastAPI + SentenceTransformers | Text → vector embeddings |
| **redis** | 6379 | 6379 | Redis | Document state cache |
| **redis-commander** | 8081 | 8081 | Node.js | Redis GUI |
| **rabbitmq** | 5672, 15672 | 5672, 15672 | RabbitMQ 3.12 | Message queue |
| **solr** | 8983 | 8983 | Solr (SolrCloud) | Primary search node |
| **solr2** | 8983 | 8984 | Solr (SolrCloud) | Replica node |
| **solr3** | 8983 | 8985 | Solr (SolrCloud) | Replica node |
| **zoo1** | 2181 | 2181 | ZooKeeper | SolrCloud coordination |
| **zoo2** | 2181 | 2182 | ZooKeeper | SolrCloud coordination |
| **zoo3** | 2181 | 2183 | ZooKeeper | SolrCloud coordination |

---

## Log Analysis

All services use the Docker `json-file` log driver with rotation (`max-size: 10m`, `max-file: 3`).

### Viewing Logs

```bash
# Follow all service logs
docker compose logs -f

# Follow a single service
docker compose logs -f solr-search
docker compose logs -f document-indexer
docker compose logs -f document-lister

# Follow multiple services
docker compose logs -f solr-search document-indexer document-lister

# Last N lines
docker compose logs --tail=100 solr-search

# Logs since a timestamp
docker compose logs --since="2025-01-15T10:00:00" solr-search

# Logs from the last hour
docker compose logs --since=1h document-indexer
```

### Filtering Logs with grep and jq

```bash
# Filter for errors across all services
docker compose logs --no-log-prefix 2>&1 | grep -i "error\|ERROR\|exception\|Exception"

# Filter document-indexer for failures
docker compose logs document-indexer 2>&1 | grep -i "failed\|error"

# Filter for a specific document path
docker compose logs document-indexer 2>&1 | grep "myfile.pdf"

# Count errors per service (quick health pulse)
for svc in solr-search document-indexer document-lister embeddings-server; do
  count=$(docker compose logs --since=1h "$svc" 2>&1 | grep -ci "error")
  echo "$svc: $count errors in the last hour"
done
```

### Structured JSON Logging

When `LOG_FORMAT=json` is set on a service, logs are emitted as JSON objects. Use `jq` to parse them:

```bash
# Parse JSON log lines
docker compose logs --no-log-prefix solr-search 2>&1 | \
  grep '^{' | jq '.'

# Filter by log level
docker compose logs --no-log-prefix solr-search 2>&1 | \
  grep '^{' | jq 'select(.level == "ERROR")'

# Filter by service name
docker compose logs --no-log-prefix solr-search 2>&1 | \
  grep '^{' | jq 'select(.service == "solr-search")'

# Extract timestamp, level, and message only
docker compose logs --no-log-prefix solr-search 2>&1 | \
  grep '^{' | jq '{timestamp: .timestamp, level: .level, message: .message}'

# Filter by correlation/request ID (when available)
docker compose logs --no-log-prefix solr-search 2>&1 | \
  grep '^{' | jq 'select(.correlation_id == "abc-123")'

# Show only WARNING and above
docker compose logs --no-log-prefix solr-search 2>&1 | \
  grep '^{' | jq 'select(.level == "WARNING" or .level == "ERROR" or .level == "CRITICAL")'
```

### Common Log Patterns

| Pattern | Service | Meaning |
|---------|---------|---------|
| `"Received <path>. Remaining messages: N"` | document-indexer | Message dequeued; N items still in queue |
| `"Indexed <title> by <author> into Solr collection books"` | document-indexer | Successful indexing (both text + embeddings) |
| `"Failed to process <path>: <error>"` | document-indexer | Indexing failure — check error detail |
| `"Waiting for Solr collection books (N/60): <error>"` | document-indexer | Solr not ready yet during startup |
| `"Found new document: <path>"` | document-lister | New PDF discovered, enqueuing |
| `"Found modified document: <path>"` | document-lister | Modified PDF detected, re-enqueuing |
| `"Document already processed: <path>"` | document-lister | No action needed |
| `"Document already in queue: <path>"` | document-lister | Already enqueued, waiting for indexer |
| `"Scanning <path> for *.pdf"` | document-lister | Poll cycle started |
| `"Document path does not exist yet: <path>"` | document-lister | Base path not mounted or empty |
| `"Loading embedding model: <model>"` | embeddings-server | Startup — model loading |
| `"Model loaded successfully: <model>"` | embeddings-server | Startup complete |
| `"Failed to load embedding model"` | embeddings-server | Critical — service cannot start |
| `"RabbitMQ closed the connection."` | document-indexer | Broker disconnected; auto-retry will fire |
| `"Invalid Redis payload for <path>. Resetting state."` | document-indexer | Corrupt Redis entry — state was reset |

---

## Health Check Reference

Every service has a Docker health check configured. View health status:

```bash
# All services at a glance
docker compose ps

# Detailed health for a specific service
docker inspect --format='{{json .State.Health}}' $(docker compose ps -q solr-search) | jq '.'
```

| Service | Health Check Command | Interval | Timeout | Retries | Start Period |
|---------|---------------------|----------|---------|---------|-------------|
| **redis** | `redis-cli ping` | 5s | 15s | 1 | — |
| **rabbitmq** | `rabbitmqctl ping` | 10s | 30s | 12 | 30s |
| **embeddings-server** | `wget http://localhost:8080/health` | 30s | 10s | 3 | 60s |
| **document-lister** | `pgrep -f python` | 30s | 10s | 3 | 10s |
| **document-indexer** | `pgrep -f python` | 30s | 10s | 3 | 10s |
| **solr-search** | `wget http://localhost:8080/health` | 30s | 10s | 3 | 30s |
| **streamlit-admin** | `python urlopen('…/_stcore/health')` | 30s | 10s | 3 | 10s |
| **redis-commander** | `node http.get(…)` | 30s | 10s | 3 | 10s |
| **aithena-ui** | `wget http://127.0.0.1:80/` | 30s | 10s | 3 | 10s |
| **nginx** | `wget http://127.0.0.1:80/health` | 30s | 10s | 3 | 10s |
| **solr / solr2 / solr3** | `curl http://localhost:8983/solr/admin/info/system` | 10s | 5s | 12 | 60s |
| **zoo1 / zoo2 / zoo3** | `ruok` + `mntr` (leader/follower check) | 10s | 5s | 12 | 30s |

> **Note:** `document-lister` and `document-indexer` use `pgrep -f python` — this only verifies the process is running, not that it's healthy. Check logs for actual processing status.

---

## Key API Endpoints for Debugging

All endpoints below are on **solr-search** (port 8080 internally, or through nginx on port 80).

### Health & Info

```bash
# Basic health check
curl -s http://localhost:8080/health | jq '.'
# → {"status":"ok","service":"Aithena Solr Search API","version":"..."}

# Service info
curl -s http://localhost:8080/info | jq '.'

# Build version details
curl -s http://localhost:8080/version | jq '.'
# → {"service":"solr-search","version":"...","commit":"...","built":"..."}
```

### System Status (Aggregated Health)

The `/v1/status` endpoint is the **single most useful debugging endpoint**. It aggregates:
- Solr cluster health (node count, indexed docs)
- Redis document state (discovered, indexed, failed, pending)
- TCP reachability for all infrastructure services
- Embeddings service availability

```bash
curl -s http://localhost:8080/v1/status | jq '.'
```

Example output:

```json
{
  "solr": {
    "status": "ok",
    "nodes": 3,
    "docs_indexed": 1542
  },
  "indexing": {
    "total_discovered": 200,
    "indexed": 185,
    "failed": 3,
    "pending": 12
  },
  "embeddings_available": true,
  "services": {
    "solr": "up",
    "redis": "up",
    "rabbitmq": "up",
    "embeddings": "up"
  }
}
```

**What to look for:**

| Field | Healthy | Investigate |
|-------|---------|-------------|
| `solr.status` | `"ok"` | `"degraded"` (< 3 nodes) or `"error"` (0 nodes) |
| `solr.nodes` | `3` | Any value < 3 |
| `indexing.failed` | `0` | Any value > 0 — check failed documents |
| `indexing.pending` | Low or `0` | Stays high — pipeline stalled |
| `embeddings_available` | `true` | `false` — semantic/hybrid search degraded |
| `services.*` | All `"up"` | Any `"down"` — that service needs attention |

### Container Status

```bash
# All container versions and health
curl -s http://localhost:8080/v1/admin/containers | jq '.'
```

Returns per-container version, commit SHA, status (`up`/`down`/`unknown`), and type (`service`/`infrastructure`/`worker`).

### Document Admin (Indexing Triage)

```bash
# List all tracked documents with their indexing state
curl -s http://localhost:8080/v1/admin/documents | jq '.'

# Requeue all failed documents
curl -s -X POST http://localhost:8080/v1/admin/documents/requeue-failed | jq '.'

# Requeue a specific document by ID
curl -s -X POST http://localhost:8080/v1/admin/documents/{doc_id}/requeue | jq '.'

# Clear all processed document state (forces full re-index on next scan)
curl -s -X DELETE http://localhost:8080/v1/admin/documents/processed | jq '.'
```

### Prometheus Metrics

```bash
curl -s http://localhost:8080/v1/metrics
```

See the [Prometheus Metrics Reference](#prometheus-metrics-reference) section below for metric definitions.

---

## Debugging Workflows

### 1. Diagnosing Search Failures

**Symptom:** User searches return no results or errors.

```
User → nginx (:80) → aithena-ui → solr-search (:8080) → Solr (:8983)
                                              └──→ embeddings-server (:8080) (semantic/hybrid only)
```

**Step 1 — Verify the search API is reachable:**

```bash
curl -s http://localhost:8080/health | jq '.'
# Expected: {"status":"ok", ...}
```

**Step 2 — Check Solr is reachable from solr-search:**

```bash
curl -s http://localhost:8080/v1/status | jq '.services.solr'
# Expected: "up"
```

**Step 3 — Test a direct search query:**

```bash
# Keyword search
curl -s "http://localhost:8080/search?q=test&mode=keyword" | jq '.results | length'

# If mode is semantic or hybrid, check embeddings
curl -s http://localhost:8080/v1/status | jq '.embeddings_available'
# If false, semantic/hybrid will degrade to keyword with a warning message
```

**Step 4 — Query Solr directly to isolate the issue:**

```bash
# Check Solr collection exists and has documents
curl -s "http://localhost:8983/solr/admin/collections?action=CLUSTERSTATUS&wt=json" | \
  jq '.cluster.collections.books.shards | to_entries[] | {shard: .key, docs: .value.replicas | to_entries[0].value.index.numDocs}'

# Run a direct Solr query
curl -s "http://localhost:8983/solr/books/select?q=*:*&rows=0&wt=json" | jq '.response.numFound'
```

**Step 5 — Check for embeddings issues (semantic/hybrid only):**

```bash
# Is the embeddings server healthy?
curl -s http://localhost:8085/health | jq '.'
# Expected: {"status":"healthy","model":"...","embedding_dim":...}

# Test embedding generation
curl -s -X POST http://localhost:8085/v1/embeddings/ \
  -H "Content-Type: application/json" \
  -d '{"input": "test query"}' | jq '.data | length'
# Expected: 1
```

**Step 6 — Check solr-search logs for errors:**

```bash
docker compose logs --since=30m solr-search 2>&1 | grep -i "error\|exception\|timeout"
```

### 2. Diagnosing Indexing Failures

**Symptom:** Documents are uploaded but never appear in search results.

```
document-lister → RabbitMQ → document-indexer → embeddings-server
                                             → Solr (Tika extract)
                                             → Solr (chunk indexing)
```

**Step 1 — Check pipeline status overview:**

```bash
curl -s http://localhost:8080/v1/status | jq '{indexing, services}'
```

**Step 2 — Check if documents are being discovered:**

```bash
docker compose logs --since=1h document-lister 2>&1 | grep -i "found\|scanning\|enqueue"
```

If you see `"Document path does not exist yet"`, the volume mount is misconfigured.

**Step 3 — Check RabbitMQ queue depth:**

```bash
# Via RabbitMQ management API
curl -s -u guest:guest http://localhost:15672/api/queues/%2f/shortembeddings | \
  jq '{messages: .messages, consumers: .consumers, state: .state}'
```

| Situation | Meaning | Action |
|-----------|---------|--------|
| `messages` high, `consumers` = 0 | Indexer is down | Check document-indexer logs/health |
| `messages` high, `consumers` > 0 | Indexer is slow or stuck | Check indexer logs for errors |
| `messages` = 0, `consumers` > 0 | Queue is drained (good) or nothing enqueued | Check document-lister |

**Step 4 — Check document-indexer processing:**

```bash
docker compose logs --since=1h document-indexer 2>&1 | \
  grep -E "Received|Indexed|Failed|Waiting for Solr"
```

**Step 5 — Check for failed documents in Redis:**

```bash
curl -s http://localhost:8080/v1/admin/documents | jq '[.[] | select(.status == "failed")]'
```

**Step 6 — Check which phase failed:**

The indexer has two phases. Redis state records `error_stage`:

| `error_stage` | Phase | Meaning |
|---------------|-------|---------|
| `text_indexing` | Phase 1 | Solr Tika extraction failed (bad PDF, Solr down) |
| `embedding_indexing` | Phase 2 | Chunk/embedding indexing failed (embeddings server down, Solr down) |
| `unknown` | Uncategorized | Error before or outside the two phases |

```bash
# Check error details for failed documents
curl -s http://localhost:8080/v1/admin/documents | \
  jq '[.[] | select(.status == "failed") | {path: .path, error: .error, stage: .error_stage}]'
```

**Step 7 — Requeue failed documents after fixing the root cause:**

```bash
curl -s -X POST http://localhost:8080/v1/admin/documents/requeue-failed | jq '.'
```

### 3. Checking Redis Cache Health

Redis stores document indexing state (queued, processed, failed) and is used by the status API.

```bash
# Is Redis reachable?
curl -s http://localhost:8080/v1/status | jq '.services.redis'

# Direct Redis connectivity test
docker compose exec redis redis-cli ping
# Expected: PONG

# Check Redis memory usage
docker compose exec redis redis-cli info memory | grep -E "used_memory_human|maxmemory"

# Count document state keys
docker compose exec redis redis-cli --scan --pattern '/shortembeddings/*' | wc -l

# Inspect a specific document's state
docker compose exec redis redis-cli get "/shortembeddings//data/documents/myfile.pdf" | python3 -m json.tool

# Check Redis keyspace info
docker compose exec redis redis-cli info keyspace
```

**Using Redis Commander (GUI):**

Navigate to `http://localhost:8081` (dev) or `http://<host>/admin/redis/` (via nginx) to browse keys visually.

### 4. Verifying RabbitMQ Queue Status

```bash
# Is RabbitMQ reachable?
curl -s http://localhost:8080/v1/status | jq '.services.rabbitmq'

# Queue details via management API
curl -s -u guest:guest http://localhost:15672/api/queues/%2f/shortembeddings | jq '.'

# Key fields to check
curl -s -u guest:guest http://localhost:15672/api/queues/%2f/shortembeddings | \
  jq '{
    name: .name,
    messages_total: .messages,
    messages_ready: .messages_ready,
    messages_unacked: .messages_unacknowledged,
    consumers: .consumers,
    state: .state,
    message_rate: .message_stats.publish_details.rate
  }'

# List all queues
curl -s -u guest:guest http://localhost:15672/api/queues | \
  jq '.[] | {name: .name, messages: .messages, consumers: .consumers}'

# Check connections (should see document-indexer and document-lister)
curl -s -u guest:guest http://localhost:15672/api/connections | \
  jq '.[] | {name: .name, state: .state, channels: .channels}'
```

**Using RabbitMQ Management UI:**

Navigate to `http://localhost:15672` (dev) or `http://<host>/admin/rabbitmq/` (via nginx).

### 5. Diagnosing Solr Cluster Issues

```bash
# Cluster status overview
curl -s "http://localhost:8983/solr/admin/collections?action=CLUSTERSTATUS&wt=json" | \
  jq '{live_nodes: .cluster.live_nodes, collections: (.cluster.collections | keys)}'

# Check individual node health
for port in 8983 8984 8985; do
  status=$(curl -sf "http://localhost:${port}/solr/admin/info/system" > /dev/null 2>&1 && echo "up" || echo "down")
  echo "solr (port $port): $status"
done

# Collection document counts per shard
curl -s "http://localhost:8983/solr/admin/collections?action=CLUSTERSTATUS&wt=json" | \
  jq '.cluster.collections.books.shards | to_entries[] | {
    shard: .key,
    state: .value.state,
    replicas: (.value.replicas | to_entries[] | {name: .key, state: .value.state, leader: .value.leader, docs: .value.index.numDocs})
  }'

# ZooKeeper health (all 3 nodes)
for port in 2181 2182 2183; do
  echo -n "zoo (port $port): "
  echo ruok | nc -w 2 localhost $port
done
```

### 6. Diagnosing Nginx / Routing Issues

```bash
# Nginx health
curl -sf http://localhost/health && echo "healthy" || echo "unhealthy"

# Check nginx can reach backends
curl -s http://localhost/v1/health | jq '.'
curl -s http://localhost/v1/info | jq '.'

# Nginx error logs
docker compose logs --since=30m nginx 2>&1 | grep -i "error\|502\|503\|504"

# Test auth flow
curl -s -X POST http://localhost/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' | jq '.'
```

---

## Common Failure Scenarios

### Scenario 1: "No search results"

| Check | Command | Expected |
|-------|---------|----------|
| Solr has documents | `curl -s http://localhost:8983/solr/books/select?q=*:*&rows=0&wt=json \| jq '.response.numFound'` | > 0 |
| solr-search is healthy | `curl -s http://localhost:8080/health \| jq '.'` | `status: "ok"` |
| Collection exists | `curl -s "http://localhost:8983/solr/admin/collections?action=LIST&wt=json" \| jq '.'` | Contains `"books"` |

**Resolution:** If no documents, check the indexing pipeline (Workflow #2). If Solr is down, restart Solr services.

### Scenario 2: "Indexing stuck — queue keeps growing"

```bash
# Confirm queue is growing
curl -s -u guest:guest http://localhost:15672/api/queues/%2f/shortembeddings | jq '.messages'

# Check if indexer is consuming
docker compose logs --tail=20 document-indexer

# Check if indexer process is alive
docker compose ps document-indexer
```

**Common causes:**
- **Solr collection not ready** — indexer logs show "Waiting for Solr collection". Wait for Solr startup to complete, or check ZooKeeper health.
- **Embeddings server down** — Phase 2 (embedding indexing) will fail. Check `docker compose ps embeddings-server`.
- **Indexer crashed** — `docker compose restart document-indexer`
- **Solr out of memory** — Check Solr container logs for OOM errors.

### Scenario 3: "Embeddings unavailable — keyword only"

```bash
# Check embeddings server
curl -s http://localhost:8085/health | jq '.'
docker compose logs --tail=50 embeddings-server

# Check status API
curl -s http://localhost:8080/v1/status | jq '.embeddings_available'
```

**Common causes:**
- **Model failed to load** — Check logs for `"Failed to load embedding model"`. The model download may have failed, or there's insufficient memory (needs ~2 GB).
- **OOM killed** — `docker compose ps embeddings-server` shows restart loop. Increase memory limit.
- **Startup not complete** — Model loading takes 30–60s. The health check has a `start_period: 60s` for this reason.

**Impact:** Search still works in keyword mode. Semantic and hybrid modes degrade gracefully to keyword with the message `"Embeddings unavailable — showing keyword results"`.

### Scenario 4: "Solr cluster degraded — fewer than 3 nodes"

```bash
# Check live nodes
curl -s "http://localhost:8983/solr/admin/collections?action=CLUSTERSTATUS&wt=json" | \
  jq '.cluster.live_nodes | length'

# Check which node is down
for port in 8983 8984 8985; do
  curl -sf "http://localhost:${port}/solr/admin/info/system" > /dev/null 2>&1 \
    && echo "port $port: UP" || echo "port $port: DOWN"
done

# Check ZooKeeper quorum
for port in 2181 2182 2183; do
  echo -n "zoo $port: "; echo mntr | nc -w 2 localhost $port | grep zk_server_state
done
```

**Resolution:**
- Restart the failed Solr node: `docker compose restart solr2` (or whichever is down)
- If ZooKeeper lost quorum (needs 2 of 3), restart failed ZK nodes first
- Search continues in degraded mode as long as at least 1 Solr node is alive

### Scenario 5: "Redis connection errors in logs"

```bash
docker compose ps redis
docker compose exec redis redis-cli ping
docker compose logs --tail=50 redis
```

**Common causes:**
- **Redis OOM** — Check `redis-cli info memory`. Redis has a 512 MB limit.
- **Redis restarting** — Check `docker compose ps redis` for restart count.
- **Network issue** — Try `docker compose exec document-indexer python -c "import redis; r=redis.Redis(host='redis'); print(r.ping())"`

**Impact:** Document state tracking fails. The indexer and lister have retry decorators (`@retry`) on Redis operations, so transient failures are handled. Persistent Redis downtime stalls the pipeline.

### Scenario 6: "RabbitMQ connection closed by broker"

```bash
docker compose logs --tail=50 rabbitmq
docker compose ps rabbitmq
curl -s -u guest:guest http://localhost:15672/api/overview | jq '{message_stats, queue_totals}'
```

**Common causes:**
- **Memory alarm** — RabbitMQ blocks publishers when memory exceeds threshold. Check `rabbitmqctl status`.
- **Disk alarm** — Insufficient disk space. Check `rabbitmqctl status`.
- **Heartbeat timeout** — Long-running indexing operations (300s Solr timeout) may exceed the 600s heartbeat.

**Resolution:** Both `document-lister` and `document-indexer` use `@retry(pika.exceptions.AMQPConnectionError)` and will auto-reconnect. If the broker itself is down, restart it: `docker compose restart rabbitmq`.

---

## Performance Investigation

### Search Latency

```bash
# Check p95 search latency from Prometheus metrics
curl -s http://localhost:8080/v1/metrics | grep "aithena_search_latency_seconds"

# Quick latency test per mode
for mode in keyword semantic hybrid; do
  time curl -s "http://localhost:8080/search?q=test&mode=$mode" > /dev/null
  echo "  ↑ $mode search"
done

# Check if Solr is slow (direct query)
time curl -s "http://localhost:8983/solr/books/select?q=test&rows=10&wt=json" > /dev/null
echo "  ↑ Direct Solr query"

# Check embeddings generation time
time curl -s -X POST http://localhost:8085/v1/embeddings/ \
  -H "Content-Type: application/json" \
  -d '{"input": "test query"}' > /dev/null
echo "  ↑ Embedding generation"
```

**Slow search checklist:**

| Bottleneck | Signal | Fix |
|-----------|--------|-----|
| Solr overloaded | High direct Solr query time | Check Solr heap, optimize queries, add nodes |
| Embeddings slow | High embedding generation time | Check embeddings-server memory, model loading |
| Network latency | Fast individual, slow combined | Check Docker network, DNS resolution |
| Large result sets | Slow with high `rows` values | Use pagination, reduce page size |

### Indexing Throughput

```bash
# Monitor queue drain rate
watch -n 5 'curl -s -u guest:guest http://localhost:15672/api/queues/%2f/shortembeddings | jq ".messages"'

# Check indexing failures metric
curl -s http://localhost:8080/v1/metrics | grep "aithena_indexing"

# Track indexing progress over time
curl -s http://localhost:8080/v1/status | jq '.indexing'
```

### Resource Usage

```bash
# Container resource usage
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"

# Check for OOM kills
docker compose ps --format "table {{.Service}}\t{{.State}}\t{{.Status}}"

# Check specific container restarts
docker inspect $(docker compose ps -q solr-search) | jq '.[0].RestartCount'
```

### Resource Limits Reference

| Service | Memory Limit | Memory Reservation | CPU Limit |
|---------|-------------|-------------------|-----------|
| redis | 512 MB | 256 MB | — |
| rabbitmq | 1 GB | 512 MB | — |
| embeddings-server | 2 GB | 1 GB | 1.0 CPU |
| document-lister | 256 MB | 128 MB | — |
| document-indexer | 512 MB | 256 MB | — |
| solr-search | 512 MB | 256 MB | 0.5 CPU |
| streamlit-admin | 512 MB | 256 MB | — |
| redis-commander | 256 MB | 128 MB | — |
| aithena-ui | 256 MB | 128 MB | — |
| nginx | 256 MB | 128 MB | — |

---

## Prometheus Metrics Reference

Metrics are exposed at `GET /v1/metrics` on solr-search in Prometheus text exposition format.

| Metric | Type | Description |
|--------|------|-------------|
| `aithena_search_requests_total{mode}` | Counter | Total search requests by mode (keyword/semantic/hybrid) |
| `aithena_search_latency_seconds_bucket{mode,le}` | Histogram | Search latency distribution |
| `aithena_search_latency_seconds_sum{mode}` | Histogram | Cumulative search latency |
| `aithena_search_latency_seconds_count{mode}` | Histogram | Total search request count |
| `aithena_indexing_queue_depth` | Gauge | Documents currently queued for indexing (from Redis state) |
| `aithena_indexing_failures_total` | Counter | Cumulative indexing failures observed since process start |
| `aithena_embeddings_available` | Gauge | `1` if embeddings server is reachable, `0` otherwise |
| `aithena_solr_live_nodes` | Gauge | Number of live Solr nodes from CLUSTERSTATUS |

**Latency buckets:** 0.1s, 0.25s, 0.5s, 1.0s, 2.5s, 5.0s, 10.0s, 30.0s

**Note:** All counters reset when solr-search restarts (in-memory only).

See [docs/monitoring.md](monitoring.md) for Prometheus scrape configuration and recommended alert thresholds.

---

## Quick Reference Card

### "Is everything healthy?"

```bash
curl -s http://localhost:8080/v1/status | jq '.'
```

### "Why isn't my document appearing in search?"

```bash
# Check if it was discovered
docker compose logs document-lister 2>&1 | grep "myfile.pdf"

# Check its Redis state
docker compose exec redis redis-cli get "/shortembeddings//data/documents/myfile.pdf" | python3 -m json.tool

# Check if it failed
curl -s http://localhost:8080/v1/admin/documents | jq '.[] | select(.path | contains("myfile"))'
```

### "How many documents are indexed?"

```bash
curl -s http://localhost:8080/v1/status | jq '.indexing'
curl -s "http://localhost:8983/solr/books/select?q=*:*&rows=0&wt=json" | jq '.response.numFound'
```

### "Restart a stuck service"

```bash
docker compose restart <service-name>

# Nuclear option — full restart
docker compose down && docker compose up -d
```

### "Reprocess all failed documents"

```bash
curl -s -X POST http://localhost:8080/v1/admin/documents/requeue-failed | jq '.'
```

### "Force re-index everything"

```bash
# Clear all document state from Redis (documents will be re-discovered on next scan)
curl -s -X DELETE http://localhost:8080/v1/admin/documents/processed | jq '.'

# The document-lister will pick them up on its next poll cycle (default: 60 seconds)
```

### "Check all service versions"

```bash
curl -s http://localhost:8080/v1/admin/containers | jq '.containers[] | {name, version, commit, status}'
```
