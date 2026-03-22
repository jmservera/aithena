# Orchestration Log — Brett (Infrastructure Architect)

**Timestamp:** 2026-03-22T10:50:00Z  
**Task:** Analyze release strategy for issue #860  
**Mode:** background  
**Outcome:** PR #862 merged

## Summary

Brett completed infrastructure analysis of current release strategy and delivered phased roadmap for optimization. Current approach rebuilds all 6 services on every release despite asymmetric change frequency (embeddings-server: 9GB, 1 commit in 4 releases; document-lister: 0 commits in 4 releases). Analysis quantifies 40-60% wasted build time.

## Analysis Results

Evaluated 4 strategies:
1. **Status Quo** — current (simple, inefficient)
2. **Change-Detection CI** — skip unchanged services, retag (40% savings, 1 week)
3. **Tiered Releases** — fast/stable/infra tracks (50-70% savings, 2-4 weeks)
4. **Independent Versioning** — per-service versions (60-80% savings, high complexity)

## Phased Recommendation

### Short-term (v1.12.0) — Change-Detection CI
- Detect changed services via `git diff $PREV_TAG..$NEW_TAG -- src/{service}`
- Skip builds for unchanged services, retag previous images
- Effort: 1 week | Risk: Low | Savings: 40%

### Mid-term (v1.13.0) — Hybrid Versioning
- Independent versioning for stable services
- Keep unified versioning for active services
- Effort: 2-3 weeks | Risk: Medium | Savings: 60%

### Long-term (v2.0.0+) — Full Independence
- All 6 services independent versions
- Service mesh/API gateway routing
- Effort: 4-6 weeks | Risk: High

## Decision Artifact

Full strategy analysis with team impact breakdown written to `.squad/decisions.md`. Awaiting PO decision on phase prioritization.

**PR:** #862  
**Status:** Merged to dev
