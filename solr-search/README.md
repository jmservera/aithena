# Aithena Solr Search API

FastAPI service that wraps the SolrCloud `/select` endpoint and exposes a clean,
normalised JSON search API for the Aithena book library.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness probe — returns `{"status": "ok"}` |
| `GET` | `/search` | Full-text search over the Solr `books` collection |

### `/search` query parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | **required** | Full-text search query (min length 1) |
| `rows` | int | `10` | Results per page (1–100) |
| `start` | int | `0` | Pagination offset (≥ 0) |
| `facet` | bool | `true` | Include facet counts in the response |

### Response shape

```json
{
  "query": "Barcelona",
  "pagination": { "total": 42, "rows": 10, "start": 0 },
  "results": [
    {
      "id": "books/amades/...",
      "title": "Auca dels costums de Barcelona",
      "author": "Amades",
      "year": 1950,
      "category": "folklore",
      "language": "ca",
      "file_path": "amades/Auca dels costums de Barcelona amades.pdf",
      "document_url": "/api/documents/amades/Auca dels costums de Barcelona amades.pdf"
    }
  ],
  "facets": {
    "category_s": { "folklore": 3, "history": 1 },
    "author_s":   { "Amades": 3 },
    "language_detected_s": { "ca": 2, "es": 2 }
  },
  "highlights": {
    "books/amades/...": {
      "content": ["costums de <em>Barcelona</em> és una obra"],
      "_text_": ["Auca dels costums de <em>Barcelona</em>"]
    }
  }
}
```

## Running locally (Docker Compose)

```bash
docker compose up solr-search
```

The service starts on port **8080**.

## Configuration

Environment variables (all optional, defaults shown):

| Variable | Default | Description |
|----------|---------|-------------|
| `SOLR_HOST` | `solr1` | SolrCloud hostname |
| `SOLR_PORT` | `8983` | SolrCloud port |
| `SOLR_COLLECTION` | `books` | Solr collection name |
| `DOCUMENT_BASE_URL` | `/api/documents` | URL prefix for `document_url` field |
| `PORT` | `8080` | Port the service listens on |

## Running the API tests

The test suite uses **pytest** and mocks all Solr I/O — no live Solr instance or
book library is required.

```bash
# Install test dependencies (once)
pip install fastapi httpx pytest

# Run all contract tests
cd solr-search
python -m pytest tests/ -v
```

Tests are organised into sections:

- **`/health`** — liveness check
- **Successful search** — field normalisation, `document_url`, all response keys
- **Pagination metadata** — `total`, `rows`, `start`
- **Facets** — presence, expected fields, positive int counts, opt-out via `facet=false`
- **Highlights** — presence and snippet structure
- **Empty results** — zero total, empty lists
- **Request validation** — missing/empty `q`, out-of-range `rows`/`start` → HTTP 422
- **Upstream failures** — Solr HTTP 500 and network errors → HTTP 502
