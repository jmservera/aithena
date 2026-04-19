# Search and Indexing Sizing Guide

This guide provides a sizing model for Aithena's search stack when you cannot run production-like benchmarks yet. The numbers here are **analytical baselines** derived from the current codebase and Compose limits, not measured throughput numbers.

Use this guide to:

- estimate RAM, CPU, and disk needs before rollout
- understand which code paths dominate indexing and query cost
- pick a safe starting point for small, medium, and large deployments
- run the included `e2e/benchmark.sh` script later in a Docker-capable environment and replace these estimates with measured data

## What this sizing model is based on

These estimates come from the current implementation:

- `docker-compose.yml` defines the default container limits and reservations for Redis, RabbitMQ, Solr, embeddings-server, document-indexer, solr-search, and nginx.
- `document-lister` and `document-indexer` store per-document JSON state in Redis under `/${QUEUE_NAME}/${path}` and process RabbitMQ messages with `prefetch_count=1`.
- `document-indexer` indexes each PDF twice: once through Solr `/update/extract` for full text, then again as chunk documents with embeddings.
- Chunking defaults are `CHUNK_SIZE=400` and `CHUNK_OVERLAP=50`, so the effective stride is **350 words**.
- The embeddings server loads `sentence-transformers/distiluse-base-multilingual-cased-v2` and the Solr schema currently declares `knn_vector_512` for both `book_embedding` and `embedding_v`.
- SolrCloud currently boots as **1 shard, replication factor 3**, so every indexed byte is stored three times across the cluster.

> **Important:** the current repository uses a **512-dimensional** embedding model and Solr field type, not 384. If you switch to a 384-dimension model later, multiply vector RAM and vector disk estimates by **0.75**.

## Quick formulas

### Chunk count per document

With the shipped defaults:

- stride = `CHUNK_SIZE - CHUNK_OVERLAP = 350`
- approximate chunk count = `ceil(total_words / 350)`

A rough rule of thumb for PDFs with 250-350 words per page:

| PDF size | Approx. words | Approx. chunks |
|---|---:|---:|
| 10 pages | 3,000 | 9 |
| 50 pages | 15,000 | 43 |
| 150 pages | 45,000 | 129 |

Every PDF produces:

- **1 parent Solr document** with extracted text and metadata
- **N chunk Solr documents** with `chunk_text_t` + `embedding_v`

That means Solr sizing is driven much more by **chunk count** than by raw PDF count.

### Vector footprint per chunk

Raw float storage is easy to estimate:

- `raw_vector_bytes = dimensions × 4`

For Aithena:

| Vector size | Raw bytes/vector | Practical HNSW working-set estimate* |
|---|---:|---:|
| 384 dims | 1,536 B | ~1.8-2.4 KB |
| 512 dims (current) | 2,048 B | ~2.4-3.2 KB |

\*The HNSW estimate adds graph links and search overhead on top of raw floats.

For a typical 50-page PDF (~43 chunks):

- **384 dims:** ~77-103 KB of vector index per document
- **512 dims:** ~103-138 KB of vector index per document

## Solr sizing

### Current deployment shape

The shipped Compose stack allocates three Solr nodes:

- `solr`, `solr2`, `solr3`
- limit: **2 GB RAM per node**
- reservation: **1 GB RAM per node**
- collection bootstrap: `numShards=1`, `replicationFactor=3` (configurable)

Because the collection currently has one shard with three replicas, each node hosts one replica core for the `books` collection.

### Configurable shards and replication

Both `docker-compose.yml` and `docker-compose.prod.yml` read shard topology from environment variables with sensible defaults:

| Variable | Default | Description |
|---|---|---|
| `SOLR_NUM_SHARDS` | `1` | Number of shards to split the collection across |
| `SOLR_REPLICATION_FACTOR` | `3` | Number of replicas per shard |

Set these in your `.env` file or export them before running `docker compose up`:

```bash
# Personal deployment (single machine, ≤30K docs)
SOLR_NUM_SHARDS=1
SOLR_REPLICATION_FACTOR=1

# Medium deployment (single machine, 30K-100K docs)
SOLR_NUM_SHARDS=2
SOLR_REPLICATION_FACTOR=1

# Distributed deployment (multi-node, HA required) — the default
SOLR_NUM_SHARDS=1
SOLR_REPLICATION_FACTOR=3
```

**How to choose:**

| Library size | Shards | Replication | Why |
|---|---:|---:|---|
| ≤30K PDFs, single machine | 1 | 1 | One core fits in 8-12 GB; RF=1 avoids 3× disk/RAM waste |
| 30K-100K PDFs, single machine | 2 | 1 | Splits the vector index across cores for better page-cache utilization |
| Any size, HA required | 1-2 | 3 | RF=3 survives node failures; requires ≥3 Solr nodes |

