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
| **Document Lister** | Scans book library filesystem | Tracks state, queues files to RabbitMQ |
| **Document Indexer** | Consumes queue, extracts metadata, uploads to Solr | Python service with configurable path heuristics |
| **Embeddings Server** | Semantic search vectors (Phase 3+) | `distiluse-base-multilingual-cased-v2` |
| **Streamlit Admin UI** | Basic document management & monitoring | Port 8501 |
| **React/Vite Frontend** | Search UI with faceting | In development (Phase 2) |
| **nginx + Certbot** | Reverse proxy, TLS termination | Production-ready |

### Data Flow

```
File Library
    ↓
Document Lister (scan + Redis tracking)
    ↓
RabbitMQ (queue)
    ↓
Document Indexer (metadata extraction + Solr POST)
    ↓
SolrCloud Books Collection (indexed, searchable)
    ↓
Frontend / Search API
```

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

### 2. Start All Services

```bash
docker compose up -d
```

This starts:
- Redis, RabbitMQ (messaging layer)
- ZooKeeper ensemble (3 nodes)
- SolrCloud cluster (3 nodes)
- Document Lister, Document Indexer, Embeddings Server
- nginx + Certbot (TLS)
- Admin UI, frontend placeholders

### 3. Create Books Collection

Upload the Solr configset to the cluster:

```bash
cd solr/books
# Upload config to ZooKeeper (requires Solr CLI tools installed)
# Or use the Solr Web UI to create collection: http://localhost:8983
```

Once the `books` collection is created:
- Document Lister automatically discovers PDFs in `/home/jmservera/booklibrary`
- Document Indexer consumes them from RabbitMQ and indexes into Solr
- Track progress in Redis (`redis-cli`)

### 4. Access Interfaces

| Service | URL | Purpose |
|---------|-----|---------|
| Solr Admin | http://localhost:8983 | Manage collections, view indexed docs |
| RabbitMQ Admin | http://localhost:15672 | Monitor queue depth |
| Redis CLI | `redis-cli` | Check `processed` & `failed` keys |
| Streamlit Admin | http://localhost:8501 | Document management (development) |

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

**Phase 1** (in progress): Core Solr indexing pipeline, metadata extraction, schema  
**Phase 2**: FastAPI search API, React search UI with faceting, PDF viewer  
**Phase 3**: Embeddings indexing, hybrid search (keyword + semantic), similar books  
**Phase 4**: PDF upload, file watcher, admin dashboard, production hardening  

Current branch: `jmservera/solrstreamlitui`

## Troubleshooting

### Document Lister not finding files?
- Check volume mount in `docker-compose.yml` points to actual library directory
- Verify permissions: `ls -la /home/jmservera/booklibrary`

### Solr returns empty results?
- Check collection was created: `http://localhost:8983/solr/#/collections`
- Monitor indexer logs: `docker compose logs document-indexer`
- Check Redis state: `redis-cli KEYS "*"`

### Indexing stuck or slow?
- Monitor RabbitMQ queue depth: `http://localhost:15672`
- Check Solr logs for extraction errors: `docker compose logs solr`
- Increase document-indexer replicas in `docker-compose.yml`

## References

- [Apache Solr Documentation](https://solr.apache.org/docs/)
- [Solr Tika Integration](https://solr.apache.org/docs/latest/indexing-and-basic-data-operations.html#indexing-binary-documents)
- [RabbitMQ](https://www.rabbitmq.com/)
- [langid.py](https://github.com/saffsd/langid.py)
- [distiluse-base-multilingual-cased-v2](https://huggingface.co/cross-encoder/distiluse-base-multilingual-cased-v2)
