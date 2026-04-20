# Deployment Topologies: Single-Node vs. Distributed

This document describes the two supported Solr deployment architectures for Aithena and helps you choose the right topology for your deployment.

## Overview

Aithena supports two fundamentally different Solr deployment topologies:

1. **SolrCloud Distributed** (default in `docker-compose.yml`) — Three-node SolrCloud cluster with three-node ZooKeeper ensemble
2. **Standalone Solr** — Single Solr node with embedded ZooKeeper (planned for resource-constrained deployments)

The choice depends on your scale, budget, operational complexity, and high-availability requirements.

---

## 1. SolrCloud Distributed Topology (Current Default)

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  ZooKeeper Ensemble (3 nodes)                             │
│  ┌───────────────┬───────────────┬───────────────┐        │
│  │    zoo1       │    zoo2       │    zoo3       │        │
│  │   :2181       │   :2181       │   :2181       │        │
│  └───────────────┴───────────────┴───────────────┘        │
│           ▲           ▲                ▲                   │
│           │           │                │ (leader election)│
│  ┌────────┴───────────┴────────────────┴─────────┐        │
│  │                                                │        │
│  │   SolrCloud Cluster (3 nodes, RF=3, 1 shard)│        │
│  │  ┌──────────────┬──────────────┬──────────┐ │        │
│  │  │   solr       │   solr2      │  solr3   │ │        │
│  │  │  :8983       │   :8983      │ :8983    │ │        │
│  │  │              │              │          │ │        │
│  │  │ (leader)     │ (replica)    │(replica) │ │        │
│  │  └──────────────┴──────────────┴──────────┘ │        │
│  │       Collection: books (3 replicas)        │        │
│  └────────────────────────────────────────────┘        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Configuration

**Docker Compose override:** Base `docker-compose.yml`  
**Environment variable:** `ZK_HOST: "zoo1:2181,zoo2:2181,zoo3:2181"`

### When to Use

- **Production deployments** with high-availability requirements
- **Books > 3,000** (>1.8M vectors)
- **Team or organizational** usage where uptime SLA matters
- **Distributed data centers** or multi-host deployments
- When **operational cost can absorb** quorum management complexity

### Hardware Requirements

| Component | Minimum | Recommended | Large Scale |
|-----------|---------|-------------|------------|
| **Solr (3 nodes)** | 2 GB each | 4–6 GB each | 8–12 GB each |
| **ZooKeeper (3 nodes)** | 256 MB each | 512 MB each | 512 MB each |
| **Other services** | 4 GB total | 8–10 GB total | 10–16 GB total |
| **Total Host RAM** | 16 GB | 24–32 GB | 48–64 GB |
| **CPU** | 8 cores | 12–16 cores | 16+ cores |
| **Disk** | 100 GB SSD | 200–500 GB SSD | 500 GB+ NVMe |

### Advantages

✅ **High Availability (HA):**
- Node failures do not disrupt search or indexing
- Automatic failover via ZooKeeper leader election
- Replication factor 3 means any single node can fail

✅ **Operational Readiness:**
- Leader → follower topology ensures consistent distributed semantics
- Zero-downtime rolling deployments
- Cluster-aware health checks (`CLUSTERSTATUS` API)

✅ **Scaling:**
- Supports horizontal growth (add shards for >100K documents)
- Distributed query execution across nodes
- Proven architecture for enterprise deployments

### Limitations

🔴 **Operational Complexity:**
- ZooKeeper quorum management required (no single-node failures tolerated)
- Distributed debugging (tracing issues across 3 nodes)
- Leader election and session timeouts can disrupt briefly
- More services to monitor and troubleshoot

🔴 **Cost:**
- 3× the infrastructure (Solr nodes, ZK nodes, volumes)
- ~2.5× more expensive than single-node for <30K books
- Significant CPU/memory overhead for coordination

🔴 **Resource Overhead:**
- ZooKeeper adds ~1.5 GB memory, 3 persistent volumes
- Inter-node network traffic (gossip, replication)
- Not ideal for dev/test environments

### Capacity Planning

Solr stores data in a **single shard with replication factor 3**. Every indexed byte exists on all three nodes.

