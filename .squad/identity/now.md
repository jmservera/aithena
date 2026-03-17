---
updated_at: 2026-03-17T11:30:00Z
focus_area: v1.4.0 milestone — Backend dependencies & tooling. Final merge round (6-7) complete. 9/14 issues closed. 4 PRs awaiting CI.
active_issues:
  - v140-pr-411: "Workflow enhancement — awaiting CI"
  - v140-pr-416: "Stats count fix (Parker, rebased) — awaiting CI"
  - v140-pr-418: "Python deps + Ruff (Parker) — awaiting CI"
  - v140-pr-419: "Clean Dependabot workflow (replaces #412) — awaiting CI"
  - remaining-issues: "5 more v1.4.0 issues TBD (est. closure after CI passes)"
---

# What We're Focused On

**✅ RELEASED milestones:**
- v1.0.1: ✅ 8/8 closed — security patch — **RELEASED**
- v1.1.0: ✅ 7/7 closed — release workflow & CI/CD — **RELEASED**
- v1.2.0: ✅ 14/14 closed — frontend quality & performance — **RELEASED**

**✅ RELEASED v1.3.0 (Backend Observability & Hardening):** 8/8 closed
- PR #393 (correlation IDs) — merged
- #343 (integration tests) — merged
- Full release documentation created
- Tags and GitHub releases published

**🔄 ACTIVE v1.4.0 (Backend Dependencies & Tooling):** 9/14 closed (64%)

### Merged PRs (7)
- #408: Dependabot automation
- #409: CI workflow improvements
- #410: Build optimization
- #413: Code quality (Ripley)
- #414: Security hardening (Ripley)
- #415: ESLint v9 + React 19 (Dallas)
- #417: Node 22 LTS (Brett)

### Awaiting CI (4)
- #411: Workflow enhancement
- #416: Stats count fix (Parker, rebased)
- #418: Python deps + Ruff (Parker)
- #419: Clean Dependabot workflow (replaces #412)

### Issues Closed (9/14)
- #344, #345, #346, #347, #348, #350, #405, #406, #407
- **Remaining (5):** #351 (Python deps), #404 (stats), + 3 TBD

**Priority on resume:**
1. ✅ P0: Release v1.0.1/v1.1.0/v1.2.0 retroactively — **COMPLETE**
2. ✅ P1: Clean up 66 stale branches — **COMPLETE**
3. 🔄 P1: v1.4.0 in progress — awaiting CI on 4 PRs, then close remaining 5 issues
4. 📋 P2: v1.4.0 release documentation (after milestone closes)

**Decision inbox status:** ✅ All decisions merged (12 files from inbox → archive)

**Environment:** Docker Compose stack running locally. All services operational (Solr, RabbitMQ 4.0 LTS upgraded, Redis, etc.).

**Team:** Ralph (CI/CD active), Dallas (frontend), Brett (infrastructure), Parker (backend), Ripley (QA/lead), Newt (PM), Lambert (tester), Juanma (PO)

