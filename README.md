# Aithena — Book Library Search Engine

A multilingual book library search engine that indexes PDFs using **Apache Solr** for full-text search, extracts metadata (author, date, language) from filenames and folder names, and supports keyword, semantic, and hybrid search via embeddings.

## What It Does

- **Indexes multilingual texts** (Spanish, Catalan, French, English, including ancient/OCR texts)
- **Extracts metadata** from filesystem paths: author, title, publication year, category
- **Performs full-text search** via Solr with multilingual analyzers
- **Supports semantic and hybrid search** with multilingual embeddings
- **Detects language** from folder structure plus Solr `langid` processing
- **Accepts PDF uploads** via drag-and-drop UI with client-side validation and rate limiting
- **Scans for security issues** with bandit (Python), checkov (IaC), and zizmor (GitHub Actions)
- **Hardens GitHub Actions supply chain** with SHA-pinned actions, least-privilege permissions, and non-persistent checkout credentials

## Features

- **Local authentication** with SQLite-backed users, Argon2id password hashing, JWT sessions, and browser/login flows
- **Protected React routes** with a dedicated login page, auth context, and automatic bearer auth for protected API calls
- **nginx auth_request gating** for browser-facing API, document, and admin routes
- **First-run installer CLI** that writes `.env`, creates auth storage, and seeds the initial admin account
- **Search page** for keyword, semantic, and hybrid search across indexed title, author, and full-text content
- **Facet filtering** by author, category, language, and year
- **Similar Books panel** that appears after opening a PDF and recommends semantically related titles
- **PDF viewer** that opens from search results and jumps to the matched page when page metadata exists
- **Upload tab** with drag-and-drop file upload and real-time progress tracking
- **Admin tab** with an embedded Streamlit dashboard for queue visibility, document management, and system status
- **Status tab** with indexing progress plus Solr, Redis, and RabbitMQ health, refreshing every 10 seconds
- **Stats tab** with indexed-book totals, page-count statistics, and breakdowns by language, author, year, and category
- **Container health checks** for all services with automatic restart on failure
- **Resource limits** on memory for production stability
- **Security-hardening CI/CD pipeline** with bandit, checkov, zizmor, SHA-pinned actions, least-privilege workflow permissions, and `persist-credentials: false` checkout defaults

## Documentation

- [User Manual](docs/user-manual.md)
- [Admin Manual](docs/admin-manual.md)
- [Deployment sizing guide](docs/deployment/sizing-guide.md)
- [v0.12.0 Release Notes](docs/release-notes-v0.12.0.md)
- [v0.12.0 Test Report](docs/test-report-v0.12.0.md)
- [v0.11.0 Feature Guide](docs/features/v0.11.0.md)
- [v0.11.0 Release Notes](docs/release-notes-v0.11.0.md)
- [v0.11.0 Test Report](docs/test-report-v0.11.0.md)
- [v0.10.0 Release Notes](docs/release-notes-v0.10.0.md)
- [v0.10.0 Test Report](docs/test-report-v0.10.0.md)
- [v0.7.0 Feature Guide](docs/features/v0.7.0.md)
- [v0.6.0 Feature Guide](docs/features/v0.6.0.md)
- [v0.5.0 Feature Guide](docs/features/v0.5.0.md)
- [v0.4.0 Feature Guide](docs/features/v0.4.0.md)
- [Security Baseline](docs/security/baseline-v0.6.0.md)
- [v0.7.0 Test Report](docs/test-report-v0.7.0.md)
- [v0.6.0 Test Report](docs/test-report-v0.6.0.md)
- [v0.5.0 Test Report](docs/test-report-v0.5.0.md)

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
| **Solr Search API** | FastAPI wrapper around the `books` collection | Normalized results, facets, highlights, PDF document URLs |
| **Embeddings Server** | Semantic search vectors (Phase 3+) | `distiluse-base-multilingual-cased-v2` |
| **Streamlit Admin UI** | Basic document management & monitoring | `/admin/streamlit/` via nginx |
| **React/Vite Frontend** | Search UI with faceting | `/` via nginx |
| **nginx + Certbot** | Reverse proxy, TLS termination, admin entry point | Production-ready |

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

