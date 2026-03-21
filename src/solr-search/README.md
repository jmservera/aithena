# solr-search

FastAPI service providing the search API for Aithena. Handles keyword (BM25),
semantic (kNN), and hybrid (RRF fusion) search over the Solr book collection.

## Quick Start

```bash
uv sync --frozen
uv run uvicorn main:app --host 0.0.0.0 --port 8080
```

## Tests & Linting

```bash
uv run pytest -v --tb=short
uv run ruff check .
```

## Search Modes

| Mode | Method | Targets |
|------|--------|---------|
| `keyword` | BM25 via edismax on `_text_` | Parent (book) documents |
| `semantic` | kNN on `embedding_v` | Chunk documents |
| `hybrid` | RRF fusion of keyword + semantic | Both, then merged |

## Data Model

The Solr collection contains two types of documents: **parent** (book metadata)
and **chunk** (text fragments with embeddings). Understanding this relationship
is critical for writing correct search queries.

> 📖 **Full documentation:** [`docs/architecture/solr-data-model.md`](../../docs/architecture/solr-data-model.md)
>
> Key points:
> - Embeddings (`embedding_v`) live on **chunk** documents only.
> - kNN queries must target chunks — never apply `EXCLUDE_CHUNKS_FQ` to kNN.
> - Results are de-duplicated to book level after retrieval.

## Configuration

Key environment variables (see `config.py` for full list):

| Variable | Default | Description |
|----------|---------|-------------|
| `SOLR_URL` | `http://solr1:8983/solr` | Solr base URL |
| `SOLR_COLLECTION` | `books` | Collection name |
| `KNN_FIELD` | `embedding_v` | Dense vector field for kNN |
| `RRF_K` | `60` | RRF damping constant |
| `EMBEDDINGS_URL` | `http://embeddings-server:8085/v1/embeddings/` | Embeddings endpoint |
| `EMBEDDINGS_TIMEOUT` | `120` | Embeddings request timeout (seconds) |
