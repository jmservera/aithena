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
| **Solr Search API** | FastAPI wrapper around the `books` collection | Normalized results, facets, highlights, PDF document URLs |
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
- Document Lister, Document Indexer, Solr Search API, Embeddings Server
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
| Search API | http://localhost:8080/search?q=historia | Query books with facets, pagination, sorting, and highlights |
| RabbitMQ Admin | http://localhost:15672 | Monitor queue depth |
| Redis CLI | `redis-cli` | Check `processed` & `failed` keys |
| Streamlit Admin | http://localhost:8501 | Document management (development) |

## Solr Schema & Fields

See [`solr/README.md`](solr/README.md) for schema design details. The FastAPI service in `solr-search/` exposes `/search`, `/facets`, and client-safe `/documents/{token}` URLs against these fields. Key fields:

- `title_s`, `title_t` — Book title (string + text)
- `author_s`, `author_t` — Author (string + text)
- `year_i` — Publication year
- `content` — Full-text PDF body (stored, highlighted)
- `language_detected_s` — Auto-detected language (es, ca, fr, en, etc.)
- `file_path_s`, `folder_path_s` — Relative paths for tracking
- `category_s` — Inferred from folder hierarchy
- `_text_` — Default query field (includes title, author, content)

## Search Query Syntax

The `/search` and `/facets` endpoints pass the `q` parameter straight to Solr using `defType=edismax`, with `_text_` as the default query field. That gives you standard Lucene/Solr query syntax with the more forgiving edismax parser.

- **Default field:** `_text_`
- **General search scope:** full text, plus copied title/author text in the Solr catch-all field
- **Match all documents:** empty query, `*`, or `*:*`
- **Not allowed in `q`:** Solr local-parameter syntax such as `{!knn ...}` (keyword search rejects it intentionally; use `mode=semantic` or `mode=hybrid` instead)

### Field names to use in queries

Use the real Solr field names when you want field-specific queries:

| Field | Meaning | Notes |
|-------|---------|-------|
| `title_s` | exact stored title | Best for exact title matches |
| `title_t` | analyzed title text | Useful when title text is indexed separately |
| `author_s` | exact stored author | Quote multi-word values, e.g. `author_s:"Medicina Balear"` |
| `author_t` | analyzed author text | Useful when author text is indexed separately |
| `category_s` | exact category | Real examples: `Balearics`, `BSAL`, `UIB` |
| `year_i` | numeric publication year | Use this for numeric/range queries |
| `language_detected_s` / `language_s` | language code | Values like `es`, `ca`, `fr`, `en` |
| `content` | extracted PDF body text | Full-text field |
| `_text_` | Solr catch-all field | Default search field |

> `title:folklore`, `author:amades`, `category:balearics`, and `year:[1900 TO 1950]` are the human-friendly Lucene examples you may know from Solr docs, but in this API you should use the real field names above: for example `title_t:folklore`, `author_s:Amades`, `category_s:Balearics`, and `year_i:[1900 TO 1950]`.

### Supported query patterns

#### 1. Basic search

```text
folklore
```

Finds documents containing the word in the default `_text_` field.

#### 2. Phrase search

```text
"catalan folklore"
```

Matches the exact phrase.

#### 3. Boolean operators

```text
folklore AND catalan
folklore OR traditions
folklore NOT modern
```

Use uppercase `AND`, `OR`, and `NOT` for clarity.

#### 4. Fuzzy search

```text
folklre~
folklore~2
```

Useful for OCR noise, old spellings, and typos in historical texts.

#### 5. Proximity search

```text
"catalan traditions"~5
```

Matches documents where the words appear within 5 words of each other.

#### 6. Wildcards

```text
folk*
fol?lore
```

- `*` matches multiple trailing characters
- `?` matches a single character

#### 7. Field-specific search

```text
title_t:folklore
author_s:Amades
author_s:"Medicina Balear"
category_s:Balearics
category_s:BSAL
```

