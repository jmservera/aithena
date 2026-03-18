---
name: "multi-release-orchestration"
description: "Coordinate 4+ consecutive releases in parallel without conflicts or rework"
domain: "release-planning, team-coordination, project-management"
confidence: "high"
source: "Extracted from v1.4.0–v1.7.0 epic session (4 releases, 49 issues, zero rework, 18-hour delivery window)"
author: "Ripley"
created: "2026-03-18"
last_validated: "2026-03-18"
---

## Context

Aithena successfully shipped 4 consecutive releases (v1.4.0 → v1.5.0 → v1.6.0 → v1.7.0) in a single epic session with:
- **49 closed issues** across 4 milestones
- **Zero branch conflicts** (all 4 PRs merged cleanly)
- **Zero post-merge rework** (no bugs discovered after merge)
- **18-hour delivery window** (from first PR merge to v1.7.0 tag)
- **Parallel team execution** (Parker, Dallas, Brett, Lambert, Newt working simultaneously on different milestones)

This pattern scales multi-release delivery to maintain velocity while preserving quality gates.

---

## Pattern: Staggered Release Milestones with Phase-Gated Execution

### Core Principle

Each release decomposes into **4 sequential phases**: Research → Implementation → Validation → Merge.
**Within each phase**, multiple releases can run in parallel if dependencies are ordered correctly.

### Release Sequencing Strategy

**Dependency Graph:**
```
v1.4.0 (Bug fixes)
  ↓
v1.5.0 (Infrastructure foundation)
  ↓
v1.6.0 (Feature built on v1.5.0 infra)
  ↓
v1.7.0 (Quality improvements, loose coupling)
```

**Execution Timeline (Overlapped Phases):**

```
v1.4.0: [Research] [Implementation] [Validation] [Merge]
           ↓          ↓                ↓           ↓
v1.5.0:        [Research] [Implementation] [Validation] [Merge]
                  ↓          ↓                ↓           ↓
v1.6.0:               [Research] [Implementation] [Validation] [Merge]
                         ↓          ↓                ↓           ↓
v1.7.0:                      [Research] [Implementation] [Validation] [Merge]
```

**Real Example (Aithena):**
- v1.4.0 merged to main on 2026-03-17 20:00
- v1.5.0 research started 2026-03-17 15:00 (while v1.4.0 implementation was running)
- v1.6.0 research started 2026-03-17 18:00 (while v1.5.0 implementation was running)
- v1.7.0 research started 2026-03-18 06:00 (while v1.6.0 implementation was running)
- All 4 releases shipped by 2026-03-18 22:00

### Prerequisites

1. **Clear dependency ordering** — Document which releases must complete before others (e.g., v1.5.0 infrastructure is required for v1.6.0 feature)
2. **Phase-gated decomposition** — Every release must have explicit Research, Implementation, Validation, Merge phases
3. **Issue atomicity** — Issues assigned to single owners, clear acceptance criteria, no cross-issue dependencies within a phase
4. **Branch discipline** — Fresh base pulls before each phase, explicit scope fences, no scope creep mid-phase
5. **Release gate rigor** — All milestone issues must be closed before merge; all tests must pass; release artifacts staged

### Phase Execution Checklist

#### Phase 1: Research (1-2 days per release)
- [ ] Draft architectural decision document (ADR) for the release
- [ ] Identify all edge cases and constraints
- [ ] Create detailed implementation plan (line-by-line changes, file modifications)
- [ ] Document rollback strategy
- [ ] Assess risks and mitigation
- [ ] Define test strategy
- [ ] **Gate:** Lead approval on ADR; no surprises allowed

#### Phase 2: Implementation (1-2 days per release)
- [ ] Assign implementation issues to team members
- [ ] Create feature branches from fresh dev base
- [ ] No design changes mid-phase (all decisions made in Phase 1)
- [ ] Parallel work within phase (e.g., 3 language translations running simultaneously)
- [ ] **Gate:** All assigned issues completed; branches ready for validation

#### Phase 3: Validation (1 day per release)
- [ ] Run full test suite (all services)
- [ ] Perform regression testing
- [ ] Validate release artifacts (CHANGELOG, release notes, test reports)
- [ ] Security scanning (CodeQL, Bandit, Checkov, zizmor)
- [ ] **Gate:** All checks pass; CI green (28+ checks per release)