| Books | Vectors | Disk per Node | Physical Total | Search Latency (p95) |
|-------|---------|---------------|-----------------|---------------------|
| 500 | 3M | 1–2 GB | 3–6 GB | <300 ms |
| 5K | 30M | 10–20 GB | 30–60 GB | <500 ms |
| 30K | 180M | 60–120 GB | 180–360 GB | <2 s (cold pages) |
| 100K | 600M | 200–400 GB | 600–1,200 GB | <5 s (cold pages) |

> Latency degrades if the working set exceeds available RAM (OS page cache). NVMe SSD storage is critical for large deployments.

### Operations: Scaling from Single-Node to Distributed

If you start with standalone Solr and outgrow it, migrating to SolrCloud requires:

1. **Stop indexing** on the single-node Solr
2. **Create SolrCloud cluster** with 3+ nodes and ZooKeeper ensemble
3. **Re-index** the entire book library from source PDFs
4. **Validate** search quality and latency before switching traffic

**Effort:** Medium-high (full re-index, temporary downtime)

---

## 2. Standalone Solr Topology (Planned for v2.0+)

### Architecture

```
┌─────────────────────────────────────────────────┐
│                                                 │
│   Single Solr Node (all data on one machine)  │
│  ┌─────────────────────────────────────────┐  │
│  │   solr (standalone mode)                │  │
│  │   :8983                                 │  │
│  │                                         │  │
│  │   • No ZooKeeper                        │  │
│  │   • Single-shard, no replication        │  │
│  │   • 100% query and index traffic here   │  │
│  │                                         │  │
│  └─────────────────────────────────────────┘  │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Configuration

**Not yet in `docker-compose.yml`** — planned for future release.  
**Environment variable:** `ZK_HOST=""` (or absent) — runs in standalone mode

### When to Use

- **Books < 3,000** (<1.8M vectors)
- **Memory-constrained** deployments (32 GB budget)
- **Development, testing,** and **sandbox** environments
- **Cost-sensitive** deployments (2.5× cheaper than SolrCloud for small scale)
- When **operational simplicity** is a priority
- **Self-hosted** or **personal** usage (no SLA required)

### Hardware Requirements

| Component | Minimum | Recommended | With GPU |
|-----------|---------|-------------|----------|
| **Solr** | 2–4 GB | 8 GB | 8–12 GB |
| **embeddings-server** | 1–2 GB | 2–4 GB | 4–8 GB (+ GPU VRAM) |
| **Other services** | 2 GB total | 4 GB total | 4 GB total |
| **Total Host RAM** | 8 GB | 16 GB | 20–32 GB |
| **CPU** | 4 cores | 8 cores | 12+ cores (GPU host) |
| **Disk** | 50 GB SSD | 100–200 GB SSD | 100–200 GB SSD |
| **GPU (optional)** | — | — | NVIDIA 2+ GB VRAM |

### Advantages

✅ **Operational Simplicity:**
- No quorum management (one process to manage)
- Single point of administration
- Easier debugging (logs in one place)
- Minimal configuration

✅ **Cost Efficiency:**
- ~2.5× cheaper infrastructure vs SolrCloud for <30K books
- No ZooKeeper overhead
- Single volume for all data
- Ideal for startups, teams, self-hosted

✅ **Development Velocity:**
- Easier to prototype and test
- Instant schema changes (no cluster coordination)
- Faster iteration for research projects

### Limitations

🔴 **No High Availability:**
- Single node failure = full system downtime
- No automatic failover
- Requires manual restore from backup
- Not suitable for production SLAs

🔴 **Scale Ceiling:**
- Recommended max: 30K books (180–360 GB index)
- Beyond that, memory becomes prohibitively expensive
- Cannot add shards for horizontal growth
- Page cache performance degrades above 50% memory pressure

🔴 **Memory Pressure:**
- Full-text index + vector HNSW graph compete for page cache
- Requires careful tuning of JVM heap vs. OS page cache
- Without optimization, 30K books needs 130+ GB RAM

### Capacity Planning

All data resides on a single node. Memory must accommodate JVM heap + OS page cache for both indexes.

| Books | Vectors | Solr HNSW | Text Index | Required RAM |
|-------|---------|-----------|-----------|--------------|
| 500 | 3M | 8 GB | 2 GB | 16 GB |
| 3K | 18M | 40 GB | 10 GB | 64 GB |
| 10K | 60M | 130 GB | 25 GB | 180 GB |
| 30K (optimized) | 180M* | 9 GB | 8 GB | 32 GB |

\* **Optimized** = page-level chunking (6× reduction) + int8 quantization (4× per-vector) + HNSW tuning  
See [Vector Optimization](#vector-optimization) for details.

### Vector Optimization (Critical for 32 GB Deployments)

If deploying a large library on a memory-constrained 32 GB machine, apply these optimizations:

#### Phase 1: Page-Level Chunking (No Schema Change)

Change chunking strategy from **400-word passages** to **full pages**:

- **Reduction:** 54M vectors → 9M vectors (6× improvement)
- **Quality loss:** Minimal (page is a natural search unit)
- **Implementation:** Modify document-indexer chunk size; re-index required
- **Timeline:** 1–2 weeks

#### Phase 2: int8 Quantization (Solr 9.7 Ready)

Enable `vectorEncoding="BYTE"` in the schema:

- **Reduction:** 4× per-vector (3,328 bytes → 832 bytes)
- **Quality loss:** ~1–3% recall@10 (acceptable trade-off)
- **Implementation:** Schema change + quantization in embeddings-server
- **Timeline:** 2–3 weeks + re-index

#### Phase 3: Model Downgrade (Optional)

Switch from `multilingual-e5-base` (768D) to `multilingual-e5-small` (384D):

- **Reduction:** 2× (384D vs 768D)
- **Quality loss:** ~5% relative on benchmarks (acceptable for teams)
- **Implementation:** Model switch in embeddings-server config + re-index
- **Timeline:** 3–4 weeks + A/B testing

**Combined (Phases 1–2):**
- HNSW footprint: 54M → 9M vectors × 832 bytes/vector = **~7.5 GB**
- Total memory budget: 2 GB (OS) + 8 GB (JVM) + 7.5 GB (HNSW) + 8 GB (text) + 6.5 GB (headroom) = **32 GB** ✅

### Operations: No Built-in Failover

If the single Solr node fails:

1. **Restore from backup** (SolrCloud snapshot or full tar.gz)
2. **Restart Solr** and wait for index warmup (5–30 minutes depending on size)
3. **Validate** search is responding
4. **Trigger re-index** if backup is stale

**RTO (Recovery Time Objective):** 30–60 minutes  
**RPO (Recovery Point Objective):** Last backup (recommend daily)

---

## Comparison Table

| Feature | SolrCloud (Distributed) | Standalone |
|---------|------------------------|-----------|
| **Nodes** | 3+ (Solr) + 3 (ZK) | 1 |
| **Replication Factor** | 3 (3 replicas) | None (single copy) |
| **High Availability** | ✅ Yes (auto-failover) | ❌ No (manual restore) |
| **Books Supported** | Unlimited (add shards) | 3K–30K (with optimization) |
| **RAM per node** | 2–8 GB | 8–32 GB |
| **Total Infrastructure Cost** | 🔴 ~2.5× | 🟢 ~1× |
| **Operational Overhead** | 🔴 High (ZK quorum) | 🟢 Low (single process) |
| **Debugging Complexity** | 🔴 High (distributed) | 🟢 Low (single point) |
| **Zero-Downtime Deployments** | ✅ Yes (rolling restart) | ❌ No (full restart) |
| **Development Velocity** | 🟡 Medium (cluster ops) | 🟢 High (instant changes) |
| **Search Latency (warm)** | 100–500 ms | 100–500 ms |
| **Search Latency (cold, 75% cache)** | 500 ms–2 s | 500 ms–2 s |
| **Index Scaling** | Add shards to grow | Re-optimize or migrate |
| **Recommended Min Books** | 1,000+ | < 3,000 |
| **Production Ready** | ✅ Yes (proven) | 🟡 Planned (not yet deployed) |

---

## Selection Guide: Which Topology Should I Use?

### Quick Decision Tree

```
Are you starting a new deployment?
├─ YES: How many books will you have?
│  ├─ < 500 books
│  │  └─ → STANDALONE (optimal for personal use)
│  ├─ 500–3,000 books
│  │  └─ → STANDALONE (cost-effective)
│  ├─ 3,000–10,000 books
│  │  ├─ Budget for 64GB+ RAM?
│  │  │  ├─ YES → STANDALONE + optimization
│  │  │  └─ NO → SOLRCLOUD (scale horizontally)
│  │  └─ Need HA/SLA?
│  │     ├─ YES → SOLRCLOUD
│  │     └─ NO → STANDALONE
│  └─ > 10,000 books
│     └─ → SOLRCLOUD (RECOMMENDED)
│
└─ NO: Migrating from another system?
   └─ → Contact support for migration path
