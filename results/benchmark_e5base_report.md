# Embedding Model Benchmark Report

**multilingual-e5-base (768D) vs distiluse-base-multilingual-cased-v2 (512D)**

Issue: #926 · Date: 2026-03-23

---

## 1. Executive Summary

We benchmarked **multilingual-e5-base** (768-dimensional embeddings) against the
current default **distiluse-base-multilingual-cased-v2** (512-dimensional embeddings)
across 90 query comparisons (30 queries × 3 search modes) over a corpus of 33 indexed
PDFs.

**Key findings:**

| Metric | Keyword (BM25) | Semantic (kNN) | Hybrid (RRF) |
|--------|---------------|----------------|---------------|
| Result overlap (Jaccard) | 0.97 | 0.01 | 0.18 |
| Latency delta (e5 vs distiluse) | −12% faster | +52% slower | +53% slower |

- **Keyword mode** results are near-identical (Jaccard ≈ 1.0), confirming both
  pipelines indexed the same documents.
- **Semantic mode** results diverge almost completely (Jaccard ≈ 0), meaning the two
  models rank documents in entirely different orders.
- **Hybrid mode** shows partial overlap (Jaccard ≈ 0.18), carried by the shared BM25
  component.
- e5-base incurs **~50% higher latency** in vector-dependent modes due to larger
  embeddings (768D vs 512D).
- **Without ground-truth relevance judgments, we cannot determine which model produces
  more relevant results.** The data shows the models are *different*, not that one is
  *better*.

**Recommendation:** Do not switch the default model at this time. The performance
regression in latency is measurable, and the relevance improvement is unproven. A
relevance evaluation with human-judged ground truth is needed before any migration.

---

## 2. Methodology

### 2.1 Test Environment

Both pipelines were deployed on the full Docker Compose stack. Each model's documents
were indexed into separate Solr collections so queries could be run against both
simultaneously.

### 2.2 Corpus

- **33 PDF documents** indexed through both pipelines
- distiluse pipeline: **520 chunks** (512D vectors)
- e5-base pipeline: **197 chunks** (768D vectors)

> **Note on chunk counts:** The ~2.6× difference in chunk counts is due to different
> text chunking strategies in each indexer pipeline, not missing documents. The keyword
> mode Jaccard of 0.97 confirms document-level parity.

### 2.3 Query Set

30 queries across 5 categories:

| Category | Description | Example |
|----------|-------------|---------|
| `simple_keyword` | Short keyword queries | "machine learning" |
| `natural_language` | Full-sentence questions | "What are the effects of climate change?" |
| `multilingual` | Non-English queries | Queries in German, French, etc. |
| `long_complex` | Multi-clause queries | Compound technical questions |
| `edge_cases` | Unusual or adversarial inputs | Empty-ish queries, special characters |

### 2.4 Search Modes

Each query was executed in three modes:

1. **Keyword (BM25):** Traditional text matching via Solr's BM25 scoring
2. **Semantic (kNN):** Pure vector similarity search using cosine distance
3. **Hybrid (RRF):** Reciprocal Rank Fusion combining BM25 and kNN results

### 2.5 Metrics

- **Jaccard similarity** of top-k result sets — measures overlap between the two
  models' returned chunk IDs (1.0 = identical results, 0.0 = no overlap)
- **Latency** — end-to-end query response time (mean, p95)
- **Error rate** — HTTP errors or timeouts

### 2.6 Limitations

- **No ground-truth relevance labels.** Jaccard measures *agreement* between models,
  not *correctness*. Two models can disagree completely yet one (or both) may be
  producing good results.
- **Chunk granularity differs.** The 520 vs 197 chunk split means result IDs are not
  directly comparable at the chunk level in semantic mode. Jaccard in semantic/hybrid
  modes partially reflects this structural difference.
- **Small corpus.** 33 documents is sufficient for a smoke test but not for
  statistical significance claims about relevance quality.

---

## 3. Results by Mode

### 3.1 Keyword Mode (BM25)