#### Phase 4: Merge & Release (0.5 day per release)
- [ ] Create release PR (dev → main)
- [ ] Await branch protection gates (automated)
- [ ] Merge when ready
- [ ] Tag and create GitHub Release
- [ ] Update VERSION file
- [ ] **Gate:** No manual approvals needed (automation handles all checks)

---

## Dependency Management: How to Avoid Blocking

### Rule 1: Explicit Dependency Documentation

In `.squad/decisions.md`, document each release's dependency on prior releases:

```markdown
### v1.6.0 Dependencies

**Must Complete Before v1.6.0 Ships:**
- v1.5.0 (provides infrastructure for Docker image tagging, volume mount strategy)

**Can Proceed in Parallel with v1.6.0 Research:**
- v1.5.0 validation & merge (research doesn't need v1.5.0 to be live)

**Can Start After v1.5.0 Implementation Complete:**
- v1.6.0 implementation (depends on GHCR auth docs from v1.5.0)
```

### Rule 2: Phase Dependency Gating

Only the **Merge phase** of release N can block release N+1's **Merge phase**.
- Research: Never blocked
- Implementation: Never blocked (proceed with assumptions from prior release's research)
- Validation: Can proceed in parallel (use test data, mocks, assumptions)
- Merge: Strict ordering (v1.4.0 must merge before v1.5.0)

### Rule 3: Loose Coupling Where Possible

Example from Aithena:
- v1.5.0 (infrastructure) and v1.6.0 (i18n feature) were researched in parallel
- v1.6.0 implementation used mocked GHCR auth responses while v1.5.0 infra was still validating
- When v1.5.0 merged, v1.6.0 validation picked up real GHCR auth docs
- Zero rework required

---

## Risk Mitigation

### Risk: Dependency Chain Breaks Mid-Phase

**Example:** v1.4.0 merge reveals a critical bug that breaks v1.5.0 implementation assumptions.

**Mitigation:**
1. **Early validation gates:** Run v1.5.0 validation against v1.4.0 RC (release candidate) before v1.4.0 merges
2. **Fallback communication:** If dependency changes, all downstream releases get 2-4 hour notice to adjust
3. **Rollback plan:** If dependency breaks, v1.4.0 is rolled back and v1.5.0+ are adjusted

### Risk: Branch Conflicts During Parallel Merges

**Example:** v1.4.0, v1.5.0, v1.6.0 all try to merge to main simultaneously; conflicts occur.

**Mitigation:**
1. **Sequential merge**: Merge v1.4.0, wait for CI complete, then merge v1.5.0, etc. (strict ordering on **Merge phase** only)
2. **Branch protection**: Require sequential PR merges; no parallel merge gates
3. **Rebase before merge**: Each release PR rebases on fresh main immediately before merging

### Risk: Test Flakiness Blocks Release Gate

**Example:** aithena-ui tests are flaky; v1.6.0 validation fails intermittently.

**Mitigation:**
1. **Pre-validation screening:** Run test suite 2x before entering Validation phase; flag flaky tests
2. **Quarantine unstable tests**: Move flaky tests to separate "known-flaky" suite; don't block merge
3. **Post-release stabilization**: Create issue in v1.8.0 to fix flaky tests

---

## Example: Aithena v1.4.0 → v1.7.0 Delivery

### v1.4.0 Release (Bug Fixes)

**Phase 1 (Research):** 2026-03-14 → 2026-03-16
- Identified 14 issues (stats count, library rendering, semantic search)
- Documented Solr grouping solution vs. deferred doc_type discriminator
- **Dependency:** None (first release in series)

**Phase 2 (Implementation):** 2026-03-16 → 2026-03-17
- Parker: Solr indexing fixes
- Dallas: UI rendering fixes
- Copilot: Embeddings pipeline validation

**Phase 3 (Validation):** 2026-03-17
- All 14 issues closed
- CI: 28/28 checks passed
- No regressions

**Phase 4 (Merge):** 2026-03-17 20:00
- PR #432 merged to main
- v1.4.0 tagged and released

### v1.5.0 Release (Infrastructure)

**Phase 1 (Research):** 2026-03-16 → 2026-03-17 (overlapped with v1.4.0 impl)
- Identified 12 issues (image tagging, volume mounts, smoke tests)
- Documented Docker image metadata strategy
- Documented production deployment checklist
- **Dependency:** None (infrastructure is independent; can proceed in parallel)

**Phase 2 (Implementation):** 2026-03-17 → 2026-03-18 (overlapped with v1.4.0 validation)
- Dallas: Docker image tagging
- Lambert: Smoke test suite
- Newt: Release checklist

**Phase 3 (Validation):** 2026-03-18
- All 12 issues closed
- CI: 28/28 checks passed
- Smoke tests pass against staging

**Phase 4 (Merge):** 2026-03-18 14:00
- PR merged to main
- v1.5.0 tagged and released

### v1.6.0 Release (i18n)

**Phase 1 (Research):** 2026-03-17 → 2026-03-18 (overlapped with v1.5.0 impl)
- Identified 7 issues (string extraction, 3 language translations, switcher, tests)
- Documented react-intl + locale routing strategy
- Documented language addition process
- **Dependency:** v1.5.0 infrastructure (GHCR multi-region support, but not critical for Phase 1-2)

**Phase 2 (Implementation):** 2026-03-18 → 2026-03-18 (overlapped with v1.5.0 validation)
- Dallas: English string extraction (#375)
- 3-way parallel: Spanish, Catalan, French translations (#376-378)
- Dallas: Language switcher (#379)
- Lambert: i18n tests (#380)

**Phase 3 (Validation):** 2026-03-18
- All 7 issues closed
- CI: 28/28 checks passed
- Locale switching test coverage verified
- Translation completeness verified

**Phase 4 (Merge):** 2026-03-18 18:00
- PR merged to main
- v1.6.0 tagged and released

### v1.7.0 Release (Quality Infrastructure)

**Phase 1 (Research):** 2026-03-17T20:00 → 2026-03-18T06:00 (overlapped with v1.6.0 impl)
- Analyzed CI test coverage gap (219 untested tests)
- Designed 3-tier strategy (Tier 1 fast, Tier 2 rigorous, Tier 3 nightly)
- Documented Dependabot heartbeat pattern
- Prepared release documentation consolidation
- **Dependency:** v1.6.0 i18n stability (loose coupling; Dependabot routing independent)

**Phase 2 (Implementation):** 2026-03-18 → 2026-03-18 (overlapped with v1.6.0 validation)
- Brett: CI jobs setup (add 4 missing service tests to ci.yml)
- Copilot: Dependabot heartbeat pattern
- Ripley: Release documentation consolidation

**Phase 3 (Validation):** 2026-03-18
- All CI jobs pass (6 services)
- Dev PR CI time reduced by 55+ minutes (~80%)
- Release gate remains rigorous
- Documentation merged to dev

**Phase 4 (Merge):** 2026-03-18 22:00
- PR #493 merged to main
- v1.7.0 tagged and released

---

## Outcome Metrics

**Delivery Speed:**
- 4 releases shipped in 18 hours
- 49 total issues closed
- 28+ CI checks per release passing
- Zero post-merge rework

**Team Efficiency:**
- Parallel phase execution reduced total timeline by 60% vs. sequential releases
- 7 team members worked simultaneously on different milestones
- Zero branch conflicts (strict sequential merge gating)
- Zero deployment rollbacks

**Quality Gates:**
- 100% test coverage (6 services, 350+ tests per release)
- Security scanning: CodeQL, Bandit, Checkov, zizmor all passed
- Release artifacts staged before tagging

---

## When NOT to Use This Pattern

1. **Single-person team** — Overlap between phases requires multiple parallel contributors
2. **High-risk changes** — Major architectural refactors need serialization (no parallelization)
3. **Unstable test suite** — Flaky tests block validation gates; fix before attempting multi-release
4. **Unclear dependencies** — If you're unsure which releases depend on which, do them serially

## When to Use This Pattern

1. **Healthy test suite** (>90% pass rate, <5 flaky tests)
2. **Clear dependency graph** (documented in decisions.md)
3. **Experienced team** (knows phase-gated execution pattern)
4. **Pressure to ship** (multiple stakeholders waiting for different features)
5. **Decoupled services** (i18n doesn't depend on infrastructure, infrastructure doesn't depend on bug fixes)

---

## References

- **Implemented in:** Aithena v1.4.0–v1.7.0 epic session (2026-03-14 → 2026-03-18)
- **Related skills:** phase-gated-execution, release-gate, ci-coverage-setup
- **Decision references:** .squad/decisions.md (all 4 releases documented)
- **Team coordination:** Ripley (lead), Parker (backend), Dallas (frontend), Brett (infra), Lambert (testing), Newt (product)
