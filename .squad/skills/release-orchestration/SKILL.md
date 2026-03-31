---
name: "release-orchestration"
description: "Release tagging, multi-release coordination, milestone wave execution, and phase-gated delivery"
domain: "release-management, project-management"
confidence: "high"
source: "consolidated from release-tagging-process, multi-release-orchestration, milestone-wave-execution, phase-gated-execution"
author: "Ripley"
created: "2026-07-25"
last_validated: "2026-07-25"
---

## Context

Apply when planning releases, coordinating multi-release delivery, managing large milestones, or executing complex features that require phase-gated team coordination. Proven across v1.4.0–v1.7.0 (4 releases, 49 issues, zero rework, 18-hour delivery).

## Pattern 1: Docs-Gate-The-Tag

**Core principle:** Release docs must be merged to `dev` BEFORE creating the version tag.

### Release Sequence
1. Close all milestone issues
2. Trigger `release-docs` workflow (generates release notes + test report)
3. Review and merge docs PR to `dev`
4. **Then** tag: `git tag -a vX.Y.Z -m "Release vX.Y.Z"`
5. Push tag → triggers `release.yml` (Docker images, GHCR, GitHub Release)
6. Verify: GitHub Release created, Docker images tagged, `/version` endpoints correct

### Release-Docs Workflow
- Manual `workflow_dispatch` with version/milestone inputs
- Generates release notes (categorized by features/fixes/infra)
- Generates test report (actual counts from test runs)
- Creates PR to `dev` with all docs

## Pattern 2: Phase-Gated Execution

Every major initiative decomposes into **4 sequential phases**. Work within a phase can be parallel.

### Phase 1: Research (1–2 days)
- ADR with options and rationale
- Implementation plan (specific file changes)
- Rollback strategy, risk assessment, test strategy
- **Exit:** Ripley approves ADR; no surprises later

### Phase 2: Implementation (1–2 days)
- Execute plan — no design changes mid-phase
- Each implementer owns one component; no overlapping work
- Discovered edge cases → halt and escalate to Ripley
- **Exit:** All code complete, reviewed, tests pass locally

### Phase 3: Validation (1 day)
- Build validation (YAML, linters)
- Test validation (all unit tests pass)
- Integration validation (services communicate)
- Rollback validation (revert confirmed working)
- **Exit:** All validations green

### Phase 4: Merge (1 hour)
- Merge PRs in dependency order
- Quick smoke test after each merge
- Close associated issues

### When to use phase-gating
✅ Major refactors, multi-component features, infrastructure changes, security hardening
❌ Single-issue features, small PRs, one-person work

## Pattern 3: Multi-Release Orchestration

### Staggered Release Phases
Releases overlap at the phase level:
```
v1.4.0: [Research] [Impl] [Validation] [Merge]
v1.5.0:      [Research] [Impl] [Validation] [Merge]
v1.6.0:           [Research] [Impl] [Validation] [Merge]
```

### Dependency Rules
- **Research:** Never blocked (can proceed with assumptions)
- **Implementation:** Never blocked
- **Validation:** Can proceed in parallel (use mocks/assumptions)
- **Merge:** Strict ordering (vN must merge before vN+1)

### Prerequisites
1. Clear dependency ordering documented in decisions.md
2. Issue atomicity — single owners, clear acceptance criteria
3. Branch discipline — fresh base pulls, no scope creep
4. Release gate rigor — all issues closed, all tests pass

## Pattern 4: Wave-Based Milestone Execution

For milestones with **15+ issues**, decompose into waves:

| Wave | Focus | Gate |
|------|-------|------|
| 0 | Bug fixes (P0 first) | All bugs closed |
| 1 | Foundations (schemas, APIs, infra) | Core APIs functional |
| 2 | Building blocks (UI, secondary APIs) | Features demo-ready |
| 3 | Integration (orchestrators, E2E flows) | Full flow working |
| 4 | Polish (E2E tests, docs, admin) | Release gate passes |

### Kickoff Ceremony
1. **Priority ordering** — P0 bugs first, then by user value
2. **Wave assignments** — every issue assigned to one wave
3. **Critical path** — longest dependency chain identified
4. **Agent load balancing** — no agent has >30% of total issues
5. **Deferral budget** — ~10% of issues for patch release
6. **Retrospective** between waves is mandatory (15+ issues)

### Agent Load Balancing
When one agent has 20+ issues: delegate infra to Brett, schema to Ash, CI/CD to Copilot. Document in kickoff.

## Anti-Patterns

- ❌ **Tag-first, docs-later** — tag without docs means release history is incomplete
- ❌ **Merging Phase 2 PRs before Phase 3 validation** — creates cascading failures
- ❌ **Implementation diverging from research plan** — halt and escalate, don't wing it
- ❌ **Skipping Validation phase** — one missed failure cascades into multiple failed merges
- ❌ **Skipping Wave 0** — starting features with known bugs creates compounding debt
- ❌ **No retrospective between waves** — Wave 0 mistakes repeat in Wave 1
- ❌ **Optimistic scope** — 48 issues without deferrals will slip; build 10% buffer
- ❌ **Ad-hoc wave assignments** — unassigned issues drift and block other work
- ❌ **Stale test counts** — generate reports from actual runs, not hardcoded numbers

## Dependency Gating Template

```markdown
### Phase 1: Research (assign Ripley)
- [ ] ADR (options, rationale, edge cases)
- [ ] Implementation plan (specific files)
- [ ] Rollback strategy
- [ ] Ripley approves

### Phase 2: Implementation (assign per component)
- Component A: @parker — [ ] Code complete — [ ] PR opened
- Component B: @dallas — [ ] Code complete — [ ] PR opened

### Phase 3: Validation (assign Dallas)
- [ ] Build validation
- [ ] Test validation
- [ ] Integration validation
- [ ] Rollback validation

### Phase 4: Merge (Ripley coordinates)
- [ ] Merge in dependency order
- [ ] All issues closed
```

## References

- `.github/workflows/release-docs.yml`, `.github/workflows/release.yml`
- `.github/ISSUE_TEMPLATE/release.md`
- Issue #363 (release packaging), PR #427 (implementation)
- v1.4.0–v1.7.0 epic session (reference implementation)
- `.squad/decisions.md` (ADRs for all major phases)
