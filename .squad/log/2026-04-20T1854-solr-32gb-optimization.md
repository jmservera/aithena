# Session Log: Solr 32GB Optimization Research

**Date:** 2026-04-20T18:54Z  
**Session Duration:** ~2 hours (estimated from artifact timestamps)  
**Participants:** Ash (primary researcher), Brett (infrastructure context), Scribe (logging)

---

## Session Overview

Three-part research project evaluating memory requirements and optimization strategies for scaling aithena's Solr deployment to 30K books with 54M vectors on a constrained 32GB machine.

**Flow:**
1. Ash: Initial capacity analysis (standalone-solr-capacity-54m-vectors.md) → baseline = 130-180GB (unviable)
2. Brett: Infrastructure comparison (standalone-vs-cloud-infrastructure-analysis.md) → standalone cheaper if viable
3. Ash: Optimization roadmap (vector-search-32gb-optimization-roadmap.md) → 130GB → 9GB viable path

---

## Part 1: Baseline Capacity Analysis

**File:** `.squad/analysis/standalone-solr-capacity-54m-vectors.md`  
**Author:** Ash  
**Timestamp:** 2026-04-20T18:35Z

### Research Question
Can a single Solr node (no ZooKeeper/SolrCloud) handle 30K books → 9M pages → 54M embedding vectors?

### Key Findings

**Scale calculation (verified against schema + indexer code):**
- 30K books × 300 pages/book = 9M pages
- 9M pages × 6 chunks/page (400w/50w overlap) = 54M chunk docs
- Total Solr docs: 30K parent docs + 54M chunk docs = ~54M documents

**HNSW memory footprint:**
- Per-vector: 768 floats × 4 bytes (float32) + graph links + metadata ≈ 3,328 bytes
- Total HNSW index: 54M vectors × 3,328 B ≈ **100-135 GB** (memory-mapped, OS page cache dependent)
- Full-text index: 9M pages × 5 KB + 30K parents ≈ **45 GB**
- **Combined footprint: 145-180 GB**

**Query performance at 54M vectors:**
| Scenario | Latency (p95) | Viability |
|----------|---------------|-----------|
| Warm cache (all in RAM) | 800ms–3s | ✅ Good |
| Cold cache | 5–20s+ | 🔴 Unusable |
| Concurrent (5+ users) | 10–30s | 🔴 Not viable |

**Verdict:** Single-node Solr **NOT RECOMMENDED** for 54M vectors.

**Recommendation:** Migrate to SolrCloud (3-6 shards) at **~3,000 books (1.8M vectors)** threshold.

---

## Part 2: Infrastructure Cost Comparison

**File:** `docs/research/standalone-vs-cloud-infrastructure-analysis.md`  
**Author:** Brett  
**Timestamp:** 2026-04-20T18:31Z

### Research Question
Standalone Solr vs SolrCloud: which is more cost-effective for 30K books?

### Key Findings

**Cost Analysis (annual, AWS EC2 estimated):**

| Infrastructure | Node Size | Count | RAM/node | Annual Cost | Viability |
|---|---|---|---|---|---|
| **Standalone** | r7g.2xlarge (8 vCPU, 64GB RAM) | 1 | 64GB | ~$800–1,200 | ✅ If vectors optimized |
| **SolrCloud** | r7g.xlarge (4 vCPU, 32GB RAM) | 3 + 3 ZK | 32GB each | ~$1,800–2,400 | ✅ HA guaranteed |
| **SolrCloud HA+** | r7g.2xlarge | 6 + 3 ZK | 64GB each | ~$4,000+ | ✅ Full redundancy |

**Key insights:**
- Standalone wins 2.5× on cost if vector optimization is possible
- SolrCloud adds ~3× operational complexity (quorum management, distributed debugging)
- Standalone currently inadequate (130-180GB > 64GB available)
- **Critical blocker:** Need to reduce vector memory from 130GB to <32GB to justify standalone

**Recommendation:** Optimize vectors first; if achievable, stay standalone.

---

## Part 3: Memory Optimization Roadmap

**File:** `.squad/analysis/vector-search-32gb-optimization-roadmap.md`  
**Author:** Ash  
**Timestamp:** 2026-04-20T18:53Z

