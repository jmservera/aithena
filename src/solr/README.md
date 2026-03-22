# Solr Configuration for Aithena Books Collections

This directory contains the SolrCloud configsets for the Aithena book search collections.

## Configsets

### `books` (baseline)
The original configset using `distiluse-base-multilingual-cased-v2` with 512-dimensional vectors.

### `books_e5base` (A/B test candidate)
A copy of the `books` configset modified for `multilingual-e5-base` with 768-dimensional vectors.
Created as part of the embedding model A/B test (PRD: `docs/prd/embedding-model-ab-test.md`, P1-2).
All non-vector fields are identical to `books`; only the vector field type and dimension differ.

| Property | `books` | `books_e5base` |
|----------|---------|----------------|
| Embedding model | distiluse-base-multilingual-cased-v2 | multilingual-e5-base |
| Vector dimensions | 512 | 768 |
| Field type | `knn_vector_512` | `knn_vector_768` |
| Similarity | cosine (HNSW) | cosine (HNSW) |
| Collection name | `books` | `books_e5base` |

## Files (per configset)

- `managed-schema.xml` — Solr schema with field definitions and analyzers
- `solrconfig.xml` — Request handlers, indexing settings, Tika extraction config
- `lang/` — Language-specific stopwords for multilingual search
- `synonyms.txt` — Optional query-time synonyms

## Key Schema Features

### Field Types

- **String fields** (`*_s`): Exact-match, not tokenized. Use for author, category, language codes.
- **Text fields** (`*_t`): Analyzed, tokenized. Use for title, content. Supports multilingual analyzers.
- **Integer/Long fields** (`*_i`, `*_l`): Year, page count, file size.
- **`knn_vector_512`**: Dense 512-dimensional vector field (HNSW, cosine similarity). Used for Phase 3 embedding search in the `books` collection.
- **`knn_vector_768`**: Dense 768-dimensional vector field (HNSW, cosine similarity). Used for A/B test embedding search in the `books_e5base` collection.
- **_text_** (default field): Catch-all for full-text search. Fed by `copyField` from `title_t`, `author_t`, `content`.

### Book-Specific Fields

| Field | Type | Indexed | Stored | Purpose |
|-------|------|---------|--------|---------|
| `id` | string | Yes | Yes | Unique doc ID (file hash or path) |
| `title_s` | string | Yes | Yes | Book title (exact) |
| `title_t` | text | Yes | No | Book title (analyzed, copied to _text_) |
| `author_s` | string | Yes | Yes | Author name (exact) |
| `author_t` | text | Yes | No | Author name (analyzed, copied to _text_) |
| `content` | text | Yes | Yes | Full PDF text body (highlighted) |
| `year_i` | int | Yes | Yes | Publication year |
| `page_count_i` | int | Yes | Yes | Number of pages |
| `file_size_l` | long | Yes | Yes | File size in bytes |
| `file_path_s` | string | Yes | Yes | Relative path (e.g., `amades/book.pdf`) |
| `folder_path_s` | string | Yes | Yes | Folder path (e.g., `amades`) |
| `category_s` | string | Yes | Yes | Inferred category/series |
| `language_detected_s` | string | Yes | Yes | Auto-detected language code |
| `book_embedding` | knn_vector_512 / knn_vector_768 | Yes | Yes | Dense embedding for semantic kNN search — 512-dim in `books`, 768-dim in `books_e5base` |
| `_text_` | text | Yes | No | Default query field (copyField from title_t, author_t) |

### Analyzers

**Multilingual support** via language-specific field types and stopwords:

- `text_es` — Spanish (stopwords, accent handling)
- `text_ca` — Catalan
- `text_fr` — French
- `text_en` — English

Default `text_t` analyzer uses standard tokenization + lowercase.

## Tika Extraction

The `/update/extract` handler is configured to:

- Extract text from PDF binaries
- Populate `content` field with extracted body text
- Pass `literal.*` parameters as document fields (title_s, author_s, year_i, etc.)

### Example POST

```bash
curl -X POST \
  http://localhost:8983/solr/books/update/extract \
  -F "myfile=@/path/to/book.pdf" \
  -F "literal.title_s=My Book Title" \
  -F "literal.author_s=John Doe" \
  -F "literal.year_i=2020" \
  -F "literal.language_detected_s=en" \
  -F "commit=true"
```

