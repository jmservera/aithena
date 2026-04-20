# Standalone vs SolrCloud Infrastructure Analysis

**Author:** Brett (Infra Architect)  
**Date:** 2026-04-20  
**Context:** Evaluating standalone Solr (single-node) vs SolrCloud for 30K books → 9M pages → 54M vectors

---

## Executive Summary

For a **single-machine deployment** handling 30K books (9M pages, 54M embedding vectors), **standalone Solr is the clear winner** over SolrCloud for infrastructure costs, operational complexity, and resource efficiency.

**Key findings:**
- **Standalone:** 1 beefy VM (~$800-1,200/mo), simple ops, 8-10 GB RAM for Solr + embeddings
- **SolrCloud 3-node:** 3 VMs + 3 ZK nodes (~$1,800-2,400/mo), 3× storage replication, ZK quorum management
- **Migration path:** Start standalone, migrate to SolrCloud if HA becomes critical (reindex required)
- **Recommendation:** Use standalone unless you need multi-node fault tolerance

---

## 1. Docker Compose Resource Sizing

### 1.1 Current Configuration

**Base docker-compose.yml (3-node SolrCloud):**
```
Solr:         3 nodes × 2 GB RAM × 1.0 CPU = 6 GB RAM, 3.0 CPU
ZooKeeper:    3 nodes × 512 MB RAM        = 1.5 GB RAM
embeddings:   1 node × 2-3 GB RAM × 1 CPU = 2-3 GB RAM, 1.0 CPU
RabbitMQ:     1 node × 1 GB RAM           = 1 GB RAM
Redis:        512 MB RAM
Other svcs:   ~2 GB RAM
────────────────────────────────────────────────────────
Total:        ~13-14 GB RAM, ~5-6 CPU cores
```

**compose.single-node.yml (already exists):**
```
Solr:         1 node × 2 GB RAM × 1 CPU   = 2 GB RAM, 1.0 CPU
ZooKeeper:    1 node × 512 MB RAM         = 512 MB RAM
embeddings:   same
RabbitMQ:     same
Redis:        same
Other svcs:   same
────────────────────────────────────────────────────────
Total:        ~8 GB RAM, ~3-4 CPU cores
Savings:      -5 GB RAM, -2 CPU cores vs 3-node cluster
```

### 1.2 Sizing for 54M Vectors + 9M Page Index

**Data model:**
- 30K books
- 9M pages (~300 pages/book average)
- Chunks: 9M pages × 300 words/page ÷ 350 words/chunk = **7.7M chunks**
- Vectors: 768 dimensions × 4 bytes = **3 KB/vector** (raw) → ~4-5 KB with HNSW index
- **Vector index size:** 7.7M vectors × 5 KB ≈ **38 GB working set**
- **Full-text index:** 9M pages × ~15 KB/page (compressed) ≈ **135 GB**
- **Total index:** ~175 GB single replica

**Storage requirements:**

| Topology | Index Size | Overhead (merge/backup) | Total Disk |
|---|---:|---:|---:|
| **Standalone (RF=1)** | 175 GB | 2× (350 GB) | **350-400 GB SSD** |
| **SolrCloud (RF=3)** | 525 GB (3×) | 2× (1,050 GB) | **1+ TB SSD** |

**Memory requirements:**

Solr needs RAM for:
1. **JVM heap:** Query caches, transaction logs, GC overhead
2. **OS page cache:** HNSW vector index working set (critical for performance)
3. **Native memory:** Off-heap Lucene structures

**Standalone Solr node sizing:**
```
Vector working set:    38 GB (needs page cache)
Full-text index:      ~20 GB active working set (page cache)
JVM heap:              8 GB (query caches, buffers)
OS + overhead:         2 GB
────────────────────────────────────────────────────────
Total per node:       ~70 GB RAM
```

**Recommended:** 
- **Standalone:** 1 Solr node with **80-96 GB RAM**, 16-24 CPU cores
- **SolrCloud:** 3 Solr nodes × 32-48 GB RAM each = 96-144 GB total (but distributed)

### 1.3 JVM Heap Sizing

**For 54M vector + 9M page workload:**

