---
name: "solr-parent-chunk-model"
description: "Parent/chunk document architecture in aithena's Solr schema — field ownership, kNN targeting rules, and filter correctness"
domain: "search, solr, data-model"
confidence: "high"
source: "earned — extracted from retro R2 incident (PR #701/#723), schema review, search_service.py analysis"
author: "Ash"
created: "2026-03-21"
last_validated: "2026-03-21"
---

## Context
Apply this skill when modifying Solr queries, adding schema fields, changing search modes, or reviewing PRs that touch `search_service.py`, `managed-schema.xml`, or document-indexer chunking logic. The parent/chunk split is the most common source of correctness bugs in this project.

## Patterns

### 1. Two document types share one Solr collection

**Parent documents (books):**
- `id` = SHA-256 of file path (unique per book)
- Metadata: `title_s/t`, `author_s/t`, `year_i`, `category_s`, `series_s`, `language_detected_s`, `file_path_s`, `folder_path_s`, `page_count_i`, `file_size_l`
- Optional: `book_embedding` (512D) for book-level similarity
- **No `parent_id_s` field** — this is how you identify a parent

**Chunk documents (text fragments):**
- `id` = `{parent_id}_chunk_{index}` (index is zero-padded, e.g. `{parent_id}_chunk_0000`)
- `parent_id_s` = parent book's `id` (foreign key)
- `chunk_text_t` = extracted text (400 words, 50-word overlap, page-aware)
- `embedding_v` = 512D dense vector (HNSW cosine) — **primary kNN search field**
- `chunk_index_i`, `page_start_i`, `page_end_i` for positioning
- Inherits parent metadata for display (title, author, year, etc.)

### 2. Filter rules differ by search mode

**Keyword (BM25):**
- Apply `EXCLUDE_CHUNKS_FQ = "-parent_id_s:[* TO *]"` to return only parent documents
- Chunks would pollute keyword results with fragment-level matches

**Semantic (kNN):**
- Do NOT apply chunk exclusion — kNN MUST target chunk documents (they carry `embedding_v`)
- Results are deduplicated at book level after retrieval

**Hybrid (RRF):**
- BM25 leg: apply chunk exclusion (parents only)
- kNN leg: no chunk exclusion (chunks only)
- RRF fusion merges both, deduplicates at book level

### 3. Adding new fields — which document type?

| Field purpose | Add to parent? | Add to chunk? | Why |
|---------------|---------------|---------------|-----|
| Book metadata (author, year) | Yes | Copy from parent | Chunks need it for display after kNN |
| Full-text search field | Yes (via Tika) | No (use chunk_text_t) | Tika extracts to parent; chunks have own text |
| Dense vector embedding | Optional (book_embedding) | Yes (embedding_v) | kNN searches chunks, not parents |
| Facet field | Yes | Not needed | Facets come from BM25 leg (parents only) |

### 4. ID generation
- Parent: `hashlib.sha256(file_path.encode()).hexdigest()`
- Chunk: `f"{parent_id}-chunk-{chunk_index}"`
- Deleting a book must delete parent AND all chunks with matching `parent_id_s`

## Anti-Patterns

- **Never apply `EXCLUDE_CHUNKS_FQ` to kNN queries** — this silently returns zero results since chunks are the only documents with embeddings. (Source: PR #701 incident)
- **Never assume parent documents have embeddings** — `book_embedding` is optional; `embedding_v` on chunks is the primary vector field.
- **Never add a new field to only one document type without considering search modes** — if the field is needed for display in semantic results, it must exist on chunks too.
- **Never delete a parent without also deleting its chunks** — orphaned chunks waste index space and pollute kNN results.

## Examples

### Correct: kNN query targeting chunks
```python
params = {
    "q": "{!knn f=embedding_v topK=10}[0.5, -0.2, ...]",
    # NO fq excluding chunks — chunks ARE the target
}
```

### Correct: BM25 query excluding chunks
```python
params = {
    "q": "search terms",
    "defType": "edismax",
    "fq": ["-parent_id_s:[* TO *]"],  # parents only
}
```

### Correct: Delete book and its chunks
```python
solr.delete(q=f'id:"{book_id}" OR parent_id_s:"{book_id}"')
solr.commit()
```

## References
- `docs/architecture/solr-data-model.md` — full architecture reference
- `src/solr-search/search_service.py` — EXCLUDE_CHUNKS_FQ constant and usage
- `src/solr/books/managed-schema.xml` — field definitions
- `src/solr-search/README.md` — data model summary