### 1. Run the first-run installer

Generate `.env`, create the auth database, and seed the initial admin user:

```bash
python3 -m installer
# or: python3 installer/setup.py
```

The installer prompts for the book library path, admin credentials, and the public origin URL, then writes `.env` and bootstraps the SQLite auth DB. Run it before `docker compose up` so the auth storage directory exists for the bind mount.

### 2. Start All Services

```bash
docker compose up -d
```

Need automation instead of prompts? Run `python3 installer/setup.py --help` for non-interactive flags such as `--library-path`, `--admin-user`, `--admin-password`, and `--origin`.

By default, Docker Compose also auto-loads `docker-compose.override.yml`, so local development/debug ports stay published.

Use the production-only surface when you want just the nginx gateway on the host:

```bash
docker compose -f docker-compose.yml up -d
```

This starts:
- Redis, RabbitMQ (messaging layer)
- ZooKeeper ensemble (3 nodes)
- SolrCloud cluster (3 nodes)
- `solr-init`, which uploads the `books` configset and creates the collection automatically
- Document Lister, Document Indexer, Solr Search API, Embeddings Server
- nginx + Certbot (TLS)
- Admin UI and frontend

### 3. Confirm Solr Bootstrap

```bash
docker compose ps
docker compose logs -f solr-init
```

Once `solr-init` completes:
- Document Lister automatically discovers PDFs in `BOOKS_PATH`
- Document Indexer consumes them from RabbitMQ and indexes into Solr
- Track progress in Redis (`redis-cli`) and the Status tab

### 4. Access Interfaces

| Service | URL | Purpose |
|---------|-----|---------|
| Main UI | http://localhost/ | Search UI via the main nginx entry point |
| Admin landing page | http://localhost/admin/ | Jump-off page for infra/admin tools |
| Solr Admin | http://localhost/admin/solr/ | Manage collections and inspect indexed docs |
| Search API | http://localhost/v1/search?q=historia | Query books with facets, pagination, sorting, and highlights through nginx |
| RabbitMQ Admin | http://localhost/admin/rabbitmq/ | Monitor queue depth through the management UI |
| Redis Commander | http://localhost/admin/redis/ | Inspect Redis state through a lightweight web UI |
| Redis CLI | `redis-cli` | Check `processed` & `failed` keys |
| Streamlit Admin | http://localhost/admin/streamlit/ | Document management dashboard |

When `docker compose up` loads `docker-compose.override.yml` (the default local workflow), these direct debug ports are also available:

| Service | Port(s) | Purpose |
|---------|---------|---------|
| solr-search | `8080` | Direct FastAPI debugging without nginx |
| solr / solr2 / solr3 | `8983`, `8984`, `8985` | Solr admin/API access per node |
| rabbitmq | `5672`, `15672` | AMQP clients and direct management UI |
| redis | `6379` | Redis CLI and direct state inspection |
| redis-commander | `8081` | Direct Redis Commander UI |
| streamlit-admin | `8501` | Direct Streamlit debugging |
| zoo1 / zoo2 / zoo3 | `18080`, `2181`, `2182`, `2183` | ZooKeeper AdminServer and node client ports |
| embeddings-server | `8085` | Embeddings API debugging / local external tools |

For production-style runs (`docker compose -f docker-compose.yml up`), only nginx publishes `80/443`.

## Solr Schema & Fields

