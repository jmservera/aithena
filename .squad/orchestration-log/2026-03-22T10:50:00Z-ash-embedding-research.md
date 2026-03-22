# Orchestration Log — Ash (Search Engineer)

**Timestamp:** 2026-03-22T10:50:00Z  
**Task:** Research embedding models for issue #861  
**Mode:** background  
**Outcome:** PR #863 merged

## Summary

Ash completed research spike on embedding model evaluation and A/B testing strategy. Deliverable: 717-line research report recommending adoption of multilingual-e5-base (512-token window, 768D, MTEB 61.5 score) contingent on A/B testing validation showing ≥5% nDCG@10 improvement.

## Report Contents

- **Model selection rationale:** 512-token context (vs. 128 current), 768D vectors, CPU-compatible, Microsoft-backed
- **A/B testing strategy:** In-repo dual-collection approach with 5 phases and 2-3 week timeline
- **Success criteria:** ≥5% nDCG@10 improvement, ≤50ms query latency increase, ≤2× index size growth
- **Team implications:** Detailed workload breakdown for Ash, Brett, Parker, Juanma (PO), Dallas
- **Risks & mitigations:** Encoding performance, index size, query latency, marginal relevance gains

## Decision Artifact

Full decision written to `.squad/decisions.md` with team impact matrix and next actions awaiting PO approval.

**PR:** #863  
**Status:** Merged to dev
