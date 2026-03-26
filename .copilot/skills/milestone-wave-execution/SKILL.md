---
name: "milestone-wave-execution"
description: "Managing large milestones (20+ issues) via wave-based decomposition with retrospectives"
domain: "project-management, leadership"
confidence: "high"
source: "earned from v1.10.0 (48 issues, 4 waves, C+ → B+ improvement trajectory)"
author: "Ripley"
created: "2026-03-20"
last_validated: "2026-03-20"
---

## Context

Use wave-based execution for milestones with 15+ issues. Smaller milestones can use simple phase-gating (see `phase-gated-execution` skill). Waves add scope control, retrospectives, and agent load balancing on top of phase-gating.

---

## Patterns

### 1. Wave Structure

| Wave | Focus | Duration | Gate |
|------|-------|----------|------|
| 0 | Bug fixes (P0 first) | 1–3 days | All bugs closed |
| 1 | Foundations (schemas, APIs, infra) | 1–2 weeks | Core APIs functional |
| 2 | Building blocks (UI, secondary APIs) | 1–2 weeks | Features demo-ready |
| 3 | Integration (orchestrators, E2E flows) | 1 week | Full flow working |
| 4 | Polish (E2E tests, docs, admin) | 1 week | Release gate passes |

**Rule:** No wave starts until the previous wave's gate passes. Retrospective between waves is mandatory for milestones over 15 issues.

### 2. Kickoff Ceremony

Before Wave 0 starts, run a kickoff that produces:
1. **Priority ordering** — P0 bugs first, then by user value
2. **Wave assignments** — Every issue assigned to exactly one wave
3. **Critical path** — Longest sequential dependency chain identified
4. **Agent load balancing** — No agent has >30% of total issues
5. **Deferrals** — Budget ~10% of issues for deferral to a patch release
6. **Research flags** — Issues needing investigation before implementation

### 3. Agent Load Balancing

**When one agent has 20+ issues, act immediately:**
- Identify which issues can be delegated to other agents
- Infra work → Brett. Schema work → Ash. CI/CD → Copilot.
- Sequence the bottleneck agent's remaining work by user value
- Document delegation in kickoff decision

### 4. Deferral Budget

For milestones with 30+ issues, pre-identify ~10% for deferral:
- Defer "hardening" items (automated drills, checksums, stress tests)
- Keep "core functionality" items
- Create a patch milestone (e.g., v1.10.1) for deferred items
- Announce deferrals in kickoff — no surprises mid-milestone

### 5. Critical Path Tracking

Identify the longest dependency chain and monitor it daily:
- Example: BCDR in v1.10.0 had 8 sequential steps — any delay cascades
- Assign critical path work to agents with lowest parallel load
- If critical path slips, escalate immediately — don't wait for retro

### 6. Cross-Service Coordination

When multiple features touch the same infrastructure:
- Assign one coordinator (e.g., Ash for Solr schema)
- All schema changes go through the coordinator to prevent conflicts
- Coordinator reviews PRs in their domain regardless of who wrote them

---

## Examples

**v1.10.0 Kickoff Summary:**
- 48 issues → 4 deferred → 44 active across 4 waves
- BCDR critical path: 8 sequential steps
- Parker bottleneck: 20+ issues → delegated to Brett (BCDR), Ash (schema), Copilot (CI/CD)
- 5 research flags identified before implementation
- Wave 0 grade: C+ → Wave 1 grade: B+ (improvement after retrospective)

---

## Anti-Patterns

- **Skipping Wave 0.** Starting features with known bugs creates compounding debt. Bugs first, always.
- **No retrospective between waves.** Without pause-and-reflect, Wave 0 mistakes repeat in Wave 1.
- **Optimistic scope.** A 48-issue milestone without deferrals will slip. Build in the 10% buffer.
- **Ignoring the bottleneck.** One overloaded agent delays the entire milestone. Delegate proactively.
- **Ad-hoc wave assignments.** If an issue isn't assigned to a wave at kickoff, it drifts and blocks other work.