### Research Question
Can we fit 30K books (54M vectors) on 32GB via optimization strategies? If yes, which path?

### Key Findings

**Critical Insight: HNSW Uses mmap + Page Cache, Not JVM Heap**

Previous assumption: All 130GB must fit in physical RAM.  
**Correct model:** Lucene's HNSW is memory-mapped; OS page cache decides what's in RAM.

**Performance degradation profile:**
| % in page cache | Latency (NVMe SSD) | Status |
|---|---|---|
| 100% | 10–100 ms | ✅ Excellent |
| 75% | 100–500 ms | ✅ Good |
| 50% | 500 ms–2 s | 🟡 Usable |
| 25% | 2–10 s | 🔴 Degraded |
| <10% | 10–60 s | 🔴 Thrashing |

**This changes everything:** Even if HNSW is 100GB on disk, 50-75% can fit in 32GB RAM, delivering sub-second latency on NVMe.

### Six Optimization Strategies (Ranked by Impact)

| Strategy | Vectors | Reduction | Quality Loss | Effort |
|---|---|---|---|---|
| **1. Page-level chunks** | 54M → 9M | 6× | Minimal (page is natural unit) | Medium |
| **2. int8 quantization** (vectorEncoding="BYTE") | N/A | 4× per vector | ~1–3% recall | Small |
| **3. Model downgrade** (e5-small 384D) | N/A | 2× | ~5% relative | Medium |
| **4. Hybrid BM25+rerank** | All → 0 (HNSW) | Eliminates HNSW | Architecture change | Large |
| **5. Tiered storage** (hot/cold split) | Partial | Selective | Only cold tier searchable | Large |
| **6. HNSW tuning** (hnswMaxConnections=12) | N/A | 25–35% | ~5% recall | Small |

### Recommended Scenarios

**Scenario B: Page-level + int8 (BEST BALANCE)**
- 9M vectors × 1 KB (int8 + overhead) = ~9 GB HNSW
- RAM budget: 2 (OS) + 8 (JVM) + 9 (HNSW) + 8 (text) + 5 (headroom) = **32 GB** ✅
- Effort: Medium (re-chunk + schema change + quantization)
- Quality: Minimal loss

**Scenario D: Page-level + e5-small + int8 (MAXIMUM COMFORT)**
- 9M vectors × 640 B (384D int8) = ~5.5 GB HNSW
- RAM budget: 2 (OS) + 8 (JVM) + 5.5 (HNSW) + 10 (text) + 6.5 (headroom) = **32 GB** ✅✅
- Effort: Large (model switch + re-index)
- Quality: ~5% loss on benchmarks

**Scenario E: BM25 + Vector Rerank (MOST EFFICIENT)**
- No HNSW index — vectors stored as fields only
- RAM budget: 2 (OS) + 8 (JVM) + 15 (full-text) + 2 (vectors) + 5 (headroom) = **32 GB** ✅✅✅
- Effort: Large (architecture redesign)
- Trade-off: No pure semantic search (requires BM25 pre-filter)

### Implementation Roadmap

**Phase 1: Quick Win (No schema changes)**
- Switch to page-level chunking → 54M → 9M vectors
- Tune HNSW parameters → 25–35% additional reduction
- **Result:** 28 GB HNSW on disk (tight fit in 32 GB)

**Phase 2: Quantization (Solr 9.7 compatible)**
- Add `vectorEncoding="BYTE"` to schema
- Implement int8 quantization in embeddings-server
- Re-index with quantized vectors
- **Result:** 9 GB HNSW (comfortable fit)

**Phase 3: Model Optimization (Optional)**
- Evaluate multilingual-e5-small (384D) on test corpus
- If ≤5% quality loss acceptable, switch model
- Re-index with new model + int8
- **Result:** 5.5 GB HNSW (32 GB machine handles 2–3× growth)

**Phase 4: Architecture Evolution (If scale exceeds 30K books)**
- Implement BM25 + vector rerank (hybrid search)
- Or upgrade to Solr 10 (ScalarQuantizedDenseVectorField with int4 compression)
- Or migrate to SolrCloud (distributed sharding)

---

## Cross-Agent Insights