## Phase 3: Embeddings and kNN Semantic Search

### Embedding Model

ADR-004 standardises on **`distiluse-base-multilingual-cased-v2`** (512-dimensional vectors,
multilingual, sentence-transformers family). This model is served by the `embeddings-server`
service on port **8008**.

### Indexing Embeddings

The embedding pipeline (app-side) generates a 512-float vector for each book's representative
text (e.g. title + first N content chunks) and POSTs it alongside the other fields:

```bash
# Index a book with its embedding (JSON update)
curl -X POST \
  http://localhost:8983/solr/books/update?commit=true \
  -H "Content-Type: application/json" \
  -d '[{
    "id": "amades/book.pdf",
    "title_s": "My Book",
    "author_s": "Joan Amades",
    "book_embedding": [0.1, -0.05, 0.32, ...]
  }]'
```

The `book_embedding` field must receive exactly 512 floats. Omit the field for documents
where no embedding is available; they will be excluded from kNN results but still match
full-text queries.

### kNN Search

Use the **`/knn`** request handler (or the `{!knn}` QParser in `/select`/`/query`) to find
the *k* nearest neighbours to a query vector.

#### Dedicated `/knn` handler

```bash
# Find 10 books most similar to a query embedding
curl "http://localhost:8983/solr/books/knn?q={!knn f=book_embedding topK=10}[0.1,-0.05,0.32,...]"
```

#### Hybrid search (full-text + semantic re-ranking)

Combine BM25 full-text results with kNN re-ranking inside a single `/select` query using
Solr's `rq` (re-rank) parameter:

```bash
curl "http://localhost:8983/solr/books/select" \
  --get \
  --data-urlencode "q=catalan folklore" \
  --data-urlencode "rq={!rerank reRankQuery={!knn f=book_embedding topK=100}[0.1,-0.05,0.32,...] reRankDocs=100 reRankWeight=2}" \
  --data-urlencode "rows=10"
```

This keeps the BM25 ordering for the top results while boosting documents whose embeddings
are close to the query vector. Adjust `reRankWeight` to balance keyword vs. semantic signal.

#### Filtering kNN results by metadata

Apply standard Solr filter queries alongside kNN to restrict the candidate set:

```bash
curl "http://localhost:8983/solr/books/knn" \
  --get \
  --data-urlencode "q={!knn f=book_embedding topK=10}[0.1,-0.05,...]" \
  --data-urlencode "fq=language_detected_s:ca" \
  --data-urlencode "fq=year_i:[1900 TO *]"
```

### Generating Query Embeddings

Call the `embeddings-server` to turn a user query into a 512-float vector:

```bash
curl -X POST http://localhost:8008/v1/embeddings/ \
  -H "Content-Type: application/json" \
  -d '{"input": "catalan folklore stories"}'
```

The response `data[0].embedding` array is the vector to pass to the kNN query.

## Deployment

### Create Collection

```bash
# Via Solr Admin UI (http://localhost:8983)
# or CLI (if Solr tools are installed):
docker exec solr solr create_collection \
  -c books \
  -d /path/to/configset/books
```

### Update Configset

Changes to `managed-schema.xml` or `solrconfig.xml` can be uploaded without redeploying:

```bash
docker exec solr solr config-set-upload \
  -zkhost zoo1:2181,zoo2:2181,zoo3:2181 \
  -n books \
  -d /path/to/configset/books
```

(Requires Solr to be reloaded on each node.)

## Tuning Tips

1. **Highlighting**: Configured to use `content` as alternate field for `_text_` queries. This shows snippets from the actual extracted PDF body.
2. **Faceting**: Add `facet=true&facet.field=author_s&facet.field=category_s&facet.field=language_detected_s` to `/select` queries.
3. **Sorting**: Use `sort=year_i desc` or `sort=title_s asc` for result ordering.
4. **Pagination**: Use `start=0&rows=20` for 20 results per page.
5. **kNN topK**: Set `topK` ≥ `rows` on the kNN QParser. A value of 100–200 is a good starting point for re-ranking hybrid searches.
6. **HNSW tuning**: The default HNSW parameters (`hnswMaxConnections=16`, `hnswBeamWidth=100`) suit collections up to ~1 M vectors. Increase `hnswMaxConnections` (e.g. 32) for higher recall at the cost of more memory.

