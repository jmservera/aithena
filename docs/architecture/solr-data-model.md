# Solr Data Model: Parent & Chunk Documents

> **Why this document exists:** During v1.10.0 development, PR #701 nearly broke
> semantic search because the implementer didn't understand that embeddings live
> on *chunk* documents, not on parent (book) documents. This reference prevents
> that class of bug from recurring.

## Overview

Aithena indexes books into **two types** of Solr documents within the same
collection:

| Document type | Purpose | Has embeddings? | Identified by |
|---------------|---------|-----------------|---------------|
| **Parent** | Book metadata (title, author, path, …) | ❌ No | `id` (SHA-256 of file path) |
| **Chunk** | Text fragment + embedding vector | ✅ Yes | `id` = `{parent_id}_chunk_{NNNN}` |

Chunks are linked to their parent via the `parent_id_s` field.

```
┌──────────────────────────────────┐
│  Parent document (book)          │
│  id: "a1b2c3…"                   │
│  title_s, author_s, year_i, …   │
│  (NO embedding_v)                │
└──────────┬───────────────────────┘
           │ parent_id_s = "a1b2c3…"
     ┌─────┼─────────┐
     ▼     ▼         ▼
  ┌──────┐ ┌──────┐ ┌──────┐
  │Chunk │ │Chunk │ │Chunk │
  │ 0000 │ │ 0001 │ │ 0002 │  …
  │emb_v │ │emb_v │ │emb_v │
  └──────┘ └──────┘ └──────┘
```

---

## Parent Documents (Book Metadata)

