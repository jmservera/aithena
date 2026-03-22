# Decision: Embedding Model Evaluation and A/B Testing Strategy

**Author:** Ash (Search Engineer)  
**Date:** 2026-03-22  
**Issue:** #861  
**PR:** #863  
**Status:** Proposed (awaiting PO approval)

## Context

The current embedding model (`distiluse-base-multilingual-cased-v2`) is constrained by a 128-token window, resulting in 90-word chunks that are too small for hierarchical chunking strategies and advanced retrieval techniques. This research spike evaluated alternatives and designed an A/B testing framework to validate improvements.

## Decision

**Primary recommendation:** Adopt **multilingual-e5-base** as the next-generation embedding model, contingent on A/B testing validation showing ≥5% nDCG@10 improvement with acceptable resource costs.

### Model Selection Rationale

- **512-token window:** Enables 300-word chunks (3.3× current context)
- **768 dimensions:** Balanced increase (+50% vs. current 512D)
- **MTEB score 61.5:** Proven multilingual retrieval leader
- **CPU-compatible:** No GPU infrastructure required
- **Active maintenance:** Microsoft-backed (intfloat/MSR-affiliated)

### A/B Testing Strategy

**In-repo dual-collection approach:**
- Parallel Solr collections: `books` (baseline) + `books_e5base` (test)
- Two document-indexer instances with different CHUNK_SIZE (90 vs 300)
- Two embeddings-server instances (port 8080 vs 8085)
- 5-phase experiment: setup → index → query → human-eval → cost-analysis
- Timeline: 2-3 weeks (10-15 days effort)

**Success criteria:**
- Relevance: ≥5% nDCG@10 improvement (statistically significant)
- Latency: ≤50ms query latency increase at p95
- Resources: ≤2× index size increase, ≥80% indexing throughput

## Implications for Team

### Ash (Search Engineer)
- **Phase 1:** Solr collection setup, schema design for 768D vectors
- **Phase 3:** Query benchmark execution, latency profiling
- **Phase 5:** Resource cost analysis, HNSW tuning if needed

### Brett (DevOps/Infra)
- **Phase 1:** Docker Compose modifications (two new services)
- **Phase 2:** Monitor cluster health during parallel indexing
- **Phase 5:** Disk/memory usage tracking, capacity planning

### Parker (Backend Engineer)
- **Phase 1:** Document-indexer configuration for 300-word chunks
- **Phase 2:** Batch indexing coordination, error handling
- **Optionally:** solr-search API extension (`?collection=books_e5base` parameter)

### Juanma (PO)
- **Phase 4:** Human relevance judgments (50 queries, 4-6 hours)
- **Decision gate:** Approve production migration or explore alternatives

### Dallas (Frontend Engineer)
- **No immediate work required** — A/B test is backend-only
- **Post-migration:** May highlight larger chunk text in UI (300 words vs 90)

## Alternatives Considered

1. **multilingual-e5-small** (384D) — Lower quality, use if resource constraints tighten
2. **multilingual-e5-large** (1024D) — Best quality, defer until e5-base validation complete
3. **BGE-M3** (8192 tok, 1024D) — Experimental, Chinese-centric training is risk for Latin languages
4. **Separate repo for testing** — Rejected per PO preference for in-repo validation

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| e5-base encoding too slow | Indexing backlog | Optimize batching, consider GPU if needed |
| 768D index too large | Disk exhaustion | Quantize to int8 (Solr 9.4+), prune test collection |
| Query latency unacceptable | Poor UX | Tune HNSW efConstruction, reduce topK |
| Relevance improvement marginal | Wasted effort | Escalate to e5-large or BGE-M3 |

## Next Actions

1. **PO review and approval** — Allocate 2-3 sprints for A/B test
2. **Phase 1 kickoff** — Ash + Brett: infrastructure setup (3-5 days)
3. **Test corpus selection** — 100-200 books, balanced language distribution
4. **Human evaluation scheduling** — Block 4-6 hours for Juanma or delegate

## References

- Research report: `docs/research/embedding-model-research.md`
- MTEB leaderboard: https://huggingface.co/spaces/mteb/leaderboard
- e5-base model card: https://huggingface.co/intfloat/multilingual-e5-base
- Current config: `src/embeddings-server/config/__init__.py` (ADR-004)

---

**Decision Status:** Awaiting PO approval to proceed with A/B testing infrastructure setup.
