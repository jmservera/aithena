# Decision: Release Strategy Analysis Findings

**Date:** 2026-03-26  
**Author:** Brett (Infrastructure Architect)  
**Context:** #860 research spike  
**Status:** Recommendation (awaiting PO decision)

## Problem

The current release strategy rebuilds all 6 services on every release with unified versioning, despite highly asymmetric change frequency:
- embeddings-server: 9GB image, 1 commit in 4 releases (v1.8.0→v1.11.0) → 3 unnecessary 10-minute rebuilds
- document-lister: 0 commits in 4 releases → rebuilt every time
- aithena-ui + solr-search: 68 commits (78% of all service changes) → always need rebuilds

Current approach wastes ~40-60% of build time on unchanged services.

## Analysis

Evaluated 4 strategies:
1. **Status Quo** — always rebuild all (current, simple but inefficient)
2. **Change-Detection CI** — skip unchanged services, retag images (40% time savings, 1 week effort)
3. **Tiered Releases** — fast/stable/infra tracks (50-70% savings, 2-4 weeks effort)
4. **Independent Versioning** — per-service versions (60-80% savings, high complexity, 2-3 weeks effort)

Full analysis: `docs/research/release-strategy-analysis.md`

## Recommendation

**Phased approach:**

### Short-term (v1.12.0) — Change-Detection CI
- Detect changed services via `git diff $PREV_TAG..$NEW_TAG -- src/{service}`
- Skip builds for unchanged services, retag previous images
- Create embeddings-server base image (pre-bake ML model)
- Add `--skip-unchanged` flag to buildall.sh
- **Effort:** 1 week | **Risk:** Low | **Savings:** 40% build time

### Mid-term (v1.13.0) — Hybrid Versioning
- Independent versioning for stable services (embeddings-server, document-lister, admin)
- Keep unified versioning for active services (aithena-ui, solr-search, document-indexer)
- API contract testing for solr-search ↔ embeddings-server
- **Effort:** 2-3 weeks | **Risk:** Medium | **Savings:** 60% build time

### Long-term (v2.0.0+) — Full Independence
- All 6 services get independent versions
- Service mesh or API gateway for version routing
- Required if scaling to 10+ microservices
- **Effort:** 4-6 weeks | **Risk:** High (requires API versioning strategy)

## Decision Needed

PO to decide which phase(s) to prioritize. Recommend starting with short-term (v1.12.0) for quick wins.

## Team Impact

- **Parker, Dallas** (backend devs) — faster local builds with `--skip-unchanged`, API contract tests in mid-term
- **Quinn** (frontend dev) — unaffected (aithena-ui always rebuilds anyway)
- **Lambert** (QA) — must verify change-detection CI doesn't break releases
- **Brett** (infra) — owns implementation of all phases
- **Ash** (Solr/search) — API contract tests affect solr-search ↔ embeddings-server integration

## Open Questions

1. Should we pin embeddings-server version in v1.12.0 or wait for v1.13.0?
2. Do we need a staging environment to validate change-detection CI before prod?
3. Should API contract tests block releases or just warn?