```

### Use Cases by Deployment Type

#### 🟢 Standalone is Right For:

- **Personal use:** Self-hosted library for one user
- **Team (< 500 books):** Small group sharing books
- **Development & CI/CD:** Local testing, GitHub Actions
- **Proof of Concept:** Evaluating Aithena before bigger investment
- **Constrained budget:** Non-profit, educational, research institutions
- **Resource limits:** 32 GB RAM available, no options to expand

**Example:** University library with 2,000 historical texts, one IT staff member, budget $500–800/year for cloud VM.

#### 🟡 Mixed Approach (Start Standalone, Plan Migration):

- **Growing team:** Expect to exceed 5,000 books in 12–18 months
- **Moderate HA needs:** Acceptable downtime 1–2 hours/month
- **Cost-conscious with scaling:** Want low TCO initially, upgrade later

**Recommendation:**
1. Deploy STANDALONE now (optimized for 32 GB)
2. Plan migration to SOLRCLOUD once books exceed 5,000
3. Document current index state for smooth migration

#### 🔴 SolrCloud is Required For:

- **Enterprise deployment:** > 100K books, critical uptime
- **Team scale:** 10+ concurrent users, predictable query load
- **High availability:** SLA < 2 hours downtime/year
- **Distributed locations:** Multi-datacenter deployment
- **Compliance:** Audit trails, disaster recovery procedures
- **Growth runway:** Expected to exceed 30K books in 12 months

**Example:** Fortune 500 corporate library with 500K documents, 500 concurrent users, 99.5% SLA requirement.

---

## Configuration: Selecting Topology via Environment

### Current Behavior

The base `docker-compose.yml` is always **SolrCloud** (3 nodes + ZooKeeper).

### Future: Environment-Based Selection (Planned)

In a future release, selection will be configurable:

```bash
# Deploy SolrCloud (current default)
SOLR_TOPOLOGY=distributed docker compose up -d

