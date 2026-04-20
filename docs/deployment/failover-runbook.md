# Failover & Recovery Runbook

This runbook covers operator recovery for the Docker Compose deployment defined in `docker-compose.yml`. It is based on the current Compose wiring, health checks, volumes, and `solr-search` behavior in `src/solr-search/main.py`.

> Docker is not available in this sandbox, so the steps below are based on code analysis rather than a live drill. Use `e2e/failover-drill.sh` in a Docker-capable environment to validate the procedure.

## Preconditions

- Run `python3 -m installer` before the first `docker compose up` so `.env`, `AUTH_DB_DIR`, `AUTH_DB_PATH`, and the SQLite auth DB exist.
- Use the base `docker-compose.yml` for full failover drills. `docker/compose.e2e.yml` intentionally disables `nginx`, so it is not suitable for the nginx outage scenario. If your deployment uses SSL, add `-f docker/compose.ssl.yml` to include the certbot sidecar.
- Use `docker compose ps` and container health checks to confirm process-level readiness.
- Use the status probe below for application-level confirmation:

```bash
docker compose exec -T solr-search wget -qO- http://localhost:8080/v1/status/
```

Why this probe is preferred:

- `solr-search` exposes `/v1/status/` without FastAPI auth.
- nginx protects `/v1/*` externally, so unauthenticated `curl http://localhost/v1/status/` will be rejected.
- The internal probe still works even when nginx is down.

A healthy baseline should show:

- `services.solr = up`
- `services.redis = up`
- `services.rabbitmq = up`
- `services.embeddings = up`
- `embeddings_available = true`
- `solr.status = ok`
- `solr.nodes >= 3`

## Service dependency map

| Service | Hard dependencies (`depends_on`) | Operational notes |
| --- | --- | --- |
| `redis` | — | Stores indexing state (`doc:*`) and supports admin/indexing services. |
| `rabbitmq` | — | Durable queue broker for indexing and uploads. |
| `zoo1`, `zoo2`, `zoo3` | — | SolrCloud coordination layer; quorum is required for stable Solr operation. |
| `solr` | `zoo1`, `zoo2`, `zoo3` healthy | Primary Solr endpoint used by `solr-search` and `document-indexer`. |
| `solr2` | `zoo1`, `zoo2`, `zoo3`, `solr` healthy | Additional Solr replica node. |
| `solr3` | `zoo1`, `zoo2`, `zoo3`, `solr2` healthy | Additional Solr replica node. |
| `solr-init` | `solr`, `solr2`, `solr3` healthy | One-shot bootstrap that uploads config and creates the `books` collection with `replicationFactor=3`. |
| `embeddings-server` | — | Required for semantic/hybrid search and document embedding. |
| `document-lister` | `rabbitmq`, `redis` healthy | Polls `document-data` and publishes indexing work to RabbitMQ. |
| `document-indexer` | `rabbitmq`, `redis`, `embeddings-server` healthy | Consumes queue items, creates embeddings, and writes to Solr. |
| `solr-search` | `solr`, `embeddings-server`, `rabbitmq`, `redis` healthy | Search/API tier. Startup is gated by Redis and RabbitMQ, but runtime search availability mainly depends on Solr and embeddings. |
| `redis-commander` | `redis` healthy | Redis admin UI. |
| `aithena-ui` | `solr-search` healthy | End-user UI. |
| `nginx` | `aithena-ui`, `solr-search`, `redis-commander`, `rabbitmq`, `solr` healthy | Public ingress and auth gate for `/v1/*`, `/documents/*`, and `/admin/*`. |
| `certbot` | — | Certificate renewal sidecar (optional — only with `docker/compose.ssl.yml`). |

### Important architecture caveat

The Solr cluster has three nodes, but the application tier is configured to talk to `http://solr:8983/solr` directly:

- `solr-search` uses `SOLR_URL=http://solr:8983/solr`
- `document-indexer` uses `SOLR_HOST=solr`

That means losing the **primary `solr` service** is still a user-visible outage even if `solr2` and `solr3` are alive.

## `/v1/status/` behavior

`/v1/status/` aggregates four checks:

- Solr cluster state and live-node count from `CLUSTERSTATUS`
- Redis `doc:*` key counts for indexing state
- TCP reachability for Solr, Redis, and RabbitMQ
- embeddings-server `/version` reachability

Expected status semantics:

| Field | Meaning |
| --- | --- |
| `solr.status = ok` | Solr `CLUSTERSTATUS` succeeded and at least 3 live nodes were seen. |
| `solr.status = degraded` | Solr answered, but fewer than 3 live nodes were seen. |
| `solr.status = error` | Solr cluster query failed or no live nodes were reachable. |
| `services.<name> = up/down` | Simple reachability check for Solr, Redis, RabbitMQ, or embeddings-server. |
| `embeddings_available` | `true` when embeddings-server answers its `/version` probe. |
| `indexing.*` | Redis-backed indexing counters; if Redis is unavailable the endpoint returns zeros. |

## Failure scenarios

### 1. Primary Solr service down (`solr`)

**Typical symptoms**

- `/v1/status/` reports:
  - `services.solr = down`
  - `solr.status = error`
  - `solr.nodes = 0`
- Keyword, semantic, and hybrid search requests fail.
- Document indexing cannot write to Solr.
- nginx may stay up, but `/v1/search` and `/documents/*` requests will fail upstream.

**Detection**

```bash
docker compose exec -T solr-search wget -qO- http://localhost:8080/v1/status/
```

**Recovery**

1. Start or restart the primary node:
   ```bash
   docker compose restart solr
   ```
2. Wait for `solr` to become healthy:
   ```bash
   docker compose ps solr
   ```
3. If the collection or configset was lost, rerun the bootstrap job:
   ```bash
   docker compose up -d solr-init
   docker compose logs --tail=100 solr-init
   ```
4. Restart direct dependents if they do not recover cleanly:
   ```bash
   docker compose restart document-indexer solr-search nginx
   ```
5. Re-run `/v1/status/` and confirm `services.solr = up`.

**Expected behavior during failure**

There is **no** fallback when Solr is unavailable. Semantic/hybrid fallback only helps when embeddings fail; it does not replace Solr.

### 2. Redis down

**Typical symptoms**

- `/v1/status/` reports `services.redis = down`.
- `indexing.total_discovered`, `indexed`, `failed`, and `pending` fall back to zeros because Redis reads fail.
- Search requests usually continue to work.
- `document-lister`, `document-indexer`, and `redis-commander` may stop working or restart repeatedly until Redis returns.

**Detection**

```bash
docker compose exec -T solr-search wget -qO- http://localhost:8080/v1/status/
```

**Recovery**

1. Restart Redis:
   ```bash
   docker compose restart redis
   ```
2. Wait for `redis-cli ping` health to recover:
   ```bash
   docker compose ps redis
   ```
3. Restart Redis-dependent services if they do not reconnect automatically:
   ```bash
   docker compose restart document-lister document-indexer redis-commander
   ```
4. Re-run `/v1/status/` and confirm `services.redis = up`.

**Expected behavior during failure**

- Existing search traffic should still work.
- Indexing progress tracking is unavailable until Redis returns.

### 3. RabbitMQ down

**Typical symptoms**

- `/v1/status/` reports `services.rabbitmq = down`.
- Search requests usually continue to work.
- New uploads and document discovery stop flowing into the indexing queue.
- `document-lister` and `document-indexer` may fail or restart until RabbitMQ is healthy again.

**Detection**

```bash
docker compose exec -T solr-search wget -qO- http://localhost:8080/v1/status/
```

**Recovery**

1. Restart RabbitMQ:
   ```bash
   docker compose restart rabbitmq
   ```
2. Wait for the broker health check to pass:
   ```bash
   docker compose ps rabbitmq
   ```
3. Restart queue-dependent services if needed:
   ```bash
   docker compose restart document-lister document-indexer
   ```
4. Re-run `/v1/status/` and confirm `services.rabbitmq = up`.

**Expected behavior during failure**

- Search remains available.
- Ingestion/indexing work pauses until the queue broker returns.

### 4. embeddings-server down

**Typical symptoms**

- `/v1/status/` reports:
  - `services.embeddings = down`
  - `embeddings_available = false`
- Keyword search still works.
- Semantic and hybrid search requests degrade to keyword mode and include:
  - `degraded: true`
  - `message: "Embeddings unavailable — showing keyword results"`
  - `requested_mode: "semantic"` or `"hybrid"`
- `document-indexer` cannot generate new embeddings while the outage lasts.

**Detection**

```bash
docker compose exec -T solr-search wget -qO- http://localhost:8080/v1/status/
```

**Recovery**

1. Restart the embeddings service:
   ```bash
   docker compose restart embeddings-server
   ```
2. Wait for its `/health` probe to pass:
   ```bash
   docker compose ps embeddings-server
   ```
3. Restart `document-indexer` if it does not reconnect automatically:
   ```bash
   docker compose restart document-indexer
   ```
4. Re-run `/v1/status/` and confirm embeddings are back up.
5. Run a semantic search probe and confirm the response is no longer degraded.

**Expected behavior during failure**