**Important notes:**

- These variables only take effect during **initial collection creation**. If the `books` collection already exists, changing them requires deleting and recreating the collection (which re-indexes all documents).
- `SOLR_REPLICATION_FACTOR` should not exceed the number of Solr nodes in the cluster.
- For a personal/lite profile with a single Solr node, set `SOLR_REPLICATION_FACTOR=1`. RF>1 with only one node means Solr creates multiple replicas on the same machine, wasting disk without adding fault tolerance.

### Memory per core

For the current topology, a useful planning baseline is:

| Collection size | Suggested memory per Solr core | Notes |
|---|---:|---|
| up to 100 parent docs | 1.5-2 GB | Current Compose default is sufficient |
| ~10K parent docs | 3-4 GB | Increase node memory to keep heap + page cache balanced |
| ~100K parent docs | 6-10 GB | Plan for more RAM and consider additional shards |

Why the floor is high even for small libraries:

- Solr itself has a meaningful fixed overhead.
- The current config enables transaction logs and near-real-time commits.
- Query caches (`filterCache`, `queryResultCache`, `documentCache`) are each set to 512 entries.
- Dense vector search benefits from filesystem cache, so not all RAM should be given to the JVM heap.

### JVM heap recommendations

Do **not** give all container RAM to the heap. For this workload, keep roughly half for the JVM and half for filesystem cache / native overhead.

| Solr node RAM | Recommended heap | When to use it |
|---|---:|---|
| 2 GB | 1 GB heap | Small libraries, light concurrency |
| 4-6 GB | 2-3 GB heap | ~10K docs, moderate semantic search |
| 8-12 GB | 4-6 GB heap | ~100K docs, larger vector working set |

Recommended Solr rules:

1. Keep at least **1× heap size** available for OS page cache.
2. If p95 semantic latency rises after the index grows, add page-cache headroom before raising cache entry counts.
3. When the collection approaches **100K average PDFs** or several million chunk vectors, move beyond the current single-shard layout.

### Disk per 1K documents

Because each PDF becomes one parent document plus many chunk documents, disk usage varies with document length. For a typical research/library mix (roughly 30-60 pages per PDF), use this planning baseline:

| Scope | Disk per 1K PDFs |
|---|---:|
| Logical collection size (single replica) | ~0.35-0.75 GB |
| Physical SolrCloud size at RF=3 | ~1.05-2.25 GB |
| Physical size with 2× merge/backup headroom | ~2.1-4.5 GB |

Notes:

- Short PDFs can land below the low end.
- OCR-heavy or very long PDFs can exceed the high end quickly because chunk count increases almost linearly with word count.
- The parent `content` field and stored `chunk_text_t` both consume disk.

### kNN vector index memory guidance

Use chunk count, not PDF count, when planning vector memory.

For **1 million chunk vectors**:

| Dimensions | Approx. vector/HNSW working set |
|---|---:|
| 384 dims | ~1.8-2.4 GB |
| 512 dims (current) | ~2.4-3.2 GB |

Practical implications:

- 10K average PDFs at ~40 chunks/doc is already ~400K vectors.
- 100K average PDFs at ~40 chunks/doc is ~4M vectors.
- At that scale, semantic search becomes page-cache sensitive and a single 2 GB Solr node is not enough.

## Redis sizing

### What Redis stores today

There are two Redis patterns in the codebase:

1. `solr-search` still defaults `REDIS_KEY_PATTERN` to `doc:*` for the legacy `/v1/status` counter path.
2. The active lister/indexer/admin workflow stores **JSON blobs** under:

```text
/${QUEUE_NAME}/${path}
```

Those JSON payloads include fields such as:

- `path`, `last_modified`, `timestamp`
- `processed`, `failed`, `error_stage`
- `title`, `author`, `year`, `category`
- `solr_id`, `page_count`, `chunk_count`

### Memory per indexed document

Plan Redis state at roughly:

| State style | Practical memory per document |
|---|---:|
| Legacy `doc:*` string markers | negligible (<100 B/doc) |
| Current JSON state entries | ~0.7-1.5 KB/doc |

That yields this baseline for the current JSON state model:

| Indexed PDFs | Estimated Redis memory |
|---|---:|
| 100 | <1 MB |
| 10K | ~7-15 MB |
| 100K | ~70-150 MB |

The current Compose limit of **512 MB** is therefore generous for document-state tracking alone.

### Connection pool sizing