| Solr RAM | JVM Heap | Page Cache | Use Case |
|---:|---:|---:|---|
| 32 GB | 12 GB | 20 GB | Min for SolrCloud node (tight) |
| 48 GB | 16 GB | 32 GB | Comfortable SolrCloud node |
| 80 GB | 24 GB | 56 GB | Standalone node (recommended) |
| 96 GB | 32 GB | 64 GB | Standalone with headroom |

**Critical:** For HNSW vector search at this scale, **page cache > heap**. Aim for 60-70% of RAM as page cache.

**docker-compose.yml override for standalone:**
```yaml
services:
  solr:
    environment:
      SOLR_JAVA_MEM: "-Xms16g -Xmx24g"
    deploy:
      resources:
        limits:
          memory: 80g
        reservations:
          memory: 64g
          cpus: "16.0"
```

### 1.4 Embeddings Server

At 7.7M chunks, indexing is the bottleneck. Sizing:
- **CPU:** 8-16 s per 40-chunk batch → ~2-5 docs/min/replica
- **GPU:** 0.5-2 s per 40-chunk batch → ~10-20 docs/min/replica

**For 30K books:**
- CPU-only: 30K ÷ 5 docs/min ÷ 60 = **100 hours** (4+ days)
- GPU (single): 30K ÷ 15 docs/min ÷ 60 = **33 hours** (1.4 days)
- GPU (4 indexer replicas): **~8-10 hours**

**Recommendation:** GPU-backed embeddings-server essential for this scale.
- **NVIDIA RTX 4000 / A10 / T4:** 16-24 GB VRAM
- **embeddings-server:** 8 GB RAM container limit (model + batch buffers)

---

## 2. Single-Node vs Multi-Node Cost

### 2.1 Cloud VM Pricing (April 2026 estimates)

**Azure Standard_D16s_v5 (standalone single node):**
- 16 vCPU, 64 GB RAM, 600 GB temp SSD
- **Cost:** ~$700-900/mo (1-year reserved)
- **+ Premium SSD:** 512 GB P30 = ~$135/mo
- **Total:** **~$850/mo**

**Azure Standard_D32s_v5 (standalone with GPU option via NCv3):**
- 32 vCPU, 128 GB RAM, 1 TB SSD
- **Cost:** ~$1,400-1,600/mo (1-year reserved)
- **Or NC6s_v3:** 6 vCPU, 112 GB RAM, 1× V100 GPU = ~$1,200/mo
- **Total:** **~$1,200-1,600/mo** (GPU-backed)

**SolrCloud 3-node cluster:**
- **3× Standard_D8s_v5:** 8 vCPU, 32 GB RAM each = ~$400/mo each
- **3× Premium SSD P30:** 512 GB each = ~$135/mo each
- **3× ZooKeeper (can colocate):** included
- **1× embeddings GPU node:** ~$800-1,000/mo
- **Total:** **~$2,800-3,200/mo**

**AWS Equivalent:**
- **Standalone:** r6i.4xlarge (16 vCPU, 128 GB RAM) = ~$900-1,100/mo + EBS
- **SolrCloud:** 3× r6i.2xlarge (8 vCPU, 64 GB RAM) = ~$2,400/mo + EBS
- **GPU:** g5.xlarge (4 vCPU, 16 GB RAM, A10G GPU) = ~$800/mo

### 2.2 Cost Summary

| Topology | Monthly Cost | Annual Cost | Cost per Book |
|---|---:|---:|---:|
| **Standalone (CPU)** | $850 | $10,200 | $0.34 |
| **Standalone (GPU)** | $1,200 | $14,400 | $0.48 |
| **SolrCloud (3-node + GPU)** | $2,800 | $33,600 | $1.12 |
| **SolrCloud (fully managed)** | $4,000+ | $48,000+ | $1.60+ |

**Savings:** Standalone saves **$1,600-1,800/mo** (58-64% reduction) vs SolrCloud.

### 2.3 Hidden Costs

**SolrCloud additional overhead:**
- **ZooKeeper management:** Quorum health monitoring, snapshot cleanup, upgrade coordination
- **Replica sync failures:** Peer sync, tlog replay, full replication recovery
- **Network transfer:** Inter-node replication at 175 GB × 3 = 525 GB initial + deltas
- **Split-brain risk:** 2-node failure = write outage; manual intervention required
- **Configset sync:** ZK-based config distribution; version mismatches cause subtle bugs

