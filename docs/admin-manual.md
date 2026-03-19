# Admin Manual

This manual covers deployment, configuration, monitoring, and troubleshooting for Aithena. If you are looking for end-user instructions, start with the [User Manual](user-manual.md). For the latest release features, see the [v1.7.0 Release Notes](release-notes-v1.7.0.md).

## System architecture overview

Aithena runs as a Docker Compose stack built around Solr, a document ingestion pipeline, and a React web UI.

### Core services

| Service | Purpose | Default access |
|---|---|---|
| `nginx` | Main reverse proxy and public entry point | `80`, `443` |
| `aithena-ui` | User-facing React frontend | proxied through `nginx` |
| `solr-search` | FastAPI search, status, stats, and document endpoints | proxied through `nginx`; direct `8080` via override |
| `solr`, `solr2`, `solr3` | SolrCloud search nodes | proxied admin through `nginx`; direct `8983`-`8985` via override |
| `solr-init` | One-shot collection/config bootstrap for `books` | internal only |
| `zoo1`, `zoo2`, `zoo3` | ZooKeeper ensemble for SolrCloud | internal only; direct `18080`, `2181`-`2183` via override |
| `redis` | Indexing state tracking | internal only; direct `6379` via override |
| `rabbitmq` | Queue for document ingestion | internal AMQP; admin proxied through `nginx`; direct `5672`, `15672` via override |
| `document-lister` | Scans the mounted library and enqueues PDFs | internal only |
| `document-indexer` | Consumes queue items and indexes books into Solr | internal only |
| `embeddings-server` | Embedding service used by the search stack | internal only; direct `8085` via override |
| `streamlit-admin` | Lightweight admin dashboard | proxied through `nginx`; direct `8501` via override |
| `redis-commander` | Web UI for Redis inspection | proxied through `nginx`; direct `8081` via override |
| `certbot` | Certificate renewal helper | internal only |

### Service dependencies

At a high level:

1. `document-lister` scans the mounted book library.
2. New or changed PDFs are pushed into RabbitMQ.
3. `document-indexer` consumes queue messages and writes metadata plus extracted content into Solr.
4. `solr-search` serves search results, PDF document links, status, and stats.
5. `aithena-ui` and `nginx` present the user-facing application.

### Pipeline dependency ordering (v0.5.0)

The v0.5.0 Compose update tightens startup ordering so pipeline services wait for healthy dependencies instead of merely started containers.

Current shipped behavior:

- `document-lister` waits for **RabbitMQ** and **Redis** with `condition: service_healthy`
- `document-indexer` waits for **RabbitMQ** and **Redis** with `condition: service_healthy`
- `streamlit-admin` waits for **RabbitMQ** and **Redis** with `condition: service_healthy`
- `redis-commander` waits for **Redis** health
- `nginx` also waits for **RabbitMQ** health before exposing the admin surfaces

This reduces startup races where the lister, indexer, or admin tools could come up before the queue or cache was actually ready.

## Deployment with Docker Compose

### 1. Choose the host library path

The stack mounts the library through the `document-data` volume. The host path is controlled by:

- `BOOKS_PATH`

If `BOOKS_PATH` is not set, Docker Compose falls back to:

- `/data/booklibrary`

Example:

```bash
export BOOKS_PATH=/absolute/path/to/your/booklibrary
```

### 2. Run the installer (v0.11.0+)

Before starting the stack, bootstrap the runtime configuration and auth storage:

```bash
python3 -m installer
# or: python3 installer/setup.py --library-path /absolute/path/to/books \
#       --admin-user admin --admin-password 'change-me' --origin http://localhost
```

The installer writes `.env`, creates the host auth directory used by Docker Compose, generates the JWT secret, and seeds the initial admin account. Re-run it whenever you need to rotate credentials or rebuild auth storage.

### 3. Start the stack

```bash
docker compose up -d
```

This starts the full stack, including SolrCloud, Redis, RabbitMQ, the indexing services, the search API, and the UI. In the default local workflow, Docker Compose also auto-loads `docker-compose.override.yml`, which republishes debug ports for direct host access.

For a production-style run with only the nginx gateway exposed on the host, use:

```bash
docker compose -f docker-compose.yml up -d
```

### 4. Watch initial bootstrap

The `solr-init` container waits for all three Solr nodes, uploads the `books` configset, creates the `books` collection if needed, and applies the config overlay.

Useful checks:

```bash
docker compose ps
docker compose logs -f solr-init
```

### 5. Open the service endpoints

Common local URLs:

| Surface | URL | Access |
|---|---|---|
| Main UI | `http://localhost/` | Protected — redirects to `/login` until authenticated |
| Login page | `http://localhost/login` | Public |
| Search API | `http://localhost/v1/search/` | Protected |
| Status API | `http://localhost/v1/status/` | Protected |
| Stats API | `http://localhost/v1/stats/` | Protected |
| Solr admin | `http://localhost/admin/solr/` | Protected |
| RabbitMQ management | `http://localhost/admin/rabbitmq/` | Protected |
| Streamlit admin | `http://localhost/admin/streamlit/` | Protected |
| Redis Commander | `http://localhost/admin/redis/` | Protected |

Health, info, version, and auth bootstrap endpoints remain available for operational checks and login flows. Direct host ports (`8080`, `8983`-`8985`, `15672`, `6379`, `2181`-`2183`, `18080`, `8501`, `8081`, `8085`) are available only when the local `docker-compose.override.yml` file is loaded.

## Configuration

### Host-mounted volume

`docker-compose.yml` defines the document library volume like this:

- volume name: `document-data`
- container path: `/data/documents`
- host path: `${BOOKS_PATH:-/data/booklibrary}`

That means every service using `/data/documents` is reading from the same mounted library root.

### Key environment variables by service

#### `document-lister`

| Variable | Value in Compose | Purpose |
|---|---|---|
| `RABBITMQ_HOST` | `rabbitmq` | RabbitMQ hostname |
| `REDIS_HOST` | `redis` | Redis hostname |
| `QUEUE_NAME` | `shortembeddings` | Queue/routing key for discovered documents |
| `BASE_PATH` | `/data/documents/` | Directory scanned inside the container |
| `DOCUMENT_WILDCARD` | `*.pdf` | File pattern to scan |
| `POLL_INTERVAL` | `60` | Seconds between scans |

#### `document-indexer`

| Variable | Value in Compose | Purpose |
|---|---|---|
| `RABBITMQ_HOST` | `rabbitmq` | RabbitMQ hostname |
| `REDIS_HOST` | `redis` | Redis hostname |
| `QUEUE_NAME` | `shortembeddings` | Queue consumed by the indexer |
| `BASE_PATH` | `/data/documents/` | Root path for source documents |
| `SOLR_HOST` | `solr` | Primary Solr hostname |
| `SOLR_PORT` | `8983` | Primary Solr port |
| `SOLR_COLLECTION` | `books` | Target collection |
| `EMBEDDINGS_HOST` | `embeddings-server` | Embeddings service hostname |
| `EMBEDDINGS_PORT` | `8085` | Embeddings service port |

#### `solr-search`

| Variable | Value in Compose | Purpose |
|---|---|---|
| `PORT` | `8080` | API listen port |
| `SOLR_URL` | `http://solr:8983/solr` | Base Solr URL |
| `SOLR_COLLECTION` | `books` | Collection used for search |
| `BASE_PATH` | `/data/documents` | Base path for document downloads |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed dev origin |
| `EMBEDDINGS_URL` | `http://embeddings-server:8001/v1/embeddings/` | Embeddings endpoint |
| `EMBEDDINGS_TIMEOUT` | `120` | Max wait for query embeddings before semantic/hybrid degrade to keyword |
| `DEFAULT_SEARCH_MODE` | `keyword` | Default API search mode |
| `RRF_K` | `60` | Reciprocal-rank fusion damping constant for hybrid ranking |
| `KNN_FIELD` | `book_embedding` | Dense-vector field used by the semantic/hybrid kNN leg |
| `UPLOAD_MAX_SIZE_MB` | `50` | Maximum upload file size (v0.6.0+) |
| `UPLOAD_RATE_LIMIT` | `10` | Uploads per minute per IP (v0.6.0+) |
| `UPLOAD_STAGING_DIR` | `/data/uploads/` | Temporary upload staging area (v0.6.0+) |
| `EXPOSE_CONTAINER_STATS` | `false` | Enable `/v1/admin/containers` endpoint (v0.7.0+) |
| `AUTH_DB_PATH` | `/data/auth/users.db` | SQLite auth database path inside the container (v0.11.0+) |
| `AUTH_JWT_SECRET` | installer-generated | JWT signing secret required at startup (v0.11.0+) |
| `AUTH_JWT_TTL` | `24h` | Session lifetime for issued JWTs (v0.11.0+) |
| `AUTH_COOKIE_NAME` | `aithena_auth` | Cookie name used for browser auth (v0.11.0+) |