| Metric | Value |
|--------|-------|
| Jaccard mean | 0.971 |
| Jaccard median | 1.000 |
| Jaccard min | 0.667 |
| Jaccard max | 1.000 |
| Baseline (distiluse) latency — mean | 20.0 ms |
| Baseline (distiluse) latency — p95 | 50.3 ms |
| Candidate (e5-base) latency — mean | 17.5 ms |
| Candidate (e5-base) latency — p95 | 31.4 ms |
| Errors | 0 |

**Analysis:** Near-perfect overlap confirms both Solr collections contain the same
documents and BM25 scoring is consistent. The small deviations (min Jaccard = 0.667)
are attributable to chunk boundary differences — the same document content is split
into different chunk IDs, causing minor set differences at the chunk level.

e5-base was marginally faster in keyword mode (17.5 ms vs 20.0 ms mean), likely due
to the smaller collection size (197 vs 520 chunks) reducing Solr's index scan work.

### 3.2 Semantic Mode (kNN)

| Metric | Value |
|--------|-------|
| Jaccard mean | 0.014 |
| Jaccard median | 0.000 |
| Jaccard min | 0.000 |
| Jaccard max | 0.111 |
| Baseline (distiluse) latency — mean | 42.5 ms |
| Baseline (distiluse) latency — p95 | 57.8 ms |
| Candidate (e5-base) latency — mean | 64.7 ms |
| Candidate (e5-base) latency — p95 | 91.7 ms |
| Errors | 0 |

**Analysis:** The near-zero Jaccard indicates the two models produce **fundamentally
different rankings** in pure vector search. This is expected — the models have
different architectures, training data, and embedding spaces.

**Latency regression:** e5-base is 52% slower on average (64.7 ms vs 42.5 ms). The
768-dimensional vectors require proportionally more compute for cosine similarity
calculations during kNN search. The p95 delta is even larger (91.7 ms vs 57.8 ms,
+59%).

**Score distribution insight — "machine learning" query:**

| Model | Top-5 Cosine Scores | Spread |
|-------|---------------------|--------|
| distiluse | 0.641, 0.587, 0.560, 0.557, 0.557 | 0.084 |
| e5-base | 0.908, 0.905, 0.905, 0.905, 0.904 | 0.004 |

The e5-base model produces much higher absolute similarity scores (0.90+ vs 0.55–0.64)
but with **20× tighter clustering** (spread of 0.004 vs 0.084). This has practical
implications:

- **Tight clustering may hurt discrimination.** When the top 5 results all score within
  0.4% of each other, the ranking is fragile — small numerical noise could reorder
  results arbitrarily.
- **Higher absolute scores do not indicate better relevance.** Different embedding spaces
  have different score distributions. A 0.90 in e5-base is not "better" than a 0.64 in
  distiluse — they are on different scales.
- **Score-based thresholds would need recalibration.** Any logic that filters by a
  minimum similarity score (e.g., "only show results above 0.5") would behave very
  differently between the two models.

### 3.3 Hybrid Mode (RRF)

| Metric | Value |
|--------|-------|
| Jaccard mean | 0.175 |
| Jaccard median | 0.213 |
| Jaccard min | 0.000 |
| Jaccard max | 0.429 |
| Baseline (distiluse) latency — mean | 45.7 ms |
| Baseline (distiluse) latency — p95 | 62.7 ms |
| Candidate (e5-base) latency — mean | 69.8 ms |
| Candidate (e5-base) latency — p95 | 93.5 ms |
| Errors | 0 |

**Analysis:** The hybrid Jaccard of 0.175 sits between keyword (0.97) and semantic
(0.01), as expected. The RRF fusion combines BM25 scores (which agree) with kNN scores
(which disagree), producing partial overlap driven primarily by the keyword component.

Latency follows the same pattern as semantic mode — e5-base is 53% slower on average
due to the kNN component of the hybrid query.

---

## 4. Results by Query Category

| Category | Mean Jaccard (all modes) |
|----------|------------------------|
| natural_language | 0.426 |
| edge_cases | 0.384 |
| long_complex | 0.380 |
| multilingual | 0.374 |
| simple_keyword | 0.366 |

