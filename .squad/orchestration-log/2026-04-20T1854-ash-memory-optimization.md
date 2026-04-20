# Orchestration Log: Ash Memory Optimization Analysis

**Date:** 2026-04-20T18:54Z  
**Agent:** Ash (Search Engineer)  
**Task:** Analyze memory optimization strategies for 32GB RAM Solr deployment with 54M vectors  
**Status:** ✅ COMPLETE

---

## Outcome

**SUCCESS.** Created comprehensive optimization roadmap showing 30K books fits in 32GB via:
- Page-level chunking (54M → 9M vectors) — 6× reduction
- int8 quantization via `vectorEncoding="BYTE"` — 4× per-vector savings
- Combined: ~9 GB HNSW fits easily in 32GB with room to spare

---

## Artifacts Produced

1. **`.squad/analysis/vector-search-32gb-optimization-roadmap.md`** (20.2 KB)
   - Executive summary: 6 optimization strategies analyzed with sizing tables
   - HNSW memory fundamentals: mmap + page cache model corrects previous assumptions
   - Scenario comparison: baseline (130 GB) → Scenario B (9 GB) → Scenario D (5.5 GB)
   - Recommended roadmap: Phase 1–4 with effort estimates
   - Alternative approaches: sidecar vector DBs, DiskANN, hybrid BM25+rerank

2. **`.squad/agents/ash/history.md`** (updated)
   - Added session context to Core Context section
   - Documented optimization strategies for future reference

---

## Key Technical Findings

### Original Question
_Does all 54M vectors need to fit in memory on a 32GB machine? Can we optimize?_

### Answer
**Yes, 30K books on 32GB is achievable** using a combination of:

| Strategy | Impact | Effort | Deployment |
|----------|--------|--------|-----------|
| **Page-level chunking** | 6× vector reduction (54M→9M) | Medium | Re-index required |
| **int8 quantization** | 4× per-vector reduction | Small | Solr 9.7 ready (`vectorEncoding="BYTE"`) |
| **Hybrid BM25+rerank** | Eliminates HNSW entirely | Large | Architecture change |
| **Model switch (e5-small)** | 2× reduction (768D→384D) | Medium | Re-index + re-embed |

### Critical Correction from Previous Analysis
- **HNSW graph is NOT JVM heap-resident** — uses mmap + OS page cache
- **Partial cache coverage is acceptable:** 50-75% page cache → ~500 ms–2s latency (usable on NVMe SSD)
- **Implication:** HNSW can exceed available memory and page to disk without catastrophic failure
- **Previous assumption (all 130GB in RAM) was incorrect** — only 50-75% needs to be cached

### Recommended Path (Scenarios B & D)

**Scenario B: Page-level + int8 (best balance)**
- 9M vectors × 1 KB = 9 GB HNSW
- Total RAM: 2 (OS) + 8 (JVM) + 9 (HNSW cache) + 8 (text index) + 5 (headroom) = 32 GB ✅

**Scenario D: Page-level + e5-small + int8 (maximum comfort)**
- 9M vectors × 640 B = 5.5 GB HNSW
- Total RAM: 2 (OS) + 8 (JVM) + 5.5 (HNSW cache) + 10 (text index) + 6.5 (headroom) = 32 GB ✅✅

---

## Impact on Other Components

### Infrastructure (Brett's domain)
- Confirms 32GB single-node Solr is viable with optimizations
- Standalone vs SolrCloud decision now has technical basis (32GB budget forces single-node)
- No ZooKeeper overhead needed — simplifies Brett's infra analysis

### Schema & Embeddings (Ash's domain)
- `managed-schema.xml`: Add `vectorEncoding="BYTE"` (Solr 9.7 compatible)
- `embeddings-server`: Add int8 quantization pipeline (optional, for Scenario B)
- `document-indexer`: Switch from 400w chunks to page-level chunks
- Re-indexing required for production

### Timeline
- **Phase 1 (quick win):** Page-level chunking → ~28 GB (no schema changes needed, just re-chunk)
- **Phase 2:** Add `vectorEncoding="BYTE"` + quantization → ~9 GB
- **Phase 3:** Model evaluation (e5-small) → ~5.5 GB
- **Phase 4 (if needed):** Hybrid BM25+rerank or upgrade to SolrCloud

---

## Related Prior Work

**Ash's earlier analyses (same session):**
- `.squad/analysis/standalone-solr-capacity-54m-vectors.md` — Baseline: 54M vectors need 130-180 GB, single-node not viable
- **This roadmap:** Shows how to get from 130 GB → 9 GB via optimization

**Brett's infrastructure analysis (same session):**
- `.squad/research/standalone-vs-cloud-infrastructure-analysis.md` — Standalone Solr cheaper than SolrCloud for single-machine
- **This roadmap:** Confirms standalone is viable if vector count is optimized

---

## Notes for Future Work

1. **Verify page-level chunking quality** — A/B test against current 400w chunking on small corpus
2. **Benchmark int8 quantization** — Confirm recall@10 loss is <3% as literature suggests
3. **E5-small evaluation** — Only if 5.5 GB headroom becomes critical
4. **BM25+rerank migration** — High-effort, architectural change; defer unless scale exceeds 50K books
5. **Update hardware requirements doc** — Currently recommends 130GB; new baseline is 32GB

---

## Decision Points for Squad

1. **Chunking strategy:** Approve page-level? Or maintain 400w for better passage-level precision?
2. **Quantization timeline:** Implement in Phase 2 (Solr 9.7 ready) or defer?
3. **Model change:** Worth re-evaluating e5-small for 2× memory + 2× speed?

These decisions are captured in `.squad/decisions.md` for squad alignment.