#### `streamlit-admin`

| Variable | Value in Compose | Purpose |
|---|---|---|
| `REDIS_HOST` | `redis` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `QUEUE_NAME` | `shortembeddings` | Queue name used by the stack |
| `RABBITMQ_HOST` | `rabbitmq` | RabbitMQ hostname |
| `RABBITMQ_MGMT_PORT` | `15672` | RabbitMQ management port |
| `RABBITMQ_MGMT_PATH_PREFIX` | `/admin/rabbitmq` | Reverse-proxy path prefix |

#### Infrastructure services

- `rabbitmq` sets `RABBITMQ_SERVER_ADDITIONAL_ERL_ARGS=-rabbit consumer_timeout 3600000000`
- `embeddings-server` sets `PORT=8085`
- Solr nodes set `SOLR_MODULES=extraction,langid` and `ZK_HOST=zoo1:2181,zoo2:2181,zoo3:2181`
- ZooKeeper nodes set `ZOO_4LW_COMMANDS_WHITELIST`, `ZOO_MY_ID`, and `ZOO_SERVERS`

### RabbitMQ startup hardening (v0.5.0)

The Compose definition now pins RabbitMQ to:

- `rabbitmq:3.13-management`

It also adds a more realistic health check:

- command: `rabbitmqctl ping`
- `interval: 10s`
- `timeout: 30s`
- `retries: 12`
- `start_period: 30s`

Additional runtime settings now include:

- `RABBITMQ_VM_MEMORY_HIGH_WATERMARK=0.6`
- `RABBITMQ_SERVER_ADDITIONAL_ERL_ARGS=-rabbit consumer_timeout 3600000000`

Operationally, this means RabbitMQ is given time to finish booting before Compose marks it unhealthy, and dependent services can safely rely on `service_healthy` ordering.

### Search mode and hybrid tuning

`solr-search` supports three request modes:

- `keyword` — BM25 / edismax only
- `semantic` — embeddings + Solr kNN only
- `hybrid` — BM25 plus kNN, merged with Reciprocal Rank Fusion (RRF)

Operators can tune the search path with these controls:

- `DEFAULT_SEARCH_MODE` sets the API default when clients do not pass a `mode` query parameter.
- Clients can switch modes per request with `GET /v1/search?mode=keyword|semantic|hybrid`.
- `RRF_K` controls how aggressively hybrid mode favors top-ranked documents from each leg.
- `KNN_FIELD` selects the Solr dense-vector field used by semantic and hybrid search.
- `EMBEDDINGS_TIMEOUT` controls how long semantic/hybrid requests wait before falling back to keyword results.

Hybrid currently uses equal contribution from the BM25 and semantic legs through standard RRF. There are no separate per-leg weight environment variables today.

### Language detection (v0.5.0)

Language metadata now comes from two coordinated sources:

1. **Solr langid** writes content-based detection into `language_detected_s`.
2. **document-indexer** inspects folder names and writes recognized ISO 639-1 language folders into `language_s`.

Examples of recognized top-level folders include `ca`, `es`, `fr`, `en`, and `la`.

Why this matters:

- prior to the fix, Solr's langid processor was aligned to the wrong field name,
- folder-based language hints were not being captured at all,
- the search API now reads language values with a `language_detected_s` first / `language_s` fallback for filters and normalized results.

This improves language facets and search filters for libraries organized as `<language>/<category>/<author>/file.pdf`.

## Deployment Updates for v0.6.0 (PDF Upload, Security Scanning, Docker Hardening)

### Docker Health Checks

v0.6.0 adds health checks to all services in `docker-compose.yml`. Services now verify they are:

1. Running
2. Ready to accept connections
3. Responsive to queries

**Example (Redis):**
```yaml
redis:
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 5s
    timeout: 15s
    retries: 1
  restart: unless-stopped
```

**Key changes:**

- Services that depend on others now use `condition: service_healthy` instead of just `service_started`
- This prevents race conditions where the indexer or admin tools come up before their dependencies are actually ready

### Resource Limits and Restart Policies

v0.6.0 enforces memory and CPU limits on all services to prevent resource exhaustion:

| Service | Memory Limit | Restart Policy |
|---------|--------------|-----------------|
| Redis | 512 MB | `unless-stopped` |
| RabbitMQ | 2 GB | `unless-stopped` |
| Solr nodes | 2 GB each | `unless-stopped` |
| Embeddings Server | 2 GB | `unless-stopped` |
| Solr Search API | 512 MB | `unless-stopped` |
| Document Indexer | 512 MB | `on-failure` |
| Document Lister | 512 MB | `on-failure` |

**Restart policies explained:**

- `restart: unless-stopped` — automatically restart unless explicitly stopped by user
- `restart: on-failure` — only restart if the container exits with a non-zero code
- `stop_grace_period` — allows graceful shutdown before forced termination

### Security Scanning

v0.6.0 adds continuous security scanning to the CI/CD pipeline:

- **Bandit** scans Python code for security vulnerabilities
- **Checkov** scans Infrastructure-as-Code (Docker Compose, deployment files)
- **Zizmor** scans GitHub Actions workflows for security issues

All scans run on every push to any branch. Results are available in GitHub Actions workflow logs.

**To review findings:**

```bash
# Check the latest Bandit scan
gh run view --log bandit 2>/dev/null | grep -A 20 "security"

# Check Checkov results for docker-compose
gh run view --log checkov 2>/dev/null | grep -i "docker-compose"
```

See `docs/security/baseline-v0.6.0.md` for the complete security findings triage (287 items catalogued).

## Deployment Updates for v0.7.0 (Versioning, Admin Observability, Release Automation)

### Semantic Versioning Infrastructure

v0.7.0 adds version tracking across all services:

- **VERSION file** in project root is the single source of truth
- Each service reads version from git tags (development) or container image labels (production)
- `docker-compose.yml` includes version in Dockerfile labels

**To check the current version:**

```bash
cat VERSION
echo "Current tag: v$(cat VERSION)"
```

**To verify all services report the same version:**

```bash
# Version endpoint on solr-search
curl -s http://localhost:8080/version | jq '.version'

# In Streamlit admin dashboard
# Navigate to System Status > Versions tab
```

### Version Endpoints (GET /version)

v0.7.0 adds `/version` endpoints to all services. Use these for monitoring and health checks:

```bash
# Get version info from solr-search
curl -s http://localhost:8080/version | jq '.'
```

**Response format:**
```json
{
  "service": "solr-search",
  "version": "0.7.0",
  "build_time": "2026-03-15T14:30:00Z",
  "git_commit": "a1b2c3d4",
  "git_branch": "main",
  "python_version": "3.11.7"
}
```

### Container Stats Endpoint (GET /v1/admin/containers)

v0.7.0 adds an endpoint for querying Docker container metadata without needing direct Docker socket access:

```bash
# Get container stats (requires EXPOSE_CONTAINER_STATS=true)
curl -s http://localhost:8080/v1/admin/containers | jq '.containers[] | "\(.name) - \(.state) (\(.cpu_percent)% CPU, \(.memory_mb)MB)"'
```

**Security note:** This endpoint is **disabled by default**. To enable it, set the environment variable:

```bash
export EXPOSE_CONTAINER_STATS=true
docker-compose up
```

### System Status Admin Page

v0.7.0 adds a new **System Status** page in the admin dashboard (Streamlit app):

**Navigation:**

1. Open the **Admin** tab in Aithena
2. Navigate to **System Status** (if not visible, ensure v0.7.0 is deployed)
3. Tabs available:
   - **Versions** — version matrix and update history for all services
   - **Health** — health check statuses and history
   - **Resources** — CPU and memory usage graphs
   - **Logs** — recent system events and state changes

![System status page](screenshots/status-page.png)

**Auto-refresh behavior:**

- Polls `/version` and `/admin/containers` every 30 seconds
- Changes highlighted in green (improvement) or red (degradation)
- Can be paused for detailed inspection

