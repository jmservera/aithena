# Vector Search on 32 GB RAM: Optimization Roadmap

**Author:** Ash (Search Engineer)  
**Date:** 2026-07-22  
**Requested by:** jmservera (Juanma)  
**Follow-up to:** [standalone-solr-capacity-54m-vectors.md](standalone-solr-capacity-54m-vectors.md)  
**Question:** The previous analysis said 54M vectors needs 130-180 GB. Does it ALL need to be in memory? Can we fit on a 32 GB machine?

---

## Executive Summary

**Yes, 30K books on 32 GB is achievable** — but NOT with the naive "54M float32 768D vectors in HNSW" approach. You need a combination of optimizations that reduce the vector count and per-vector memory cost. The most impactful strategies are:

1. **Change chunking strategy** (page-level → 9M vectors instead of 54M) — **6× reduction**
2. **Scalar quantization** (float32 → int8) — **4× reduction** per vector
3. **Dimensionality reduction** (768D → 384D via smaller model) — **2× reduction**
4. **Hybrid BM25+rerank architecture** (vectors only for reranking) — **eliminates HNSW entirely**

Combined, these can reduce memory from **130+ GB to under 20 GB**, making 32 GB not just possible but comfortable.

---

## 1. HNSW Memory: Clarifying What's Actually In Memory

### 1.1 mmap, Not Heap

**Critical correction to the previous analysis:** Lucene's HNSW graph is NOT JVM heap-resident. It uses `MMapDirectory` — the operating system's virtual memory maps the index files into the process address space, and the **OS page cache** decides what stays in physical RAM.

This means:
- The **entire HNSW graph does NOT need to fit in RAM**
- It CAN exceed available memory and page to/from disk
- Performance degrades **gradually** (not catastrophically) as the working set exceeds RAM

### 1.2 Degradation Profile

| RAM Coverage of HNSW | Expected kNN Latency (NVMe SSD) | Status |
|----------------------|--------------------------------|--------|
| 100% in page cache | 10-100 ms | ✅ Excellent |
| 75% in page cache | 100-500 ms | ✅ Good |
| 50% in page cache | 500 ms - 2 s | 🟡 Usable |
| 25% in page cache | 2-10 s | 🔴 Degraded |
| <10% in page cache | 10-60 s (thrashing) | 🔴 Unusable |

**Key insight:** HNSW graph traversal is **random-access heavy**. Each query hops between distant graph nodes. On HDD this is catastrophic; on NVMe SSD, partial page cache coverage (50-75%) can still deliver sub-second latency for moderate query rates.

### 1.3 What This Means for 32 GB

With 32 GB total RAM, after OS + JVM heap (8 GB) + full-text index cache, you have **~20 GB for HNSW page cache**. The HNSW index must be small enough that 50-75% fits in 20 GB, meaning the on-disk HNSW should be ≤30-40 GB for acceptable performance.

**Baseline (no optimization): 100-135 GB HNSW → only 15-20% would be cached → unusable.**

So the question becomes: how do we shrink the HNSW index to ≤30 GB?

---

## 2. Optimization Strategies (Ordered by Impact)

### 2.1 Chunking Strategy: The Biggest Lever (6× reduction)

Current: 400 words/chunk, 50-word overlap → ~6 chunks/page → **54M vectors for 9M pages**

| Strategy | Vectors | Reduction | Quality Impact |
|----------|---------|-----------|----------------|
| Current (400w chunks) | 54M | baseline | Best for passage-level retrieval |
| Large chunks (1000w) | ~18M | 3× | Good for book search; misses fine-grained passages |
| **Page-level (1 per page)** | **9M** | **6×** | Good for book search; natural document unit |
| Chapter-level | ~300K | 180× | Too coarse; loses page-level precision |

**Recommendation: Page-level chunking for the 32 GB target.**

For book search, a page is a natural retrieval unit. Users searching for concepts in books typically want "which page discusses X?" not "which 400-word fragment?" Page-level vectors are the sweet spot:
- Still granular enough for meaningful semantic matching
- Each page is ~300 words, well within the 512-token context window of e5-base
- Reduces vector count from 54M to 9M — the single biggest memory saving

**Quality trade-off:** Minimal for book search. Page-level retrieval is standard in academic search. Sub-page chunking mainly helps when you need to highlight exact sentences, but Solr's BM25 highlighting can handle that.

### 2.2 Scalar Quantization (4× reduction per vector)