Created by `document-indexer` during **Phase 1** (text extraction via Solr
Tika's `/update/extract` handler).

### Fields

| Field | Solr Type | Description |
|-------|-----------|-------------|
| `id` | `string` | **Primary key.** SHA-256 hash of the file path. |
| `title_s` | `string` | Book title (exact match). |
| `title_t` | `text_general` | Book title (full-text, copied to `_text_`). |
| `author_s` | `string` | Author name (exact match). |
| `author_t` | `text_general` | Author name (full-text, copied to `_text_`). |
| `year_i` | `pint` | Publication year. |
| `page_count_i` | `pint` | Total page count. |
| `file_path_s` | `string` | Absolute path to the source file. |
| `folder_path_s` | `string` | Folder path (used for folder facet). |
| `file_size_l` | `plong` | File size in bytes. |
| `category_s` | `string` | Category label. |
| `language_detected_s` | `string` | Language detected by Solr langid. |
| `series_s` | `string` | Series name. |

**Key point:** Parent documents do **not** contain an `embedding_v` field or a
`parent_id_s` field.

### How to distinguish parents from chunks

```
EXCLUDE_CHUNKS_FQ = "-parent_id_s:[* TO *]"
```

Any document that has `parent_id_s` set is a chunk. Documents without it are
parents. The filter query above (defined in `search_service.py`) excludes
chunks from a result set, leaving only parent documents.

---

## Chunk Documents (Text + Embeddings)

Created by `document-indexer` during **Phase 2** (chunking & embedding).

### Fields

| Field | Solr Type | Description |
|-------|-----------|-------------|
| `id` | `string` | `{parent_id}_chunk_{NNNN}` (zero-padded index). |
| `parent_id_s` | `string` | **Foreign key** → parent document `id`. |
| `chunk_index_i` | `pint` | Sequential position of this chunk (0-based). |
| `chunk_text_t` | `text_general` | The chunk's text content. |
| `embedding_v` | `knn_vector_512` | 512-dimensional dense vector (HNSW, cosine). |
| `page_start_i` | `pint` | First page this chunk spans. |
| `page_end_i` | `pint` | Last page this chunk spans. |
| `title_s` | `string` | Inherited from parent (for display without join). |
| `author_s` | `string` | Inherited from parent. |
| `file_path_s` | `string` | Inherited from parent. |
| `folder_path_s` | `string` | Inherited from parent. |

Chunks also carry optional metadata fields (`category_s`, `year_i`,
`language_detected_s`) copied from the parent so that facet filters can be
applied directly to kNN results without a Solr join.

### Chunking strategy

| Parameter | Default | Env var |
|-----------|---------|---------|
| Chunk size | 400 words | `CHUNK_SIZE` |
| Overlap | 50 words | `CHUNK_OVERLAP` |

Chunking is **word-based** (not character-based). Each chunk tracks the page
range it spans (`page_start_i`, `page_end_i`). The overlap ensures context is
not lost at chunk boundaries.

### Embedding generation

Each chunk's text is sent to the **embeddings-server** (`POST /v1/embeddings/`),
which returns a 512-dimensional vector using the
`distiluse-base-multilingual-cased-v2` model. The vector is stored in the
`embedding_v` field, which is configured as a `DenseVectorField` with HNSW
indexing and cosine similarity.

---

## Search Flow

### Keyword search (BM25)

```
User query
    → edismax parser on _text_ field
    → fq: EXCLUDE_CHUNKS_FQ  (parent docs only)
    → returns parent documents with highlights
```

Keyword search queries **parent documents only**. The `EXCLUDE_CHUNKS_FQ`
filter (`-parent_id_s:[* TO *]`) removes all chunk documents from the result
set. Highlighting uses the unified highlighter on `_text_`.

### Semantic search (kNN)

```
User query
    → embeddings-server → 512-dim vector
    → {!knn f=embedding_v topK=N} on chunk documents
    → returns chunk documents (with parent metadata)
    → normalize_book() maps chunk fields to book-level response
```

Semantic search queries **chunk documents** because that is where `embedding_v`
lives. The kNN query naturally targets chunks — there is no need (and it would
be **wrong**) to apply `EXCLUDE_CHUNKS_FQ` to the kNN leg.

Each chunk carries inherited parent metadata (`title_s`, `author_s`, etc.) so
results can be displayed without an additional join.

### Hybrid search (RRF fusion)

```
                ┌─── BM25 leg ──────────────────────┐
User query ─────┤                                    ├─→ RRF fusion → ranked results
                └─── kNN leg (via embeddings-server) ┘
```

1. **BM25 leg:** Keyword search on parent documents (with `EXCLUDE_CHUNKS_FQ`).
2. **kNN leg:** Semantic search on chunk documents (without `EXCLUDE_CHUNKS_FQ`).
3. **Fusion:** `reciprocal_rank_fusion()` merges both result lists using RRF
   scores (`1 / (k + rank)`, default `k=60`). Documents appearing in both legs
   score higher.

The BM25 leg provides highlights and facet counts; the kNN leg does not produce
Solr-style facets or highlights.

### Collection statistics

The `/stats` endpoint uses Solr grouping by `parent_id_s` to count distinct
books (as opposed to total documents, which includes chunks).

---

## ⚠️ Critical Rules

These rules exist because violating them **breaks search silently** — queries
return zero results or incorrect results with no error message.

### 1. kNN queries MUST target chunks

Embeddings live **only** on chunk documents (`embedding_v`). Parent documents do
not have this field. A kNN query filtered to parent-only documents will always
return zero results.

### 2. Never apply `EXCLUDE_CHUNKS_FQ` to kNN queries

```python
# ✅ CORRECT — kNN targets chunks, no chunk exclusion filter
params = build_knn_params(vector, top_k, knn_field)

# ❌ WRONG — this eliminates all kNN candidates
params = build_knn_params(vector, top_k, knn_field)
params["fq"].append(EXCLUDE_CHUNKS_FQ)  # BREAKS SEMANTIC SEARCH
```

The comment in `search_service.py` (line 280) explicitly warns:

> Do NOT add `EXCLUDE_CHUNKS_FQ` here. Embedding vectors live on chunk
> documents (they carry `parent_id_s`), so filtering them out would eliminate
> all kNN candidates and break semantic/hybrid search.

### 3. De-duplication happens after retrieval

Results from the kNN leg may include multiple chunks from the same book. De-
duplication to book-level results happens in `reciprocal_rank_fusion()` (for
hybrid) or in result normalization (for pure semantic), **not** in the Solr
query itself.

### 4. Facet filters go on both legs

User-selected facet filters (author, year, language, etc.) are applied to
**both** the keyword and kNN legs so that filtered results are consistent. This
works because chunk documents carry copies of parent metadata fields.

---

## Indexing Pipeline

```
PDF file on disk
        │
        ▼
┌───────────────────────────────┐
│  Phase 1: Text Extraction     │
│  (Solr Tika /update/extract)  │
│  → Creates PARENT document    │
│  → id = SHA-256(file_path)    │
│  → Metadata fields populated  │
│  → State saved to Redis       │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│  Phase 2: Chunk & Embed       │
│  → Extract text per page      │
│  → Split into word chunks     │
│    (400 words, 50 overlap)    │
│  → POST to embeddings-server  │
│  → Creates CHUNK documents    │
│  → Each has parent_id_s,      │
│    chunk_text_t, embedding_v  │
│  → Indexed via Solr /update   │
└───────────────────────────────┘
```

---

## Quick Reference

| Question | Answer |
|----------|--------|
| Where do embeddings live? | **Chunk documents** (`embedding_v` field) |
| Where does book metadata live? | **Parent documents** |
| How are they linked? | `parent_id_s` on chunks → `id` on parents |
| What filter excludes chunks? | `EXCLUDE_CHUNKS_FQ = "-parent_id_s:[* TO *]"` |
| Should kNN queries exclude chunks? | **No!** That would return zero results. |
| Embedding dimensions? | 512 (cosine similarity, HNSW algorithm) |
| Embedding model? | `distiluse-base-multilingual-cased-v2` |
| Chunk size? | 400 words (configurable via `CHUNK_SIZE`) |
| Chunk overlap? | 50 words (configurable via `CHUNK_OVERLAP`) |

---

## Source Code References

| Component | File | Key lines |
|-----------|------|-----------|
| Solr schema | `src/solr/books/managed-schema.xml` | Field definitions, `knn_vector_512` type |
| Parent doc creation | `src/document-indexer/__main__.py` | `build_literal_params()` |
| Chunk doc creation | `src/document-indexer/__main__.py` | `build_chunk_doc()`, `index_chunks()` |
| Chunking logic | `src/document-indexer/chunker.py` | `chunk_text_with_pages()` |
| Embedding client | `src/document-indexer/embeddings.py` | `get_embeddings()` |
| `EXCLUDE_CHUNKS_FQ` | `src/solr-search/search_service.py:56` | Filter definition |
| Keyword query builder | `src/solr-search/search_service.py` | `build_solr_params()` |
| kNN query builder | `src/solr-search/search_service.py` | `build_knn_params()` |
| RRF fusion | `src/solr-search/search_service.py` | `reciprocal_rank_fusion()` |
| Stats grouping | `src/solr-search/search_service.py` | `parse_stats_response()` |