**To troubleshoot the System Status page:**

```bash
# Verify version endpoints are responsive
curl -s http://localhost:8080/version | jq '.version'

# Verify container stats endpoint is responsive (if enabled)
export EXPOSE_CONTAINER_STATS=true
curl -s http://localhost:8080/v1/admin/containers | jq '.containers | length'
```

### Version Display in User Interface

v0.7.0 adds version display in the footer of the web app:

- Shows **Aithena v0.7.0** (or current version) in bottom-right corner
- Hover tooltip reveals full version metadata (commit hash, build time)
- Gracefully displays "unknown" if version endpoint is unavailable

### Monitoring Version Consistency

Use the System Status page to detect version skew (services at different versions):

**Workflow:**

1. After a deploy, open the **Versions** tab in System Status
2. Confirm all services are at v0.7.0 (or your target version)
3. If any service is at an older version, wait for it to restart or check deployment logs
4. Set up a monitoring alert: alert if any service version differs from the others

**Manual check:**

```bash
for service in solr-search document-indexer document-lister embeddings-server; do
  echo -n "$service: "
  # Requires knowledge of each service's version endpoint and port
done
```

### Release Automation

v0.7.0 includes a CI/CD workflow (`.github/workflows/release.yml`) that automates versioned releases:

**Trigger:** Merge to `main` branch (or manual trigger)

**What it does:**

1. Determines new version using conventional commits
2. Updates `VERSION` file
3. Updates `CHANGELOG.md` from commit messages
4. Creates git tag (e.g., `v0.7.0`)
5. Builds and tags container images (`:v0.7.0`, `:latest`)
6. Creates GitHub Release with changelog

**Supported pre-release tags:**

- `v0.7.0-rc1` (release candidate)
- `v0.7.0-beta` (beta)
- `v0.7.0-alpha` (alpha)

**To test locally:**

```bash
# Check if release workflow would trigger
git log --oneline -5 | head -3

# Check current version
cat VERSION
```

## Deployment Updates for v0.12.0 (Metrics, Credential Rotation, Resilience)

### `/v1/metrics` and monitoring setup

`solr-search` now exposes Prometheus-compatible metrics at `/v1/metrics`. Because the public nginx surface protects `/v1/*`, operators should normally scrape the internal service target (`solr-search:8080`) or another private/authenticated path rather than relying on the public URL.

Current metrics cover:

- request volume by search mode (`keyword`, `semantic`, `hybrid`)
- search latency histograms
- indexing queue depth and failure counters
- embeddings availability
- Solr live-node count

For a ready-to-use scrape example and starter alert thresholds, see the dedicated [Monitoring guide](monitoring.md).

### Credential rotation procedure

The v0.12.0 deployment path assumes operator-managed credential rotation for the auth bootstrap user, JWT secret, RabbitMQ credentials, and Redis password.

Preferred workflow:

1. Re-run the installer:
   ```bash
   python3 -m installer
   python3 -m installer --reset  # when you need to rebuild auth storage and rotate generated secrets
   ```
2. If you manage service credentials manually, update `.env` with strong replacements for `RABBITMQ_USER`, `RABBITMQ_PASS`, and `REDIS_PASSWORD`.
3. Recreate every dependent service so clients reconnect with the new credentials:
   ```bash
   docker compose up -d --force-recreate redis rabbitmq redis-commander streamlit-admin document-lister document-indexer solr-search nginx
   ```

The full production procedure and recovery notes are documented in the [Production deployment guide](deployment/production.md).

### Degraded-mode semantic search behavior

When Solr is healthy but the embeddings service is unavailable, semantic and hybrid requests no longer fail closed. Instead, `solr-search` automatically reruns the request in keyword mode and returns a normal search payload with extra metadata describing the degradation:

- `degraded: true`
- `message: "Embeddings unavailable — showing keyword results"`
- `requested_mode: "semantic"` or `"hybrid"`
- `mode: "keyword"` to show the effective execution path

Operationally, this keeps the UI and API available during embeddings outages. It does **not** replace Solr failover; if Solr is down, all search modes still fail.

### Failover runbook and drill reference

v0.12.0 adds an operator runbook for outage handling across Solr, Redis, RabbitMQ, embeddings-server, and nginx.

Use these artifacts together:

- [Failover & Recovery Runbook](deployment/failover-runbook.md)
- `e2e/failover-drill.sh` for rehearsal in a Docker-capable environment

The runbook also calls out an important limitation in the current Compose deployment: the application tier still targets the primary `solr` service directly, so losing that node is a user-visible outage even when replica nodes remain healthy.

### Sizing guide and benchmark reference

Capacity planning for v0.12.0 is documented in the [Search and Indexing Sizing Guide](deployment/sizing-guide.md). It includes:

- analytical sizing formulas for chunk counts, vector footprint, and Solr memory/disk planning
- deployment profiles for small, medium, and large libraries
- Redis, RabbitMQ, embeddings-server, and document-indexer sizing guidance
- `e2e/benchmark.sh` for replacing the analytical baseline with measured results on your own hardware

Treat the published numbers as planning guidance until you have benchmark data from representative production hardware.

## Monitoring

### Use the Status tab

The UI **Status** tab is the fastest operator-friendly health check.

![System status page](screenshots/status-page.png)

It shows:

- indexing counts from Redis-backed document tracking
- Solr cluster status, live node count, and indexed document count
- up/down reachability for Solr, Redis, and RabbitMQ
- automatic refresh every 10 seconds

Important: this dashboard is focused on the search and ingestion path. It does **not** report health for every container in the stack.

![Collection statistics](screenshots/stats-page.png)

### Use the API directly

#### Status endpoint

```bash
curl http://localhost/v1/status/
```

This endpoint aggregates:

- Solr `CLUSTERSTATUS`
- Redis `doc:*` state counts
- TCP reachability checks for Solr, Redis, and RabbitMQ
- embeddings service availability via the embeddings `/version` probe

The response now includes:

- `embeddings_available` — boolean summary for semantic-search readiness
- `services.embeddings` — `up` or `down`

#### Stats endpoint

```bash
curl http://localhost/v1/stats/
```

This endpoint returns:

- total indexed books
- page-count totals and min/avg/max
- facet-style breakdowns by language, author, year, and category

### Compose health checks

Docker Compose defines explicit health checks for:

- `redis` using `redis-cli ping`
- `rabbitmq` using `rabbitmqctl ping`
- `zoo1`, `zoo2`, `zoo3` using `ruok` and `mntr`
- `solr`, `solr2`, `solr3` using `curl http://localhost:8983/solr/admin/info/system`

Useful commands:

```bash
docker compose ps
docker compose logs --tail=100 solr
docker compose logs --tail=100 document-indexer
docker compose logs --tail=100 document-lister
```

## Full reindex procedure after the language fix

Run a full reindex after deploying the v0.5.0 language detection changes so existing books are rebuilt with the corrected language fields.

### Why the reindex is necessary

Older documents may have been indexed before:

- Solr's detected-language field was aligned to `language_detected_s`, and
- folder-derived language hints were written into `language_s`.

Without a reindex, language filters and language-facing reports can mix old and new metadata.

### Recommended operator workflow

1. Confirm the stack is healthy:
   ```bash
   docker compose ps
   ```
2. Open the embedded admin dashboard at **Admin** in the UI or directly at `http://localhost/admin/streamlit/`.
3. In **Document Manager → Processed**, click **🗑️ Clear All** and confirm. This removes the Redis processed-state entries so the lister will rediscover the files.
4. In **Document Manager → Failed**, click **🔄 Requeue All** if any failed documents are present.
5. Wait for the next lister scan (default: **60 seconds**) or restart the lister/indexer services if you need the cycle to begin immediately.
6. Watch progress from:
   - the **Status** tab,
   - the **Admin** dashboard counters,
   - `docker compose logs --tail=100 document-lister document-indexer`
7. Verify the rebuilt collection through the API:
   ```bash
   curl http://localhost/v1/stats/
   curl "http://localhost/v1/search/?q=historia&fq_language=ca"
   ```

### Why this is safe

The indexer uses deterministic document IDs derived from the file path, and chunk IDs are derived from that same parent ID plus the chunk index. Reindexing therefore refreshes the existing documents in place instead of creating duplicates for unchanged files.

## Troubleshooting common issues

### Solr not responding

Symptoms:

- search returns errors
- Status tab shows Solr down or degraded
- Solr admin UI does not open

Checks:

```bash
docker compose ps solr solr2 solr3 solr-init zoo1 zoo2 zoo3
docker compose logs --tail=100 zoo1
docker compose logs --tail=100 solr
docker compose logs --tail=100 solr-init
docker compose exec solr curl -f http://localhost:8983/solr/admin/info/system
```

What to look for:

- ZooKeeper nodes must be healthy before Solr finishes booting.
- `solr-init` must complete so the `books` configset and collection exist.
- A degraded Status tab usually means fewer than 3 live Solr nodes were detected.

### Redis connection problems

Symptoms:

- Status tab shows Redis down
- indexing counts stay at zero or stop changing
- document-lister or document-indexer logs show connection failures

Checks:

```bash
docker compose ps redis
docker compose logs --tail=100 redis
docker compose logs --tail=100 document-lister
docker compose logs --tail=100 document-indexer
docker exec -it $(docker compose ps -q redis) redis-cli ping
```

What to look for:

- Redis must be reachable on port `6379`.
- The search API relies on Redis for the indexing counters shown in `/v1/status/`.
- The lister and indexer both expect the hostname `redis` inside the Compose network.

### RabbitMQ problems

Symptoms:

- new books are discovered but never indexed
- queue consumers stall
- Status tab shows RabbitMQ down

Checks:

```bash
docker compose ps rabbitmq
docker compose logs --tail=100 rabbitmq
docker compose logs --tail=100 document-lister
docker compose logs --tail=100 document-indexer
```

Also inspect the management UI at `http://localhost/admin/rabbitmq/` (or `http://localhost:15672/` when the dev override is loaded).

What to look for:

- The queue name in this stack is `shortembeddings`.
- `document-lister` publishes with that routing key.
- `document-indexer` must consume the same queue name.

### New books do not appear in search

Checks:

- confirm `BOOKS_PATH` points to the correct host directory
- confirm the files are actually present in that directory
- confirm the files end in `.pdf`
- remember that the lister scans every `60` seconds by default
- inspect `document-lister` logs for repeated scans and enqueue activity

### PDFs open from search, then fail to load

Checks:

- confirm the file still exists under the mounted library path
- confirm the file is still inside the configured `BASE_PATH`
- confirm the document really is a PDF

The `/v1/documents/{document_id}` endpoint only serves files that resolve inside the configured base path and end in `.pdf`.

## Service health checks and what they mean

### What the Status tab means

- **Solr up/down**: whether the API can open a TCP connection to the configured Solr host and port
- **Redis up/down**: whether the API can open a TCP connection to Redis
- **RabbitMQ up/down**: whether the API can open a TCP connection to RabbitMQ
- **Solr status = ok**: 3 live Solr nodes were detected
- **Solr status = degraded**: Solr answered, but fewer than 3 live nodes were detected
- **Solr status = error**: Solr cluster status could not be read or no live nodes were found

### Semantic and hybrid degraded mode

If Solr is healthy but the embeddings service is unavailable, `mode=semantic` and `mode=hybrid` requests no longer fail with `5xx`. Instead, `solr-search` automatically reruns the request as a keyword search and returns normal results with extra metadata:

- `degraded: true`
- `message: "Embeddings unavailable — showing keyword results"`
- `requested_mode: "semantic"` or `"hybrid"`
- `mode: "keyword"` to show the effective execution path

This degraded path keeps the search UI and API usable during embeddings outages. If Solr itself is unavailable, the request still fails because there is no keyword fallback source.

### What Compose health means

Compose health checks are container-specific and stricter than the UI's simple up/down indicators. A service can be TCP reachable and still be unhealthy by its own container health test.

Use both views together:

- **Status tab / `/v1/status/`** for operator-friendly application health
- **`docker compose ps` + container logs** for root-cause diagnosis

## Adding new books to the library

### Supported formats

The document-lister scans with `*.pdf` and explicitly skips files that are not PDFs. For this stack, **PDF is the supported ingestion format**.

### Where to put files

Copy new PDFs into the host directory bound to `BOOKS_PATH` (or `/data/booklibrary` if you are using the default). Inside containers, that same content is visible at:

- `/data/documents/`

### How discovery works

- `document-lister` recursively scans the mounted library with `rglob()`
- scan interval is controlled by `POLL_INTERVAL`
- default interval is `60` seconds
- new or modified PDFs are published to RabbitMQ for indexing

### Metadata-friendly path patterns

The metadata extraction logic is path-aware. These patterns are covered by tests and are good choices for new files:

- `Author/Title.pdf`
- `Author - Title (Year).pdf`
- `Category/Author/Title.pdf`
- `Category/Author - Title (Year).pdf`

If a file does not match a known pattern, the indexer falls back conservatively:

- title from the filename stem
- author set to `Unknown`
- top-level category only when the path structure supports it

## Operational checklist

Before calling a deployment healthy, confirm:

- `docker compose ps` shows core services running
- `solr-init` completed successfully
- the installer has written `.env` and the `AUTH_DB_DIR` host path exists
- `http://localhost/login` loads and accepts the installer-seeded admin credentials
- `http://localhost/v1/status/` returns JSON after authentication
- `http://localhost/v1/stats/` returns JSON after authentication
- the main UI at `http://localhost/` loads Search, Status, and Stats after login
- a known PDF can be searched and opened from results
- `/admin/streamlit/`, `/admin/solr/`, and `/admin/rabbitmq/` redirect or deny access when unauthenticated

## Deployment Updates for v1.3.0 (Structured Logging, Admin Auth, Observability)

### Structured JSON logging

v1.3.0 introduces structured JSON logging across all Python services. This improves log machine-parseability and enables automated analysis tools.

**Configuration:**

All services respect the `LOG_LEVEL` environment variable (default: `INFO`). Valid levels are:
- `DEBUG` — detailed diagnostic information
- `INFO` — general operational events (default)
- `WARNING` — potential issues worth investigating
- `ERROR` — service errors and failures

**Set log level for all services:**

```bash
export LOG_LEVEL=DEBUG  # or INFO, WARNING, ERROR
docker compose up -d
```

**Example JSON log entry:**

```json
{
  "timestamp": "2026-03-17T14:30:45.123Z",
  "level": "INFO",
  "service": "solr-search",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Search query processed",
  "query": "machine learning",
  "mode": "hybrid",
  "duration_ms": 125
}
```

**Parsing JSON logs with jq:**

```bash
# Show all INFO-level logs for a service
docker compose logs document-indexer | jq 'select(.level=="INFO")'

# Find all errors for a correlation ID
docker compose logs | jq 'select(.correlation_id=="550e8400-e29b-41d4-a716-446655440000")'

# Extract just the message field
docker compose logs | jq '.message'
```

For comprehensive guidance, see `docs/observability-runbook.md`.

### Admin dashboard authentication

v1.3.0 requires authentication for the embedded Streamlit admin dashboard. Users must log in before accessing the dashboard.

**Admin access behavior:**

- Users accessing `/admin/streamlit/` while not authenticated are redirected to `/login`
- After successful login, users can access the admin dashboard via the **Admin** tab in the UI
- Sessions expire after 24 hours (configurable via `AUTH_JWT_TTL`)
- Logging out clears the browser session

![Admin dashboard](screenshots/admin-dashboard.png)

**Environment variables:**

| Variable | Purpose |
|---|---|
| `AUTH_JWT_SECRET` | JWT signing secret (generated by installer) |
| `AUTH_JWT_TTL` | Session timeout, default `24h` |
| `AUTH_COOKIE_NAME` | Browser cookie name, default `aithena_auth` |

Re-run the installer to set admin credentials:

```bash
python3 -m installer --reset
```

### Circuit breaker for Redis and Solr

v1.3.0 implements circuit breaker pattern to gracefully degrade when Redis or Solr are unavailable.

**Circuit breaker behavior:**

| Service | Failure | Fallback | Result |
|---------|---------|----------|--------|
| **Redis** | Connection timeout or unavailable | Skip caching; continue search | Slightly slower search, no crash |
| **Solr** | Connection timeout or unavailable | Return error message | Search fails, but API doesn't crash |

**Configuration:**

Circuit breaker thresholds are hardcoded in the services:
- **Redis timeout:** 2 seconds
- **Solr timeout:** 10 seconds
- **Circuit state:** open / half-open / closed

**Health check behavior:**

If Redis or Solr is unavailable, the `/v1/status/` endpoint shows the degraded state with details:

