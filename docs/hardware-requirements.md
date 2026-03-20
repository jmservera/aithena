# Minimum Hardware Requirements & Tuning Guide

This document provides minimum hardware requirements for deploying Aithena, a per-service resource breakdown, and actionable tuning guidelines. Use it alongside the [Search and Indexing Sizing Guide](deployment/sizing-guide.md) for detailed analytical formulas and the [Admin Manual](admin-manual.md) for deployment procedures.

> **Scope:** Aithena is a fully on-premises Docker Compose application. All requirements assume a single host running the complete stack — no cloud dependencies.

---

## Quick Reference: Deployment Profiles

| Deployment | Documents | CPU | RAM | Disk (stack) | Expected Search Latency (p95) |
|---|---:|---:|---:|---:|---:|
| **Small** (personal) | < 500 | 4 cores | 8 GB | 20 GB SSD | < 500 ms |
| **Medium** (team) | < 5,000 | 8 cores | 16 GB | 50 GB SSD | < 1 s |
| **Large** (organization) | < 50,000 | 16 cores | 32 GB | 200 GB SSD | < 2 s |

Disk figures are for the application stack only. Add your source PDF library size and backup retention on top.

---

## 1. Per-Service Resource Breakdown

The table below summarizes the Docker Compose resource limits shipped in `docker-compose.yml`, the minimum allocation needed for the service to function, and the recommended allocation for production workloads.

### 1.1 Compute and Memory

| Service | Instances | Memory Limit (default) | Memory Reservation | CPU Reservation | Min RAM | Recommended RAM | CPU-Bound? |
|---|---:|---:|---:|---:|---:|---:|---|
| **Solr** (solr, solr2, solr3) | 3 | 2 GB each | 1 GB each | 1.0 vCPU each | 1 GB each | 2–4 GB each | I/O (disk + page cache) |
| **ZooKeeper** (zoo1, zoo2, zoo3) | 3 | 512 MB each | 256 MB each | — | 256 MB each | 512 MB each | No |
| **embeddings-server** | 1 | 2 GB | 1 GB | 1.0 vCPU | 1 GB | 2–4 GB | Yes (model inference) |
| **solr-search** (API) | 1 | 512 MB | 256 MB | 0.5 vCPU | 256 MB | 512 MB | No |
| **document-indexer** | 1 | 512 MB | 256 MB | — | 256 MB | 512 MB | Moderate (PDF parsing) |
| **document-lister** | 1 | 256 MB | 128 MB | — | 128 MB | 256 MB | No (I/O-bound) |
| **RabbitMQ** | 1 | 1 GB | 512 MB | — | 512 MB | 1 GB | No |
| **Redis** | 1 | 512 MB | 256 MB | — | 128 MB | 256 MB–1 GB | No |
| **admin** (Streamlit) | 1 | 256 MB | 128 MB | — | 128 MB | 256 MB | No |
| **aithena-ui** (Nginx serving React) | 1 | 256 MB | 128 MB | — | 128 MB | 256 MB | No |
| **nginx** (reverse proxy) | 1 | 256 MB | 128 MB | — | 64 MB | 128 MB | No |
| **redis-commander** | 1 | 256 MB | 128 MB | — | 128 MB | 128 MB | No |

**Default stack totals (all containers):**

| Profile | Container RAM Total | Host RAM (with OS + overhead) |
|---|---:|---:|
| Small (defaults) | ~12 GB | 8 GB minimum (tight), 16 GB recommended |
| Medium (Solr at 4 GB/node) | ~22 GB | 24–32 GB recommended |
| Large (Solr at 8 GB/node) | ~40 GB | 48–64 GB recommended |

### 1.2 Key Observations

- **Solr nodes dominate memory.** Three Solr nodes at 2 GB each account for 6 GB before any other service starts.
- **ZooKeeper is lightweight** but requires three instances for quorum. Budget 1.5 GB total.
- **embeddings-server** is the primary CPU bottleneck. Model loading takes 30–60 s on CPU; inference scales linearly with batch size.
- **document-indexer** is the pipeline throughput limiter. A single replica processes one PDF at a time (prefetch_count=1).

---

## 2. Storage Requirements

### 2.1 Solr Indexes

SolrCloud runs with **1 shard, replication factor 3** — every indexed byte is stored three times across the cluster.

| Collection Size | Single-Replica Disk | Physical Disk (RF=3) | With 2× Merge Headroom |
|---:|---:|---:|---:|
| 1K PDFs | 0.35–0.75 GB | 1.05–2.25 GB | 2.1–4.5 GB |
| 10K PDFs | 3.5–7.5 GB | 10.5–22.5 GB | 21–45 GB |
| 50K PDFs | 17.5–37.5 GB | 52.5–112.5 GB | 105–225 GB |

