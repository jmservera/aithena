# Decision: v1.18.0 PRD Batch Decomposition & Milestone Assignment

**Author:** Ripley (Project Lead)  
**Date:** 2026-03-26  
**Status:** DECIDED  
**Requested by:** Juanma (jmservera)

## Context

Four Product Requirements Documents (PRDs) were submitted for decomposition into concrete work items:
1. `docs/prd/cicd-workflow-review.md` — CI/CD consolidation and release pipeline hardening
2. `docs/prd/stress-testing.md` — Stress testing suite and minimum requirements documentation
3. `docs/prd/folder-path-facet.md` — Folder path facet for search and batch operations
4. `docs/prd/bcdr-plan.md` — Backup, restore, and disaster recovery procedures

The milestones referenced in these PRDs (v1.9.0, v1.10.0, v1.11.0) are outdated. v1.16.0 was just released, v1.17.0 is active with 15 GPU acceleration issues, and v2.0 has admin migration work.

## Decision

All 25 work items (8 from CI/CD, 6 from stress testing, 4 from folder facet, 7 from BCDR) are assigned to **v1.18.0**, a new infrastructure-focused milestone.

### Milestone Rationale

- **v1.17.0** (GPU acceleration) already has 15 issues assigned. Adding 25 more infrastructure items would create a 40-issue milestone with split technical focus.
- **v1.18.0** provides a dedicated lane for infrastructure, tooling, and performance work without competing with GPU acceleration.
- **Scope:** v1.18.0 is explicitly non-feature — all work is operational, testing, or search-infrastructure focused.

### Per-PRD Assignments

**CI/CD Workflow Review (8 issues: #1188–#1195)**
- Owner: Brett (Infrastructure)
- Type: Tooling consolidation (workflow deduplication, security hardening, reliability)
- Effort: ~2 weeks
- Status: Ready to assign; no dependencies

**Stress Testing Suite (6 issues: #1196–#1201)**
- Owner: Parker (Backend), with Ash/Dallas/Lambert support
- Type: Performance infrastructure (data generation, benchmarking, results analysis)
- Effort: ~5 weeks (phased)
- Critical path: Phase 1 (infrastructure) blocks Phases 2–6
- Status: Ready to assign; Phase 1 is blocker

**Folder Path Facet (4 issues: #1202–#1205)**
- Owner: Ash (Search) lead; Dallas (Frontend) support
- Type: Search feature (faceting, UI, filtering, testing)
- Effort: ~2 weeks
- Depends on: Nothing (field already indexed)
- Status: Ready to assign; can start immediately in parallel with other work

**BCDR Plan (7 issues: #1206–#1212)**
- Owner: Brett (Infrastructure)
- Type: Operational resilience (backup scripts, restore procedures, admin UI, runbook)
- Effort: ~3 weeks (sequential: scripts → restore → UI → docs)
- Status: Ready to assign; script implementation is critical path

## Key Technical Decisions

### 1. Bandit as Hard Blocker

**Decision:** `security-bandit.yml` will enforce Bandit SAST findings as a **required** status check for dev and main PRs (currently non-blocking with `continue-on-error: true`).

**Rationale:**
- Current state allows critical vulnerabilities to be merged without detection.
- User has indicated commitment to security-first releases.
- Bandit is fast (~30s) and rarely produces false positives on this codebase.
- Aligns with pre-PR self-review checklist best practices.

**Scope:** Issue #1189 is the implementation.

### 2. Phase-Gated Stress Testing

**Decision:** Stress testing is strictly phase-gated: Phase 1 (infrastructure setup) must complete before Phase 2–6 benchmarks can run.

**Rationale:**
- Phase 1 builds shared test fixtures, data generators, Docker stats collectors, and Locust framework.
- All subsequent phases depend on these foundations.
- No parallel execution between phases; phases are sequential gates.

**Scope:** Issues #1196–#1201 follow the 6-phase plan in the PRD.

### 3. BCDR Tiers with RPO/RTO Targets

**Decision:** Three-tier backup system with clear SLOs:
- **Critical** (auth DB, collections DB, secrets): RPO < 1 hour, RTO < 5 min, every 30 min
- **High** (Solr + ZooKeeper): RPO < 24 hours, RTO 15–60 min, daily 2 AM
- **Medium** (Redis + RabbitMQ): RPO < 4 hours, RTO 5–15 min, daily 3 AM

**Rationale:**
- Critical data (auth, secrets) is irreplaceable and must have shortest RPO/RTO.
- High-value data (Solr index) is rebuildable but takes hours, so daily snapshots acceptable.
- Medium data (cache/queue state) rebuilds automatically on restart.
- Tiered approach keeps backup costs reasonable while protecting against realistic failure scenarios.

**Scope:** Issues #1206–#1212 implement the tiers sequentially (backup scripts → restore → admin UI → runbook).

### 4. Folder Facet as Zero-Schema Work

**Decision:** Folder path facet requires **zero schema changes** — the `folder_path_s` field is already indexed and stored.

**Rationale:**
- Backend work is trivial (3-line addition to `FACET_FIELDS`).
- Frontend work is medium (hierarchical tree component).
- Testing is straightforward (existing test framework).
- No risk of Solr reindexing or downtime.

**Scope:** Issues #1202–#1205 can be completed independently without coordination with Ash's Solr work.

## Risk Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Stress testing outputs clutter git repo | Medium | `tests/stress/results/` added to `.gitignore`; results never committed |
| BCDR scripts have bugs, restore fails in production | High | All scripts support `--dry-run` flag; monthly automated restore drills validate |
| CI/CD consolidation breaks existing workflows | Medium | Refactoring is non-breaking (consolidate, don't remove); test on sample PR first |
| Folder facet with thousands of paths → slow facet computation | Low | Use `facet.limit` to cap results (100 default); document path-prefix optimization for Phase 2 |
| Bandit false positives block legitimate PRs | Low | Codebase has no common Bandit triggers; review first batch of findings with security lead |

## Alternatives Considered

1. **Split across v1.17.0 and v1.18.0:** Rejected — v1.17.0 is GPU-focused; adding infrastructure work creates context switching.
2. **Defer to v1.19.0:** Rejected — these are operational necessities (BCDR, CI/CD) and performance enablers (stress testing); delaying increases risk.
3. **Create v1.18.0 as "everything leftover":** Rejected — explicit scope (infrastructure + tooling + search features) keeps milestone coherent.

## Acceptance Criteria

- [ ] All 25 issues assigned to v1.18.0 milestone
- [ ] Each issue has clear acceptance criteria and PRD reference
- [ ] Team routing is clear (Brett: CI/CD + BCDR, Ash: folder facet backend, Dallas: folder facet UI, Parker: stress testing)
- [ ] Phase dependencies are documented (stress testing Phase 1 blocks 2–6; BCDR scripts block restore)
- [ ] User review confirms scope and priorities before squad assignment

## Next Steps

1. Juanma reviews this decision and the 25 issues.
2. Ripley hands off to squad member assignment (Brett, Ash, Dallas, Parker, Lambert per PRD recommendations).
3. Brett (CI/CD lead) confirms no conflicts with active v1.17.0 GPU work.
4. Parker confirms stress testing Phase 1 infrastructure is a critical path blocker before Phase 2.

---