#### What's Available in Solr

| Feature | Solr 9.3+ | Solr 9.7 (current) | Solr 10+ |
|---------|-----------|--------------------|---------| 
| `vectorEncoding="BYTE"` | ✅ | ✅ | ✅ |
| `ScalarQuantizedDenseVectorField` | ❌ | ❌ | ✅ |
| Automatic int7/int4 quantization | ❌ | ❌ | ✅ |

**Two approaches:**

#### Option A: `vectorEncoding="BYTE"` (Available NOW in Solr 9.7)

```xml
<fieldType name="knn_vector_768_byte" class="solr.DenseVectorField"
    vectorDimension="768"
    vectorEncoding="BYTE"
    similarityFunction="cosine"
    knnAlgorithm="hnsw"/>
```

- **Requirement:** You must quantize vectors to int8 [-128, 127] BEFORE indexing
- **Memory reduction:** 4× on raw vectors (768 × 4 bytes → 768 × 1 byte = 3072 → 768 bytes)
- **Total per-vector with HNSW overhead:** ~3328 bytes → ~1024 bytes
- **Recall impact:** ~1-3% recall loss at typical benchmarks; negligible for book search

**Implementation:** Add quantization in the embeddings-server before sending to Solr:
```python
# In embeddings-server, after generating float32 embeddings:
import numpy as np
embedding_float = model.encode(text)  # float32, 768D
# Scale to int8 range
embedding_int8 = np.clip(
    np.round(embedding_float * 127), -128, 127
).astype(np.int8)
```

#### Option B: `ScalarQuantizedDenseVectorField` (Requires Solr 10 upgrade)

```xml
<fieldType name="knn_vector_768_sq"
    class="solr.ScalarQuantizedDenseVectorField"
    vectorDimension="768"
    similarityFunction="cosine"
    bits="7"
    confidenceInterval="0.99"/>
```

- **Advantage:** Automatic quantization — you index float32 vectors and Solr quantizes internally
- **Extra option:** `bits="4"` with `compress="true"` for 8× reduction (more quality loss)
- **Better quality:** Dynamic confidence intervals optimize quantization range per segment
- **Not available in Solr 9.7** — requires upgrading to Solr 10

### 2.3 Dimensionality Reduction (2× reduction)

#### Option A: Switch to multilingual-e5-small (384D)

| Model | Dimensions | BEIR Score | Mr. TyDi MRR@10 | Memory per vector |
|-------|-----------|------------|-----------------|-------------------|
| multilingual-e5-base | 768 | 48.9 | 65.9 | 3072 bytes (float32) |
| multilingual-e5-small | 384 | 46.6 | 64.4 | 1536 bytes (float32) |

- **Quality drop:** ~5% relative on benchmarks (2.3 BEIR points)
- **For book search:** Minimal practical impact — book search queries are typically broad topic queries where the quality difference is hard to notice
- **Memory reduction:** 2× on raw vectors
- **Bonus:** Faster inference (~2× faster embedding generation)

**Trade-off:** This requires re-indexing the entire collection and updating the schema + embeddings-server config. It's a bigger change than quantization.

#### Option B: Matryoshka Truncation (768D → 384D or 256D)

**⚠️ NOT available with multilingual-e5-base.** The standard `intfloat/multilingual-e5-base` was NOT trained with Matryoshka Representation Learning (MRL). Truncating its vectors to 384D would cause significant quality degradation because the dimensions are not ordered by importance.

A Matryoshka-trained variant (`multilingual-e5-base-matryoshka`) would be needed. If such a variant is available, truncation quality would be:
- 768 → 384: ~2-4% quality loss
- 768 → 256: ~5-8% quality loss

**Recommendation:** If dimensionality reduction is needed, switching to e5-small (384D) is cleaner and better-tested than trying to find/train a Matryoshka variant.

### 2.4 Hybrid BM25 + Vector Reranking (Eliminates Large HNSW)

**This is the most architecturally impactful optimization** and the best fit for a 32 GB machine at 30K book scale.

#### The Idea

Instead of building an HNSW index over ALL vectors and doing full kNN search, use a two-stage approach:

1. **Stage 1 (BM25):** Full-text search retrieves top-N candidates (fast, memory-efficient)
2. **Stage 2 (Vector rerank):** Compute vector similarity ONLY for the top-N candidates

This eliminates the need for an HNSW graph entirely. Vector similarity is computed on-the-fly for a small candidate set.