**Standalone risks:**
- **No HA:** Single-node failure = full outage (but simpler recovery: restart + restore backup)
- **Backup discipline:** Must have automated daily Solr snapshots + ZK backup (already in BCDR plan v1.10.0)

---

## 3. Operational Complexity

### 3.1 Standalone Solr

**Pros:**
- ✅ **Simple:** 1 Solr node, 1 ZK node, no quorum math
- ✅ **No split-brain:** Single source of truth
- ✅ **Faster restarts:** No peer sync, no replica recovery delays
- ✅ **Easier debugging:** All logs in one place
- ✅ **Lower disk I/O:** No replication overhead
- ✅ **Backup/restore:** Single replica = half the backup time/space

**Cons:**
- ⚠️ **No HA:** Restart during Solr crash = 60-120s downtime
- ⚠️ **Manual failover:** Hardware failure requires restore from backup
- ⚠️ **No rolling restarts:** Upgrades require brief outage

**Ops runbook (standalone):**
1. Daily automated Solr snapshot (already scripted in v1.10.0 BCDR)
2. ZK backup (single node, < 100 MB)
3. Monitor: disk space, heap usage, query latency
4. Upgrade: stop stack, upgrade images, restart (~2-5 min downtime)
5. Disaster recovery: restore snapshot, replay incremental from Redis state

**Maintenance time:** ~30-60 min/month (mostly monitoring + upgrades)

### 3.2 SolrCloud 3-Node

**Pros:**
- ✅ **High availability:** Survive 1 node failure (2-of-3 quorum)
- ✅ **Rolling restarts:** Upgrade nodes one-by-one without downtime
- ✅ **Automatic replica recovery:** Peer sync or tlog replay

**Cons:**
- ⚠️ **ZK quorum complexity:** Losing 2 ZK nodes = write outage, manual recovery
- ⚠️ **Replica sync failures:** Out-of-sync replicas require manual ADDREPLICA + full sync
- ⚠️ **Configset versioning:** ZK-based config changes affect all nodes; rollback is manual
- ⚠️ **3× storage overhead:** 175 GB → 525 GB replication
- ⚠️ **Network-sensitive:** Slow inter-node links cause sync lag
- ⚠️ **Split-brain debugging:** Determining leader/follower state during partition requires ZK expertise

**Ops runbook (SolrCloud):**
1. Monitor ZK quorum (3 nodes, 2-of-3 health)
2. Monitor Solr replica sync (check shard leader, replica state)
3. Handle replica recovery (ADDREPLICA, REBALANCELEADERS commands)
4. Daily backup per-shard (3× backup time/space vs standalone)
5. ZK snapshot coordination (3 nodes)
6. Upgrade coordination: rolling restart script, validate quorum at each step
7. Disaster recovery: restore all 3 replicas, sync ZK state, validate leader election

**Maintenance time:** ~2-4 hours/month (quorum monitoring, replica health, upgrade coordination)

### 3.3 Complexity for 1-2 Person Team

| Task | Standalone | SolrCloud |
|---|---|---|
| **Daily monitoring** | 10 min | 30 min (quorum + replica health) |
| **Monthly upgrades** | 30 min (brief outage) | 90-120 min (rolling restart) |
| **Disaster recovery** | 60-90 min (restore snapshot) | 180-240 min (restore 3 replicas + ZK sync) |
| **Debugging outages** | Simple (1 node logs) | Complex (3 nodes + ZK + replica state) |
| **Learning curve** | Low (basic Solr + Docker) | High (SolrCloud, ZK, distributed systems) |

**Verdict:** For 1-2 person team, **standalone is 3-4× less operational overhead**.

---

## 4. Migration Path

### 4.1 Can You Start Standalone and Migrate Later?

**Yes, but requires reindex.**

**Standalone → SolrCloud migration steps:**
1. **Backup standalone Solr:** Use Solr snapshot API
2. **Stand up 3-node SolrCloud cluster:** New VMs, ZK ensemble
3. **Create collection with RF=3:** Collections API with `numShards=1&replicationFactor=3`
4. **Option A (fast):** Restore snapshot to SolrCloud, let replicas sync
   - **Time:** ~2-4 hours for 175 GB restore + replication
