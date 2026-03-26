---
name: "phase-gated-execution"
description: "Parallel work coordination through phase-based decomposition and dependency gating"
domain: "project-management, architecture"
confidence: "high"
source: "extracted from v0.9.0 restructure (Research→Implementation→Validation→Merge), v1.3.0 admin consolidation, and Ripley's parallel execution patterns"
author: "Ripley"
created: "2026-03-18"
last_validated: "2026-03-18"
---

## Context

Use this pattern when managing complex features that require multiple team members working in parallel without conflicts. Aithena has used phase-gating successfully to deliver major architectural changes (Solr migration, src/ restructure, admin consolidation) with zero rework.

**Key insight:** Explicit phase dependencies (Research before Implementation, Implementation before Validation) prevent work sprawl and enable safe parallelization within each phase.

---

## Phase Structure

Every major initiative (feature, refactor, restructure) decomposes into **4 sequential phases**. Work within a phase can be parallel; phases execute sequentially.

### Phase 1: Research (1-2 days)
**Purpose:** Identify all edge cases, constraints, and risks upfront.

**Deliverables:**
- Architectural decision document (ADR) with options and rationale
- Implementation plan (line-by-line edits, file changes, dependencies)
- Rollback strategy
- Risk assessment
- Test strategy

**Exit Criteria:**
- Ripley reviews and approves ADR
- All edge cases documented
- No surprises discovered later (if there are, research is incomplete)
- Plan is detailed enough for parallel implementation in Phase 2

