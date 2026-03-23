# Embedding Model Migration: multilingual-e5-base

## Summary

Aithena has migrated from `sentence-transformers/distiluse-base-multilingual-cased-v2` (512D) to
`intfloat/multilingual-e5-base` (768D) as the sole embedding model. This change improves semantic
search quality based on benchmark results (see `results/benchmark_e5base_report.md`).

## What Changed

### Embedding model
- **Before:** `distiluse-base-multilingual-cased-v2` — 512-dimensional embeddings
- **After:** `intfloat/multilingual-e5-base` — 768-dimensional embeddings
- The e5 model uses query/passage prefixes automatically (`"query: "` for search, `"passage: "` for indexing)

### Docker Compose services removed
- `embeddings-server-e5` — the A/B test e5 server (now the default `embeddings-server` uses e5)
- `document-indexer-e5` — the A/B test indexer for the `books_e5base` collection

### Solr schema
- `src/solr/books/managed-schema.xml` — vector fields changed from 512D to 768D
- `src/solr/books_e5base/` — **deleted** (no longer needed; `books` is now the e5 collection)

### Configuration
- `E5_COLLECTIONS=books` is now set by default (was empty)
- `CHUNK_SIZE=300` and `CHUNK_OVERLAP=50` are now the default indexer parameters (was 90/10)
- Embeddings server memory increased: 3GB limit / 2GB reservation (was 2GB / 1GB)
- Health check `start_period` increased to 120s (e5 model loads slower)

### Files removed
| File/Directory | Reason |
|----------------|--------|
| `src/solr/books_e5base/` | Merged into `src/solr/books/` (768D vectors) |

## Breaking Changes

**Existing Solr data is incompatible.** The `books` collection previously stored 512-dimensional
vectors. After this migration, it expects 768-dimensional vectors. You **must** reindex the entire
library after upgrading.

## How to Reindex

### Option A: Admin Portal (recommended)

1. Open the Aithena Admin Dashboard
2. Navigate to **Reindex Library** in the sidebar
3. Click **Start Full Reindex** and confirm
4. Wait for the document-lister to rediscover and re-enqueue all files

### Option B: API call

```bash
# Authenticate (get a JWT token or use ADMIN_API_KEY)
curl -X POST "http://localhost:8080/v1/admin/reindex?collection=books" \
  -H "X-API-Key: YOUR_ADMIN_API_KEY"
```

### Option C: Manual steps

1. **Delete all documents from Solr:**
   ```bash
   curl "http://solr:8983/solr/books/update?commit=true" \
     -u "solr_admin:YOUR_PASSWORD" \
     -H "Content-Type: application/json" \
     -d '{"delete": {"query": "*:*"}}'
   ```

2. **Clear Redis tracking state:**
   ```bash
   redis-cli -a YOUR_PASSWORD --scan --pattern "/shortembeddings/*" | \
     xargs -r redis-cli -a YOUR_PASSWORD DEL
   ```

3. **Wait** — the document-lister will automatically rediscover all files and
   re-enqueue them via RabbitMQ. The document-indexer will re-embed each document
   with the e5 model and index it into Solr.

### Option D: Fresh deployment

If doing a clean deployment, simply delete the Solr data volumes and Redis data:

```bash
docker compose down -v
rm -rf /source/volumes/solr-data*
rm -rf /source/volumes/redis/dump.rdb
docker compose up -d
```

## Upgrade Checklist

- [ ] Pull latest code (`git pull`)
- [ ] Rebuild all containers (`./buildall.sh` or `docker compose up --build`)
- [ ] Reindex the library (Option A, B, C, or D above)
- [ ] Verify search results (try keyword, semantic, and hybrid modes)

## Technical Notes

- The e5 model automatically prefixes texts with `"query: "` or `"passage: "` — this is handled
  by `model_utils.py` in the embeddings server. No manual prefixing is needed.
- Semantic search latency may increase ~50% compared to distiluse (768D vs 512D HNSW index).
  Keyword search is unaffected.
- The `E5_COLLECTIONS` config variable tells solr-search which collections use the e5 model
  (for proper query prefixing). It defaults to `"books"` after this migration.
