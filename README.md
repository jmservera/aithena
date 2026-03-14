# Aithena — Book Library Search Engine

A multilingual book library search engine that indexes PDFs using **Apache Solr** for full-text search, extracts metadata (author, date, language) from filenames and folder names, and supports semantic search via embeddings.

## What It Does

- **Indexes multilingual texts** (Spanish, Catalan, French, English, including ancient/OCR texts)
- **Extracts metadata** from filesystem paths: author, title, publication year, category
- **Performs full-text search** via Solr with multilingual analyzers
- **Detects language** automatically using `langid`
- **Prepares for semantic search** with pre-extracted embeddings (Phase 2+)

## Architecture

### Core Stack

| Component | Purpose | Notes |
|-----------|---------|-------|
| **SolrCloud** (3 nodes) | Full-text indexing & search | Managed by 3-node ZooKeeper ensemble |
| **Tika (in Solr)** | PDF text extraction & metadata parsing | Via `/update/extract` handler |
| **RabbitMQ** | Message queue for indexing pipeline | Decouples file discovery from indexing |
| **Redis** | State tracking (processed, failed files) | Persists indexing progress |
| **Document Lister** | Scans book library filesystem | 60 s polling, tracks state in Redis, queues files to RabbitMQ |
| **Document Indexer** | Consumes queue, extracts metadata, uploads to Solr | Python service with configurable path heuristics; scales via `replicas` |
| **Embeddings Server** | Semantic search vectors (Phase 3+) | `distiluse-base-multilingual-cased-v2` |
| **Admin UI** | Document management & indexing monitoring | Streamlit, port 8501 |
| **React/Vite Frontend** | Search UI with faceting (Phase 2) | In development |
| **nginx + Certbot** | Reverse proxy, TLS termination | Production-ready |

### Data Flow

```
File Library (/data/documents inside containers)
    ↓
Document Lister (60 s poll + Redis state tracking)
    ↓
RabbitMQ (queue: shortembeddings)
    ↓
Document Indexer (metadata extraction + Solr Tika POST)
    ↓
SolrCloud Books Collection (indexed, searchable)
    ↓
Frontend / Search API
```

### Service Port Map

| Service | Host Port | Notes |
|---------|-----------|-------|
| Solr (node 1) | 8983 | Admin UI + direct query; restrict in production |
| Solr (node 2) | 8984 | Dev access to secondary node |
| Solr (node 3) | 8985 | Dev access to tertiary node |
| RabbitMQ AMQP | 5672 | Message broker |
| RabbitMQ Management | 15672 | Monitoring only; restrict in production |
| Redis | 6379 | State store |
| Admin UI | 8501 | Streamlit admin dashboard |
| Embeddings Server | 8085 | Dev access; internal-only in production |
| Search API (solr-search) | 8080 | FastAPI; fronted by nginx /api in production |
| nginx | 80 / 443 | Public entry point for all production traffic |

ZooKeeper nodes (zoo1–zoo3): zoo1 client port (2181) and admin HTTP (8080) are exposed to the host; zoo2/zoo3 client ports are accessible on 2182/2183.

## Quick Start

### 1. Configure Book Library Path

Edit `docker-compose.yml`, update the `document-data` volume:

```yaml
volumes:
  document-data:
    driver: local
    driver_opts:
      type: "none"
      o: "bind"
      device: "/path/to/your/booklibrary"  # ← Change this
```

Default: `/home/jmservera/booklibrary`

You also need to create the persistent volume directories on the host:

```bash
sudo mkdir -p /source/volumes/{rabbitmq-data,nginx-data,redis,solr-data,solr-data2,solr-data3}
sudo mkdir -p /source/volumes/{certbot-data/conf,certbot-data/www}
sudo mkdir -p /source/volumes/{zoo-data1,zoo-data2,zoo-data3}/{logs,data,datalog}
sudo mkdir -p /source/volumes/zoo-backup
```

### 2. Start All Services

```bash
docker compose up -d
```

Services start in dependency order (health-check gated):
1. Redis, RabbitMQ (messaging layer)
2. ZooKeeper ensemble (zoo1 → zoo2 → zoo3)
3. SolrCloud cluster (waits for all ZK nodes to be healthy)
4. Document Lister, Document Indexer (wait for messaging layer + Solr)
5. Admin UI (waits for Redis)
6. nginx + Certbot (TLS)

### 3. Create Books Collection

After Solr is healthy, upload the schema configset and create the `books` collection:

```bash
# Copy the books configset into the running Solr container
docker compose cp solr/books/. solr:/tmp/books-config

# Upload the config to ZooKeeper
docker compose exec solr solr zk upconfig -n books -d /tmp/books-config -z zoo1:2181

# Create the collection (1 shard, 3 replicas — one per node)
docker compose exec solr solr create_collection -c books -n books -shards 1 -replicationFactor 3
```

Alternatively, use the Solr Admin UI at http://localhost:8983 to create and configure the collection.

Once created, Document Lister automatically discovers PDFs and Document Indexer uploads them to Solr.

### 4. Access Interfaces

