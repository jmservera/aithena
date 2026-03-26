# Ripley — History

## Core Context

**Role:** Project Lead — Architecture, Roadmap, Release Planning, Team Coordination

**Release History (as of 2026-03-20):**
- **v1.0.1–v1.3.0:** Security, CI/CD, frontend quality, admin consolidation (Streamlit → React)
- **v1.4.0:** Stats & filtering (fixed book count via Solr grouping)
- **v1.5.0:** Production infrastructure (Docker tagging, volumes, smoke tests)
- **v1.6.0:** Internationalization (React-intl, 4 languages, language switcher)
- **v1.7.0:** Quality infrastructure (CI coverage: +219 tests, Dependabot automation)
- **v1.7.1–v1.9.0:** SHIPPED (tech debt, UI/UX, user management)
- **v1.10.0:** IN PROGRESS — 48 issues, 4-wave execution, BCDR + collections + metadata editing

**Architecture (Canonical):**
1. **SolrCloud 3-node** — Tika PDF extraction, multilingual support, parent/chunk document hierarchy
2. **Hybrid search** — RRF-based keyword + semantic fusion, `distiluse-base-multilingual-cased-v2` embeddings
3. **6 services:** solr-search (FastAPI), embeddings-server (FastAPI), document-indexer (RabbitMQ), document-lister (RabbitMQ), aithena-ui (React 18/Vite), admin (Streamlit, deprecated)
4. **Infrastructure:** Redis, RabbitMQ, Nginx reverse proxy. Fully on-premises, no cloud dependencies.
5. **Data model (CRITICAL):** Documents have parent/chunk hierarchy. Embeddings live on **chunks**, not parents. kNN queries MUST target chunks. Grouping by `parent_id_s` aggregates to book level.

**Ownership Map:**
- **Parker:** Backend implementation (Solr, FastAPI, indexing)
- **Dallas:** Frontend (React, UI/UX), build validation
- **Brett:** CI/CD, GitHub Actions, Docker, infrastructure
- **Ash:** Search engineering (Solr schema, embeddings, kNN)
- **Kane:** Security (CVE triage, RBAC, audits)
- **Lambert:** Testing (pytest, Vitest, E2E, Playwright)
- **Newt:** Release planning, documentation, milestones
- **Copilot:** Well-scoped issue implementation
- **Ripley:** Architecture, roadmap, team coordination, decision arbitration

---

## Critical Patterns (Earned Knowledge)

### 1. Phase-Gated Execution
Break features into Research → Implementation → Validation → Merge. Work within a phase is parallel; phases are sequential. Prevents sprawl, enables safe parallelization, creates clear hand-offs. **Validated across 10+ milestones.**
- Skill: `.squad/skills/phase-gated-execution`

### 2. Pragmatic Incrementalism
Ship the quick win, validate with users, then invest in architecture. Phase 1 delivers value; Phase 2 is data-driven. **Risk:** Requires discipline to revisit Phase 2 commitments.
- Example: Stats book count — Solr grouping (Phase 1, v1.4.0) shipped; doc_type discriminator (Phase 2) deferred

### 3. Branch Hygiene (MANDATORY)
Always `git fetch origin && git checkout -b <branch> origin/dev`. Never branch from local state. Cross-branch contamination is a systemic risk in multi-agent repos — it silently reverts recent work.
- Decision: `.squad/decisions/inbox/ripley-branch-hygiene.md`

### 4. No Silent Degradation
Error handlers MUST NOT silently change search mode or drop results. Must log WARNING and return clear error. Requires Lead/PO approval for any degradation behavior. Born from PR #700 rejection.
- Decision: `.squad/decisions/inbox/ripley-no-degradation.md`

### 5. Scientific Debugging
Bug fixes require reproduction evidence before PR. Root cause analysis before code changes. Agents default to "fix the symptom" under pressure — process guardrails prevent this.
- Template: `.github/ISSUE_TEMPLATE/bug_report.yml`
- Checklist: `.squad/templates/pr-checklist.md`

### 6. Documentation-First Releases
Commit all release artifacts (CHANGELOG, notes, test reports) to dev before tagging. Process: (1) artifacts → (2) VERSION bump → (3) dev→main merge → (4) tag + GitHub Release. Git tags bypass branch protection.
- Skill: `.squad/skills/release-gate`