> Disk usage depends heavily on average document length. OCR-heavy or long PDFs produce many more chunks and consume proportionally more space.

### 2.2 ZooKeeper Data

ZooKeeper stores SolrCloud configuration and cluster state. Typical size is under 100 MB. Allow 1–2 GB per node for logs and snapshots, plus periodic cleanup.

### 2.3 RabbitMQ

Queue messages are file paths (small). Disk usage is dominated by durable message logs during long backlogs. Allow **2–5 GB** on the RabbitMQ volume.

### 2.4 Redis

Redis stores per-document JSON state (~0.7–1.5 KB per document). At 10K documents, that is only ~7–15 MB. The default 512 MB container limit is generous.

### 2.5 Document Library

The source PDF library is mounted via the `BOOKS_PATH` volume. This is entirely user-controlled and is **not** included in the stack disk figures above.

### 2.6 Backups and Snapshots

Plan additional storage for:

- Solr snapshots (same size as a single replica)
- ZooKeeper backup volume (shared across all three nodes at `/source/volumes/zoo-backup`)
- Redis RDB snapshots (small — under 50 MB for most deployments)

### 2.7 Docker Image Storage

All container images combined require approximately **5–8 GB** of disk space. This is a one-time cost per version.

### 2.8 Summary by Deployment Size

| Deployment | Stack Volumes | Source Library (user) | Backups | Docker Images | **Total Minimum** |
|---|---:|---:|---:|---:|---:|
| Small (< 500 docs) | 10 GB | varies | 5 GB | 8 GB | **~25 GB + library** |
| Medium (< 5K docs) | 50 GB | varies | 25 GB | 8 GB | **~85 GB + library** |
| Large (< 50K docs) | 250 GB | varies | 125 GB | 8 GB | **~385 GB + library** |

Use **SSD or NVMe** storage for all stack volumes. Solr performance is highly sensitive to disk latency.

---

## 3. GPU Requirements

### 3.1 Embeddings Server

The embeddings server loads the `sentence-transformers/distiluse-base-multilingual-cased-v2` model (512 dimensions). It runs on **CPU by default** — the shipped `docker-compose.yml` does not request GPU resources.

| Mode | Model Load Time | Single Query Embedding | 32-Chunk Batch | 64-Chunk Batch |
|---|---:|---:|---:|---:|
| CPU (1–2 vCPU) | 30–60 s | 200–800 ms | 2–8 s | 4–15 s |
| Mid-range GPU | 10–25 s | 30–120 ms | 0.2–1.0 s | 0.5–2.0 s |

### 3.2 When to Add a GPU

- **Small deployments (< 500 docs):** GPU is not necessary. CPU inference is adequate for occasional searches and small indexing batches.
- **Medium deployments (< 5K docs):** GPU is beneficial if semantic search latency or indexing throughput are priorities.
- **Large deployments (< 50K docs):** GPU is **strongly recommended**. CPU-only indexing of 50K documents takes significantly longer, and semantic search latency degrades under concurrent load.

### 3.3 GPU Configuration

To enable GPU passthrough, add a `docker-compose.gpu.yml` override:

```yaml
services:
  embeddings-server:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

Launch with:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

**Minimum GPU requirements:**

| Spec | Minimum | Recommended |
|---|---|---|
| VRAM | 2 GB | 4 GB+ |
| Driver | NVIDIA 470+ with CUDA 11.x | NVIDIA 525+ with CUDA 12.x |
| Runtime | [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) | — |

The `distiluse-base-multilingual-cased-v2` model is small (~500 MB on disk, ~1 GB in GPU memory). Any modern NVIDIA GPU with 2+ GB VRAM is sufficient.

---

## 4. Network Requirements

### 4.1 Internal Networking

All services communicate over a single Docker Compose bridge network. No special network configuration is needed.

| Traffic Path | Protocol | Typical Volume |
|---|---|---|
| solr-search → Solr | HTTP | High (search queries, index updates) |
| solr-search → embeddings-server | HTTP | Moderate (one call per semantic/hybrid query) |
| document-indexer → embeddings-server | HTTP | High during indexing (full-batch per doc) |
| document-indexer → Solr | HTTP | High during indexing |
| document-lister → RabbitMQ | AMQP | Low (file path messages) |
| document-indexer → RabbitMQ | AMQP | Low (consume one at a time) |
| All services → Redis | TCP | Moderate (state lookups, caching) |
| ZooKeeper ensemble (×3) | TCP | Low (cluster coordination) |

### 4.2 External Access

Only **nginx** is exposed on the host network (port 80 by default, 443 with TLS). All other services are internal.

| Requirement | Details |
|---|---|
| Inbound | Port 80 (HTTP) and optionally 443 (HTTPS via `docker-compose.ssl.yml`) |
| Outbound | **None required at runtime.** All models are baked into Docker images at build time (`HF_HUB_OFFLINE=1`). |
| Bandwidth | Minimal for the application itself. Largest transfers are PDF uploads (capped at 50 MB by default). |

### 4.3 Firewall Rules

For a production deployment, only port 80/443 needs to be open to users. If `docker-compose.override.yml` is active (development mode), additional debug ports are exposed — do not use the override in production.

---

## 5. Tuning Guidelines

### 5.1 Solr JVM Heap

The most impactful tuning parameter. Keep roughly **half** the container memory for the JVM heap and half for OS page cache and native overhead.

| Solr Node RAM | Recommended Heap (`SOLR_JAVA_MEM`) | Use Case |
|---:|---:|---|
| 2 GB | `-Xms512m -Xmx1g` | Small libraries, light concurrency |
| 4–6 GB | `-Xms1g -Xmx3g` | ~10K docs, moderate semantic search |
| 8–12 GB | `-Xms2g -Xmx6g` | ~100K docs, larger vector working set |

To override, set the `SOLR_JAVA_MEM` environment variable in your Compose override:

```yaml
services:
  solr:
    environment:
      SOLR_JAVA_MEM: "-Xms1g -Xmx3g"
  solr2:
    environment:
      SOLR_JAVA_MEM: "-Xms1g -Xmx3g"
  solr3:
    environment:
      SOLR_JAVA_MEM: "-Xms1g -Xmx3g"
