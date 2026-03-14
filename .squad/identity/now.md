---
updated_at: 2026-03-13T23:00:00Z
focus_area: Phase 1 complete — Phase 2/3 parallel dev — 8 PRs in conflict resolution queue
active_issues:
  - pr-conflicts: "#55, #59 (merge conflicts)"
  - service-mismatch: "#56, #58 (wrong target)"
  - backlog: "#81-#100 (UV/security/linting)"
---

# What We're Focused On

**Phase 1 (Core Solr Indexing):** COMPLETE  
Solr schema live, indexer rewritten for Tika extraction, metadata extraction from filesystem paths active.

**Phase 2 & 3:** IN PROGRESS  
FastAPI search service and React UI in development. Embeddings model evaluation ready to start.

**Immediate Blockers:** 8 PRs waiting on @copilot  
- 2 PRs with merge conflicts (#55, #59) — need resolution
- 2 PRs with wrong service targets (#56, #58) — need rerouting
- 4 more PRs expected to merge after conflicts resolved

**Next Phase:** Phase 3 (embeddings/hybrid search) — 22 issues created (#81-#100) for follow-up quality work (UV security, linting, type checking).
