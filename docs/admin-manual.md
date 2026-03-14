# Admin Manual

This manual covers deployment, configuration, monitoring, and troubleshooting for Aithena. If you are looking for end-user instructions, start with the [User Manual](user-manual.md). For the release-facing feature summary, see the [v0.4.0 Feature Guide](features/v0.4.0.md).

## System architecture overview

Aithena runs as a Docker Compose stack built around Solr, a document ingestion pipeline, and a React web UI.

### Core services

| Service | Purpose | Default access |
|---|---|---|
| `nginx` | Main reverse proxy and public entry point | `80`, `443` |
| `aithena-ui` | User-facing React frontend | proxied through `nginx` |
| `solr-search` | FastAPI search, status, stats, and document endpoints | `8080` |
| `solr`, `solr2`, `solr3` | SolrCloud search nodes | `8983`, `8984`, `8985` |
| `solr-init` | One-shot collection/config bootstrap for `books` | internal only |
| `zoo1`, `zoo2`, `zoo3` | ZooKeeper ensemble for SolrCloud | `2181`, `2182`, `2183` |
| `redis` | Indexing state tracking | `6379` |
| `rabbitmq` | Queue for document ingestion | `5672`, `15672` |
| `document-lister` | Scans the mounted library and enqueues PDFs | internal only |
| `document-indexer` | Consumes queue items and indexes books into Solr | internal only |
| `embeddings-server` | Embedding service used by the search stack | `8085` |
| `streamlit-admin` | Lightweight admin dashboard | proxied through `nginx` |
| `redis-commander` | Web UI for Redis inspection | proxied through `nginx` |
| `certbot` | Certificate renewal helper | internal only |

### Service dependencies

At a high level:

1. `document-lister` scans the mounted book library.
2. New or changed PDFs are pushed into RabbitMQ.
3. `document-indexer` consumes queue messages and writes metadata plus extracted content into Solr.
4. `solr-search` serves search results, PDF document links, status, and stats.
5. `aithena-ui` and `nginx` present the user-facing application.

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

This starts the full stack, including SolrCloud, Redis, RabbitMQ, the indexing services, the search API, and the UI.

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
| Search API | `http://localhost:8080/v1/search/` |
| Status API | `http://localhost:8080/v1/status/` |
| Stats API | `http://localhost:8080/v1/stats/` |
| Solr admin | `http://localhost:8983/solr/` |
| RabbitMQ management | `http://localhost:15672/` |
| ZooKeeper node 1 | `localhost:2181` |

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

## Monitoring

### Use the Status tab

The UI **Status** tab is the fastest operator-friendly health check.

It shows:

- indexing counts from Redis-backed document tracking
- Solr cluster status, live node count, and indexed document count
- up/down reachability for Solr, Redis, and RabbitMQ
- automatic refresh every 10 seconds

Important: this dashboard is focused on the search and ingestion path. It does **not** report health for every container in the stack.

### Use the API directly

#### Status endpoint

```bash
curl http://localhost:8080/v1/status/
```

This endpoint aggregates:

- Solr `CLUSTERSTATUS`
- Redis `doc:*` state counts
- TCP reachability checks for Solr, Redis, and RabbitMQ

#### Stats endpoint

```bash
curl http://localhost:8080/v1/stats/
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
curl -f http://localhost:8983/solr/admin/info/system
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

Also inspect the management UI at `http://localhost:15672/`.

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
- `http://localhost:8080/v1/status/` returns JSON
- `http://localhost:8080/v1/stats/` returns JSON
- the main UI at `http://localhost/` loads Search, Status, and Stats
- a known PDF can be searched and opened from results