#### How It Works in Solr 9.7

**Option A: Solr's built-in ReRank Query Parser**

```
q=machine learning techniques
&rq={!rerank reRankQuery=$rqq reRankDocs=200 reRankWeight=2.0}
&rqq={!knn f=embedding_v topK=50}[0.12, -0.34, ...]
```

This is limited because Solr's `{!knn}` still searches the HNSW graph (it doesn't compute similarity on a candidate set). The rerank parser works better with function queries or LTR.

**Option B: Application-level two-stage search (RECOMMENDED)**

```python
# Stage 1: BM25 search in Solr
bm25_results = solr.search(q="machine learning", rows=200)
candidate_ids = [doc['id'] for doc in bm25_results]

# Stage 2: Get embeddings for candidates, compute similarity
query_embedding = embed("query: machine learning")
for doc in bm25_results:
    chunk_embedding = get_stored_embedding(doc['id'])
    doc['vector_score'] = cosine_similarity(query_embedding, chunk_embedding)

# Stage 3: RRF or weighted fusion
final_results = rrf_fuse(bm25_results, vector_scores, k=60)
```

#### What You Need for This Architecture

- **Store vectors as stored fields** (not just indexed): The vectors need to be retrievable, not just searchable
- **No HNSW index needed** on the vector field (or a very small one for pure-semantic queries)
- **Vectors stored on disk:** 9M pages × 3 KB = 27 GB on disk, served via stored fields
- **RAM for this approach:** Only BM25 index in memory (~5-10 GB) + JVM heap

**This is the most RAM-efficient approach by far** — but it changes the search architecture significantly.

#### Trade-offs

| Aspect | Full HNSW | BM25 + Rerank |
|--------|-----------|---------------|
| Pure semantic search | ✅ Fast kNN | ❌ Not available (needs BM25 first stage) |
| Hybrid search quality | ✅ Full kNN + BM25 fusion | 🟡 BM25 recall ceiling limits semantic candidates |
| Memory usage | 🔴 HNSW graph in page cache | ✅ Only BM25 index + stored vectors |
| Latency | 🟡 Depends on cache | ✅ Predictable (BM25 + N similarity computations) |
| Implementation complexity | ✅ Single Solr query | 🟡 Two-stage pipeline in application |

**The BM25 recall ceiling:** If a relevant document doesn't appear in the top-200 BM25 results, vector reranking can't rescue it. For book search with good metadata (title, author, full text), BM25 recall@200 is typically 90-95%.

### 2.5 Tiered Storage: Hot/Cold Split

Split the collection into tiers based on access patterns:

| Tier | Content | Vector Index | Text Index | RAM Budget |
|------|---------|-------------|------------|------------|
| **Hot** | Recent/popular books (e.g., last 5 years, top 5K) | Full HNSW | Full BM25 | 15-20 GB |
| **Cold** | Archive (remaining 25K books) | No vectors / stored only | Full BM25 | 5-10 GB |

**Implementation:** Two Solr cores, query both with distributed search, merge results.

- Hot core: 5K books × 300 pages × 1 vector/page = 1.5M vectors (easily fits in 8 GB)
- Cold core: 25K books, text-only search, very low memory footprint

**Trade-off:** Semantic search only works on hot tier. Cold books are keyword-searchable only. This may be acceptable if most searches target recent/popular material.

### 2.6 HNSW Parameter Tuning (25-35% reduction)

Reduce graph connectivity for lower memory:

```xml
<fieldType name="knn_vector_768"
    class="solr.DenseVectorField"
    vectorDimension="768"
    similarityFunction="cosine"
    knnAlgorithm="hnsw"
    hnswMaxConnections="12"
    hnswBeamWidth="80"/>
```

| Parameter | Default | Tuned | Memory Impact | Quality Impact |
|-----------|---------|-------|---------------|----------------|
| hnswMaxConnections | 16 | 12 | ~25% graph reduction | ~3-5% recall loss |
| hnswBeamWidth | 100 | 80 | No memory impact (query-time) | ~2-3% latency increase |

This alone won't solve the problem but helps when combined with other strategies.

---

## 3. Combined Optimization Scenarios

### 3.1 Memory Calculation Formula

```
HNSW memory = num_vectors × (vector_bytes + graph_overhead)
where:
  vector_bytes = dimensions × encoding_size
  graph_overhead ≈ maxConnections × 12 + 64 bytes
```

