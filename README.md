# Aithena — Book Library Search Engine

A multilingual book library search engine that indexes PDFs using **Apache Solr** for full-text search, extracts metadata (author, date, language) from filenames and folder names, and supports keyword, semantic, and hybrid search via embeddings.

**Current Release:** v1.9.1 — Docker build fix for aithena-ui.  
**Development:** v1.10.0 milestones active. All PRs target `dev` branch; releases merge `dev` → `main`.  
**[View Milestones](https://github.com/jmservera/aithena/milestones)** | **[Latest Release Notes](docs/release-notes/v1.9.1.md)**

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
- **Admin portal** with queue visibility, document management, user management, and system status
- **Status tab** with indexing progress plus Solr, Redis, and RabbitMQ health, refreshing every 10 seconds
- **Stats tab** with indexed-book totals, page-count statistics, and breakdowns by language, author, year, and category
- **Container health checks** for all services with automatic restart on failure
- **Resource limits** on memory for production stability
- **Security-hardening CI/CD pipeline** with bandit, checkov, zizmor, SHA-pinned actions, least-privilege workflow permissions, and `persist-credentials: false` checkout defaults

## v1.x Development Process

This section documents how the team develops, branches, and releases v1.x versions.

### Branching Strategy

- **`dev` branch** — Active development. All feature branches create pull requests against `dev`.
- **`main` branch** — Production releases only. Merges from `dev` happen at release boundaries (e.g., v1.0.0 → v1.1.0).
- **Feature branches** — Use the squad naming convention: `squad/{issue-number}-{kebab-case-slug}`
  - Example: `squad/298-update-v1x-docs`

### Pull Request Workflow

1. **Create a feature branch** from `dev`:
   ```bash
   git checkout dev && git pull origin dev
   git checkout -b squad/{issue-number}-{kebab-case-slug}
   ```

2. **Push and open a PR against `dev`**:
   ```bash
   git push origin squad/...
   gh pr create --base dev --title "..." --body "Closes #{issue-number}"
   ```

3. **PR Reviews & Merging**:
   - All PRs require review before merge (branch protection on `dev`).
   - Squad members or designated reviewers approve.
   - Maintainers merge to `dev` using `gh pr merge` or the GitHub UI.

### Release Process

When a v1.x milestone is complete:

1. **Create a release tag** on `dev`:
   ```bash
   git tag -a v1.x.y -m "Release v1.x.y" && git push origin v1.x.y
   ```

2. **Merge `dev` → `main`**:
   ```bash
   git checkout main && git pull origin main
   git merge dev && git push origin main
   ```

3. **Update version file** (if needed for next development cycle):
   - Edit `VERSION` file in the repo root
   - Commit and push to `dev`

See [Release Process Overview](#release-process-overview) below for full details.

## Documentation

### Guides

- [User Manual](docs/user-manual.md)
- [Admin Manual](docs/admin-manual.md)
- [Deployment Sizing Guide](docs/deployment/sizing-guide.md)
- [i18n Contributor Guide](docs/guides/i18n-guide.md)
- [Security Baseline](docs/security/baseline-v0.6.0.md)

### Release Notes (newest first)

- [v1.9.1 Release Notes](docs/release-notes/v1.9.1.md)
- [v1.9.0 Release Notes](docs/release-notes/v1.9.0.md)
- [v1.8.2 Release Notes](docs/release-notes/v1.8.2.md)
- [v1.8.1 Release Notes](docs/release-notes/v1.8.1.md)
- [v1.8.0 Release Notes](docs/release-notes/v1.8.0.md)
- [v1.7.0 Release Notes](docs/release-notes/v1.7.0.md)
- [v1.6.0 Release Notes](docs/release-notes/v1.6.0.md)
- [v1.5.0 Release Notes](docs/release-notes/v1.5.0.md)
- [v1.4.0 Release Notes](docs/release-notes/v1.4.0.md)
- [v1.3.0 Release Notes](docs/release-notes/v1.3.0.md)
- [v1.2.0 Release Notes](docs/release-notes/v1.2.0.md)
- [v1.1.0 Release Notes](docs/release-notes/v1.1.0.md)
- [v1.0.1 Release Notes](docs/release-notes/v1.0.1.md)
- [v1.0.0 Release Notes](docs/release-notes/v1.0.0.md)
- [v0.12.0 Release Notes](docs/release-notes/v0.12.0.md)
- [v0.11.0 Release Notes](docs/release-notes/v0.11.0.md)
- [v0.10.0 Release Notes](docs/release-notes/v0.10.0.md)

### Test Reports (newest first)

- [v1.8.1 Test Report](docs/test-reports/v1.8.1.md)
- [v1.8.0 Test Report](docs/test-reports/v1.8.0.md)
- [v1.7.0 Test Report](docs/test-reports/v1.7.0.md)
- [v1.6.0 Test Report](docs/test-reports/v1.6.0.md)
- [v1.5.0 Test Report](docs/test-reports/v1.5.0.md)
- [v1.4.0 Test Report](docs/test-reports/v1.4.0.md)
- [v1.3.0 Test Report](docs/test-reports/v1.3.0.md)
- [v1.2.0 Test Report](docs/test-reports/v1.2.0.md)
- [v1.0.0 Test Report](docs/test-reports/v1.0.0.md)
- [v0.12.0 Test Report](docs/test-reports/v0.12.0.md)
- [v0.11.0 Test Report](docs/test-reports/v0.11.0.md)
- [v0.10.0 Test Report](docs/test-reports/v0.10.0.md)

### Feature Guides

- [v0.11.0 Feature Guide](docs/features/v0.11.0.md)
- [v0.7.0 Feature Guide](docs/features/v0.7.0.md)
- [v0.6.0 Feature Guide](docs/features/v0.6.0.md)
- [v0.5.0 Feature Guide](docs/features/v0.5.0.md)
- [v0.4.0 Feature Guide](docs/features/v0.4.0.md)

## Roadmap

| Milestone | Theme | Status |
|-----------|-------|--------|
| [v1.8.0](https://github.com/jmservera/aithena/milestone/22) | UI/UX improvements, design system | Complete |
| [v1.8.1](https://github.com/jmservera/aithena/milestone/24) | Bug fixes (search, stats, i18n, admin) | Complete |
| [v1.8.2](https://github.com/jmservera/aithena/milestone/25) | Legacy admin retirement, infra UI links | Complete |
| [v1.9.0](https://github.com/jmservera/aithena/milestone/23) | Authentication & user management | Complete |
| [v1.9.1](https://github.com/jmservera/aithena/milestone/28) | Docker build fix | Complete |
| [v1.10.0](https://github.com/jmservera/aithena/milestone/26) | User collections, metadata editing | Planned |
| [v1.10.1](https://github.com/jmservera/aithena/milestone/27) | BCDR backup/restore | Planned |

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
| **Embeddings Server** | Semantic search vectors | `intfloat/multilingual-e5-base` (768D) |
| **React/Vite Frontend** | Search UI with faceting, document management | `/` via nginx |
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

### Deployment Topologies

Aithena supports two SolrCloud deployment modes optimized for different scales:

- **SolrCloud Distributed (default)**: 3-node Solr cluster + 3-node ZooKeeper ensemble. Recommended for production (>3K books, high availability required).
- **Single-Node SolrCloud**: 1 Solr node + 1 ZooKeeper container via `docker/compose.single-node.yml`. Ideal for development, testing, and small deployments (<3K books, 32 GB RAM available).

See [**Deployment Topologies Guide**](docs/deployment-topologies.md) for detailed architecture, capacity planning, formulas, and migration paths between topologies.

## Quick Start

### 1. Run the first-run installer

Generate `.env`, create the auth database, and seed the initial admin user:

```bash
python3 -m installer
# or: python3 installer/setup.py
```

The installer guides you through:
1. **Environment** — Development or Production
2. **GPU detection** — auto-detects NVIDIA (`nvidia-smi`) and Intel (`/dev/dri`) GPUs, asks for confirmation
3. **SSL** — optional Let's Encrypt setup with domain prompt
4. **Book library path** — where your PDFs live
5. **Public origin** — auto-suggested based on SSL choice
6. **Admin credentials** — username and password

It writes `.env`, bootstraps the SQLite auth DB, and generates `./start.sh` with the correct `docker compose -f ...` chain for your configuration.

### 2. Start All Services

```bash
./start.sh
```

The generated `start.sh` combines the right compose files based on your installer choices. You can also run compose directly:

```bash
# Development (builds from source, debug ports exposed)
docker compose -f docker-compose.yml -f docker/compose.dev-ports.yml up -d --build

# Production (pre-built GHCR images)
docker compose -f docker-compose.yml -f docker/compose.prod.yml up -d

# Production + NVIDIA GPU
docker compose -f docker-compose.yml -f docker/compose.prod.yml -f docker/compose.gpu-nvidia.yml up -d

# Production + SSL
docker compose -f docker-compose.yml -f docker/compose.prod.yml -f docker/compose.ssl.yml up -d
```

Need automation instead of prompts? Run `python3 installer/setup.py --help` for non-interactive flags such as `--library-path`, `--admin-user`, `--admin-password`, `--origin`, `--environment`, `--gpu`, `--ssl`, and `--domain`.

### Compose File Layout

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Base services (always included) |
| `docker/compose.prod.yml` | Production — pre-built GHCR images |
| `docker/compose.dev-ports.yml` | Development — exposes debug ports |
| `docker/compose.gpu-nvidia.yml` | NVIDIA GPU acceleration |
| `docker/compose.gpu-intel.yml` | Intel GPU acceleration (OpenVINO) |
| `docker/compose.ssl.yml` | SSL/TLS with Let's Encrypt |
| `docker/compose.e2e.yml` | E2E test overrides |

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

When `docker compose up` loads `docker/compose.dev-ports.yml` (the default local workflow), these direct debug ports are also available:

| Service | Port(s) | Purpose |
|---------|---------|---------|
| solr-search | `8080` | Direct FastAPI debugging without nginx |
| solr / solr2 / solr3 | `8983`, `8984`, `8985` | Solr admin/API access per node |
| rabbitmq | `5672`, `15672` | AMQP clients and direct management UI |
| redis | `6379` | Redis CLI and direct state inspection |
| redis-commander | `8081` | Direct Redis Commander UI |
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
docker compose -f docker-compose.yml -f docker/compose.e2e.yml up -d
```

The override (`docker/compose.e2e.yml`) mounts `E2E_LIBRARY_PATH` as the document library instead of `/home/jmservera/booklibrary`, so the test run is fully isolated from the real corpus. It also sets the document-lister poll interval to 10 seconds for faster feedback.

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

Current branch: `dev`

## Release Process Overview

### Preflight Checks

Before tagging a release, verify:

1. **Tests pass locally:**
   ```bash
   cd src/solr-search && uv run pytest -v --tb=short
   cd src/document-indexer && uv run pytest -v --tb=short
   cd src/aithena-ui && npm run build && npx vitest run
   ```

2. **Docker Compose validates:**
   ```bash
   python3 -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"
   ```

3. **E2E suite passes:**
   ```bash
   export E2E_LIBRARY_PATH=/tmp/aithena-e2e-library && mkdir -p "$E2E_LIBRARY_PATH"
   docker compose -f docker-compose.yml -f docker/compose.e2e.yml up -d
   cd e2e && pip install -r requirements.txt && pytest
   ```

### Documentation Requirements

Every release must include:

- **Release Notes** (`docs/release-notes-v1.x.y.md`) — Feature summary and breaking changes
- **Test Report** (`docs/test-report-v1.x.y.md`) — Test counts and coverage
- **User/Admin Manual Updates** (`docs/user-manual.md`, `docs/admin-manual.md`) — Updated instructions for new features
- **README.md Updates** — Feature list and links to new documentation

Documentation must be **committed to `dev` before the release tag is created**.

### Cutting the Release

1. **Ensure `dev` is up to date and clean:**
   ```bash
   git checkout dev && git pull origin dev && git status
   ```

2. **Update VERSION file** (if not already set):
   ```bash
   echo "1.x.y" > VERSION && git add VERSION && git commit -m "Version bump: v1.x.y"
   ```

3. **Tag the release:**
   ```bash
   git tag -a v1.x.y -m "Release v1.x.y: {summary}" && git push origin v1.x.y
   ```

4. **Merge to `main` (production):**
   ```bash
   git checkout main && git pull origin main
   git merge dev
   git push origin main
   ```

5. **Publish GitHub release** (manual or via CI):
   ```bash
   gh release create v1.x.y --target main --notes-file docs/release-notes-v1.x.y.md
   ```

### Rollback

If a release needs to be rolled back:

1. **Create a hotfix branch from `main`:**
   ```bash
   git checkout main && git pull origin main
   git checkout -b squad/{issue}-hotfix-{slug}
   ```

2. **Fix and test locally**, then open a PR against `main`.

3. **After merge, cherry-pick the fix to `dev`:**
   ```bash
   git checkout dev && git pull origin dev
   git cherry-pick {commit-sha}
   git push origin dev
   ```

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
- [multilingual-e5-base](https://huggingface.co/intfloat/multilingual-e5-base)