Notes:
- `*_s` fields are exact/string fields, so case and full value matter more
- Quote multi-word string values such as `author_s:"Medicina Balear"`
- `category_s:Balearics` and `category_s:BSAL` are practical examples from the current collection

#### 8. Range queries

```text
year_i:[1900 TO 1950]
year_i:[1900 TO *]
```

Use `year_i` for numeric year ranges.

#### 9. Boosting

```text
folklore^2 traditions
```

Boosts matches on `folklore` so they rank higher.

#### 10. Grouping

```text
(folklore OR traditions) AND catalan
```

Parentheses control evaluation order.

#### 11. Negation

```text
-modern
```

Excludes documents containing that term.

#### 12. Escaping special characters

Escape special Lucene characters with a backslash when you want a literal value:

```text
+ - && || ! ( ) { } [ ] ^ " ~ * ? : \ /
```

Examples:

```text
author_s:"Medicina Balear"
content:folklore\:balear
```

### Practical collection examples

```text
author_s:Amades
category_s:Balearics
category_s:BSAL
author_s:"Medicina Balear" AND year_i:[2010 TO 2014]
```

### Search tips

- The collection is **multilingual**: Spanish, Catalan, French, and English can all appear in the same index.
- Many books are **old or OCR-heavy**, so fuzzy queries such as `amads~` or `folklre~` can recover variant spellings.
- If you are calling the HTTP API directly, remember to **URL-encode** quotes, spaces, backslashes, and other special characters.

## Development

### Development Setup

This project uses [**uv**](https://docs.astral.sh/uv/) for Python dependency management across all backend services. `uv` replaces `pip` + `requirements.txt` with a fast, reproducible workflow backed by `pyproject.toml` and a locked `uv.lock` file.

#### 1. Install uv

```bash
# macOS / Linux (standalone installer)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Homebrew
brew install uv

# pip (if you already have Python)
pip install uv
```

See the [uv installation docs](https://docs.astral.sh/uv/getting-started/installation/) for more options.

#### 2. Install dependencies for a service

Each Python service (`document-indexer`, `document-lister`, `solr-search`, `admin`, etc.) has a `pyproject.toml` and a `uv.lock` lockfile. To install all dependencies:

```bash
cd <service-directory>   # e.g. cd document-indexer
uv sync                  # installs runtime + dev deps from uv.lock
```

To install runtime dependencies only (no dev tools):

```bash
uv sync --no-dev
```

#### 3. Run tests with uv

```bash
cd document-indexer
uv run python -m pytest tests/ -v

cd solr-search
uv run python -m pytest tests/ -v
```

#### 4. Run any command in the uv-managed environment

```bash
uv run python main.py
uv run ruff check .
```

#### Note: requirements.txt deprecation

> ⚠️ The `requirements.txt` files in each service directory are **deprecated** and will be removed once the `uv` migration is complete. They are kept temporarily for backward compatibility. **New development should use `uv sync` instead of `pip install -r requirements.txt`.**

Services **not** migrated to `uv` (custom base images): `embeddings-server`, `llama-base`.

#### References

- [uv documentation](https://docs.astral.sh/uv/)
- [uv project structure](https://docs.astral.sh/uv/concepts/projects/)
- [pyproject.toml reference](https://docs.astral.sh/uv/reference/pyproject/)

### Testing

```bash
cd document-indexer
python3 -m pytest tests/ -v
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
- Adjust the scan frequency via the `POLL_INTERVAL` environment variable (default: `60` seconds)

### Document Lister Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `POLL_INTERVAL` | `60` | Seconds between library scans. New and modified files are re-queued; unchanged processed files are skipped. |
| `BASE_PATH` | `/data/documents/` | Root directory to scan for documents. |
| `DOCUMENT_WILDCARD` | `*` | Glob pattern for files to consider. |
| `QUEUE_NAME` | `new_documents` | RabbitMQ queue name for discovered documents. |

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