```bash
curl http://localhost/v1/status/
```

Returns:

```json
{
  "redis": {
    "status": "degraded",
    "message": "Redis circuit breaker open (timeout exceeded)"
  },
  "solr": {
    "status": "up",
    "live_nodes": 3,
    "indexed_documents": 12345
  }
}
```

### Correlation ID tracking

v1.3.0 adds correlation IDs for end-to-end request tracing across all service boundaries.

**Correlation ID flow:**

1. FastAPI middleware generates a UUID v4 for each incoming request
2. Correlation ID added to all log entries for that request
3. Correlation ID propagated in RabbitMQ message headers (document-lister → document-indexer)
4. Correlation ID returned in HTTP response headers (`X-Correlation-ID`)

**Example tracing workflow:**

1. User makes a search request; correlation ID is `550e8400-e29b-41d4-a716-446655440000`
2. `solr-search` logs the search with that correlation ID
3. If embeddings are needed, the request to `embeddings-server` includes the correlation ID
4. All logs carry this correlation ID for that transaction

**Using correlation IDs for debugging:**

```bash
# Get the correlation ID from the response header
curl -i http://localhost/v1/search/?q=test 2>&1 | grep "X-Correlation-ID"

# Find all logs related to that request
CORR_ID="550e8400-e29b-41d4-a716-446655440000"
docker compose logs | jq --arg id "$CORR_ID" 'select(.correlation_id==$id)'
```

See `docs/observability-runbook.md` for comprehensive examples and debugging strategies.

### Observability runbook

v1.3.0 includes comprehensive documentation for log analysis and debugging:

- **Log analysis** — how to query JSON logs, filter by level, service, correlation ID
- **Request tracing** — how to follow a request through all services
- **Debugging workflows** — common issues and diagnostic procedures
- **Examples** — practical jq commands and log queries

Reference: `docs/observability-runbook.md`

### URL-based search state

v1.3.0 enables users to bookmark and share search state via URL query parameters.

**URL structure:**

```
http://localhost/?q=keyword&filters=year:2020,language:en&sort=relevance&page=2
```

Parameters:
- `q` — search query
- `filters` — comma-separated facet filters (e.g., `year:2020,language:en`)
- `sort` — sort order (relevance, year, title, author)
- `page` — result page number (starts at 1)
- `per_page` — results per page (10, 20, or 50)

**User experience:**

- Users can copy the URL to share a filtered view
- Browser back/forward buttons navigate search history
- Bookmarked URLs restore exact search state
- No need to manually re-apply filters

This is backward-compatible; old search URLs without parameters still work (but do not preserve filter state).

---

## Deployment Updates for v1.5.0 (Production Deployment & Infrastructure)

v1.5.0 is the production deployment release, establishing complete infrastructure for deploying Aithena in production environments. This section covers production-specific deployment procedures, pre-built Docker images, install script automation, and data persistence validation.

### Pre-built Docker images on GHCR

v1.5.0 publishes production-ready Docker images to GitHub Container Registry (GHCR), enabling deployments without source code.

**Image naming and versioning:**

All images follow semantic versioning tags:
- `ghcr.io/jmservera/aithena-{service}:v1.5.0` — Latest production release
- `ghcr.io/jmservera/aithena-{service}:latest` — Most recent build
- `ghcr.io/jmservera/aithena-{service}:v1.5.0-{short-sha}` — Exact commit

Services published to GHCR:
- `aithena-ui` — React frontend with nginx
- `solr-search` — FastAPI search API
- `embeddings-server` — Embedding service
- `document-indexer` — PDF indexing consumer
- `document-lister` — Library scanner
- `admin` — Streamlit admin dashboard
- `nginx` — Reverse proxy

**OCI image labels:**

All images include OCI metadata:
```
org.opencontainers.image.version=1.5.0
org.opencontainers.image.revision=a1b2c3d4...
org.opencontainers.image.created=2026-03-17T...
org.opencontainers.image.source=https://github.com/jmservera/aithena
```

**Verifying image provenance:**

```bash
# Inspect image labels
docker inspect ghcr.io/jmservera/aithena-solr-search:v1.5.0 | jq '.[].Config.Labels'

# Expected output:
# {
#   "org.opencontainers.image.version": "1.5.0",
#   "org.opencontainers.image.revision": "a1b2c3d4...",
#   ...
# }
```

### GHCR authentication

Private image repositories require authentication to pull images.

**Authenticating with GitHub Personal Access Token (PAT):**

1. Create a GitHub PAT with `read:packages` scope: https://github.com/settings/tokens
2. Authenticate Docker with GHCR:
   ```bash
   echo "$GITHUB_TOKEN" | docker login ghcr.io -u {username} --password-stdin
   ```
3. Docker Compose automatically uses your credentials when pulling images

**For automated deployments (CI/CD, Kubernetes):**

Create a `ghcr-auth.json` file:

```json
{
  "auths": {
    "ghcr.io": {
      "auth": "BASE64(username:token)"
    }
  }
}
```

Then reference it in Docker Compose:

```bash
docker compose --config=ghcr-auth.json up -d
```

**Troubleshooting authentication:**

```bash
# Test connection to GHCR
docker pull ghcr.io/jmservera/aithena-solr-search:v1.5.0

# If authentication fails:
# Error response from daemon: unauthorized
# → Check PAT has read:packages scope
# → Verify credentials: docker logout ghcr.io && docker login ghcr.io
```

### Production docker-compose.yml

v1.5.0 provides a production-ready `docker-compose.yml` that uses pre-built GHCR images instead of building from source.

**Key differences from development:**

| Feature | Dev | Production |
|---------|-----|-----------|
| Image source | Local build | GHCR pre-built |
| Override file | docker-compose.override.yml | None |
| Debug ports | Published (5173, 8080, 8085, 8501) | Not published |
| Health checks | Simple, permissive | Strict, production timeouts |
| Volume mounts | Simple paths | Validated, backed up |
| Logging | Human-readable | JSON structured |

**Starting production stack:**

```bash
# Authenticate with GHCR
echo "$GITHUB_TOKEN" | docker login ghcr.io -u {username} --password-stdin

# Start stack (no override file)
docker compose -f docker-compose.yml up -d

# Verify services
docker compose ps
```

**Production environment:**

Set environment variables in `.env` or via `docker-compose.yml`:

```bash
# .env
VERSION=1.5.0
BOOKS_PATH=/data/library
ADMIN_USER=admin
ADMIN_PASSWORD=secure-password
LOG_LEVEL=INFO
AUTH_JWT_TTL=24h
ORIGIN=https://aithena.example.com
```

### Production install script

v1.5.0 includes an automated install script that configures the production environment, generates secrets, and sets up persistent storage.

**Basic installation:**

```bash
python3 installer/setup.py \
  --library-path /absolute/path/to/books \
  --admin-user admin \
  --admin-password 'secure-password' \
  --origin https://aithena.example.com
```

**Installation steps:**

1. Validates paths and creates directories if needed
2. Generates `.env` with all required variables
3. Creates JWT secret in `AUTH_DB_DIR`
4. Seeds admin user credentials
5. Configures persistent volume mounts
6. Sets up logging configuration

**Script options:**

```
--library-path PATH      Absolute path to book library (required)
--admin-user NAME        Initial admin username (default: admin)
--admin-password PASS    Initial admin password (required)
--origin ORIGIN          Public origin URL, e.g., https://aithena.example.com (required)
--log-level LEVEL        Default log level: INFO, DEBUG, WARNING, ERROR (default: INFO)
--auth-ttl TTL           JWT session timeout, e.g., 24h, 7d (default: 24h)
--reset                  Reset all credentials and auth storage
--dry-run                Show changes without writing files
```

**Re-running the script:**

Re-run anytime to update credentials, change log level, or reset authentication:

```bash
# Update admin password
python3 installer/setup.py --reset --admin-password 'new-password'

# Change log level for all services
python3 installer/setup.py --log-level DEBUG

# Verify configuration without making changes
python3 installer/setup.py --dry-run
```

### Production environment configuration

v1.5.0 standardizes environment variable configuration for production deployments.

**Required environment variables:**

| Variable | Purpose | Example |
|---|---|---|
| `BOOKS_PATH` | Host path to book library | `/mnt/storage/books` |
| `ORIGIN` | Public origin URL | `https://aithena.example.com` |
| `LOG_LEVEL` | Default log level | `INFO` |
| `AUTH_JWT_SECRET` | JWT signing secret (generated) | `{random-secret}` |
| `AUTH_JWT_TTL` | Session timeout | `24h` |