`solr-search` creates a singleton `redis.ConnectionPool`, but does not currently cap `max_connections`. For production, explicitly size the pool instead of leaving it effectively unbounded.

Recommended starting point:

```text
max_connections = max(16, 2 × API workers + 8)
```

Examples:

| solr-search workers | Recommended Redis pool cap |
|---|---:|
| 2 | 16 |
| 4 | 16-24 |
| 8 | 24-32 |
| 16 | 40-64 |

Why keep headroom:

- `/v1/status` scans Redis keys.
- admin document endpoints also scan and fetch Redis state.
- uploads and queue/status operations can overlap under operator traffic.

## RabbitMQ sizing

### Current workload shape

The queue is durable and the document-indexer consumes with:

- `prefetch_count=1`
- one document per consumer at a time
- current Compose replica count: **1** for `document-indexer`

That means queue depth is mostly an **operational signal**, not a memory risk.

### Queue depth guidelines

Use queue depth as "how long will the backlog take to drain?"

| Deployment size | Healthy steady-state backlog | Investigate / scale out |
|---|---:|---:|
| Small | <50 queued docs | >200 |
| Medium | <500 queued docs | >2,000 |
| Large | <5,000 queued docs | >20,000 |

A simpler rule: keep backlog below about **15-30 minutes of ingest capacity**. If the queue stays above that for sustained periods, add indexer replicas before increasing broker memory.

### Memory and disk limits

Current RabbitMQ settings:

- container limit: **1 GB**
- reservation: **512 MB**
- `vm_memory_high_watermark.relative = 0.6`

That means memory alarms will typically start around **600 MB** of broker memory use.

For this application, queue messages are only file paths, so queue storage is small. The broker usually runs out of headroom because of:

- persistent backlog growth
- management UI overhead
- accumulated logs / on-disk durable queue data during long outages

Recommended operator targets:

- keep at least **2-5 GB** free on the RabbitMQ volume
- alert when queue depth keeps growing for more than one poll interval window
- scale consumers before increasing broker RAM unless you also add larger messages later

## embeddings-server sizing

### CPU vs GPU expectations

The service loads `sentence-transformers/distiluse-base-multilingual-cased-v2` at startup and calls `model.encode(...)` on the full batch sent by clients.

The shipped Compose file does **not** request a GPU, so the default deployment is CPU-bound.

Expected baseline ranges:

| Mode | Startup | Single query embedding | 32-chunk batch | 64-chunk batch |
|---|---:|---:|---:|---:|
| CPU (1-2 dedicated vCPU) | ~30-60 s | ~200-800 ms | ~2-8 s | ~4-15 s |
| Mid-range GPU | ~10-25 s | ~30-120 ms | ~0.2-1.0 s | ~0.5-2.0 s |

These are planning numbers, not measured guarantees.

### Batch size tuning

Current behavior:

- search sends **one query string** per semantic/hybrid request
- document-indexer sends **all chunks from a PDF in a single request**

That means the effective batch size is the document's chunk count.

Recommended targets:

| Platform | Safe batch target |
|---|---:|
| CPU | 16-64 chunks/request |
| GPU | 64-256 chunks/request |

If many PDFs exceed those batch sizes:

- split embedding requests at the client side, or
- raise timeouts and accept lower tail-latency during indexing

### Timeout guidance

Current timeout-related settings in the repo:

- `solr-search`: `EMBEDDINGS_TIMEOUT=120` seconds for query-time embeddings
- `src/document-indexer/document_indexer/embeddings.py`: hardcoded request timeout of **300** seconds
- `src/embeddings-server/config/__init__.py`: `EMBEDDINGS_TIMEOUT` default of **30 minutes**, but the server currently does not enforce request timeout itself

Practical guidance:

| Scenario | Suggested timeout |
|---|---:|
| interactive semantic search | 5-15 s target, 30-120 s hard ceiling |
| indexing short/medium PDFs | 60-180 s |
| indexing very large OCR-heavy PDFs | 300-900 s or split batches |

## document-indexer sizing

### Current throughput constraints

A single worker processes each document serially:

1. Tika extraction through Solr `/update/extract`
2. PDF text extraction with `pdfplumber`
3. chunking at 400/50 words
4. embedding request for all chunks
5. JSON update of chunk documents back into Solr

Because the queue QoS is `prefetch_count=1`, each worker does one PDF at a time.

### Throughput expectations

Use these starting estimates for a single `document-indexer` replica:

| Workload | CPU embeddings | GPU-backed embeddings |
|---|---:|---:|
| Short PDFs (<=10 pages) | ~8-15 docs/min | ~15-30 docs/min |
| Typical PDFs (30-60 pages) | ~2-6 docs/min | ~5-15 docs/min |
| Long/OCR-heavy PDFs | ~0.5-2 docs/min | ~1-5 docs/min |