| Service | URL | Purpose |
|---------|-----|---------|
| Solr Admin | http://localhost:8983 | Manage collections, view indexed docs |
| RabbitMQ Admin | http://localhost:15672 | Monitor queue depth |
| Admin UI | http://localhost:8501 | Document management (Streamlit) |
| Search API | http://localhost:8080/docs | FastAPI search endpoints (OpenAPI docs) |
| Redis CLI | `docker compose exec redis redis-cli` | Check `processed` & `failed` keys |

## Environment Variables

Key variables wired in `docker-compose.yml` (override via `.env` or compose `environment` block):

| Variable | Service | Default | Description |
|----------|---------|---------|-------------|
| `REDIS_HOST` | lister, indexer, admin | `redis` | Redis service hostname |
| `RABBITMQ_HOST` | lister, indexer, admin | `rabbitmq` | RabbitMQ service hostname |
| `QUEUE_NAME` | lister, indexer, admin | `shortembeddings` | Shared queue/namespace; must match across services |
| `BASE_PATH` | indexer | `/data/documents/` | Mount point inside the indexer container |
| `SOLR_HOST` | indexer | `solr` | Solr hostname for Tika extraction posts |
| `SOLR_PORT` | indexer | `8983` | Solr port |
| `SOLR_COLLECTION` | indexer | `books` | Solr collection name |
| `EMBEDDINGS_HOST` | indexer | `embeddings-server` | Embeddings server hostname (Phase 3) |
| `EMBEDDINGS_PORT` | indexer | `8085` | Embeddings server port (Phase 3) |
| `SOLR_URL` | solr-search | `http://solr:8983/solr` | Full Solr base URL |
| `CORS_ORIGINS` | solr-search | `http://localhost:5173` | Allowed CORS origins for the search API |
| `RABBITMQ_MGMT_PORT` | admin | `15672` | RabbitMQ management API port |
| `RABBITMQ_USER` | admin | `guest` | RabbitMQ management API username |
| `ZK_HOST` | solr, solr2, solr3 | `zoo1:2181,zoo2:2181,zoo3:2181` | ZooKeeper ensemble addresses |
| `SOLR_MODULES` | solr, solr2, solr3 | `extraction,langid` | Solr modules to enable (Tika + language detection) |

## Solr Schema & Fields

See [`solr/README.md`](solr/README.md) for schema design details. Key fields:

- `title_s`, `title_t` — Book title (string + text)
- `author_s`, `author_t` — Author (string + text)
- `year_i` — Publication year
- `content` — Full-text PDF body (stored, highlighted)
- `language_detected_s` — Auto-detected language (es, ca, fr, en, etc.)
- `file_path_s`, `folder_path_s` — Relative paths for tracking
- `category_s` — Inferred from folder hierarchy
- `_text_` — Default query field (includes title, author, content)

## Development

### Testing

```bash
cd document-indexer
python3 -m pytest tests/ -v
```

### Metadata Extraction

Supports flexible path patterns:

- `Author/Title.pdf` → title from filename, author from folder
- `Category/Author - Title (Year).pdf` → parsed fields from filename
- `amades/some title amades.pdf` → heuristic-based single-author folders
- `balearics/ESTUDIS_BALEARICS_01.pdf` → category/series folder with uppercase patterns

Unknown patterns fallback conservatively:
- `title` = filename stem
- `author` = "Unknown"

See `document-indexer/tests/test_metadata.py` for test cases and real library examples.

### Project Phases

**Phase 1** (complete): Core Solr indexing pipeline, metadata extraction, schema  
**Phase 2**: FastAPI search API, React search UI with faceting, PDF viewer  
**Phase 3**: Embeddings indexing, hybrid search (keyword + semantic), similar books  
**Phase 4** (this PR): PDF upload, file watcher, admin dashboard, production hardening  

Current branch: `jmservera/solrstreamlitui`

## Troubleshooting

### Document Lister not finding files?
- Check volume mount in `docker-compose.yml` points to actual library directory
- Verify permissions: `ls -la /home/jmservera/booklibrary`
- Check lister logs: `docker compose logs document-lister`

### Solr returns empty results?
- Check collection was created: `http://localhost:8983/solr/#/collections`
- Monitor indexer logs: `docker compose logs document-indexer`
- Check Redis state: `docker compose exec redis redis-cli KEYS "*"`

### Indexing stuck or slow?
- Monitor RabbitMQ queue depth: `http://localhost:15672`
- Check Solr logs for extraction errors: `docker compose logs solr`
- Increase document-indexer replicas: edit `deploy.replicas` in `docker-compose.yml`

### Service health?
```bash
docker compose ps          # shows health status for all services
docker compose logs --tail=50 <service>
```

## References

- [Apache Solr Documentation](https://solr.apache.org/docs/)
- [Solr Tika Integration](https://solr.apache.org/docs/latest/indexing-and-basic-data-operations.html#indexing-binary-documents)
- [RabbitMQ](https://www.rabbitmq.com/)
- [langid.py](https://github.com/saffsd/langid.py)
- [distiluse-base-multilingual-cased-v2](https://huggingface.co/cross-encoder/distiluse-base-multilingual-cased-v2)