See [`src/solr/README.md`](src/solr/README.md) for schema design details. The FastAPI service in `src/solr-search/` exposes `/search`, `/facets`, and client-safe `/documents/{token}` URLs against these fields. Key fields:

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
cd src/solr-search && uv run pytest -v --tb=short
cd src/document-indexer && uv run pytest -v --tb=short
cd src/aithena-ui && npx vitest run
```

### E2E Tests

The E2E suite validates the full upload → indexing → search → PDF viewing pipeline against a local development stack using fixture data isolated from the real book corpus.

#### 1. Create the test library directory

```bash
export E2E_LIBRARY_PATH=/tmp/aithena-e2e-library
mkdir -p "$E2E_LIBRARY_PATH"
```

#### 2. Start the local stack with the E2E override

```bash
docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d
```

The override (`docker-compose.e2e.yml`) mounts `E2E_LIBRARY_PATH` as the document library instead of `/home/jmservera/booklibrary`, so the test run is fully isolated from the real corpus. It also sets the document-lister poll interval to 10 seconds for faster feedback.

#### 3. Install test dependencies

```bash
pip install -r e2e/requirements.txt
```

#### 4. Run the E2E suite

```bash
cd e2e && pytest
```

#### What the suite tests

| Step | Test | Description |
|------|------|-------------|
| Upload | `test_fixture_pdf_exists_in_library` | Fixture PDF written to test library directory |
| Indexing | `test_index_document_into_solr` | PDF POSTed to Solr `/update/extract`; doc confirmed indexed |
| Search | `test_search_returns_indexed_document` | Solr query returns doc with correct title, author, year |
| Viewing | `test_pdf_file_path_is_accessible` | `file_path_s` resolves to an accessible file on disk |

#### Failure diagnostics

When a test fails, the suite automatically captures and prints:
- The Solr response body (recent documents)
- Last 50 lines of `document-indexer` container logs

#### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SOLR_URL` | `http://localhost:8983/solr/books` | Solr collection endpoint |
| `E2E_LIBRARY_PATH` | `/tmp/aithena-e2e-library` | Temporary library root (must match volume bind-mount) |

### Metadata Extraction

Supports flexible path patterns:

- `Author/Title.pdf` → title from filename, author from folder
- `Category/Author - Title (Year).pdf` → parsed fields from filename
- `amades/some title amades.pdf` → heuristic-based single-author folders
- `balearics/ESTUDIS_BALEARICS_01.pdf` → category/series folder with uppercase patterns

Unknown patterns fallback conservatively:
- `title` = filename stem
- `author` = "Unknown"

See `src/document-indexer/tests/test_metadata.py` for test cases and real library examples.

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
- Adjust the scan frequency via the `POLL_INTERVAL` environment variable (default: `60` seconds)

### Document Lister Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `POLL_INTERVAL` | `60` | Seconds between library scans. New and modified files are re-queued; unchanged processed files are skipped. |
| `BASE_PATH` | `/data/documents/` | Root directory to scan for documents. |
| `DOCUMENT_WILDCARD` | `*.pdf` | Glob pattern for files to consider. Non-PDF files are skipped explicitly. |
| `QUEUE_NAME` | `shortembeddings` | RabbitMQ queue name for discovered documents in the current Docker Compose stack. |

### Solr returns empty results?
- Check collection was created: `http://localhost/admin/solr/#/collections` (or `http://localhost:8983/solr/#/collections` when the dev override is loaded)
- Monitor indexer logs: `docker compose logs document-indexer`
- Check Redis state: `redis-cli KEYS "*"`

### Indexing stuck or slow?
- Monitor RabbitMQ queue depth: `http://localhost/admin/rabbitmq/` (or `http://localhost:15672` with the dev override)
- Check Solr logs for extraction errors: `docker compose logs solr`
- Increase document-indexer replicas in `docker-compose.yml`

## References

- [Apache Solr Documentation](https://solr.apache.org/docs/)
- [Solr Tika Integration](https://solr.apache.org/docs/latest/indexing-and-basic-data-operations.html#indexing-binary-documents)
- [RabbitMQ](https://www.rabbitmq.com/)
- [langid.py](https://github.com/saffsd/langid.py)
- [distiluse-base-multilingual-cased-v2](https://huggingface.co/cross-encoder/distiluse-base-multilingual-cased-v2)
