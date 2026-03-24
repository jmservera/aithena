# Session Log — 2026-03-24T14:25 v1.14.1 Release & Analysis

**Session:** v1.14.1 release completion + architecture analysis + issue triage  
**Duration:** Analysis + PR completion  
**Status:** COMPLETE

## Summary

Completed v1.14.1 release preparation with three architectural analyses and two PR implementations:

1. **Architecture Analyses (3 decisions captured)**
   - Embeddings-server extraction strategy (Ripley)
   - Docker layer optimization (Brett)
   - Internal service authentication assessment (Kane)

2. **PR Implementations (2 completed)**
   - HF_TOKEN workflow integration (Parker)
   - Log analyzer deduplication (Brett)

## Key Decisions

### Embeddings-Server Extraction
Extract `src/embeddings-server/` to independent repository to enable faster model iteration, genericization as reusable service, and 2–3 minute faster releases.

### Docker Build Optimization
Implement 4-stage Dockerfile (model → deps → app → runtime) to cache models independently; 80% faster incremental builds.

### Internal Service Auth
Simplify auth for non-exposed services (Redis, ZK, Solr); drop Redis/ZK, keep thin Solr layer; fixes ZK 3.9 startup bug.

## Orchestration Log
Detailed team roster and deliverables: `.squad/orchestration-log/2026-03-24T1425-analysis-batch.md`

---

**Next Phase:** Merge decisions, update agent histories, commit squad state.