### 3.2 Optimization Combinations

| Scenario | Vectors | Dims | Encoding | Per-Vector | Total HNSW | Fits 32GB? |
|----------|---------|------|----------|-----------|------------|------------|
| **Baseline** | 54M | 768 | float32 | 3,328 B | **~170 GB** | ❌ |
| A: Page-level chunks | 9M | 768 | float32 | 3,328 B | **~28 GB** | 🟡 Tight |
| B: A + int8 encoding | 9M | 768 | int8 | 1,024 B | **~9 GB** | ✅ |
| C: A + e5-small (384D) | 9M | 384 | float32 | 1,792 B | **~15 GB** | ✅ |
| D: A + e5-small + int8 | 9M | 384 | int8 | 640 B | **~5.5 GB** | ✅ Comfortable |
| E: BM25 + rerank (no HNSW) | 0 | — | stored | — | **0 GB** | ✅ Trivial |
| F: Tiered (5K hot books) | 1.5M | 768 | float32 | 3,328 B | **~4.7 GB** | ✅ |

### 3.3 Full RAM Budget for Recommended Scenarios

#### Scenario B: Page-level + int8 (Best balance)

| Component | RAM |
|-----------|-----|
| OS + system | 2 GB |
| JVM heap | 8 GB |
| HNSW page cache (9M × 1 KB) | 9 GB |
| Full-text index cache | 8 GB |
| Headroom | 5 GB |
| **Total** | **32 GB** ✅ |

#### Scenario D: Page-level + e5-small + int8 (Maximum comfort)

| Component | RAM |
|-----------|-----|
| OS + system | 2 GB |
| JVM heap | 8 GB |
| HNSW page cache (9M × 640 B) | 5.5 GB |
| Full-text index cache | 10 GB |
| Headroom | 6.5 GB |
| **Total** | **32 GB** ✅✅ |

#### Scenario E: BM25 + Rerank (Most RAM-efficient)

| Component | RAM |
|-----------|-----|
| OS + system | 2 GB |
| JVM heap | 8 GB |
| Full-text index cache | 15 GB |
| Stored vector retrieval buffer | 2 GB |
| Headroom | 5 GB |
| **Total** | **32 GB** ✅✅✅ |

---

## 4. Alternative Approaches

### 4.1 Sidecar Vector Database

Use Solr for text search + a lightweight vector DB for semantic search:

| Option | Disk-based? | Max vectors | Integration complexity |
|--------|-------------|-------------|----------------------|
| **sqlite-vec** | ✅ | 10M+ (brute-force or IVF) | Low (Python, single file) |
| **usearch** | ✅ | 100M+ (HNSW, mmap) | Medium (C++/Python bindings) |
| **hnswlib** | ❌ (RAM) | ~10M on 32 GB | Medium |
| **lancedb** | ✅ | 100M+ (IVF-PQ) | Medium |

**sqlite-vec** is particularly interesting for this project:
- Stores vectors in a SQLite database on disk
- Brute-force search for small candidate sets (after BM25 pre-filtering)
- No HNSW graph overhead — just stored vectors + linear scan
- Perfect for the BM25+rerank architecture

**However:** Adding a second search engine increases operational complexity. The Solr-only approaches (scenarios B/C/D) are simpler.

### 4.2 Embeddings-Server as ANN Search

The embeddings-server already loads the model. Could it also handle vector search?

- Load vectors into a Python-side index (usearch, faiss, or hnswlib)
- Solr handles text search only
- Application fuses results

**Problem:** The embeddings-server is designed for encoding, not serving as a search index. Adding ANN search would make it stateful and complex. Not recommended unless the architecture is redesigned.

### 4.3 DiskANN / Vamana