# Deploy Standalone Solr (planned)
SOLR_TOPOLOGY=standalone docker compose up -d
```

**Implementation status:**
- ✅ Design documented in `.squad/decisions.md`
- ⏳ Standalone Compose override in development
- ⏳ Automated topology detection in initialization scripts
- ⏳ Migration helper scripts (distributed → standalone, vice versa)

---

## Migration Path: Distributed ↔ Standalone

### Scenario 1: Starting with Distributed, Scale Becomes a Problem

If SolrCloud incurs too much operational overhead for your small deployment:

1. **Export current index** via Solr snapshot or replication
2. **Build standalone** node in parallel
3. **Validate** on standalone (run A/B queries)
4. **Cutover** (pause indexing, switch traffic, resume)

**Downtime:** 2–4 hours (worst case)

### Scenario 2: Starting with Standalone, Books Exceed Limit

If standalone reaches capacity (32 GB RAM, > 30K books):

1. **Pause indexing** to freeze book count
2. **Deploy SolrCloud cluster** (3+ nodes)
3. **Re-index** entire library from PDFs (or from single-node backup)
4. **Validate** distributed searches
5. **Migrate traffic** to SolrCloud

**Downtime:** 4–24 hours (depends on library size)

### Scenario 3: Optimize Single-Node Before Upgrading

If standalone is approaching limits but you want to stay cost-effective:

1. **Implement Phase 1 (page-level chunking):** 6× vector reduction
2. **Implement Phase 2 (int8 quantization):** 4× per-vector reduction
3. **Result:** 30K books fit in optimized 32 GB single-node
4. **Defer distributed** 6–12 months until truly outgrowing capacity

**Downtime:** 0 (re-index in background, switch when ready)

---

## Quantization Modes and Hardware Requirements

Vector quantization reduces memory footprint and affects hardware budgets.

### Quantization Strategies

| Mode | Dimensions | Per-Vector Size | Total (30K books) | Quality Loss | Solr Version |
|------|-----------|-----------------|------------------|--------------|------------|
| **No quantization** (float32) | 768 (e5-base) | 3,328 B | 130–180 GB | None | 9.3+ |
| **int8 (byte encoding)** | 768 (e5-base) | 832 B | 25–35 GB | ~1–3% | 9.7+ |
| **Model downgrade** (e5-small) | 384 | 1,664 B (float32) | 65–90 GB | ~5% relative | 9.3+ |
| **e5-small + int8** | 384 | 416 B | 13–18 GB | ~5% + ~1–3% | 9.7+ |
| **ScalarQuantized (int4)** | 768 | 416 B | 13–18 GB | ~2–5% | 10.0+ (future) |

### Recommended Combinations

**For 32 GB Standalone (Scenario B):**
```
Page-level chunking: 54M → 9M vectors
int8 quantization: 768D × 832 B = 7.5 GB HNSW
Total: ~32 GB (with OS + JVM + text headroom)
```

**For 64 GB Standalone (Scenario D, maximum comfort):**
```
Page-level chunking: 54M → 9M vectors
e5-small model: 384D float32 = 15 GB HNSW
Total: ~48 GB (with OS + JVM + text headroom)
```

**For Distributed (any scale):**
```
No quantization required; memory per node is 2–8 GB for Solr
Recommend: int8 for indexing performance (less memory → faster disk I/O)
```

---

## Monitoring and Health Checks

### SolrCloud Health Indicators

Monitor these to detect problems early:

```bash
# Check cluster status
curl -u admin:pass http://localhost:8983/solr/admin/collections?action=CLUSTERSTATUS | jq .

