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

## Learnings

### v1.11.0 PRD: Search Results Redesign (2026-03-21)

**Session:** Research + PRD authoring for 4 requirements from Juanma.

**Key findings from code research:**
- **Chunk text is already stored** — `chunk_text_t` in Solr schema is `stored="true"`, but `SOLR_FIELD_LIST` in `search_service.py` doesn't include it. The vector search text preview (R1) is a genuinely small change.
- **Similar books aren't grayed out** — they're rendered below results but visually obscured by the PDF viewer's overlay (z-index 1000 with 65% black overlay). The fix is architectural: decouple similar books from PDF state.
- **Parent vs chunk search gap** — keyword search returns parents (chunks excluded via `-parent_id_s:[* TO *]`), semantic returns chunks (with embeddings). Hybrid RRF merges both. This means chunk text previews only apply to semantic/hybrid results.
- **Thumbnail generation is the largest risk** — no PDF rendering capability exists in the indexer today. Needs new dependencies (pymupdf or pdf2image), Docker changes, and storage decisions. Recommended deferral to Phase 3 or v1.12.0.

**Decisions made:**
- Created milestone v1.11.0 (GitHub milestone #29)
- Separated chunking strategy into its own issue (#796) — PO decision needed before R1 implementation
- PRD issue #797, PR #798 for review
- Phasing: R1+R2 (quick wins) → R3 (main deliverable) → R4 (deferred)

**Pattern reinforced:** "Research before implementation" — 30 minutes of code reading revealed that R1 is 80% done (chunk text stored but not retrieved), which completely changes the scoping estimate from what it would have been without research.

### v1.10.1 Security & Performance Gate Review (2026-03-21)

**Session:** Milestone gate review for all 13 v1.10.1 issues before release.

**Verdict:** APPROVE — no blockers.

**Key findings:**
- **SQL injection surface clean.** `collections_service.py` uses parameterized queries throughout. Two `# noqa: S608` remain but are justified false positives (dynamic column names and placeholder counts, not user data).
- **Auth hardening solid.** All four 401 paths include WWW-Authenticate headers (RFC 7235). Auth middleware uses if-guards, not exception-driven flow. JWT decode still uses try/except (correct — crypto parsing should use exceptions).
- **Shell scripts safe.** `verify-backup.sh` uses `set -euo pipefail`, whitelist validation for tier names, `umask 077`, `flock` concurrency guard. No `eval` or command injection vectors.
- **GitHub Actions workflows well-secured.** Both `monthly-restore-drill.yml` and `stress-tests.yml` use SHA-pinned actions, `persist-credentials: false`, minimal permissions.
- **Batch operations scoped correctly.** Admin-only (API key + JWT role), filter whitelist, value escaping via `solr_escape()`, query caps (1000 IDs / 5000 query results).
- **Performance observation:** Sequential batch updates (up to 5000 docs) could take ~100s at max load. Acceptable for admin-only scope in v1.10.1; recommend async chunking for v1.11+.

**Pattern reinforced:** Gate reviews catch the subtle things — the S608 suppressions required careful reading to confirm they're justified (dynamic column names vs user data). Automated linting alone would either flag false positives or miss the distinction.

### PDF Text Extraction Pipeline Analysis (2026-03-21)

**Session:** Deep investigation of the two-tool extraction pipeline for hierarchical chunking feasibility.

**Key findings:**
- **Dual extraction is intentional:** Tika (embedded in Solr via `SOLR_MODULES: extraction`) handles full-text + metadata for keyword search. pdfplumber handles per-page text for chunk-based semantic search. Tika doesn't expose per-page boundaries; pdfplumber doesn't reliably extract metadata.
- **Neither tool currently extracts document structure.** Tika flattens everything to `_text_` via `fmap.content`. pdfplumber uses only `page.extract_text()` — no font metadata analyzed.
- **Tika COULD provide XHTML with heading tags** if called directly (not via Solr's ExtractingRequestHandler). This is the most practical path to hierarchical chunking.
- **Current chunker is purely word-count based** — no sentence, paragraph, or section awareness. 400-word window, 50-word overlap.
- **Short-term fix exists:** Sentence boundary awareness in `chunker.py` is a small change that significantly improves preview readability without requiring structure extraction.

**Deliverables:**
- PRD updated with Section 5 (PDF Text Extraction Pipeline) — PR #803
- Issue #796 commented with structure extraction analysis and recommendations
- Open Questions updated with hierarchical chunking questions for PO and Ash

**Pattern reinforced:** "Document the data model before anyone touches it" — the dual-extraction architecture had no documentation. Without reading `__main__.py` end-to-end, you'd assume Tika and pdfplumber were redundant. They're complementary by design.

### Reskill + Wins Report for v1.10.1 (2026-03-21)

**Session:** Extract skills from v1.10.1 work and write wins report.

**Skills created:**
1. **branch-protection-strict-mode** — Sequential PR merges with GitHub strict branch protection (use `gh pr merge --admin` to bypass BEHIND states when status checks pass)
2. **milestone-gate-review** — Security/performance/architecture audit before closing any milestone (first enforced in v1.10.1, 13 issues reviewed, 0 blockers)
3. **milestone-branching-strategy** — Using `milestone/v{X.Y.Z}` branches for parallel milestone work (planned for v1.11.0, confidence: medium, not yet validated)
4. **copilot-review-to-issues** — Triage Copilot PR review comments into GitHub issues (P0–P2 get issues, P3 deferred). v1.10.1 had 7 issues from Copilot review → all fixed.
5. **fastapi-query-params** — FastAPI silently ignores undeclared query params (different from Flask/Express). Bug found in #656: `fq_folder` sent but not received.
6. **pdf-extraction-dual-tool** — Tika (Solr, full-text + metadata) vs pdfplumber (indexer, per-page chunks) — complementary tools, not redundant.

**Skill updated:**
- **fastapi-auth-patterns** — Confirmed in v1.10.1 auth hardening (WWW-Authenticate headers, no exception-driven flow, role checks enforced)

**Wins report highlights:**
- 13 issues closed, 7 PRs merged, 0 blockers
- Security hardening (SQL injection prevention, auth RFC compliance, exception flow elimination)
- BCDR workflows (monthly restore drills, stress test CI, backup checksums)
- 4 new processes established (gate review, Copilot → issues, strict branch protection, milestone branching)
- 5 lessons learned (Parker direct-push, cascading BEHIND states, docs-only PR gaps, FastAPI silent params, dual PDF extraction confusion)
- Team performance: Parker+Lambert consolidated 7 issues into 1 PR, Brett took over infrastructure from Dallas

**PR #805 created** — reskill + wins report to dev (pending CI checks)

**Pattern reinforced:** "Reskill after every milestone" — v1.10.1 yielded 6 new skills + 1 update. Without dedicated reskill time, these patterns would have been lost. The wins report captures team morale, process improvements, and lessons learned in a shareable format for Juanma.