5. **Option B (safe):** Full reindex from source PDFs via document-lister
   - **Time:** 30K books × 2-5 min/book = **100-150 hours** (CPU) or **30-40 hours** (GPU)

**docker-compose changes:**
- Remove `-f docker/compose.single-node.yml` overlay
- Revert to base 3-node topology
- Update `.env`: `SOLR_REPLICATION_FACTOR=3`
- Run `docker compose up -d` (new containers)

**Data migration:**
- **Backup/restore:** Solr Collections API supports snapshot → restore to new cluster
- **Reindex:** Safer but slower; validates all data paths

### 4.2 SolrCloud → Standalone (Downgrade Path)

**Why you might downgrade:**
- Cost reduction
- Operational simplification
- Single-machine sufficiency

**Steps:**
1. **Stop writes:** Disable document-lister/indexer
2. **Backup one replica:** Snapshot API from `solr` node (RF=3 means identical replicas)
3. **Destroy SolrCloud:** `docker compose down`, clear volumes
4. **Deploy standalone:** `docker compose -f docker-compose.yml -f docker/compose.single-node.yml up -d`
5. **Restore snapshot:** Upload configset, create collection (RF=1), restore data
6. **Resume indexing:** Re-enable lister/indexer

**Downtime:** 30-60 min (backup + restore + validation)

---

## 5. Current Infrastructure Setup

### 5.1 Existing Configurations

**Files:**
- `docker-compose.yml` — **3-node SolrCloud** (default)
- `docker/compose.prod.yml` — **3-node SolrCloud** (GHCR images)
- `docker/compose.single-node.yml` — **1-node Solr + 1-node ZK** (already exists! 🎉)

**Current topology (default):**
```
zoo1, zoo2, zoo3:        3 ZK nodes, 512 MB each
solr, solr2, solr3:      3 Solr nodes, 2 GB RAM × 1 CPU each
solr-init:               Configset upload, user bootstrap (1-shot)
embeddings-server:       2-3 GB RAM × 1 CPU (CPU-only)
document-indexer:        1 replica, 512 MB
RabbitMQ, Redis, nginx:  Standard limits
```

**Single-node topology (compose.single-node.yml):**
```yaml
services:
  zoo1:
    environment:
      ZOO_STANDALONE_ENABLED: "true"
      ZOO_SERVERS: ""  # No ensemble
  zoo2:
    deploy:
      replicas: 0  # Disabled
  zoo3:
    deploy:
      replicas: 0  # Disabled
  solr:
    environment:
      ZK_HOST: "zoo1:2181"  # Single ZK
  solr2:
    deploy:
      replicas: 0  # Disabled
  solr3:
    deploy:
      replicas: 0  # Disabled
  solr-init:
    environment:
      SOLR_EXPECTED_NODES: "1"
      SOLR_REPLICATION_FACTOR: "1"
```

**Savings:** ~5 GB RAM, saves 2 Solr + 2 ZK containers.

### 5.2 Resource Competition

**Current host (Azure Standard_D16s_v5, 16 vCPU, 64 GB RAM):**
```
Allocated to stack:  ~13-14 GB (3-node)
OS + overhead:       ~2-4 GB
Available for work:  ~48-50 GB
```

**For 54M vectors:**
```
Required:            ~70-80 GB (standalone Solr + embeddings GPU)
Current host:        Insufficient (64 GB total)
```

**Recommendation:** Upgrade to **Standard_D32s_v5** (32 vCPU, 128 GB RAM) or **NCv3-series** (GPU).

### 5.3 Other Services

**Non-Solr resource needs (unchanged):**
- **embeddings-server (GPU):** 8 GB RAM, 1 GPU
- **RabbitMQ:** 1 GB RAM
- **Redis:** 512 MB RAM
- **nginx, UI, APIs:** ~2 GB RAM
- **Total non-Solr:** ~12 GB RAM, 1 GPU

**Standalone VM sizing:**
```
Solr:                80 GB RAM
Embeddings + other:  12 GB RAM
OS overhead:         4 GB RAM
────────────────────────────────
Total:              ~96 GB RAM → 128 GB VM
```