```

> **Rule of thumb:** If p95 semantic search latency rises as your index grows, add page-cache headroom (increase container RAM without raising heap) before increasing Solr cache entry counts.

### 5.2 Solr Query Caches

The shipped Solr configuration sets `filterCache`, `queryResultCache`, and `documentCache` each to **512 entries**. For most deployments, these defaults are adequate.

| Deployment | Cache Action |
|---|---|
| Small | Leave defaults (512 entries each) |
| Medium | Monitor hit ratios via Solr admin UI; increase to 1024 if hit rate < 80% |
| Large | Consider increasing to 2048+ and monitor heap usage |

### 5.3 Embeddings Batch Size

The document-indexer sends **all chunks from a PDF in a single request** to the embeddings server. Very large PDFs (150+ pages, ~129 chunks) can cause high latency or timeouts.

| Platform | Safe Batch Target | Action for Large PDFs |
|---|---:|---|
| CPU | 16–64 chunks | Split requests or increase timeouts |
| GPU | 64–256 chunks | Usually fine; monitor GPU memory |

Related timeout settings:

| Setting | Location | Default | Recommendation |
|---|---|---:|---|
| `EMBEDDINGS_TIMEOUT` | solr-search env | 120 s | 30–120 s for interactive search |
| Request timeout | document-indexer code | 300 s | 300–900 s for large OCR-heavy PDFs |

### 5.4 RabbitMQ Prefetch Count

The document-indexer consumes with `prefetch_count=1` — one document per worker at a time. This is conservative and correct for the default single-replica setup.

| Indexer Replicas | Prefetch Count | Notes |
|---:|---:|---|
| 1 | 1 | Default; simple and safe |
| 2–3 | 1–2 | Increase only if queue depth stays high |
| 4+ | 2–5 | Monitor embeddings-server load |

### 5.5 Document-Indexer Replicas

Scale the indexing pipeline by adding replicas. Near-linear gains are realistic until one of these saturates: embeddings-server CPU/GPU, Solr update throughput, or disk I/O.

| Deployment | Replicas | Notes |
|---|---:|---|
| Small | 1 | Default |
| Medium | 2 | Good first scale-out step |
| Large | 3–4 | Pair with GPU-backed embeddings |

To increase replicas, set in a Compose override:

```yaml
services:
  document-indexer:
    deploy:
      replicas: 3
```

### 5.6 RabbitMQ Memory Watermark

The shipped configuration sets `vm_memory_high_watermark.relative = 0.6`. With a 1 GB container limit, memory alarms trigger at ~600 MB.

For larger deployments with deep queues, increase the container limit before changing the watermark:

```yaml
services:
  rabbitmq:
    deploy:
      resources:
        limits:
          memory: 2g