This is the designed graceful-degradation path: semantic/hybrid requests fall back to keyword search instead of returning 502/504.

### 5. nginx down

**Typical symptoms**

- `curl http://localhost/health` fails.
- External access to `/`, `/documents/*`, `/admin/*`, and `/v1/*` fails.
- Internal service-to-service traffic continues; `solr-search` can still answer `/v1/status/` internally.

**Detection**

- External ingress check:
  ```bash
  curl -f http://localhost/health
  ```
- Internal API check (works even when nginx is stopped):
  ```bash
  docker compose exec -T solr-search wget -qO- http://localhost:8080/v1/status/
  ```

**Recovery**

1. Confirm upstream services are healthy enough to serve traffic:
   ```bash
   docker compose ps aithena-ui solr-search redis-commander rabbitmq solr
   ```
2. Restart nginx:
   ```bash
   docker compose restart nginx
   ```
3. Validate external ingress:
   ```bash
   curl -f http://localhost/health
   ```
4. If nginx still returns 502/503, recover the unhealthy upstream and restart nginx again.

**Expected behavior during failure**

nginx is only the ingress tier. Its failure does not stop the internal search/indexing stack, but it removes external access.

## Graceful degradation: semantic → keyword fallback

The fallback applies only when the embeddings request fails with a transient backend error (`502` or `504`):

- `mode=semantic` → returns a keyword search payload with `degraded: true`
- `mode=hybrid` → returns a keyword search payload with `degraded: true`
- `mode=keyword` → unaffected

Operationally, this means:

- An embeddings outage should not take the search UI offline.
- A Solr outage still breaks all search modes because keyword search also depends on Solr.
- Recovery validation should include one semantic or hybrid request after embeddings-server returns to confirm `degraded` goes back to `false`.

## Recommended restart ordering

Compose health checks define the safe recovery order. Restart from the bottom of the dependency graph upward.

1. **Core stateful infrastructure**
   - `redis`
   - `rabbitmq`
   - `zoo1`, `zoo2`, `zoo3`
2. **Search cluster**
   - `solr`, `solr2`, `solr3`
   - `solr-init` (if collection/config bootstrap must be replayed)
3. **ML service**
   - `embeddings-server`
4. **Workers and API**
   - `document-lister`
   - `document-indexer`
   - `solr-search`
5. **Operator and user interfaces**
   - `redis-commander`
   - `aithena-ui`
6. **Ingress**
   - `nginx`

### Practical rule

After restoring an upstream dependency, restart the services that depend on it if they do not reconnect automatically. Compose `depends_on` only guarantees startup ordering; it does not re-run that logic after a later runtime failure.

## Data durability

| Data / state | Backing storage | What survives restart | What can be lost |
| --- | --- | --- | --- |
| Solr index (`books`) | Bind-mounted `solr-data`, `solr-data2`, `solr-data3` | Indexed documents and vectors survive normal restarts. | If the Solr volumes are deleted or corrupted, search data is lost and must be rebuilt from source documents. |
| ZooKeeper metadata | Bind-mounted `zoo-data*` volumes | Collection metadata and cluster coordination data survive restarts. | Losing ZooKeeper data can require re-running `solr-init` and re-forming the cluster. |
| Redis indexing state | Bind-mounted `/source/volumes/redis`, Redis RDB snapshots (`--save 20 1`) | Most `doc:*` state survives orderly restarts. | Recent in-memory updates since the last snapshot can be lost on crash/forced stop. |
| RabbitMQ queue state | Bind-mounted `/source/volumes/rabbitmq-data` | Durable queues and persistent messages survive broker restarts. | In-flight work can be retried; if the volume is removed, queued work is lost. |
| Auth DB | Host bind mount from `AUTH_DB_DIR` to `/data/auth`, SQLite `users.db` | Users, password hashes, and auth data survive container restarts. | If `AUTH_DB_DIR` is deleted, logins are lost until the DB is restored or recreated. |
| Source documents | `document-data` bind mount | PDFs remain intact because they live on the host library path. | Not affected by container restarts unless the host path changes or is deleted. |

## Suggested operator validation after recovery

Run these after any fix:

```bash
# Core application health
docker compose exec -T solr-search wget -qO- http://localhost:8080/v1/status/

# Public ingress (nginx scenarios)
curl -f http://localhost/health

# Optional authenticated search smoke test
curl -f -H "Authorization: Bearer $TOKEN" \
  "http://localhost/v1/search?q=history&mode=keyword&page_size=1"
```

If the outage involved embeddings-server, repeat the smoke test with `mode=semantic` and confirm the response is no longer degraded.