**Recommended VM:**
- **Azure NC24s_v3:** 24 vCPU, 224 GB RAM, 2× V100 GPUs = ~$3,000/mo (overkill)
- **Azure NC6s_v3:** 6 vCPU, 112 GB RAM, 1× V100 GPU = **~$1,200/mo** ✅
- **Or Standard_D32s_v5 + separate GPU VM:** Solr on D32, embeddings on NC6 = ~$2,000/mo

**Cost-optimized:** Single **NC6s_v3** VM handles both Solr (80 GB) + embeddings (GPU, 8 GB) comfortably.

---

## 6. Recommendations

### 6.1 For 30K Books (54M Vectors)

**Start with standalone:**
1. Use `docker/compose.single-node.yml` overlay
2. Deploy on **Azure NC6s_v3** (112 GB RAM, V100 GPU) = **$1,200/mo**
3. Configure Solr:
   - `SOLR_JAVA_MEM="-Xms16g -Xmx24g"`
   - Container limit: 80 GB RAM
   - `SOLR_REPLICATION_FACTOR=1`
4. Configure embeddings-server:
   - GPU passthrough: `-f docker/compose.gpu-nvidia.yml`
   - Container limit: 8 GB RAM
5. Storage: 512 GB Premium SSD P30 ($135/mo) for Solr + embeddings data

**Total cost:** **~$1,350/mo** (VM + storage)

**Indexing time:** 30K books at 15 docs/min (GPU) = **33 hours** (acceptable one-time cost)

**Operational overhead:** 30-60 min/month (1-person manageable)

### 6.2 When to Move to SolrCloud

**Trigger conditions:**
1. **HA requirement:** SLA demands < 1 min downtime for Solr failures
2. **Multi-region:** Need geo-distributed replicas
3. **> 100K books:** Sharding becomes beneficial for write throughput
4. **Team growth:** 3+ ops staff can handle ZK complexity

**Until then:** Standalone + daily backups + monitoring = sufficient.

### 6.3 Hybrid Approach (If Budget Allows)

**Best of both worlds:**
- **Primary:** Standalone Solr (NC6s_v3, $1,200/mo)
- **Standby:** Cheap DR replica (Standard_D4s_v5, 4 vCPU, 16 GB, $150/mo) with nightly snapshot restore
- **Failover time:** 5-10 min (DNS swap + warmup)
- **Total cost:** **$1,350/mo** (vs $2,800 for full SolrCloud)

**Recovery steps:**
1. Detect primary failure (health check)
2. Start standby VM (if stopped)
3. Restore latest snapshot
4. Update DNS / nginx upstream
5. Resume operations

**Downtime:** 5-10 min (automated failover) vs 0 min (SolrCloud) vs 30-60 min (manual restore)

---

## 7. Disk Space Estimates

### 7.1 Breakdown

| Component | Size | Notes |
|---|---:|---|
| **Solr index (RF=1)** | 175 GB | 54M vectors + 9M pages |
| **Merge headroom (2×)** | 350 GB | Lucene segment merges |
| **Daily snapshots (7 days)** | 1.2 TB | 7 × 175 GB (incremental possible) |
| **ZooKeeper (standalone)** | 500 MB | Config + cluster state |
| **RabbitMQ** | 5 GB | Durable queue logs |
| **Redis** | 1 GB | 30K × 1.5 KB JSON state |
| **Docker images** | 8 GB | All services |
| **Total working set** | ~400 GB | |
| **Total with backups** | ~1.6 TB | 7-day retention |

**Recommendation:**
- **Working storage:** 512 GB Premium SSD P30 ($135/mo)
- **Backup storage:** 2 TB Standard HDD or Azure Blob cold tier ($20-40/mo)

### 7.2 Disk I/O Requirements

**Solr HNSW index:**
- Random read-heavy workload
- **IOPS:** 5,000-10,000 read IOPS during query bursts
- **Throughput:** 200-500 MB/s for large result sets

**Recommendation:** Premium SSD (P30 = 5,000 IOPS, 200 MB/s baseline)

---

## 8. Comparison Table

