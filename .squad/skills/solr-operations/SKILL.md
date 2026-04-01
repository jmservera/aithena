---
name: "solr-operations"
description: "Solr parent/chunk data model, hybrid search, PDF indexing, and SolrCloud Docker operations"
domain: "search, solr, infrastructure, docker"
confidence: "high"
source: "consolidated from solr-parent-chunk-model, solr-pdf-indexing, solrcloud-docker-operations"
author: "Ripley"
created: "2026-07-25"
last_validated: "2026-07-25"
---

## Context

Apply when modifying Solr queries, schema fields, search modes, PDF indexing, or operating the SolrCloud/ZooKeeper stack. Covers the full Solr surface from data model through Docker operations.

## Pattern 1: Parent/Chunk Document Model

### Two document types share one collection

**Parent documents (books):**
- `id` = SHA-256 of file path
- Metadata: `title_s/t`, `author_s/t`, `year_i`, `category_s`, `language_detected_s`, `file_path_s`, etc.
- Optional: `book_embedding` (512D) for book-level similarity
- **No `parent_id_s` field** — this identifies a parent

**Chunk documents (text fragments):**
- `id` = `{parent_id}_chunk_{index}` (zero-padded)
- `parent_id_s` = parent book's `id`
- `chunk_text_t` = extracted text (400 words, 50-word overlap, page-aware)
- `embedding_v` = 512D dense vector (HNSW cosine) — **primary kNN field**

### Filter rules by search mode

| Mode | Chunk exclusion | Target |
|------|----------------|--------|
| Keyword (BM25) | Apply `-parent_id_s:[* TO *]` | Parents only |
| Semantic (kNN) | Do NOT apply | Chunks only (carry `embedding_v`) |
| Hybrid (RRF) | BM25 leg: exclude chunks; kNN leg: no exclusion | Both, deduplicate |

### Adding new fields

| Field purpose | Parent? | Chunk? | Why |
|---------------|---------|--------|-----|
| Book metadata | Yes | Copy from parent | Chunks need it for display |
| Full-text search | Yes (via Tika) | No | Tika extracts to parent |
| Dense vector | Optional | Yes (`embedding_v`) | kNN searches chunks |
| Facet field | Yes | Not needed | Facets from BM25 leg |

### Hybrid Search (BM25 + kNN + RRF)
- Run BM25 and kNN in parallel (ThreadPoolExecutor)
- Fuse with RRF: `score = sum(1/(k + rank))`, k=60
- Facets/highlights from BM25 leg only
- Use POST for Solr queries (kNN vectors >4KB exceed GET limits)
- **Timeout alignment:** Embeddings 120s, nginx ≥180s (1.5x), or you get 502

## Pattern 2: PDF Indexing

- **Use Solr Tika extraction** — POST raw PDF binary to `/update/extract` with `literal.*` params
- **Language detection** via `update.chain=langid`
- **Extract metadata from paths** (see `path-metadata` skill)
- **Schema:** Explicitly declare domain fields; use `*_s` for facets, `*_t` for search, `*_i` for numbers
- **Index embeddings separately** from full-text (different concerns, different availability)
- **Three search modes:** keyword (BM25), semantic (kNN), hybrid (RRF)

## Pattern 3: SolrCloud Docker Operations

### Current topology
3-node ZooKeeper (`zoo1`–`zoo3`), 3-node SolrCloud (`solr`, `solr2`, `solr3`)

### Volume persistence
- **Solr:** One dedicated volume per node at `/var/solr/data` (never share)
- **ZooKeeper:** Persist `/data` (snapshots), `/datalog` (transaction logs), `/logs` (optional)

### Failure recovery runbook

**Triage:**
```bash
docker compose exec zoo1 sh -lc 'printf ruok | nc -w 2 localhost 2181'
curl -s 'http://localhost:8983/solr/admin/collections?action=CLUSTERSTATUS&wt=json'
```

**Crashed Solr node (volume intact):** `docker compose restart solr2` — let SolrCloud self-heal

**Lost volume:** Delete and recreate replica:
```bash
curl -X DELETE 'http://localhost:8983/api/collections/books/shards/shard1/replicas/<core_node>'
curl -X POST 'http://localhost:8983/api/collections/books/shards/shard1/replicas' \
  -H 'Content-Type: application/json' \
  -d '{"node":"solr2:8983_solr","type":"nrt","waitForFinalState":true}'
```

**ZooKeeper loss:** Re-upload configsets, recreate collections, restore or reindex.

**Full catastrophic recovery:** Stop writers → rebuild ZK quorum → bring up Solr → re-upload configsets → recreate collections → reindex from source.

### Docker Compose hardening
- Health checks: ZK uses `ruok | grep imok`, Solr uses `/admin/info/system` or `/books/admin/ping`
- Dependencies: `condition: service_healthy` (not just start order)
- Restart: `unless-stopped` for stateful services
- Graceful shutdown: `stop_grace_period: 60s`
- Heap sizing: pair with container memory limits (not same number)

### ZK SASL Limitation (v1.14.0+)
SASL DIGEST-MD5 from Solr to ZK is broken (Solr 9.7 + Java 17 + ZK 3.9). Use Docker network isolation + ZK digest ACLs instead.

## Anti-Patterns

- ❌ **Never apply `EXCLUDE_CHUNKS_FQ` to kNN** — returns zero results (PR #701 incident)
- ❌ **Never assume parents have embeddings** — `embedding_v` on chunks is the primary vector
- ❌ **Never delete a parent without its chunks** — orphans pollute kNN results
- ❌ **Don't use pdfplumber when Solr Tika is available** — duplicates work
- ❌ **Don't rely on auto-schema** — explicitly define domain fields
- ❌ **Don't share a Solr data volume between nodes**
- ❌ **Don't treat ZK data as disposable** — holds configsets, collection state, security.json
- ❌ **Don't use REQUESTRECOVERY after volume loss** — recreate the replica
- ❌ **Don't rely on Compose start order as readiness** — use health checks

## References

- `src/solr-search/search_service.py`, `src/solr/books/managed-schema.xml`
- `solr/add-conf-overlay.sh`, `docker-compose.yml`
- PRs #701, #706, #723 (data model, POST fix, documentation)
- `docs/architecture/solr-data-model.md`