**Optional environment variables:**

| Variable | Purpose | Default |
|---|---|---|
| `AUTH_COOKIE_NAME` | Browser session cookie | `aithena_auth` |
| `REDIS_TIMEOUT` | Redis connection timeout | `2s` |
| `SOLR_TIMEOUT` | Solr connection timeout | `10s` |
| `RABBITMQ_PREFETCH` | Message prefetch count | `10` |

**Secrets management:**

For production deployments, avoid hardcoding secrets in `.env`. Instead, use environment variable references:

```bash
# .env (development)
AUTH_JWT_SECRET=dev-secret-only

# Production .env
AUTH_JWT_SECRET=${JWT_SECRET_FROM_VAULT}
```

Then set the secret before starting:

```bash
export JWT_SECRET_FROM_VAULT=$(aws secretsmanager get-secret-value --secret-id aithena/jwt-secret)
docker compose up -d
```

### Volume mounts and data persistence

v1.5.0 validates that all persistent data survives container restarts.

**Persistent volumes:**

| Volume | Mount Point | Host Path | Purpose |
|--------|-------------|-----------|---------|
| `solr-data` | `/var/solr/data` | `/var/lib/aithena/solr` | Solr indexes |
| `redis-data` | `/data` | `/var/lib/aithena/redis` | Redis snapshots |
| `rabbitmq-data` | `/var/lib/rabbitmq` | `/var/lib/aithena/rabbitmq` | Queue messages |
| `document-data` | `/data/documents` | `${BOOKS_PATH}` | Book library |
| `auth-data` | `/app/auth` | `${AUTH_DB_DIR}` | Auth credentials |

**Validating volume mounts:**

1. Before starting production stack, verify host paths exist:
   ```bash
   ls -la /var/lib/aithena/solr /var/lib/aithena/redis /var/lib/aithena/rabbitmq
   ```

2. Start the stack:
   ```bash
   docker compose up -d
   ```

3. Run smoke tests to verify data persistence:
   ```bash
   docker compose -f docker-compose.smoke.yml up --abort-on-container-exit
   ```

4. The smoke test suite validates:
   - All volumes mounted correctly
   - Data persists across container restarts
   - Search indexes not lost after restart
   - Redis snapshots restored on restart
   - RabbitMQ queue messages preserved

**Data persistence checklist:**

- [ ] `/var/lib/aithena/solr` owned by UID 8983 (Solr user)
- [ ] `/var/lib/aithena/redis` owned by UID 999 (Redis user)
- [ ] `/var/lib/aithena/rabbitmq` owned by UID 999 (RabbitMQ user)
- [ ] All volumes have at least 50 GB free space for production library
- [ ] Volumes backed up regularly via snapshot (daily recommended)
- [ ] Smoke test suite passes all persistence validation tests

### Deployment health checks

v1.5.0 includes strict health checks for production deployments.

**Service health endpoints:**

| Service | Endpoint | Check | Timeout |
|---------|----------|-------|---------|
| nginx | `/` | HTTP 200 | 10s |
| aithena-ui | `/` | HTTP 200 + React app loads | 15s |
| solr-search | `/v1/health/` | JSON `{"status": "ok"}` | 10s |
| Solr | `/solr/admin/ping` | HTTP 200 | 10s |
| Redis | Redis PING | PONG | 2s |
| RabbitMQ | `/api/healthchecks/node` | HTTP 200 | 10s |
| document-indexer | `/health/` | HTTP 200 | 5s |

**Checking health after deployment:**

```bash
# All services ready?
docker compose ps

# Check each service individually
curl http://localhost:8080/v1/health/
curl http://localhost:8983/solr/admin/ping
curl http://localhost:6379 -c 'PING'  # via redis-cli
docker compose exec rabbitmq curl -s http://localhost:15672/api/healthchecks/node
```

**Production health check procedure:**

1. Start stack: `docker compose -f docker-compose.yml up -d`
2. Wait 30 seconds for Solr init to complete
3. Check all services: `docker compose ps` (all should show `healthy`)
4. Access UI: `https://aithena.example.com/` and log in
5. Run smoke tests: `docker compose -f docker-compose.smoke.yml up --abort-on-container-exit`
6. Verify search works: Execute a known search query
7. Check admin dashboard: Access `/admin/streamlit/` after login

### Rollback procedures

If a deployment fails or requires rollback to a previous version:

**Rollback steps:**

1. Stop current stack:
   ```bash
   docker compose down
   ```

2. Update `docker-compose.yml` or `.env` to previous version:
   ```bash
   # Change image version in docker-compose.yml or .env
   VERSION=1.4.0
   ```

3. Restart stack with previous images:
   ```bash
   docker compose -f docker-compose.yml up -d
   ```

4. Run health checks to verify previous version is operational

5. Monitor logs for any issues:

## Deployment Updates for v1.4.0 (Dependency Upgrades & Infrastructure)

v1.4.0 introduces major infrastructure upgrades: Python 3.12, Node 22 LTS, React 19, ESLint v9, and comprehensive dependency updates. This section covers deployment considerations and breaking changes.

### Python 3.12 upgrade (DEP-4)

**What changed:**

- All backend services (solr-search, document-indexer, document-lister, embeddings-server, admin) now require Python 3.12 or later
- Dockerfiles updated to use `python:3.12-slim` and `python:3.12-alpine`
- All pyproject.toml files updated to `requires-python = ">=3.12"`
- 15-20% performance improvement observed in benchmark tests

**Deployment checklist:**

1. **Verify Python 3.12 availability:**
   ```bash
   python3 --version  # Should show 3.12.x or later
   ```

2. **Rebuild Docker images** with Python 3.12 base:
   ```bash
   ./buildall.sh  # Uses VERSION=1.4.0, builds with Python 3.12 bases
   ```

3. **Reinstall dependencies:**
   ```bash
   cd src/solr-search && uv sync --frozen
   cd src/document-indexer && uv sync --frozen
   cd src/document-lister && uv sync --frozen
   cd src/admin && uv sync --frozen
   cd src/embeddings-server && pip install -r requirements.txt  # pip-managed, not uv
   ```

4. **Test the upgraded services:**
   ```bash
   cd src/solr-search && uv run pytest -v  # Should pass all 193 tests
   cd src/document-indexer && uv run pytest -v  # Should pass all 91+ tests
   ```

5. **Performance verification:**
   - Backend test execution time reduced by ~15% (v1.3.0: 45s → v1.4.0: 38s)
   - No slowdowns observed in production workloads

**Rollback:** If issues occur, revert to v1.3.0 (uses Python 3.11)

### Node 22 LTS upgrade (DEP-5)

**What changed:**

- aithena-ui Dockerfile updated to use `node:22-alpine`
- CI workflows updated to use `actions/setup-node@v4 with node-version: 20`
- Node 22 is LTS with support through 2026
- Vite, React, and all frontend dependencies verified compatible

**Deployment checklist:**

1. **Verify Node 22 LTS availability:**
   ```bash
   node --version  # Should show v22.x.x or later
   ```

2. **Rebuild frontend Docker image:**
   ```bash
   docker compose build aithena-ui
   ```

3. **Reinstall frontend dependencies:**
   ```bash
   cd src/aithena-ui && npm install
   ```

4. **Test the frontend:**
   ```bash
   npm run lint  # All checks pass with ESLint v9
   npm run build  # TypeScript + Vite build succeeds
   npm test  # All 189 tests pass
   ```

5. **Performance verification:**
   - Vite build time reduced from 218ms to 200ms (-8%)
   - Lighthouse score improved from 92 to 94

**Rollback:** If issues occur, revert to v1.3.0 (uses Node 20)

### React 19 migration (DEP-7)

**What changed:**

- React upgraded from v18 to v19
- React DOM upgraded from v18 to v19
- Component types updated to modern patterns (`function MyComponent(): JSX.Element` instead of `React.FC<Props>`)
- Improved Error Boundary behavior and error recovery
- Better TypeScript support and type inference

**Breaking changes:**

- `React.FC` deprecated; use function declaration with `JSX.Element` return type
- Component props type definitions unchanged (still use `interface Props { ... }`)
- All existing components migrated successfully; no functionality changes

**Deployment checklist:**

1. **Verify npm install succeeds:**
   ```bash
   cd src/aithena-ui && npm install  # Should resolve all React 19 dependencies
   ```

