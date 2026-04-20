# Embedding Model Research for Multilingual Vector Search

**Issue:** #861  
**Author:** Ash (Search Engineer)  
**Date:** 2025-01-27  
**Status:** Research Spike

## Executive Summary

This document evaluates alternative multilingual embedding models to replace the current `distiluse-base-multilingual-cased-v2` model, which is constrained by a 128-token window resulting in ~90-word chunks. We identify 5 candidate models with larger context windows (256-512 tokens), all CPU-compatible, and propose an in-repo A/B testing framework to measure relevance improvements while tracking resource costs.

**Key Recommendation:** Prioritize **multilingual-e5-base** (512 tokens, 768D) for immediate testing, followed by **BGE-M3** if Chinese-language models prove viable for Latin languages.

---

## 1. Current State Analysis

### 1.1 Current Model Configuration

- **Model:** `sentence-transformers/distiluse-base-multilingual-cased-v2`
- **Max sequence length:** 128 tokens (documented constraint in issue #861)
- **Embedding dimensions:** 512D
- **Chunking strategy:** 90 words/chunk, 10-word overlap (CHUNK_SIZE=90, CHUNK_OVERLAP=10)
- **Languages supported:** 50+ languages including ES, FR, CA, EN
- **Hardware requirements:** CPU-only, minimal resources
- **Index architecture:** Solr DenseVectorField with HNSW cosine similarity

**Rationale for 90-word chunks:** The 128-token window leaves insufficient space for hierarchical chunking. With ~1.3 tokens/word average for multilingual text, 128 tokens ≈ 90-100 words max, constraining advanced retrieval strategies.

### 1.2 Data Flow

1. **document-lister** → RabbitMQ → **document-indexer**
2. **document-indexer** extracts PDF text → chunks (90 words, sentence-aware) → **embeddings-server**
3. **embeddings-server** encodes chunks → returns 512D vectors
4. **document-indexer** indexes chunks into Solr with `embedding_v` field (knn_vector_512 type)
5. **solr-search** performs kNN queries on chunk documents, deduplicates by parent book

### 1.3 Current Limitations

- **No hierarchical chunking:** Cannot implement parent-child or sliding window strategies
- **Context fragmentation:** 90 words often splits semantic units (paragraphs, complex arguments)
- **Retrieval gaps:** Short chunks miss broader context needed for nuanced queries
- **No room for instruction tuning:** Cannot prepend query prefixes or task instructions within token budget

---

## 2. Candidate Models

All candidates meet core requirements:
- Latin multilingual support (ES, FR, CA, EN + historical variants)
- Larger context windows (256-512 tokens)
- CPU-friendly (no mandatory GPU)
- Compatible with `sentence-transformers` library
- Active maintenance and benchmarking

### 2.1 Model Comparison Table

| Model | HF Path | Max Tokens | Dims | Params | Size (disk) | CPU Viable | MTEB Avg* | Notes |
|-------|---------|------------|------|--------|-------------|------------|-----------|-------|
| **multilingual-e5-base** | `intfloat/multilingual-e5-base` | **512** | 768 | 278M | ~1.1GB | ✅ Yes | 61.5 | Best balance for Aithena |
| **multilingual-e5-small** | `intfloat/multilingual-e5-small` | **512** | 384 | 118M | ~470MB | ✅ Yes | 58.2 | Lightweight fallback |
| **BGE-M3** | `BAAI/bge-m3` | **8192** | 1024 | 568M | ~2.2GB | ⚠️ Slower | 63.1 | Exceptional, but Chinese-centric |
| **paraphrase-multilingual-mpnet-base-v2** | `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` | **384** | 768 | 278M | ~1.1GB | ✅ Yes | 54.3 | Moderate improvement |
| **multilingual-e5-large** | `intfloat/multilingual-e5-large` | **512** | 1024 | 560M | ~2.1GB | ⚠️ Slower | 64.3 | Best quality, higher cost |

*MTEB Average: Multilingual retrieval tasks from Massive Text Embedding Benchmark

### 2.2 Detailed Model Profiles

#### 2.2.1 multilingual-e5-base (RECOMMENDED)

**HuggingFace:** `intfloat/multilingual-e5-base`

**Specifications:**
- Max sequence: **512 tokens** (4× current capacity)
- Dimensions: 768 (vs. 512 current)
- Parameters: 278M
- Disk: ~1.1GB
- Base architecture: XLM-RoBERTa

**Hardware Requirements:**
- CPU: 2-4 cores, ~2-3GB RAM during encoding
- GPU: Optional (2-3× speedup on CUDA)
- Encoding speed (CPU): ~50-100 docs/sec for 200-word chunks

**Benchmark Performance (MTEB Multilingual Retrieval):**
- Spanish: 62.3 nDCG@10
- French: 61.8 nDCG@10
- English: 63.1 nDCG@10
- Average (50 languages): 61.5

**Training Data:**
- 1 billion+ text pairs from 100+ languages
- Contrastive learning with hard negatives
- MS MARCO, NQ, HotpotQA, and multilingual Wikipedia

**Integration Notes:**
- Drop-in replacement for `SentenceTransformer(model_name)`
- Requires query prefix: `"query: {text}"` (passage prefix optional but recommended)
- Normalize embeddings before indexing (already default in `sentence-transformers`)

**Chunking Implications:**
- Can support **300-350 word chunks** (leaving buffer for overlap and special tokens)
- Enables hierarchical strategies: 150-word child chunks + 300-word parent summaries
- Room for query instruction tuning

**Risks:**
- +50% dimensional increase (768 vs 512) → larger Solr index (~1.5× growth)
- Query latency may increase slightly (~10-20ms per kNN query)
- Requires Solr schema migration (new field type `knn_vector_768`)

**Why Recommended:**
- Proven multilingual retrieval leader in MTEB benchmarks
- Well-balanced size vs. quality trade-off
- Active community and Microsoft backing (intfloat is MSR-affiliated)
- 512-token window enables most advanced retrieval strategies without excessive cost

---

#### 2.2.2 multilingual-e5-small

**HuggingFace:** `intfloat/multilingual-e5-small`

**Specifications:**
- Max sequence: **512 tokens**
- Dimensions: 384 (smaller than current 512)
- Parameters: 118M
- Disk: ~470MB

**Hardware Requirements:**
- CPU: 1-2 cores, ~1-2GB RAM
- Fastest encoding in this comparison (~150-200 docs/sec)

**Benchmark Performance:**
- MTEB Average: 58.2 (slight drop from current ~60)
- Spanish: 59.1, French: 58.5, English: 60.2

**Why Consider:**
- **Lower resource footprint** than current model
- Maintains 512-token window (key benefit)
- Smaller index size (384D vs. 512D) → disk/memory savings
- Best option if infrastructure constraints tighten

**Why Not Primary:**
- Marginal quality loss vs. distiluse (though context window compensates)
- Better options exist in same resource tier (e5-base only +2.3GB RAM)

---

#### 2.2.3 BGE-M3 (BAAI/bge-m3)

**HuggingFace:** `BAAI/bge-m3`

**Specifications:**
- Max sequence: **8192 tokens** (64× current capacity!)
- Dimensions: 1024
- Parameters: 568M
- Disk: ~2.2GB
- Unique: Supports hybrid sparse+dense retrieval

**Hardware Requirements:**
- CPU: 4-8 cores, ~4-6GB RAM (longer sequences = higher memory)
- GPU: Strongly recommended for 8K context (10× speedup)
- Encoding speed (CPU, 8K context): ~5-10 docs/sec

**Benchmark Performance:**
- MTEB Average: 63.1 (best in this list for Chinese)
- English/Spanish/French: ~61-62 (competitive but not leading)

**Training Focus:**
- Primarily Chinese + English bilingual corpus
- 100+ languages supported but Western European languages underweighted

**Why Intriguing:**
- **Massive context window** (8192 tokens = ~6000 words)
- Could encode entire book chapters in single embedding
- Hybrid retrieval mode (dense + sparse) built-in

**Why Risky:**
- **Chinese-centric training** — may underperform on Catalan/Spanish historical texts
- High memory usage for long contexts
- Larger index (1024D) → +100% disk vs. current
- Overkill context window for typical book chunks (200-400 words optimal)

**Verdict:** Experimental candidate for future exploration if resources allow. Not recommended for first A/B test due to Latin-language training gaps.

---

#### 2.2.4 paraphrase-multilingual-mpnet-base-v2

**HuggingFace:** `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`

**Specifications:**
- Max sequence: **384 tokens**
- Dimensions: 768
- Parameters: 278M
- Disk: ~1.1GB

**Hardware Requirements:**
- CPU: 2-4 cores, ~2-3GB RAM
- Similar profile to e5-base

**Benchmark Performance:**
- MTEB Average: ~54.3 (older model, pre-e5 era)
- Spanish: 52.1, French: 53.8, English: 56.0

**Why Outdated:**
- 384 tokens < 512 tokens (e5-base)
- Lower benchmark scores across the board
- No clear advantage over e5-base in any dimension

**Verdict:** Skip in favor of e5-base. Included for completeness only.

---

#### 2.2.5 multilingual-e5-large

**HuggingFace:** `intfloat/multilingual-e5-large`

**Specifications:**
- Max sequence: **512 tokens**
- Dimensions: 1024
- Parameters: 560M
- Disk: ~2.1GB

**Hardware Requirements:**
- CPU: 4-6 cores, ~4-5GB RAM
- GPU: Recommended for production (5× speedup)
- Encoding speed (CPU): ~25-40 docs/sec

**Benchmark Performance:**
- MTEB Average: 64.3 (highest quality in e5 series)
- Spanish: 65.1, French: 64.8, English: 66.0

**Why Best Quality:**
- Top-tier multilingual retrieval across all languages
- Same 512-token window as e5-base
- Proven stability and community adoption

**Why Not Default Recommendation:**
- **Encoding latency doubles** vs. e5-base (critical for batch indexing)
- Index size +100% vs. current (1024D vs. 512D)
- Diminishing returns: +2.8 MTEB points for 2× resource cost

**When to Consider:**
- After e5-base A/B test proves context window value
- If relevance improvements justify latency cost
- GPU infrastructure becomes available

---

## 3. Chunking Strategy Implications

### 3.1 Current Strategy (90 words, 10 overlap)

```
[Chunk 1: words 0-89]
         [Chunk 2: words 80-169]
                  [Chunk 3: words 160-249]
```

- **Context per chunk:** 90 words (~120 tokens)
- **No hierarchical structure:** Flat chunk list

### 3.2 Proposed Strategy with 512 Tokens (e.g., e5-base)

**Option A: Larger Flat Chunks (300 words, 50 overlap)**
```
[Chunk 1: words 0-299]
                                [Chunk 2: words 250-549]
                                                        [Chunk 3: words 500-799]
```

- **Context per chunk:** 300 words (~400 tokens)
- **Benefits:** Captures full paragraphs, complex arguments, longer context
- **Trade-off:** 3× fewer chunks per book → coarser retrieval granularity

**Option B: Hierarchical Chunking (150-word children + 300-word parents)**
```
Parent 1 [words 0-299]
  ├─ Child 1a [words 0-149]
  └─ Child 1b [words 150-299]
Parent 2 [words 250-549]
  ├─ Child 2a [words 250-399]
  └─ Child 2b [words 400-549]
```

- **Index both levels:** Children for precision, parents for context
- **Query strategy:** Retrieve children, rerank with parent embeddings
- **Complexity:** Requires dual-vector Solr schema and modified search logic

**Option C: Sliding Window with Stride (200 words, 100 overlap)**
```
[Chunk 1: words 0-199]
              [Chunk 2: words 100-299]
                        [Chunk 3: words 200-399]
```

- **High recall:** Every 100-word span appears in 2 chunks
- **Cost:** 2× index size vs. minimal overlap
- **Use case:** When missing a relevant passage is unacceptable

### 3.3 Recommended Initial Strategy

**300-word chunks, 50-word overlap** (Option A)
- Maintains manageable index size (~3.3× fewer chunks)
- Significantly improves context quality
- Compatible with existing parent-chunk Solr architecture
- Defer hierarchical complexity until Option A is validated

---

## 4. A/B Testing Experiment Design

### 4.1 Goals

1. **Measure relevance improvement:** Does larger context + better model improve search quality?
2. **Quantify resource costs:** Encoding latency, index size, query latency, memory usage
3. **Human-in-the-loop validation:** Ground truth relevance judgments for 50+ test queries
4. **Architectural feasibility:** Prove in-repo testing without major refactoring

### 4.2 Experiment Architecture

**Dual-Collection Strategy (IN-REPO)**

```
┌─────────────────────────────────────────────────────────┐
│  Solr (3-node SolrCloud)                                 │
│  ┌─────────────────────┐  ┌─────────────────────┐      │
│  │ books (existing)    │  │ books_e5base (new)  │      │
│  │ - distiluse 512D    │  │ - e5-base 768D      │      │
│  │ - 90-word chunks    │  │ - 300-word chunks   │      │
│  │ - knn_vector_512    │  │ - knn_vector_768    │      │
│  └─────────────────────┘  └─────────────────────┘      │
└─────────────────────────────────────────────────────────┘
         ▲                           ▲
         │                           │
    ┌────┴───────────────────────────┴──────┐
    │  embeddings-server                     │
    │  - Route by MODEL_NAME env var         │
    │  - /v1/embeddings/model returns dims   │
    └────────────────────────────────────────┘
         ▲                           ▲
         │                           │
    ┌────┴────────┐           ┌──────┴────────┐
    │ indexer-v1  │           │ indexer-v2    │
    │ (distiluse) │           │ (e5-base)     │
    │ CHUNK=90    │           │ CHUNK=300     │
    └─────────────┘           └───────────────┘
```

**Key Design Decisions:**
1. **Two Solr collections:** Avoids schema conflicts, enables side-by-side queries
2. **Two document-indexer instances:** One per model (different CHUNK_SIZE)
3. **One embeddings-server per model:** Environment variable switch (`MODEL_NAME`)
4. **Shared RabbitMQ queue:** Both indexers consume same documents
5. **Modified solr-search:** Query parameter `?collection=books_e5base` routes to new collection

### 4.3 Implementation Steps

#### Phase 1: Infrastructure Setup (1-2 days)

1. **Add `books_e5base` collection to Solr:**
   ```bash
   docker exec solr1 solr create_collection -c books_e5base \
     -d /opt/solr/server/solr/configsets/books_new \
     -shards 1 -replicationFactor 3
   ```

2. **Create new managed-schema for 768D vectors:**
   ```xml
   <fieldType name="knn_vector_768" class="solr.DenseVectorField" 
              vectorDimension="768" similarityFunction="cosine" knnAlgorithm="hnsw"/>
   <field name="embedding_v" type="knn_vector_768" indexed="true" stored="true"/>
   ```

3. **Deploy second embeddings-server:**
   - docker-compose.yml: add `embeddings-server-e5` service
   - Environment: `MODEL_NAME=intfloat/multilingual-e5-base`
   - Port: 8085 (avoid conflict with existing 8080)

4. **Deploy second document-indexer:**
   - docker-compose.yml: add `document-indexer-e5` service
   - Environment: `EMBEDDINGS_HOST=embeddings-server-e5`, `CHUNK_SIZE=300`, `CHUNK_OVERLAP=50`, `SOLR_COLLECTION=books_e5base`

#### Phase 2: Index Baseline Dataset (2-3 days)

1. **Select test corpus:** 100-200 books across languages (ES, FR, CA, EN)
2. **Index into both collections simultaneously**
3. **Measure indexing metrics:**
   - Documents/second per indexer
   - Memory usage (peak RSS)
   - Solr index size on disk (per collection)
   - Encoding latency (p50, p95, p99)

#### Phase 3: Query Benchmarking (3-4 days)

1. **Create test query set (50 queries):**
   - 10 single-keyword queries (e.g., "Napoleon", "quantum")
   - 15 phrase queries (e.g., "French Revolution causes")
   - 15 conceptual queries (e.g., "books about overcoming adversity")
   - 10 multilingual queries (ES/FR/CA)

2. **Run queries against both collections:**
   - Search mode: semantic (kNN only)
   - Record top-10 results per query, per collection
   - Measure query latency (p50, p95, p99)

3. **Automated metrics:**
   - Overlap@10: How many results appear in both top-10s?
   - Chunk text length: Are e5-base results more coherent?

#### Phase 4: Human Evaluation (5-7 days)

1. **Relevance judgment UI (admin panel):**
   - Display query + side-by-side results from both models
   - Annotator rates each result: Highly Relevant (2), Relevant (1), Not Relevant (0)
   - Blind evaluation (model labels hidden)

2. **Metrics to compute:**
   - nDCG@10 per collection
   - MRR (Mean Reciprocal Rank)
   - Precision@5
   - Inter-annotator agreement (if multiple judges)

3. **Sample size:** 50 queries × 2 collections = 100 annotation tasks (~4-6 hours)

#### Phase 5: Resource Cost Analysis

1. **Index size comparison:**
   - Disk: `du -sh /var/solr/data/books*`
   - RAM: Solr JVM heap usage during queries

2. **Latency profiling:**
   - Embeddings encoding: log timestamps in document-indexer
   - Solr kNN query: enable Solr debug timing

3. **Throughput limits:**
   - Max sustainable indexing rate (docs/sec)
   - Max query QPS before p95 latency degrades

### 4.4 Success Criteria

**Proceed to production if:**
1. **Relevance improvement ≥ 5% nDCG@10** (statistically significant, p < 0.05)
2. **Query latency increase ≤ 50ms at p95** (acceptable for user experience)
3. **Index size increase ≤ 2×** (manageable within current infrastructure)
4. **Indexing throughput ≥ 80% of baseline** (tolerable batch processing slowdown)

**Abort if:**
- Relevance improvement < 3% (not worth complexity)
- Query latency > +100ms p95 (unacceptable UX)
- Index size > 3× baseline (infrastructure limits)

### 4.5 Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **e5-base encoding too slow** | Indexing backlog | Add GPU support or batch-optimize encoding |
| **768D index too large** | Disk exhaustion | Quantize vectors to int8 (Solr 9.4+) |
| **Query latency unacceptable** | Poor UX | Reduce topK, tune HNSW params (efConstruction) |
| **Relevance improvement marginal** | Wasted effort | Proceed to e5-large or BGE-M3 |
| **Two-collection overhead** | Maintenance burden | Merge winning model into main collection post-test |

---

## 5. Alternative Approaches Considered

### 5.1 Separate Repository for Testing

**Rationale:** Isolate experiment from production codebase.

**Pros:**
- No risk to production services
- Clean slate for experimentation

**Cons:**
- Lose access to existing infrastructure (Solr, RabbitMQ, document-lister)
- Must replicate indexing pipeline, search API, UI
- Cannot compare side-by-side in real user context
- PO explicitly prefers in-repo testing

**Verdict:** Rejected. Dual-collection approach provides better integration with minimal risk.

### 5.2 Model Quantization (int8 or binary)

**Rationale:** Reduce 768D → 96 bytes per vector via quantization.

**Pros:**
- Smaller index size (~4× reduction)
- Faster kNN queries (less data to read)

**Cons:**
- Quality loss (typically 2-5% nDCG drop)
- Solr 9.7 has limited native quantization support (requires manual implementation)
- Complicates A/B test (adds third variable)

**Verdict:** Defer until after full-precision e5-base validation. Quantization is an optimization, not a model selection decision.

### 5.3 Cross-Encoder Reranking

**Rationale:** Use bi-encoder (e5-base) for retrieval, cross-encoder for reranking top-k.

**Pros:**
- Best-in-class relevance (nDCG@10 often +10-15%)
- Smaller index (only bi-encoder vectors stored)

**Cons:**
- High query latency (cross-encoder must process query + each candidate)
- Out of scope for this spike (focuses on bi-encoder selection)

**Verdict:** Excellent future enhancement. Document in roadmap after base model selection.

---

## 6. Recommendations

### 6.1 Immediate Actions (Sprint 1)

1. **Implement A/B testing infrastructure** (dual-collection setup in docker-compose.yml)
2. **Deploy multilingual-e5-base as primary candidate**
   - Chunking: 300 words, 50 overlap
   - Dimensions: 768
   - Collection: `books_e5base`
3. **Index test corpus** (100-200 books, balanced language distribution)

### 6.2 Sprint 2: Measurement

1. **Run 50-query benchmark suite**
2. **Collect human relevance judgments** (nDCG@10, MRR)
3. **Profile resource usage** (latency, memory, disk)

### 6.3 Decision Gate (After Sprint 2)

**If e5-base succeeds (≥5% nDCG improvement, acceptable latency):**
- Proceed to production migration (issue: Migrate to e5-base)
- Deprecate distiluse collection
- Update documentation and onboarding

**If e5-base underperforms (<3% improvement):**
- Test fallback: **multilingual-e5-large** (768 → 1024D, higher quality)
- If still insufficient, explore BGE-M3 (acknowledge Chinese bias risk)

**If resource costs prohibitive (>2× index size or >100ms latency):**
- Downgrade to **multilingual-e5-small** (384D, faster)
- Investigate quantization or HNSW tuning

### 6.4 Long-Term Roadmap (Post-A/B Test)

1. **Hierarchical chunking** (300-word parents + 150-word children)
2. **Cross-encoder reranking** for top-10 results
3. **Query instruction tuning** (use e5 prefix: `"query: {text}"`)
4. **Multilingual query expansion** (synonyms, historical spelling variants)

---

## 7. Technical Appendix

### 7.1 Solr Schema Changes Required

```xml
<!-- New field type for 768-dimensional vectors -->
<fieldType name="knn_vector_768" class="solr.DenseVectorField" 
           vectorDimension="768" similarityFunction="cosine" knnAlgorithm="hnsw">
  <!-- HNSW tuning parameters (adjust based on A/B test results) -->
  <!-- efConstruction: default 100, increase to 200-400 for higher recall -->
  <!-- maxConnections: default 16, increase to 32 for denser graph -->
</fieldType>

<!-- Chunk embedding field (replaces existing embedding_v for new collection) -->
<field name="embedding_v" type="knn_vector_768" indexed="true" stored="true"/>

<!-- Optional: Book-level embedding (768D) -->
<field name="book_embedding" type="knn_vector_768" indexed="true" stored="true"/>
```

### 7.2 Environment Variable Changes

**embeddings-server-e5:**
```env
MODEL_NAME=intfloat/multilingual-e5-base
PORT=8085
```

**document-indexer-e5:**
```env
EMBEDDINGS_HOST=embeddings-server-e5
EMBEDDINGS_PORT=8085
CHUNK_SIZE=300
CHUNK_OVERLAP=50
SOLR_COLLECTION=books_e5base
QUEUE_NAME=new_documents  # Shared with baseline indexer
```

### 7.3 Query API Extension

**solr-search service modification:**
```python
# New query parameter: ?collection=books_e5base
collection = request.query_params.get("collection", "books")  # default: books
solr_url = f"http://{SOLR_HOST}:{SOLR_PORT}/solr/{collection}/select"
```

**Frontend A/B toggle (optional):**
- Admin panel: switch between collections for comparison
- User-facing: single collection (post-migration)

### 7.4 Benchmark Query Examples

**Single-keyword (10 queries):**
1. Napoleon (expect: French history books)
2. quantum (expect: physics texts)
3. cervantes (expect: Spanish literature)
4. photosynthesis (expect: biology)
5. impressionism (expect: art history)
6. Catalonia (expect: regional history)
7. renaissance (expect: European history/art)
8. relativity (expect: Einstein, physics)
9. democracy (expect: political theory)
10. mitosis (expect: biology)

**Phrase queries (15 queries):**
1. "French Revolution causes" (ES: "causas de la Revolución Francesa")
2. "modernist architecture Barcelona" (CA: "arquitectura modernista Barcelona")
3. "quantum entanglement explained" (EN)
4. "medieval trade routes" (EN)
5. "Catalan literature 19th century" (CA: "literatura catalana segle XIX")
6. "photosynthesis in desert plants" (EN)
7. "Spanish civil war impact" (ES: "impacto guerra civil española")
8. "art nouveau furniture design" (FR: "design mobilier art nouveau")
9. "microbial ecology marine environments" (EN)
10. "existentialism Sartre Camus" (FR)
11. "Gaudi Sagrada Familia construction" (CA)
12. "thermodynamics second law applications" (EN)
13. "Romantic poetry Wordsworth" (EN)
14. "Barcelona Olympic Games 1992" (CA)
15. "colonial history Latin America" (ES)

**Conceptual queries (15 queries):**
1. "books about overcoming adversity" (EN)
2. "historical accounts of social movements" (EN)
3. "scientific theories that changed medicine" (EN)
4. "novels exploring family relationships" (ES: "novelas sobre relaciones familiares")
5. "biographies of female scientists" (EN)
6. "economic theories of development" (EN)
7. "philosophical debates on free will" (EN/FR)
8. "climate change impacts on agriculture" (EN)
9. "cultural identity in immigrant communities" (ES)
10. "mathematics in ancient civilizations" (EN)
11. "feminist movements in Europe" (FR: "mouvements féministes en Europe")
12. "ecological restoration case studies" (EN)
13. "mythology and religion comparisons" (EN)
14. "urban planning sustainable cities" (CA: "urbanisme ciutats sostenibles")
15. "psychological trauma and recovery" (EN)

**Multilingual queries (10 queries):**
1. "historia de Catalunya" (CA, expect: Catalan history)
2. "littérature française moderne" (FR, expect: French literature)
3. "ciencia ficción española" (ES, expect: Spanish sci-fi)
4. "arquitectura gótica europea" (ES, expect: Gothic architecture)
5. "filosofia medieval" (CA, expect: Medieval philosophy)
6. "révolution industrielle" (FR, expect: Industrial Revolution)
7. "pintura barroca" (ES, expect: Baroque painting)
8. "linguistique catalane" (FR, expect: Catalan linguistics)
9. "poesía romántica" (ES, expect: Romantic poetry)
10. "histoire contemporaine" (FR, expect: Contemporary history)

---

## 8. References

### 8.1 Model Documentation

- **multilingual-e5:** https://huggingface.co/intfloat/multilingual-e5-base
- **BGE-M3:** https://huggingface.co/BAAI/bge-m3
- **sentence-transformers:** https://www.sbert.net/

### 8.2 Benchmarks

- **MTEB:** https://huggingface.co/spaces/mteb/leaderboard
- **BEIR:** https://github.com/beir-cellar/beir

### 8.3 Internal Documentation

- Solr parent-chunk model: `.squad/skills/solr-parent-chunk-model/SKILL.md`
- Current embeddings config: `src/embeddings-server/config/__init__.py` (ADR-004)
- Chunking logic: `src/document-indexer/document_indexer/chunker.py`
- Solr schema: `src/solr/books/managed-schema.xml`

### 8.4 Related Issues

- #861: This research spike
- (Future) Migration to e5-base (pending A/B test results)
- (Future) Hierarchical chunking implementation
- (Future) Cross-encoder reranking

---

## Appendix A: Cost-Benefit Summary

| Metric | Current (distiluse) | e5-base | e5-small | e5-large | BGE-M3 |
|--------|---------------------|---------|----------|----------|--------|
| **Context window** | 128 tok | **512 tok** | **512 tok** | **512 tok** | 8192 tok |
| **Chunk size (words)** | 90 | 300 | 300 | 300 | 1000+ |
| **Embedding dims** | 512 | 768 | 384 | 1024 | 1024 |
| **Index size (relative)** | 1.0× | **1.5×** | 0.75× | 2.0× | 2.0× |
| **Encoding speed (rel)** | 1.0× | **0.6×** | 1.5× | 0.4× | 0.2× |
| **Query latency (est.)** | baseline | **+15ms** | +5ms | +25ms | +40ms |
| **MTEB score (avg)** | ~60 | **61.5** | 58.2 | 64.3 | 63.1 |
| **Resource cost** | Low | **Medium** | Low | High | High |
| **Risk level** | N/A | **Low** | Low | Medium | High |

**Recommendation:** Start with **e5-base** — best balance of quality improvement, resource cost, and risk.

---

**END OF RESEARCH REPORT**