**Example: v0.9.0 src/ Restructure (PR #222)**
- Researched 9 services moving to src/
- Documented path strategy (src/ for services, installer/ at root with rationale)
- Identified 50-60 line edits across 10 files
- Created rollback playbook

---

### Phase 2: Implementation (1-2 days)
**Purpose:** Execute the plan in parallel, no design changes mid-phase.

**Rules:**
- Implementation MUST NOT diverge from research plan
- If edge cases are discovered (e.g., missing file, unexpected dependency), halt and escalate to Ripley
- Each implementer owns one component; no overlapping work
- Push branches to origin for visibility; do not merge yet

**Exit Criteria:**
- All implementers report code complete
- Code review passed for each component
- All tests pass locally
- Branch pushed to origin

**Example: v0.9.0 Phase 2**
- Parker: Dockerfile edits (service build args)
- Dallas: docker-compose.yml path updates
- Brett: CI workflow path fixes
- All in parallel, zero conflicts

---

### Phase 3: Validation (1 day)
**Purpose:** Verify the implementation works end-to-end before merging.

**Validations:**
1. **Build validation:** All services compile/build clean (no docker daemon needed; validate YAML, run linters)
2. **Test validation:** All unit tests pass
3. **Integration validation:** Services can communicate (if docker available, run docker compose up)
4. **Rollback validation:** Rollback plan is tested (revert changes, verify cleanup)

**Exit Criteria:**
- All validations passing
- No unknown issues discovered
- Rollback plan confirmed working

**Owner:** Dallas (build/infra focus) or assigned Validation Lead

**Example: v0.9.0 Phase 3**
- Dallas validated docker-compose.yml syntax
- Brett validated CI workflows
- Parker validated service startup logs
- All reported green

---

### Phase 4: Merge (1 hour)
**Purpose:** Land all Phase 2 PRs to dev in quick succession.

**Merge Order:** Follow implementation dependencies (if service B depends on service A, merge A first).

**Process:**
1. Merge PR 1 → dev
2. Merge PR 2 → dev (may conflict; resolve + re-test)
3. Merge PR 3 → dev (repeat)
4. All merged → coordinate celebration, close associated issues

**Anti-Pattern:** Don't merge to dev as PRs complete during Phase 2. Wait until Phase 3 validation is done; this prevents cascading failures if an edge case was missed.

**Example: v0.9.0 Phase 4**
- Merged 4 PRs (#222, #223, #224, #225) in 30 minutes
- Zero conflicts (research phase identified dependencies)
- All issues closed

---

## Ownership & Team Coordination

### Research Phase
- **Owner:** Ripley (architecture lead)
- **Participants:** Subject matter experts (Parker for Solr, Dallas for infra, Brett for CI)
- **Deliverable:** ADR in `.squad/decisions.md` or `.squad/decisions/inbox/`

### Implementation Phase
- **Owners:** Individual implementers (Parker, Dallas, Brett, etc.)
- **Coordinator:** Ripley (watches for blocked/diverging work)
- **Visibility:** Daily standup or status in issue comments

### Validation Phase
- **Owner:** Dallas (build/infra) or explicitly assigned Validation Lead
- **Checklist:** Use `.squad/skills/pr-integration-gate/` for validation steps
- **Report:** Summary of all validations passed in issue comment

### Merge Phase
- **Owner:** Ripley (decides merge order) or Newt (release lead)
- **Conflict resolution:** Assigned implementer (they know the code best)
- **Verification:** Quick smoke test after each merge

---

## Dependency Gating Template

Add this to complex issues to establish phase gates:

```markdown
## Phase Decomposition

### Phase 1: Research (assign Ripley)
- [ ] Architectural decision document (options, rationale, edge cases)
- [ ] Implementation plan (specific file changes)
- [ ] Rollback strategy documented
- [ ] Risk assessment (what could go wrong?)
- [ ] Ripley reviews and approves

### Phase 2: Implementation (assign team members per component)
- Component A: @parker
  - [ ] Code complete
  - [ ] PR opened (target dev, draft until Phase 3)
- Component B: @dallas
  - [ ] Code complete
  - [ ] PR opened
- Validation: Phase 2 not complete until ALL components done + reviewed

### Phase 3: Validation (assign Dallas or Validation Lead)
- [ ] Build validation (docker-compose config, linting)
- [ ] Test validation (all tests pass)
- [ ] Integration validation (if docker available, services communicate)
- [ ] Rollback validation (can revert without residue?)
- [ ] Dallas reports green

### Phase 4: Merge (Ripley coordinates)
- [ ] Merge Component A PR
- [ ] Merge Component B PR
- [ ] All issues closed
- [ ] Celebrate
```

---

## When to Use Phase Gating

### ✅ Use for:
- Major refactors (src/ restructure, Solr migration)
- Multi-component features requiring coordination (auth deployment, API versioning)
- Infrastructure changes (Solr cluster upgrade, Docker base image change)
- Security hardening (error handling audit, baseline exception rollout)

### ❌ Don't use for:
- Single-issue features (search filter improvements, bug fixes)
- Small PRs (dependency bumps, documentation, style fixes)
- Work done by one person (no coordination needed)

---

## Anti-Patterns

### ❌ Merging Phase 2 PRs before Phase 3 validation
This creates cascading failures. Phase 1 research should catch all issues, but merging during Phase 2 before validation breaks the gate.

### ❌ Implementation diverging from research plan
If implementer discovers a different approach is better, they halt and escalate to Ripley. The research phase is authoritative until formally revised.

### ❌ Skipping Validation phase
Tempting when time-pressed, but one missed test failure in Phase 3 cascades into three failed merges in Phase 4.

### ❌ No communication during Phase 2
Daily standup or async status in issue prevents unblocked work from stalling.

---

## Real-World Example: v1.3.0 Admin Consolidation

**Initiative:** Merge Streamlit admin UI into React, deprecate src/admin/

**Phase 1 Research (PR pending):**
- Decision: React admin is feature-complete; Streamlit is redundant
- Plan: Add RabbitMQ metrics to React, deprecate Streamlit service, remove from docker-compose.yml
- Files affected: AdminPage.tsx (add metrics), docker-compose.yml, src/admin/ (mark deprecated)
- Rollback: Revert docker-compose.yml, restore src/admin/ in build

**Phase 2 Implementation (assigned):**
- Copilot: Add RabbitMQ metrics to React AdminPage
- Parker: Verify API endpoint supports metrics or create new endpoint
- Dallas: Update docker-compose.yml (remove admin service)
- Brett: Update CI workflow (remove admin container build)

**Phase 3 Validation (Dallas):**
- [ ] React build succeeds with new metrics component
- [ ] All tests pass (AdminPage + API tests)
- [ ] docker-compose.yml syntax valid
- [ ] CI workflow runs clean without admin build
- [ ] RabbitMQ metrics render (manual smoke test)

**Phase 4 Merge:**
- Merge all 4 PRs to dev
- Close issue #418 (admin consolidation)

---

## Integration with Release Planning

Phase-gating feeds into release milestones:
- **v1.3.0:** Admin consolidation (Phase 1-4 within 3-week milestone)
- **v1.4.0:** Stats improvements (Phase 1-4 within 3-week milestone)

Each milestone may have 1-3 complex initiatives using phase gating; simple features skip the gate.

---

## References

- **PR #222-225:** v0.9.0 src/ restructure (Phase 1-4 reference implementation)
- **Issue #418:** v1.3.0 admin consolidation (upcoming phase-gated initiative)
- **Decisions:** `.squad/decisions.md` (ADRs for all major phases)