2. **No console errors or warnings:**
   ```bash
   npm run build  # Should build without warnings
   ```

3. **All tests pass:**
   ```bash
   npm test  # All 189 Vitest tests pass
   ```

4. **Manual testing:**
   - Open http://localhost:5173 (Vite dev) or http://localhost (production)
   - Verify search, filtering, pagination work correctly
   - Check browser console for any errors (should be clean)

**Rollback:** If issues occur, revert to v1.3.0 (uses React 18)

### ESLint v9 migration (DEP-2)

**What changed:**

- ESLint upgraded from v8 to v9
- Configuration format changed from `.eslintrc.json` to flat config (`eslint.config.js`)
- All rules migrated to flat config format
- All lint checks pass; no new violations introduced

**Breaking changes:**

- `.eslintrc.json` is no longer used and should be removed
- Custom ESLint configurations must be converted to flat config format
- Shareable configs (if used) must be compatible with flat config

**Deployment checklist:**

1. **Verify ESLint v9 configuration:**
   ```bash
   cd src/aithena-ui && npx eslint --config eslint.config.js .
   # Should pass all checks with 0 violations
   ```

2. **Verify .eslintrc.json is removed:**
   ```bash
   ls -la .eslintrc.json  # Should not exist
   ```

3. **Test the linter in CI:**
   ```bash
   npm run lint  # Should pass all checks
   ```

**Rollback:** If issues occur, revert to v1.3.0 (uses ESLint v8)

### Dependency upgrades (DEP-3, DEP-8)

**What changed:**

- All Python dependencies audited and upgraded to latest compatible versions
- All security patches and CVE fixes applied
- High-priority upgrades identified and applied
- uv.lock files updated with new dependency versions

**Breaking changes:**

- Some deprecated packages may have been replaced (e.g., python-jose → PyJWT in future)
- Library APIs may have changed; existing code reviewed and updated
- Some deprecation warnings may have changed or been resolved

**Deployment checklist:**

1. **Verify all dependencies installed:**
   ```bash
   cd src/solr-search && uv sync --frozen
   cd src/document-indexer && uv sync --frozen
   # ... repeat for other Python services
   ```

2. **Test all services with upgraded dependencies:**
   ```bash
   cd src/solr-search && uv run pytest -v  # 193 tests pass
   cd src/document-indexer && uv run pytest -v  # 91+ tests pass
   # ... repeat for other Python services
   ```

3. **No deprecation warnings:**
   - All test output should be clean (no "DeprecationWarning" messages)
   - All services should start without warnings

**Rollback:** If issues occur, revert to v1.3.0 (uses earlier dependency versions)

### Bug fixes (DEP-9+)

v1.4.0 fixes 4 critical bugs:

- **#404 Stats show indexed chunks instead of book count** — Parent/child document hierarchy in Solr now correctly counts distinct books
- **#405 Library page shows empty** — Frontend API endpoint and authentication token handling fixed
- **#406 Semantic search returns 502** — Vector field population and kNN query formatting fixed for Solr 9.x
- **#407 release.yml Publish GitHub Release job fails** — Added missing checkout step to CI workflow

**Impact:**

- Stats endpoint now returns accurate book count instead of inflated chunk count
- Library page displays all books correctly
- Semantic search works without errors
- GitHub Release creation succeeds automatically

### Automated Dependabot PR review (DEP-6)

v1.4.0 introduces automated Dependabot PR review workflow that:

- Runs security checks (CodeQL, Dependabot scanning) on all Dependabot PRs
- Runs full test suite (pytest for Python, npm test for frontend)
- Auto-merges patch/minor updates if all checks pass
- Requires manual review for major version updates

**Configuration:**

Workflow file: `.github/workflows/dependabot-automerge.yml`

- Triggers on Dependabot PRs (`pull_request` event)
- Auto-merge enabled for: dependencies, npm, pip (patch/minor only)
- Manual review required for: major version bumps

**Impact:**

- 70%+ reduction in manual dependency review burden
- Security patches applied faster (auto-merge enabled)
- Major version updates still reviewed manually
- All changes still validated by CI before merge

### Regression testing (DEP-9)

v1.4.0 includes comprehensive regression testing on the upgraded stack:

**Test results:**

- ✅ All 386 Python tests pass (193 solr-search + 91 document-indexer + 81 admin + 12 document-lister + 9 embeddings-server)
- ✅ All 189 frontend tests pass (Vitest + React Testing Library)
- ✅ All integration tests pass (e2e test suite)
- ✅ Performance improvements: 15% faster backend, 8% faster frontend
- ✅ No regressions detected

**Deployment checklist:**

1. **Run full test suite after upgrade:**
   ```bash
   cd src/solr-search && uv run pytest -v
   cd src/document-indexer && uv run pytest -v
   cd src/aithena-ui && npm test
   ```

2. **Performance verification:**
   ```bash
   # Backend test execution: should be faster than v1.3.0 (38s vs 45s)
   time uv run pytest -v
   
   # Frontend build: should be faster than v1.3.0 (200ms vs 218ms)
   time npm run build
   ```

3. **Manual smoke testing:**
   - Open http://localhost/
   - Search for a keyword → results display correctly
   - Apply filters → results narrow correctly
   - Open a result → PDF loads correctly
   - Check Stats tab → book count is accurate
   - Check Status tab → all services healthy
   - Check Library tab → books display correctly

### Rollback procedure for v1.4.0

If issues occur after upgrading to v1.4.0:

1. **Revert to v1.3.0:**
   ```bash
   git checkout v1.3.0
   ```

2. **Rebuild and restart services:**
   ```bash
   ./buildall.sh  # Uses VERSION from VERSION file (should be v1.3.0)
   docker compose down
   docker compose up -d
   ```

3. **Reinstall dependencies to match v1.3.0:**
   ```bash
   cd src/solr-search && uv sync --frozen
   cd src/document-indexer && uv sync --frozen
   # ... repeat for other services
   ```

4. **Validate rollback:**
   ```bash
   curl http://localhost:8080/health
   curl http://localhost:8080/v1/stats
   ```

5. **Monitor logs for errors:**
   ```bash
   docker compose logs -f
   ```

**Data recovery:**

All persistent data (Solr indexes, Redis snapshots, RabbitMQ queues) are stored in volumes. Rolling back to a previous version does not affect data — indexes, cached results, and queue messages remain intact.

**Zero-downtime blue-green deployment:**

For critical production systems, deploy v1.5.0 alongside v1.4.0:

1. Start v1.5.0 stack on different host or network interface
2. Run full smoke test suite on v1.5.0
3. Switch nginx/load balancer to point to v1.5.0
4. Keep v1.4.0 running for 1 hour (quick rollback if needed)
5. After validation period, stop v1.4.0 stack

This requires separate docker-compose instances and load balancer configuration.

---

**Note:** Rollback is safe; no database migrations were required for v1.4.0, so all data is preserved.

### Compatibility matrix for v1.4.0

| Component | v1.3.0 | v1.4.0 | Notes |
|-----------|--------|--------|-------|
| Python | 3.11 | 3.12+ | Upgrade required; 3.11 no longer supported |
| Node.js | 20 LTS | 22 LTS | Upgrade required; Node 20 no longer supported |
| React | 18 | 19 | Upgrade required; component types updated |
| ESLint | 8 (.eslintrc.json) | 9 (eslint.config.js) | Config format changed; .eslintrc.json removed |
| Solr | 9.x | 9.x | No upgrade needed; parent/child hierarchy added |
| RabbitMQ | 3.11+ | 3.11+ | No upgrade needed |
| Redis | 6+ | 6+ | No upgrade needed |

### Summary

v1.4.0 is a significant infrastructure upgrade that modernizes the entire platform with current, supported language versions and toolchain. All services have been tested on the new stack with no regressions detected. The upgrade is recommended for immediate adoption.

## Deployment Updates for v1.6.0 (Internationalization & Quality)

v1.6.0 introduces full internationalization (i18n) support, Redis client upgrades, ESLint 10, and backend test coverage improvements. This section covers deployment considerations for operators.

### Internationalization (i18n) — no operator action required

The i18n feature is fully client-side and requires **no server-side configuration or environment variables**.

**How it works:**

- All UI strings are stored in JSON locale files bundled into the frontend build.
- Four languages are supported: English (`en`), Spanish (`es`), Catalan (`ca`), and French (`fr`).
- The LanguageSwitcher dropdown appears in the application header.
- On first visit, the browser's preferred language is auto-detected via `navigator.language`.
- The user's selection is persisted in `localStorage` and restored on subsequent visits.