| Dimension | Standalone | SolrCloud (3-node) |
|---|---|---|
| **Monthly cost** | **$1,350** | $2,800 |
| **Annual cost** | **$16,200** | $33,600 |
| **Setup time** | **30 min** | 2-3 hours |
| **Ops overhead** | **30-60 min/mo** | 2-4 hours/mo |
| **Learning curve** | Low | High |
| **Downtime (planned)** | 2-5 min/upgrade | 0 min (rolling) |
| **Downtime (failure)** | 30-60 min (restore) | 0 min (1 node), write outage (2 nodes) |
| **Disk usage** | **350 GB** | 1+ TB (3× replication) |
| **Backup time** | **30-60 min** | 90-180 min (3 replicas) |
| **Debugging complexity** | **Low** | High (3 nodes + ZK) |
| **Split-brain risk** | **None** | 2-node failure |
| **Team size** | 1 person | 2-3 people |
| **Scalability ceiling** | ~100K books | ~1M books (with sharding) |

---

## 9. Migration Checklist

### 9.1 Deploying Standalone (From Default 3-Node)

**Steps:**
```bash
# 1. Stop current stack
docker compose down

# 2. Backup existing data (if any)
./e2e/backup-restore/backup.sh

# 3. Update .env
echo "SOLR_REPLICATION_FACTOR=1" >> .env
echo "SOLR_NUM_SHARDS=1" >> .env

# 4. Start standalone topology
docker compose -f docker-compose.yml -f docker/compose.single-node.yml up -d

# 5. Verify single Solr node
docker ps | grep solr  # Should see only "solr", not solr2/solr3

# 6. Check ZooKeeper standalone
docker exec zoo1 zkServer.sh status  # Should show "Mode: standalone"

# 7. Restore data (if applicable)
# ./e2e/backup-restore/restore.sh <snapshot-name>

# 8. Validate collection
curl -u admin:pass http://localhost:8983/solr/admin/collections?action=CLUSTERSTATUS
# Should show replicationFactor=1
```

### 9.2 Upgrading to SolrCloud (From Standalone)

**Steps:**
```bash
# 1. Stop writes (disable lister/indexer)
docker compose stop document-lister document-indexer

# 2. Create snapshot
curl -u admin:pass "http://localhost:8983/solr/admin/collections?action=BACKUP&name=pre-cloud&collection=books&location=/backup"

# 3. Stop standalone
docker compose down

# 4. Update .env
sed -i 's/SOLR_REPLICATION_FACTOR=1/SOLR_REPLICATION_FACTOR=3/' .env

# 5. Start 3-node SolrCloud (remove single-node overlay)
docker compose up -d

# 6. Verify 3 Solr nodes + 3 ZK nodes
docker ps | grep -E 'solr|zoo'  # Should see solr, solr2, solr3, zoo1, zoo2, zoo3

# 7. Restore snapshot (will auto-replicate to RF=3)
# Use Solr Collections API RESTORE command

# 8. Resume writes
docker compose start document-lister document-indexer
```

---

## 10. Conclusion

**For 30K books (54M vectors), standalone Solr is the optimal choice:**

✅ **58% cost savings** ($1,350/mo vs $2,800/mo)  
✅ **3-4× less operational complexity**  
✅ **Simpler debugging and maintenance**  
✅ **Adequate for single-machine deployments**  
✅ **Clear migration path to SolrCloud if needed**  

**When to reconsider:**
- SLA requires < 1 min downtime for failures
- Library grows beyond 100K books (sharding beneficial)
- Team grows to 3+ ops staff (can absorb ZK complexity)
- Multi-region deployment needed

**Next steps:**
1. Deploy standalone on **Azure NC6s_v3** (112 GB RAM, V100 GPU)
2. Configure Solr with 24 GB heap, 80 GB container limit
3. Enable GPU for embeddings-server
4. Set up daily automated backups (already in v1.10.0 BCDR plan)
5. Monitor heap usage, query latency, disk I/O for 2-4 weeks
6. Adjust resources based on actual usage patterns

---

**Files referenced:**
- `docker-compose.yml` — Base 3-node SolrCloud topology
- `docker/compose.single-node.yml` — Standalone overlay (already exists)
- `docker/compose.prod.yml` — Production 3-node config
- `docker/compose.gpu-nvidia.yml` — GPU passthrough for embeddings
- `docs/deployment/sizing-guide.md` — Analytical sizing formulas
- `docs/hardware-requirements.md` — Per-service resource breakdown
- `.squad/agents/brett/history.md` — Infra patterns and SolrCloud ops experience