**Analysis:** Category-level Jaccard values are relatively uniform (0.37–0.43),
suggesting no dramatic category-specific advantage for either model. The slightly
higher agreement on natural language queries may reflect both models handling
well-formed sentences more consistently than terse keyword queries.

The multilingual category (0.374) does not show a meaningful advantage for e5-base
despite its "multilingual" branding — though again, agreement is not the same as
quality.

---

## 5. Key Findings

### 5.1 The models produce genuinely different semantic rankings

Jaccard ≈ 0 in semantic mode is not an error — it reflects fundamentally different
learned representations. The two models disagree on which chunks are most relevant for
a given query, which means switching models would noticeably change the user experience.

### 5.2 We cannot determine which ranking is better without ground truth

This benchmark measures **agreement**, not **quality**. To evaluate whether e5-base
produces more relevant results, we would need:

- A set of queries with human-judged relevant documents (a "qrels" file)
- Standard IR metrics: nDCG@10, MAP, MRR
- Ideally, blind side-by-side evaluation by domain experts

### 5.3 e5-base has a measurable latency cost

| Mode | distiluse (mean) | e5-base (mean) | Delta |
|------|------------------|----------------|-------|
| Keyword | 20.0 ms | 17.5 ms | −12% |
| Semantic | 42.5 ms | 64.7 ms | +52% |
| Hybrid | 45.7 ms | 69.8 ms | +53% |

The 50%+ latency increase in semantic and hybrid modes is directly attributable to
the 50% larger vector dimensionality (768 vs 512). This affects:

- **Query-time kNN search** — more dimensions to compute per distance calculation
- **Index storage** — 50% more disk and memory per vector
- **Indexing throughput** — larger embeddings take longer to generate and store

### 5.4 Score clustering in e5-base may reduce result quality

The extremely tight score clustering (spread of 0.004 in top-5 vs 0.084 for distiluse)
means e5-base's kNN results have very low discriminative power. In practice, this could
lead to:

- Unstable rankings where minor perturbations change result order
- Difficulty implementing meaningful relevance cutoffs
- Reduced effectiveness of score-based boosting in hybrid/RRF fusion

### 5.5 Chunk count differences confound the comparison

The 520 vs 197 chunk split means the two pipelines are not strictly comparable at the
chunk level. A fairer comparison would use identical chunking strategies so that result
set differences reflect only the embedding model, not the text segmentation.

---

## 6. Recommendation

### Do not switch the default model at this time.

**Rationale:**

1. **No evidence of relevance improvement.** The benchmark shows the models differ but
   cannot show which is better. Switching without relevance data risks degrading the
   user experience with no measurable upside.

2. **Measurable performance regression.** The ~50% latency increase in semantic and
   hybrid modes is a concrete cost. At current corpus sizes this is acceptable (70 ms
   is still fast), but it will compound as the corpus grows.

3. **Tight score clustering is a concern.** The e5-base score distribution raises
   questions about ranking stability that should be investigated before committing to
   the model.

4. **Migration cost is non-trivial.** Switching models requires re-indexing all
   documents, recalibrating any score-based thresholds, and updating the Solr schema
   for 768-dimensional vectors.

### Suggested next steps

| Priority | Action | Effort |
|----------|--------|--------|
| **P1** | Create a ground-truth relevance set (30–50 queries with human-judged relevant documents) and evaluate both models with nDCG@10/MAP | Medium |
| **P2** | Normalize the chunking strategy so both models operate on identical chunks, then re-run the benchmark | Low |
| **P3** | Profile the score distribution issue — test whether e5-base's tight clustering degrades ranking stability with larger corpora | Low |
| **P4** | If relevance testing shows e5-base is superior, plan a migration with schema changes, re-indexing, and threshold recalibration | High |

---

*Report generated from benchmark data in `results/benchmark_e5base.json`.*
*Corpus: 33 PDFs · 30 queries · 90 comparisons · Zero errors.*