```

### 5.7 Redis Connection Pool

The solr-search API creates a singleton Redis `ConnectionPool` without an explicit `max_connections` cap. For production, size the pool based on API worker count:

```
max_connections = max(16, 2 × API_workers + 8)
```

### 5.8 Nginx

For most Aithena deployments, nginx defaults are sufficient. Adjustments for high concurrency:

| Traffic Level | Action |
|---|---|
| < 200 clients | Defaults are fine |
| 200–500 clients | Validate keepalive and upstream timeouts |
| > 500 clients | Set `worker_connections 4096`, raise file-descriptor limits |

Ensure `client_max_body_size` is at least as large as the `MAX_UPLOAD_SIZE_MB` setting (default 50 MB):

```nginx
client_max_body_size 64m;
```

---

## 6. Scaling Considerations

### 6.1 Vertical Scaling (Single Host)

The simplest way to improve performance:

| Bottleneck | Symptom | Action |
|---|---|---|
| Slow semantic search | High p95 latency, embeddings-server at 100% CPU | Add GPU, or increase embeddings-server CPU allocation |
| Slow indexing | Large queue backlog, indexer saturated | Add indexer replicas + increase embeddings capacity |
| Solr query slowdowns | High GC pauses, low cache hit rates | Increase Solr node RAM, tune heap |
| OOM kills on any service | Container restarts in `docker events` | Raise memory limits in Compose override |
| Disk I/O bottleneck | High iowait, slow Solr commits | Move to faster SSD/NVMe storage |

### 6.2 Horizontal Scaling

The current architecture has limited horizontal scaling options within Docker Compose:

| What Scales | How | Limit |
|---|---|---|
| document-indexer replicas | `deploy.replicas` in Compose | Limited by embeddings-server and Solr throughput |
| Solr replicas | Already 3 nodes (RF=3) | Add nodes for read throughput; add shards for write throughput at > 100K docs |
| embeddings-server | Can run multiple instances behind a load balancer | GPU count is the practical limit |

What **does not** scale horizontally in the current architecture:

- **solr-search API** — single instance; stateless, so adding replicas behind nginx is straightforward if needed.
- **document-lister** — single instance by design (one scanner per library).
- **RabbitMQ / Redis** — single instances; unlikely bottlenecks at Aithena's scale.

### 6.3 When to Consider Splitting Hosts

If a single host cannot meet the deployment requirements:

| Scenario | Recommendation |
|---|---|
| Need GPU for embeddings but main host has none | Run embeddings-server on a GPU host; point other services to it via network URL |
| Solr needs more RAM than the host has | Move SolrCloud to dedicated hosts; update `ZK_HOST` and `SOLR_URL` accordingly |
| > 100K documents | Consider multi-shard SolrCloud topology across multiple hosts |

---

## 7. Development and Testing Profile

For local development and testing (not production), a lighter configuration is possible:

| Spec | Minimum |
|---|---|
| CPU | 4 cores |
| RAM | 8 GB |
| Disk | 20 GB SSD |
| GPU | Not required |

**Development tips:**

- Use `docker-compose.override.yml` for debug port access (ports 8080, 8085, 8983–8985, etc.)
- Reduce Solr to a single node if resources are constrained (not recommended for testing replication behavior)
- The embeddings model downloads at build time and is baked into the image — no internet access needed at runtime
- Monitor resource usage with `docker stats` to identify tight spots on your development machine

---

## 8. Operating System Requirements

| Requirement | Details |
|---|---|
| **OS** | Linux (x86_64). Docker Desktop on macOS/Windows works for development but is not recommended for production. |
| **Docker Engine** | 24.0+ with Compose V2 |
| **File system** | ext4 or XFS for Docker volumes. Use `noatime` mount option for Solr volumes. |
| **Kernel** | 5.10+ recommended. Ensure `vm.max_map_count >= 262144` for Solr (SolrCloud may fail to start otherwise). |
| **GPU (optional)** | NVIDIA driver 470+, NVIDIA Container Toolkit installed |

Set the kernel parameter:

```bash
# Temporary (lost on reboot)
sudo sysctl -w vm.max_map_count=262144

# Persistent
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.d/99-solr.conf
sudo sysctl --system
```

---

## 9. Pre-Deployment Checklist

Use this checklist before deploying Aithena to a new host:

- [ ] Host meets minimum CPU, RAM, and disk requirements for your deployment size (see §1)
- [ ] SSD or NVMe storage is available for all Docker volumes
- [ ] `vm.max_map_count` is set to 262144 or higher
- [ ] Docker Engine 24.0+ and Compose V2 are installed
- [ ] (Optional) NVIDIA Container Toolkit is installed if using GPU
- [ ] `python3 -m installer` has been run to generate `.env`, auth storage, and JWT secret
- [ ] Firewall allows inbound traffic on port 80 (and 443 if using TLS)
- [ ] No outbound internet access is required at runtime
- [ ] Sufficient disk space is available for the source PDF library plus stack volumes

---

## Further Reading

- [Search and Indexing Sizing Guide](deployment/sizing-guide.md) — analytical formulas for chunk counts, vector footprint, and Solr memory planning
- [Admin Manual](admin-manual.md) — deployment procedures, configuration reference, and monitoring
- [Failover & Recovery Runbook](deployment/failover-runbook.md) — outage handling for all services