# Expected output: 3 live_nodes, books collection with RF=3
{
  "cluster": {
    "live_nodes": ["solr1:8983", "solr2:8983", "solr3:8983"],
    "collections": {
      "books": {
        "shards": { "shard1": { "replicas": { ... } } },
        "rf": 3
      }
    }
  }
}

# If fewer than 2 live nodes, ZooKeeper quorum is lost → immediate action needed
```

### Standalone Health Indicators

```bash
# Check single-node status
curl -u admin:pass http://localhost:8983/solr/admin/info/system | jq '.jvm.memory'

# Monitor page cache pressure
free -h
# If used > 75% of available RAM, performance will degrade

# Monitor index size
du -sh /source/volumes/solr-data/*
# Should track with expected book count
```

---

## Further Reading

- [Hardware Requirements & Tuning](hardware-requirements.md) — Per-service resource breakdown and scaling guidelines
- [Search and Indexing Sizing Guide](deployment/sizing-guide.md) — Analytical formulas for capacity planning
- [Production Deployment Guide](deployment/production.md) — Step-by-step deployment procedures
- [Failover & Recovery Runbook](deployment/failover-runbook.md) — Handling outages and service recovery
- [Admin Manual](admin-manual.md) — Operational procedures and configuration reference

---

## FAQ

**Q: Can I switch topologies without re-indexing?**  
A: No. Topology changes require re-indexing from source PDFs. Plan 4–24 hours of downtime depending on library size.

**Q: Is SolrCloud required for production?**  
A: Recommended for >100K books and SLA-driven deployments. Standalone + optimization works for < 30K books if HA is acceptable.

**Q: What's the cost difference?**  
A: Standalone is ~2.5× cheaper for < 30K books ($800–1,200/year vs $1,800–2,400/year on AWS). Beyond that, marginal cost favors SolrCloud due to linear scaling.

**Q: Can I run both topologies simultaneously?**  
A: Not in the same Docker Compose stack. You would need separate VMs or clusters. Not a typical use case.

**Q: How long does re-indexing take?**  
A: ~1–2 documents/second (PDFs processed sequentially). 30K books ≈ 8–12 hours. Use GPU for 2–3× speedup.

**Q: What if I need > 64GB RAM on a single machine?**  
A: Standalone is not recommended. Migrate to SolrCloud and distribute shards across nodes.

**Q: Does quantization require re-indexing?**  
A: Yes. Quantization is applied during embedding generation. Changing it requires re-embedding all chunks.

---

**Document version:** v1.0  
**Last updated:** 2026-04-21  
**Audience:** Architects, DevOps engineers, team leads planning Aithena deployments