**Impact on existing deployments:**

- Existing deployments will continue to show English by default.
- No database schema changes, no new environment variables, no configuration file updates.
- The UI build includes all 4 locale files (~20 KB total); no additional assets to serve.

**Adding new languages (for contributors):**

See `docs/i18n-guide.md` for the complete process: creating locale files, key naming conventions, testing requirements, and PR submission guidelines.

### Redis 7.3.0 client upgrade

All four Python services (solr-search, document-indexer, document-lister, admin) now use **redis-py 7.3.0** (upgraded from 4.x).

**Server compatibility:**

| Redis server version | Compatible with redis-py 7.3.0 | Notes |
|---------------------|-------------------------------|-------|
| Redis 6.x           | ✅ Yes                         | Fully compatible; recommended minimum |
| Redis 7.x           | ✅ Yes                         | Full feature support; recommended for new deployments |
| Redis 5.x or older  | ⚠️ Untested                   | May work but not validated |

**Operator actions:**

- No Redis server upgrade is mandatory. redis-py 7.3.0 is backward-compatible with Redis 6+ servers.
- For new deployments, Redis 7.x server is recommended to match the client version.
- Connection pool configuration remains unchanged (`ConnectionPool` singleton with double-checked locking).
- `scan_iter()`, `mget()`, and pipeline operations continue to work identically.

**Verifying Redis compatibility after upgrade:**

```bash
# Check Redis server version
docker compose exec redis redis-cli INFO server | grep redis_version

# Verify service health after deploying v1.6.0
curl -s http://localhost:8080/health | jq .
```

### ESLint 10 and react-hooks 7

ESLint has been upgraded from v9 to v10 with the react-hooks plugin upgraded to v7.

**Impact on operators:** None. This is a development-only toolchain change with no runtime impact.

**Impact on contributors:**

- ESLint 10 uses flat config format (`eslint.config.js`), continuing from the v9 migration in v1.4.0.
- react-hooks v7 enforces stricter hook dependency rules. Contributors should run `npm run lint` before submitting PRs.

### Frontend code quality fixes

- `useRef` usage corrected across components to pass TypeScript strictNullChecks.
- URL search parameters standardized for consistent behavior with the URL-based search state introduced in v1.2.0.

**Impact on operators:** None. These are internal code quality improvements with no configuration or behavioral changes.

### Test coverage improvements

- **solr-search:** 231 tests (up from 198 in v1.5.0), 94.76% coverage. 38 new tests cover the `/v1/books` endpoint comprehensively.
- **aithena-ui:** 212 tests (up from 132 in v1.5.0), including new i18n tests for locale switching and translation completeness.
- **Total across all services:** 640 tests (up from 579 in v1.5.0).

### Upgrade procedure for v1.6.0

1. Pull the latest images:
   ```bash
   docker compose pull
   ```
2. Restart the stack:
   ```bash
   docker compose up -d
   ```
3. Verify services are healthy:
   ```bash
   curl -s http://localhost:8080/health | jq .
   ```
4. Open the UI and verify the language switcher appears in the header.
5. No database migrations, no configuration changes, no Redis server upgrade required.

### Rollback procedure for v1.6.0

To roll back to v1.5.0:

1. Stop the current stack:
   ```bash
   docker compose down
   ```
2. Switch to v1.5.0 images:
   ```bash
   # Update image tags in docker-compose.yml to v1.5.0, or:
   git checkout v1.5.0 -- docker-compose.yml
   docker compose pull
   docker compose up -d
   ```
3. No data migration rollback needed — v1.6.0 makes no schema changes.

## Deployment Updates for v1.7.0 (Quality & Infrastructure)

v1.7.0 is a quality and infrastructure release focusing on CI/CD robustness, data persistence consistency, and internationalization foundation. This section covers operator-relevant changes and deployment validation.

### localStorage key standardization and auto-migration

v1.7.0 renames the language preference storage key from `aithena-locale` to `aithena.locale` for consistency.

**What changed:**

- UI now reads and writes language preference to `aithena.locale` (dot-notation) instead of `aithena-locale` (hyphen-notation).
- Auto-migration logic: on first load after v1.7.0 upgrade, the application checks for the old `aithena-locale` key and migrates it to `aithena.locale` automatically.
- Existing users retain their language preference without any action.

**Impact on operators:**

- No environment variables, configuration files, or database changes needed.
- No user action required — the migration is silent and happens on first app load.
- The `aithena.locale` key is the new standard; new deployments use it from startup.

**Verifying migration after upgrade:**

```bash
# Open the app in a browser and check the developer console (F12 → Application → Storage → Local Storage)
# Look for the new key 'aithena.locale' after the app loads
# The old 'aithena-locale' key should be gone if auto-migration succeeded
```

**New deployments:**

Fresh v1.7.0 deployments use `aithena.locale` from first startup. No old key exists, so no migration occurs.

### Page-level internationalization extraction

v1.7.0 extends i18n to all page components and the application shell.

**What changed:**

- All UI strings in `SearchPage`, `LibraryPage`, `UploadPage`, `LoginPage`, `AdminPage`, and `App.tsx` are now extracted and use `react-intl` for rendering.
- New strings are registered in the locale files (en, es, ca, fr) but default to English.
- The application is now fully i18n-ready at the component and page layer.

**Impact on operators:**

- No configuration changes, no new environment variables.
- No visible behavior change — the UI renders identically in English (default language).
- If operators have deployed locale files or custom translations, all new page strings will appear in English until translated.

**Impact on contributors:**

Contributors can now add translations for page-level strings by editing the locale files in `src/aithena-ui/src/locales/`.

**Verifying page i18n after upgrade:**

```bash
# Switch language using the LanguageSwitcher (top-right corner)
# Verify that page text updates correctly for all 4 languages (en, es, ca, fr)
# Check browser console for any missing translation warnings
```

### Dependabot CI improvements

v1.7.0 upgrades the Dependabot auto-merge workflow to Node 22 and adds explicit failure handling.

**What changed:**

- `dependabot-automerge.yml` now runs on Node 22 instead of Node 20 (the last holdout).
- Removed `continue-on-error: true` from the auto-merge step; failures now trigger explicit labeling and comments for visibility.
- Enhanced heartbeat workflow (`squad-heartbeat.yml`) detects Dependabot PRs and routes them to the appropriate squad member by dependency domain.

**Impact on operators:**

- No direct operator impact — these are CI/CD changes internal to GitHub Actions.
- The heartbeat workflow may route more Dependabot PRs to maintainers with clearer signals about which domain (Node, Python, Docker) owns the dependency.

**Verifying CI after upgrade:**

- Dependabot auto-merge will continue to work for qualifying PRs (automerge label, passing CI, no conflicts).
- If auto-merge fails, the PR is now labeled and commented with clear failure reasons instead of silent skips.

### Deployment checklist for v1.7.0

1. **Pre-upgrade:**
   - Verify all services are healthy: `curl -s http://localhost/health`
   - Note any active Dependabot PRs for manual review post-upgrade

2. **Upgrade:**
   ```bash
   docker compose pull
   docker compose up -d
   ```

3. **Post-upgrade validation:**
   - Check that the app loads and displays in your preferred language
   - Switch languages using the LanguageSwitcher to verify all page text updates
   - Verify the new `aithena.locale` key appears in browser localStorage after the first page load
   - Confirm no console warnings about missing translations
   - Check `docker compose ps` to ensure all services are running

4. **No rollback-specific actions needed:**
   - All v1.7.0 changes are additive (new key name, new extracted strings, CI improvements).
   - If you roll back to v1.6.0, the app will recreate the old `aithena-locale` key on first load.

### Rollback procedure for v1.7.0

To roll back to v1.6.0:

1. Stop the current stack:
   ```bash
   docker compose down
   ```
2. Switch to v1.6.0 images:
   ```bash
   git checkout v1.6.0 -- docker-compose.yml
   docker compose pull
   docker compose up -d
   ```
3. No data migration rollback needed — v1.7.0 makes no schema or volume changes. Note: v1.6.0 code reads only the old `aithena-locale` key, so after rollback it will not find the migrated `aithena.locale` key. Users who switched languages during v1.7.0 will revert to browser locale detection on their next visit. This is a cosmetic reset, not data loss.