Microsoft's DiskANN algorithm is designed for billion-scale vector search on SSD with minimal RAM. However:
- No Solr/Lucene plugin exists
- Available in [diskannpy](https://github.com/microsoft/DiskANN) for Python
- Would require a sidecar service
- Overkill for 9M vectors — only relevant at 100M+ scale

---

## 5. Recommended Optimization Roadmap

### Phase 1: Quick Wins (No model/architecture changes)

**Target: Reduce from 130 GB to ~28 GB**

1. **Switch to page-level chunking** (1 vector per page instead of 6)
   - Change document-indexer chunking config
   - Re-index collection
   - 54M → 9M vectors

2. **Tune HNSW parameters** (hnswMaxConnections=12)
   - Schema change only
   - ~25% additional reduction

3. **Add NVMe SSD** for Solr data directory
   - Ensures page cache misses are fast (~100 μs vs 10 ms for HDD)

**Result: ~28 GB HNSW → fits in 32 GB with tight margins**

### Phase 2: Quantization (Solr 9.7 compatible)

**Target: Reduce from 28 GB to ~9 GB**

1. **Add `vectorEncoding="BYTE"`** to schema
2. **Add int8 quantization** in embeddings-server output pipeline
3. **Re-index collection** with quantized vectors

**Result: ~9 GB HNSW → comfortable fit in 32 GB, room for growth**

### Phase 3: Model Optimization (Optional, for maximum headroom)

**Target: Reduce from 9 GB to ~5.5 GB**

1. **Evaluate e5-small (384D)** on test corpus
2. If quality is acceptable, switch model + update schema
3. Re-index with 384D int8 vectors

**Result: ~5.5 GB HNSW → 32 GB machine can handle 2-3× growth**

### Phase 4: Architecture Evolution (If needed at scale)

**When book count exceeds what 32 GB can handle:**

1. **Implement BM25 + vector rerank** for hybrid search
2. **Or** upgrade to Solr 10 for `ScalarQuantizedDenseVectorField` (int4 + compress = 8× reduction)
3. **Or** migrate to SolrCloud with 2-3 nodes

---

## 6. Answers to the Original Questions

### Does the ENTIRE HNSW graph need to fit in RAM?
**No.** Lucene uses mmap — the OS page cache manages what's in physical RAM. Performance degrades gradually as the working set exceeds available memory, but it doesn't fail. With NVMe SSD, 50% cache coverage still gives sub-second latency.

### Is there any way to make 30K books work on 32 GB?
**Yes, multiple ways.** The most practical path:
1. Page-level chunking (9M instead of 54M vectors) — biggest impact
2. int8 quantization (`vectorEncoding="BYTE"` in Solr 9.7) — 4× per-vector savings
3. Combined: ~9 GB HNSW fits easily in 32 GB with room to spare

### What's the minimum viable configuration?
**Scenario B (page-level + int8): 9M vectors × 1 KB = ~9 GB HNSW.** Total RAM ~25 GB, fits in 32 GB.

### Is there a hard floor?
**For full kNN search:** ~5 GB (Scenario D: 9M vectors, 384D, int8).  
**For BM25+rerank:** ~0 GB for vectors (only text index needed).

### What about Solr 10?
Solr 10 adds `ScalarQuantizedDenseVectorField` with automatic int7/int4 quantization and optional compression. This would make the optimization path even easier (no manual quantization in embeddings-server). Worth planning for, but not required — Solr 9.7 with `vectorEncoding="BYTE"` covers the critical need.

---

## 7. Impact on Existing Architecture

### What Changes

| Component | Change Required | Effort |
|-----------|----------------|--------|
| `managed-schema.xml` | Add `vectorEncoding="BYTE"` or change vectorDimension | Small |
| `embeddings-server` | Add int8 quantization output option | Small |
| `document-indexer` | Change chunking to page-level | Medium |
| `search_service.py` | Update if switching to rerank architecture | Medium-Large |
| `solr-search` | Minor query adjustments | Small |

### What Stays the Same

- Parent-chunk document model (parent docs + chunk docs)
- Three search modes (keyword/semantic/hybrid)
- RRF fusion logic
- Metadata extraction pipeline
- A/B testing framework

---

## References

- `src/solr/books/managed-schema.xml:50` — current knn_vector_768 definition
- `src/embeddings-server/config/__init__.py:17` — multilingual-e5-base config
- [Solr DenseVectorField docs](https://solr.apache.org/guide/solr/latest/query-guide/dense-vector-search.html)
- [SOLR-16674: DenseVectorField BYTE encoding](https://issues.apache.org/jira/browse/SOLR-16674) (Solr 9.3+)
- [Sease: Scalar Quantization in Apache Solr](https://sease.io/2026/01/scalar-quantization-of-dense-vectors-in-apache-solr.html) (Solr 10)
- [Lucene HNSW mmap behavior](https://lucene.apache.org/core/) — uses MMapDirectory by default
- [multilingual-e5-base](https://huggingface.co/intfloat/multilingual-e5-base) — 768D, not Matryoshka-trained
- [multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small) — 384D alternative
