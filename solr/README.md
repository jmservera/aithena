# Solr Configuration for Aithena Books Collection

This directory contains the SolrCloud configset for the `books` collection.

## Files

- `managed-schema.xml` — Solr schema with field definitions and analyzers
- `solrconfig.xml` — Request handlers, indexing settings, Tika extraction config
- `lang/` — Language-specific stopwords for multilingual search
- `synonyms.txt` — Optional query-time synonyms

## Key Schema Features

### Field Types

- **String fields** (`*_s`): Exact-match, not tokenized. Use for author, category, language codes.
- **Text fields** (`*_t`): Analyzed, tokenized. Use for title, content. Supports multilingual analyzers.
- **Integer/Long fields** (`*_i`, `*_l`): Year, page count, file size.
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

## References

- [Solr Schema](https://solr.apache.org/docs/latest/schema-elements-intro.html)
- [Tika Integration](https://solr.apache.org/docs/latest/indexing-and-basic-data-operations.html#indexing-binary-documents)
- [Multilingual Search](https://solr.apache.org/docs/latest/language-analyzers.html)