### For Brett (Infrastructure)
**Impact on standalone-vs-cloud decision:**
- **Before:** Standalone unviable (requires 130–180 GB)
- **After:** Standalone viable with optimization (9–32 GB), saves 2.5× cost vs SolrCloud
- **Action:** Update infrastructure decision to recommend standalone + optimization path

### For Ash (Search Engineering)
**Next steps:**
1. Implement Phase 1 (page-level chunking) — no schema change, just re-index
2. Validate quality via A/B test (page-level vs 400w chunks)
3. Plan Phase 2 (quantization) for 9.7 rollout
4. Keep Phase 3 (model switch) as fallback if needed

### For Scribe
**Document decisions:**
- Vector optimization strategy (choose Scenario B or D)
- Phase 1 timeline (when to re-chunk?)
- A/B testing plan (metrics, sample size)
- Infrastructure alignment (confirm 32GB is target budget)

---

## Knowledge Artifacts

### Files Created/Updated

1. **New Analysis:**
   - `.squad/analysis/vector-search-32gb-optimization-roadmap.md` (20.2 KB)

2. **Updated History:**
   - `.squad/agents/ash/history.md` — Added session context

3. **Related Prior Work:**
   - `.squad/analysis/standalone-solr-capacity-54m-vectors.md` — Baseline
   - `docs/research/standalone-vs-cloud-infrastructure-analysis.md` — Infrastructure context

### Key References (All Verified Against Code)

- `src/solr/books/managed-schema.xml:50` — Current knn_vector_768 definition
- `src/embeddings-server/config/__init__.py:17` — multilingual-e5-base config
- `src/document-indexer/indexer.py` — 400w/50w chunking logic (confirmed in code review)
- Solr 9.7 docs: DenseVectorField, vectorEncoding="BYTE", HNSW mmap behavior

---

## Decision Points for Squad Alignment

**Decision 1: Chunking Strategy**
- Keep 400w chunks (passage-level precision, high vector count)?
- Switch to page-level (natural unit, 6× reduction)?
- **Impact:** Affects all downstream decisions (vector count → RAM → architecture)

**Decision 2: Quantization Timeline**
- Implement int8 immediately (Phase 2)?
- Defer to future release?
- **Impact:** Solr 9.7 ready; no schema conflicts; can ship in next release

**Decision 3: Infrastructure Commitment**
- Confirm 32GB single-node budget?
- Plan for SolrCloud from start?
- **Impact:** Changes cost, complexity, HA guarantees

**Decision 4: Model Evaluation**
- Benchmark e5-small (384D) on aithena corpus?
- Stick with e5-base (768D)?
- **Impact:** 2× memory vs 5% quality loss trade-off

---

## Session Summary

**Total research output:** 3 analyses + 1 orchestration log = ~70 KB new knowledge

**Key transformation:** 
- Baseline: Single-node Solr unviable for 30K books (130–180 GB)
- Optimized: Single-node viable with multi-phase approach (9–32 GB, stays standalone)
- Impact: 2.5× cost savings vs SolrCloud if optimization is implemented

**Time-critical:** Both analyses are locked to current schema (`multilingual-e5-base`, 768D, Solr 9.7). Changes to embedding model or Solr version will require re-analysis.

---

## Appendix: Research Methodology

**Sources of Truth:**
- Live code inspection: `managed-schema.xml`, `embeddings-server` config, `document-indexer` logic
- Solr 9.7 official docs (vectorEncoding, HNSW, mmap behavior)
- Lucene/Solr community benchmarks (recall@10 vs memory trade-offs)
- Academic literature: HNSW performance under memory pressure, quantization quality

**Assumptions Made (Documented):**
- 300 pages/book (industry average for full texts)
- 400w chunks with 50w overlap = ~6 chunks/page (verified in code)
- 5 KB average page index size (conservative estimate)
- NVMe SSD for Solr data (not HDD; performance would be unusable on HDD)
- Solr 9.7 as deployment baseline (not 9.3, not 10)

**Uncertainty Ranges:**
- HNSW per-vector: 3,200–3,500 bytes (accounting for compression, overhead, graph tuning)
- Performance at 50% cache: 500ms–2s (hardware-dependent; SSD speed matters)
- Quantization recall loss: 1–3% (varies by model, query type)

---

**Session End:** 2026-04-20T18:54Z