### 7. Security Baseline Exceptions
When a CVE has no patched version, accept baseline exception if runtime mitigation is proven. Document risk assessment, create follow-up issue for proper fix. Applied to ecdsa CVE-2024-23342.

### 8. Wave-Based Milestone Execution
For large milestones (20+ issues), decompose into waves: Wave 0 (bugs) → Wave 1 (foundations) → Wave 2 (building blocks) → Wave 3 (integration) → Wave 4 (polish). Run retrospective between waves. **Grade improvement: C+ → B+ across waves in v1.10.0.**

### 9. Agent Load Balancing
Identify bottleneck agents early. Parker was primary on 20+ issues in v1.10.0 — mitigated by delegating BCDR to Brett, search to Ash, CI/CD to Copilot. Single-owner issues prevent confusion.

### 10. Domain Knowledge as First-Class Deliverable
The parent/chunk document relationship caused the scariest near-miss (PR #701). Undocumented domain knowledge creates invisible risk. Document critical data model relationships BEFORE implementation.

---

## Release Planning Methodology

**Milestone Strategy:**
1. Phase breakdown per milestone (Research → Impl → Validation → Merge)
2. Single owner per issue with clear acceptance criteria
3. Dependencies in decisions.md; phase gating enforced
4. Parallel execution within phases

**Release Gate:** See `.squad/skills/release-gate/SKILL.md`
- All milestone issues closed (milestone + label verification)
- All 6 test suites passing
- Release artifacts committed to dev
- VERSION bumped, documentation verified, screenshots captured
- Tag created, GitHub Release published

**Pre-PR Self-Review:** See `.squad/templates/pr-checklist.md`
- Scope, security, data model impact, error handling, tests, branch hygiene

---

## Session Archive (Compressed)

### v1.4.0–v1.7.0 Epic Session (2026-03-18)
Coordinated 4 consecutive releases in one session. 49 issues closed across 4 milestones. Zero rework. Validated phase-gated execution at scale.

### v1.7.1–v1.8.0 Planning (2026-03-18)
Planned tech debt (uv migration, Docker multi-stage) and UI/UX (Lucide React icons, design tokens, WCAG AA). Sequential delivery: v1.7.1 → v1.8.0.

### Screenshot Pipeline (2026-03-18)
Created issues #530–#534 for automated Playwright screenshots in release workflows.

### User Management Design (2026-03-19)
Designed 3-tier RBAC (admin/user/viewer) for v1.9.0. 12 issues created (#549–#560). Key decisions: phased X-API-Key migration, 128-char password max (Argon2 DoS), stateless JWT sufficient for library app.

### CI Tier Strategy (2026-03-17)
Found 219 untested tests. Implemented Tier 1 (fast dev CI) + Tier 2 (rigorous release CI). 80% CI time reduction.

### v1.10.0 PRD Decomposition (2026-03-20)
Decomposed 2 PRDs into 16 issues: User Document Collections (7) + Book Metadata Editing (9). Key: `series_s` field naming, collections in SQLite, metadata overrides in Redis.

### v1.10.0 Kickoff (2026-03-20)
48 issues, 4-wave plan. Deferred 4 hardening issues. BCDR is critical path (8 sequential steps). Parker bottleneck mitigated via delegation.

### v1.10.0 Retrospective (2026-03-20)
Wave 0: C+ (PR #700 rejection, silent degradation). Wave 1: B+. 5 decisions made, 8 action items. Implemented R1, R3, R4, R6 via PR #720.

### Docker Build Diagnosis (2026-03-20)
Inconsistent build context pattern: solr-search and admin use repo-root, others use service-dir. Both work, but noted for future architectural decision.

---

## Decision References

Active decisions in `.squad/decisions.md`:
- Security baseline exceptions (ecdsa, PyJWT migration)
- Admin consolidation (Streamlit → React)
- Docs-gate-the-tag release process
- Docker health check best practices
- CI Tier 1 + Tier 2 strategy
- Branch hygiene rule
- No silent degradation rule
- Pre-PR self-review checklist
- v1.10.0 wave plan and deferrals
- Solr schema coordination (Ash owns all schema changes)

---

## Reskill Notes (2026-03-20)

### Self-Assessment
**What I do well:**
- Milestone decomposition and wave planning — consistently delivers parallel execution without conflicts
- Decision documentation — every significant choice gets an ADR with rationale
- Risk identification — Parker bottleneck, BCDR critical path, and cross-branch contamination caught early
- Retrospectives — measurable improvement (C+ → B+) across waves

**What I need to improve:**
- **Faster domain knowledge extraction.** The parent/chunk data model gap should have been documented in v0.5, not discovered as a near-miss in v1.10.0. I should audit for undocumented domain knowledge proactively.
- **Phase 2 tracking.** Pragmatic incrementalism generates deferred work (doc_type discriminator, PyJWT migration). I need a systematic way to track and schedule deferred Phase 2 items.
- **Agent coaching.** "Fix the symptom" behavior recurs because agents don't have debugging methodology baked into their workflow. The bug template and PR checklist help, but I should review whether they're actually being followed.
- **Scope estimation accuracy.** v1.10.0 started at 48 issues — 4 were immediately deferred. Future kickoffs should build in a 10% deferral budget upfront.

### Patterns I'd Tell My Future Self
1. **When you see 20+ issues on one agent, act immediately.** Delegation isn't optional — it's the difference between a milestone landing on time or not.
2. **"Research before implementation" is your highest-ROI process.** Every time it was skipped (PR #700, PR #701), things went wrong. Every time it was followed (v0.9.0, v1.6.0 i18n), things went right.
3. **Process fixes beat training.** Branch hygiene, PR checklists, bug templates — mechanical guardrails work better than verbal instructions for agents.
4. **Wave retrospectives are non-negotiable for milestones over 15 issues.** The learning velocity between Wave 0 and Wave 1 proved this.
5. **Document the data model before anyone touches it.** The single most dangerous knowledge gap is always in the data model.

---

## Learnings & Skill Consolidation (v1.10.1–v1.14.0 Era)

### Skills Database Pruning: 49 → 34 High-Confidence Skills

**Aggressive pruning completed (2026-03-21).** Removed 15 unvalidated, one-time, and overlapping skills (ci-coverage-setup, ralph-dependency-check, smoke-testing, i18n-extraction-workflow, reskill, project-conventions, tdd-clean-code, lead-retrospective, dependabot-triage-routing, copilot-review-to-issues, squad-pr-workflow, docker-health-checks, hybrid-search-parent-chunk, hybrid-search-patterns). Consolidated hybrid-search patterns into solr-parent-chunk-model.

**Final 37 skills by category:**
- **Architecture:** phase-gated-execution, solr-parent-chunk-model (with hybrid search), solr-pdf-indexing, nginx-reverse-proxy, http-wrapper-services
- **Testing:** pytest-aithena-patterns, vitest-testing-patterns, playwright-e2e-aithena, path-metadata-tdd
- **Backend:** fastapi-auth-patterns, fastapi-query-params, redis-connection-patterns, pika-rabbitmq-fastapi, logging-security
- **Frontend:** react-frontend-patterns, accessibility-wcag-react
- **Infrastructure:** docker-compose-operations, solrcloud-docker-operations, bind-mount-permissions, branch-protection-strict-mode
- **Security:** security-scanning-baseline, workflow-secrets-security, ci-workflow-security
- **Release/Quality:** release-gate, release-tagging-process, multi-release-orchestration, pr-integration-gate, ci-gate-pattern, milestone-gate-review, milestone-wave-execution, api-contract-alignment, agent-debugging-discipline, pdf-extraction-dual-tool, path-metadata-heuristics
- **Patterns/Misc:** aithena-ab-testing-benchmarking, embedding-model-selection, prd-writing-aithena

**Pattern:** Aggressive pruning works better than slow accumulation. Ruthlessly removing unvalidated, one-time, and overlapping content leaves 37 battle-tested patterns (and emerging patterns like A/B testing, embedding selection, and PRD writing) that guide team work.

### Skills Created/Validated (v1.10.1 Reskill)

1. **branch-protection-strict-mode** — Sequential PR merges with GitHub strict branch protection. Use `gh pr merge --admin --merge` to bypass BEHIND states when status checks pass.
2. **milestone-gate-review** — Security/performance/architecture audit before closing any milestone. First enforced in v1.10.1: 13 issues reviewed, 0 blockers. Gate reviews catch subtle things (e.g., S608 suppressions vs actual SQL injection) that automated linting misses.
3. **fastapi-query-params** — FastAPI silently ignores undeclared query params. Bug found in #656: `fq_folder` sent but not received. Different from Flask/Express behavior.
4. **pdf-extraction-dual-tool** — Tika (Solr, full-text + metadata) vs pdfplumber (indexer, per-page chunks) are complementary, not redundant. Tika doesn't expose per-page boundaries; pdfplumber doesn't reliably extract metadata.

**Skill validated:**
- **fastapi-auth-patterns** — Confirmed in v1.10.1 auth hardening: WWW-Authenticate headers (RFC 7235), if-guards (not exception-driven), role checks enforced.

### v1.11.0 & A/B Testing PRD Research

**Key findings from code research** (2026-03-21, 2026-03-22):
- **R1 (chunk text preview):** Already 80% done. `chunk_text_t` stored in Solr but not in `SOLR_FIELD_LIST`. Simple retrieval change.
- **Similar books gap:** Rendered below results but obscured by PDF viewer z-index. Architectural fix: decouple from PDF state.
- **A/B test bottleneck:** RabbitMQ competing consumers trap. Both indexers on same queue → messages routed to ONE consumer. Requires fanout exchange or separate queues.
- **Solr schema coupling:** `knn_vector_512` hardcoded. New collection needs `knn_vector_768` field type.
- **PDF extraction architecture:** Tika handles full-text + metadata (keyword search). pdfplumber handles per-page chunks (semantic search). Neither extracts structure. Sentence-boundary awareness in chunker.py is short-term improvement.
- **Chunking:** Currently word-count based (400 words, 50-word overlap). No section awareness.

**Decisions:** 3-phase A/B test with PO decision gate. Thumbnail generation deferred to Phase 3/v1.12.0 (requires PDF rendering, not available today).

### v1.10.1 Gate Review Findings (2026-03-21)

**Security:** SQL injection clean (parameterized queries, S608 suppressions justified). Auth RFC 7235 compliant (WWW-Authenticate headers). Shell scripts safe (set -euo pipefail, flock, umask). GitHub Actions hardened (SHA-pinned, persist-credentials: false).

**Performance:** Sequential batch updates ~100s at 5000 docs max load. Acceptable for admin-only scope; async chunking recommended for v1.11+.

**Verdict:** APPROVE, 0 blockers.

### Infrastructure & Extraction Insights (2026-03-22–2026-03-24)

- **Offline audit:** Confirmed fully on-premises. Zero cloud APIs, telemetry, external auth. All services on Docker network. HuggingFace models pre-downloaded.
- **e5 migration review:** Core migration solid. 10 issues (2 medium, 8 low). Missing: tests for new reindex endpoint. Two blocking: timeout mismatch, dangling scripts/ references.
- **embeddings-server extraction analysis:** Technically ready for standalone repo. Zero coupling, HTTP-only, OpenAI-compatible API. New registry: `ghcr.io/jmservera/embeddings-server`. Version pinning discipline required.

**Key pattern reinforced:** "Research before implementation" — 20–30 min of code reading catches major issues (RabbitMQ competing consumers, R1 80%-done state, dual-extraction complementarity) that would emerge only during testing/launch without upfront research.

---

## Recent Milestones & Decisions (Summary)

### v1.14.0: e5 Model Migration (Complete)
- e5-base migration reviewed and approved (PR #964)
- 10 issues identified (2 medium, 8 low), all addressed in follow-ups
- A/B comparison deferred (e5 benchmarks showed clear superiority)
- Offline audit confirmed: zero cloud dependencies

### v1.11.0: Search Results Redesign (In Progress)
- PRD created with 4 user requirements
- R1+R2 phased as quick wins; R3 main deliverable; R4 deferred
- Chunking strategy decision pending from PO
- PDF thumbnails deferred to v1.12.0

### v1.10.1: Collections + BCDR (Released)
- Gate review: 13 issues, 0 blockers, APPROVE
- Security hardened: parameterized SQL, RFC 7235 auth, shell script safety
- BCDR workflows implemented: monthly restore drills, stress tests
- Performance: sequential batch ops ~100s @ 5000 docs (acceptable for admin-only scope)

### Strategic Decisions in Queue
1. **Embeddings-Server Extraction** — Technical readiness confirmed. Awaiting jmservera approval to extract to `github.com/jmservera/embeddings-server`. Zero coupling, HTTP-only, semantic versioning discipline.
2. **A/B Testing as Compose Overlay** — Pattern established: experimental services in separate compose file prevents production drift, trivial cleanup. 
3. **Release Process Hardening** — Mandatory security + performance review before shipping. 8 security checkpoints + 4 performance checkpoints.

---
