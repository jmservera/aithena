---
name: "embedding-model-selection"
description: "Methodology for evaluating and selecting multilingual embedding models for semantic search in Aithena"
domain: "search, embeddings, model-evaluation, benchmarking"
confidence: "high"
source: "earned — extracted from #861 research spike (PR #863), MTEB benchmark analysis, A/B testing framework design"
author: "Ash"
created: "2026-03-22"
last_validated: "2026-03-22"
---

## Context

Apply this skill when evaluating alternative embedding models for vector search, particularly when context window limitations or relevance issues arise. This methodology emerged from research spike #861, which evaluated 5 multilingual models to address the 128-token window constraint of distiluse-base-multilingual-cased-v2.

## Patterns

### 1. Model Evaluation Criteria

**Non-negotiable requirements for Aithena:**
- **Latin multilingual support:** ES, FR, CA, EN (including historical text variants)
- **CPU-compatible:** No mandatory GPU (infrastructure constraint)
- **sentence-transformers library:** Drop-in replacement via `SentenceTransformer(model_name)`
- **Active maintenance:** Recent updates, community support, published benchmarks

**Quality metrics (in priority order):**
1. **MTEB multilingual retrieval score** — gold standard for semantic search
2. **Target language coverage** — verify ES/FR/CA/EN performance (not just EN-centric)
3. **Context window size** — larger = better chunking strategies
4. **Vector dimensions** — balance quality vs. index size

**Resource constraints:**
- Max index size increase: 2× baseline (disk limits)
- Max query latency increase: +50ms at p95 (UX requirement)
- Max encoding latency: 80% of baseline throughput (batch indexing tolerance)

### 2. Benchmark Interpretation

**MTEB (Massive Text Embedding Benchmark):**
- Multilingual retrieval tasks across 50+ languages
- nDCG@10 is primary metric (normalized discounted cumulative gain)
- Average score aggregates performance across languages
- **Critical:** Check per-language scores — Chinese models may skew high on average but underperform on Latin languages

**Scoring heuristics (MTEB averages):**
- 50-55: Older generation models (mpnet, early multilingual)
- 56-61: Current generation (distiluse, e5-small)
- 62-66: State-of-art (e5-base/large, BGE-M3)
- 67+: Emerging cutting-edge (often GPU-only or English-focused)

### 3. Context Window vs. Chunk Size

**Token-to-word conversion (multilingual text):**
- Latin languages: ~1.2-1.3 tokens/word average
- Formula: `max_chunk_words = (max_tokens - special_tokens_overhead) / 1.3`
- Leave 20-30% buffer for overlap and edge cases

**Examples:**
- 128 tokens → ~90 words usable
- 512 tokens → ~350 words usable (recommend 300 for safety)

**Optimal range for books:** 200-400 words per chunk (balance context vs. precision)

### 4. A/B Testing Framework Design

**Dual-collection strategy (in-repo):**
- Parallel Solr collections: `{base_name}` + `{base_name}_{model_tag}`
- Two embeddings-server instances (different MODEL_NAME, separate ports)
- Modified solr-search: `?collection={name}` query parameter

**Success criteria thresholds:**
- Relevance: ≥5% nDCG@10 improvement (p < 0.05 statistical significance)
- Latency: ≤50ms query increase at p95
- Index size: ≤2× baseline
- Throughput: ≥80% baseline indexing rate

## Anti-Patterns

- **Never assume English benchmarks apply to multilingual use cases** — always check per-language scores
- **Never test only one candidate** — always have a fallback model
- **Never skip human evaluation** — automated metrics miss nuanced relevance
- **Never increase dimensions without capacity planning** — 512D → 1024D doubles index size
- **Never ignore model-specific requirements** — e5 models need query prefix (`"query: {text}"`)

## References

- Research report: `docs/research/embedding-model-research.md` (issue #861, PR #863)
- MTEB leaderboard: https://huggingface.co/spaces/mteb/leaderboard
- Current model config: `src/embeddings-server/config/__init__.py` (ADR-004)