## References

- [Solr Schema](https://solr.apache.org/docs/latest/schema-elements-intro.html)
- [Solr Dense Vector Search](https://solr.apache.org/docs/latest/query-guide/dense-vector-search.html)
- [Tika Integration](https://solr.apache.org/docs/latest/indexing-and-basic-data-operations.html#indexing-binary-documents)
- [Solr Dense Vector Search (kNN)](https://solr.apache.org/docs/latest/query-guide/dense-vector-search.html)

---

## Phase 3 — Dense Vector Field (`book_embedding`)

The `book_embedding` field (type `knn_vector_512`, 512-dim cosine similarity, HNSW index) is used
for semantic and hybrid search.

- **Type:** `solr.DenseVectorField` with `vectorDimension=512`, `similarityFunction=cosine`
- **Indexing:** The document-indexer chunks each PDF post-Tika and calls the embeddings server
  (`distiluse-base-multilingual-cased-v2`) to populate the `book_embedding` field (ADR-004).
- **Query syntax:** `{!knn f=book_embedding topK=10}[0.1,0.2,...,0.512]`

---

## Search API — Mode Behaviour

The `solr-search` FastAPI service (`src/solr-search/main.py`) wraps this Solr collection and
supports three search modes via the `?mode=` query parameter.

### `keyword` (default, backward-compatible)

- Queries Solr using the **Extended DisMax** (`edismax`) query parser.
- Fields boosted: `title_t^2`, `author_t^1.5`, `_text_`.
- **Facets** — populated from `author_s`, `category_s`, `language_detected_s`, `year_i`.
- **Highlights** — populated from the `content` field using Solr's Unified Highlighter.
- **Pagination** — use `?page=N&page_size=N` (maps to Solr `start`/`rows`).
- **Filtering** — `?fq_author=`, `?fq_category=`, `?fq_language=`, `?fq_year=`.

### `semantic`

- Encodes the query via the embeddings server (`distiluse-base-multilingual-cased-v2`).
- Queries Solr with `{!knn f=book_embedding topK=N}[vec...]` for nearest-neighbour retrieval.
- **Facets** — empty (Solr kNN does not aggregate facets in the same pass); returned as
  empty lists in the `facets` object.
- **Highlights** — empty (`[]` per result); no snippet extraction is performed.
- **Pagination** — controlled by `?page_size=N`; cursor pagination is not supported.

### `hybrid`

- Runs keyword (BM25) and semantic (kNN) searches concurrently
  (`candidate_limit = max(page_size*2, 20)` per leg).
- Fuses results using **Reciprocal Rank Fusion** (RRF, `k=60` by default).
- **Facets** — sourced from the keyword (BM25) leg only; semantic-only hits will not
  have facet coverage.
- **Highlights** — sourced from the keyword (BM25) leg only; results that appear only
  in the semantic leg will have empty `highlights` arrays.
- **Pagination** — truncated to `?page_size=N` after RRF fusion; no offset pagination.
- `RRF_K` can be tuned via the `RRF_K` environment variable (default `60`).

### Normalised Response Shape

All three modes return the same JSON envelope so the UI can consume them uniformly:

```json
{
  "query": "search text",
  "mode": "keyword | semantic | hybrid",
  "page": 1,
  "page_size": 10,
  "total_results": 42,
  "total_pages": 5,
  "sort": {"by": "score", "order": "desc"},
  "results": [
    {
      "id": "...",
      "score": 0.95,
      "title": "Book Title",
      "author": "Author Name",
      "year": 2020,
      "file_path": "amades/book.pdf",
      "folder_path": "amades",
      "category": "History",
      "language": "ca",
      "page_count": 320,
      "file_size": 5242880,
      "highlights": ["...relevant snippet..."],
      "document_url": "http://host/documents/encoded-token"
    }
  ],
  "facets": {
    "author":   [{"value": "Author A", "count": 5}],
    "category": [{"value": "History",  "count": 3}],
    "language": [],
    "year":     []
  }
}
```

- [Multilingual Search](https://solr.apache.org/docs/latest/language-analyzers.html)