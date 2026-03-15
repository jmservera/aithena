# Admin Manual

This manual covers deployment, configuration, monitoring, and troubleshooting for Aithena. If you are looking for end-user instructions, start with the [User Manual](user-manual.md). For the release-facing feature summary, see the [v0.5.0 Feature Guide](features/v0.5.0.md).

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

### 2. Start the stack

```bash
docker compose up -d
```

This starts the full stack, including SolrCloud, Redis, RabbitMQ, the indexing services, the search API, and the UI. In the default local workflow, Docker Compose also auto-loads `docker-compose.override.yml`, which republishes debug ports for direct host access.

For a production-style run with only the nginx gateway exposed on the host, use:

```bash
docker compose -f docker-compose.yml up -d
```

### 3. Watch initial bootstrap

The `solr-init` container waits for all three Solr nodes, uploads the `books` configset, creates the `books` collection if needed, and applies the config overlay.

Useful checks:

```bash
docker compose ps
docker compose logs -f solr-init
```

### 4. Open the service endpoints

Common local URLs:

| Surface | URL |
|---|---|
| Main UI | `http://localhost/` |
| Search API | `http://localhost/v1/search/` |
| Status API | `http://localhost/v1/status/` |
| Stats API | `http://localhost/v1/stats/` |
| Solr admin | `http://localhost/admin/solr/` |
| RabbitMQ management | `http://localhost/admin/rabbitmq/` |
| Streamlit admin | `http://localhost/admin/streamlit/` |
| Redis Commander | `http://localhost/admin/redis/` |

Direct host ports (`8080`, `8983`-`8985`, `15672`, `6379`, `2181`-`2183`, `18080`, `8501`, `8081`, `8085`) are available only when the local `docker-compose.override.yml` file is loaded.

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
| `DEFAULT_SEARCH_MODE` | `keyword` | Default API search mode |

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

## Monitoring

### Use the Status tab

The UI **Status** tab is the fastest operator-friendly health check.

![Status tab](images/status-tab.png)

It shows:

- indexing counts from Redis-backed document tracking
- Solr cluster status, live node count, and indexed document count
- up/down reachability for Solr, Redis, and RabbitMQ
- automatic refresh every 10 seconds

Important: this dashboard is focused on the search and ingestion path. It does **not** report health for every container in the stack.

![Stats tab](images/stats-tab.png)

### Use the API directly

#### Status endpoint

```bash
curl http://localhost/v1/status/
```

This endpoint aggregates:

- Solr `CLUSTERSTATUS`
- Redis `doc:*` state counts
- TCP reachability checks for Solr, Redis, and RabbitMQ

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
- `http://localhost/v1/status/` returns JSON
- `http://localhost/v1/stats/` returns JSON
- the main UI at `http://localhost/` loads Search, Status, and Stats
- a known PDF can be searched and opened from results