These rates assume the default single-replica setup and no heavy concurrent search load.

### Concurrent workers

The current Compose file sets:

- `document-indexer` replicas: **1**

To scale indexing, add replicas. Near-linear gains are realistic until one of these saturates:

- embeddings-server CPU/GPU
- Solr update throughput
- disk I/O on the Solr volumes

Recommended starting points:

| Deployment | Indexer replicas | Notes |
|---|---:|---|
| Small | 1 | Default |
| Medium | 2 | Good first scale-out step |
| Large | 3-4 | Prefer GPU embeddings or more embeddings capacity |

## nginx sizing

### Current profile

The shipped nginx container has:

- **256 MB** memory limit
- reverse-proxy duties for UI, Solr admin, RabbitMQ admin, Redis Commander, auth validation, and API traffic
- WebSocket upgrade headers for admin surfaces

### Connection limits

The config does not currently override `worker_connections`, so nginx defaults apply. For this stack's mostly small JSON responses, that is usually enough for light-to-moderate concurrency.

Practical guidance:

| Traffic level | Recommendation |
|---|---|
| up to ~200 active clients | current defaults are usually fine |
| ~200-500 active clients | keep 256 MB limit, but validate keepalive and upstream timeouts |
| >500 active clients | explicitly set `worker_connections 4096` and raise file-descriptor limits |

### Proxy buffer sizing

The current config relies on nginx defaults. That is acceptable for:

- search responses
- status/stats payloads
- most admin pages

If you expect larger responses or want safer headroom for large facet payloads, use:

```nginx
client_max_body_size 64m;
proxy_buffer_size 16k;
proxy_buffers 8 32k;
proxy_busy_buffers_size 64k;
```

That lines up with the app-level `MAX_UPLOAD_SIZE_MB=50` setting and avoids nginx becoming the smaller upload bottleneck.

## Overall deployment profiles

These profiles assume the **shipped 3-node SolrCloud topology** and exclude the raw PDF corpus itself. Add your source-library size, backup space, and snapshot retention on top.

### Small deployment (~100 PDFs)

| Spec | Minimum | Recommended |
|---|---:|---:|
| CPU | 8 vCPU | 8-12 vCPU |
| RAM | 16 GB | 24 GB |
| Fast SSD/NVMe for stack volumes | 100 GB | 150-200 GB |
| Solr | 3 nodes × 2 GB | 3 nodes × 2 GB |
| embeddings-server | 2 GB CPU | 2-4 GB CPU |
| indexer replicas | 1 | 1 |

### Medium deployment (~10K PDFs)

| Spec | Minimum | Recommended |
|---|---:|---:|
| CPU | 12 vCPU | 16 vCPU |
| RAM | 24 GB | 32-48 GB |
| Fast SSD/NVMe for stack volumes | 250 GB | 500 GB |
| Solr | 3 nodes × 4 GB | 3 nodes × 4-6 GB |
| embeddings-server | 4 GB CPU | 4 GB CPU or 1 GPU-backed instance |
| indexer replicas | 2 | 2-3 |

### Large deployment (~100K PDFs)

| Spec | Minimum | Recommended |
|---|---:|---:|
| CPU | 16 vCPU | 24+ vCPU |
| RAM | 48 GB | 64-96 GB |
| Fast SSD/NVMe for stack volumes | 1 TB | 2 TB |
| Solr | 3 nodes × 8 GB | 3+ nodes, 8-12 GB each, consider more shards |
| embeddings-server | GPU strongly recommended | GPU + dedicated inference capacity |
| indexer replicas | 3 | 4+ with matching embeddings capacity |

## How to replace estimates with measured numbers later

When Docker is available, run:

```bash
./e2e/benchmark.sh --docs 100 --output e2e/benchmark-results.json
```

The script:

1. starts the Compose stack with the E2E override
2. creates a configurable number of sample PDFs in the bound library path
3. measures indexing throughput end-to-end through the lister → RabbitMQ → indexer → Solr pipeline
4. measures keyword, semantic, and hybrid search latency
5. captures per-service memory usage from Docker
6. writes all results to JSON so you can compare hosts or commit benchmark snapshots

## Recommended next step after the first real benchmark

Update this guide with:

- measured chunk-count distributions from your real corpus
- p50/p95 indexing time by PDF size bucket
- p50/p95 search latency by mode under concurrency
- observed Solr disk growth per 1K PDFs on your actual document set
- embeddings-server CPU vs GPU measurements on your target hardware
