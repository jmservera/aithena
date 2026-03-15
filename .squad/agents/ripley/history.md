# Ripley — History

## Project Context
- **Project:** aithena — Book library search engine with Solr indexing, multilingual embeddings, PDF processing
- **User:** jmservera
- **Stack:** Python (backend), TypeScript/React + Vite (UI), Docker Compose, Apache Solr, multilingual embeddings
- **Book library:** `/home/jmservera/booklibrary`
- **Existing services:** Redis, RabbitMQ, Qdrant (being replaced), LLaMA server, embeddings server, document lister/indexer, search API, React UI

## Core Context

**Architectural Achievements (Phase 2-3 Complete):**
- Solr migration COMPLETE: SolrCloud 3-node cluster, Tika extraction, multilingual langid detection
- FastAPI search service (`solr-search/`) live: secure, well-tested (+11 unit tests), clean architecture
- React search UI converted from chat to search: FacetPanel, ActiveFilters, BookCard, pagination, sort
- PDF viewer panel integrated with page navigation
- Status + Stats tabs: health monitoring (Solr, Redis, RabbitMQ), collection stats by lang/author/year/category
- Embeddings model aligned to `distiluse-base-multilingual-cased-v2`, dense vectors added, chunking implemented
- Search modes (keyword/semantic/hybrid) with RRF fusion; similar-books endpoint working

**Critical Bugs Identified:**
- #166: RabbitMQ timeout on first start (khepri_projections)
- #167: Document pipeline stalled (new files not detected)

**Branch Management Lessons:**
- Copilot agents must pull fresh base before starting (prevent stale branches by 28+ commits)
- Stale branches create "time bomb" PRs that delete recently merged work
- Established guardrails: explicit base-branch instructions, scope fences, dependency gating

**Codbase patterns established:**
- Clean Architecture: Presentation → Application → Domain → Infrastructure
- TDD mandatory for all work; all services have 8-14 unit tests each
- Type-first: Backend Python return dicts mirror TypeScript interface contracts
- Zero defects: Phase 2 + 3 PRs merged with clean code quality

**Outstanding Work:**
- v0.5 Phase 3 completion: #163 (search mode selector UI), #41 (frontend tests), #47 (similar books UI)
- v0.6 Phase 4: upload endpoint (#49), upload UI (#50), hardening (#52)
- Security scanning: #88-#98 (requires triage or Kane assignment)

## Learnings

<!-- Append learnings below -->

### 2026-03-14T23:xx — Reskill: Current Codebase State & v0.5 Roadmap Update

**Release Status:**
- **v0.4.0 SHIPPED** — All 7 Phase 2 PRs merged to `dev` (Search API, UI, Status/Stats tabs, PDF navigation). Release commit: `c27fa4b`
- **v0.5 (Phase 3: Embeddings Enhancement) IN PROGRESS** — 5 of 6 core issues verified complete on `dev`:
  - #42, #43, #44, #45, #46 all delivered (embeddings model, dense vectors, chunking, search modes, similar-books API)
  - #163 (search mode selector UI) created as the remaining gap — assigned `squad:copilot`, 🟢 good fit
  - Two parallel copilot issues also open: #41 (frontend tests, 🟢) and #47 (similar books UI, 🟡 needs review)
- **v0.6 (Phase 4)** planned but unstarted — upload endpoint (#49), upload UI (#50), hardening (#52)

**Key Patterns Observed:**
1. **Copilot work is highly reliable:** Phase 2 + Phase 3 PRs are well-structured, test-covered, clean code. Zero defects merged to dev.
2. **Phase-based issue decomposition works:** Explicit dependencies + single-owner issues prevent PR sprawl.
3. **Architecture board (decisions.md) is the source of truth:** All major decisions (ADRs, team assignments, risk mitigations) recorded and traceable.
4. **Clean Code + TDD is the standard:** All services follow separation of concerns, comprehensive type hints, error handling edge cases in tests.

**Next Lead Action Items:**
1. Triage & assign bugs #166-#167 (RabbitMQ + file detection failures)
2. Clarify v0.5 copilot queue: #163, #41, #47 parallelization + merge sequencing
3. Review open security scanning issues (#88-#98) — defer or assign to security team (Kane)?
4. Plan v0.6 roadmap: #49, #50, #52 — coordinate with Parker (backend) + Dallas (frontend) + Ash (search tuning)

### 2026-03-14T23:xx — v0.5 PR Batch 1 Review

**Reviewed & Approved:**
- **PR #164** (search mode selector) — ✅ Clean, complete. All #163 acceptance criteria met. Mode type, API param, toggle UI, error handling all correct.
- **PR #165** (Vitest test coverage) — ✅ 19 behavioral tests, 3 components. Proper mocking, no snapshots. Solid foundation for #41.
- **PR #170** (Admin tab iframe) — ✅ Minimal, correct stop-gap for #168. Relative path, sandbox attribute, graceful fallback.

**Issues Found:**
1. **Pre-existing CI failure:** `solr-search/tests/test_integration.py:1115` has a ruff SIM117 violation that fails Python lint on every PR branch. Needs independent fix — opened as known issue.
2. **CI gap:** `npm run test` (vitest) is not in the CI pipeline. Frontend tests exist but don't run in CI. Should be added as a follow-up.

**Observations:**
- Copilot agent continues to deliver clean, well-structured code. All 3 PRs target `dev`, follow existing React patterns, use proper TypeScript types, and match the project's hook-based architecture.
- No hardcoded URLs in any PR. Relative paths used consistently.
- The Copilot agent handles edge cases well (empty query guard for semantic mode, sandbox attribute on iframe, proper ARIA attributes).
- Recommended merge order: #165 → #164 → #170 (tests first for baseline).

### 2025-07-24 — v0.5 Bug Fix PR Review (Batch 2)

**Reviewed & Approved:**
- **PR #173** (document-lister restart idempotency) — ✅ Investigation-only PR. Copilot correctly identified that persistent state tracking (Redis + mtime) was already implemented. Added one edge-case test. No production code changed.
- **PR #174** (language detection fix) — ✅ Three-pronged fix: Solr langid field rename (`language_s` → `language_detected_s`), new folder-based language extraction (`extract_language()` with 35 ISO 639-1 codes), and indexer pass-through for `language_s`. 13 new tests. Requires full reindex after merge.

**CI Gap (recurring):**
- Only CodeQL runs automatically on these PR branches. Ruff + pytest are not triggered — likely need first-time workflow approval in GitHub UI. This is the second review batch where full CI hasn't run. Should be escalated to unblock automated validation.

**Observations:**
1. Copilot agent shows good investigative judgement — PR #173 correctly concluded "already fixed" rather than introducing unnecessary changes.
2. PR #174 demonstrates multi-layer debugging: Solr config + Python metadata + indexer pipeline all needed coordinated fixes. Well-decomposed.
3. The dual-field language architecture (`language_detected_s` for content analysis, `language_s` for folder-based) is a sound design that gives content detection priority with folder fallback.
4. Merge order matters: #173 → #174, then schedule full reindex for the library.

### 2026-07-24 — v0.6.0 Release Planning

**Context:**
- v0.5.0 shipped successfully (197 tests, 9 issues closed)
- 22 open issues across Phase 4 features, security scanning, and Dependabot vulnerabilities
- Newt's v0.5.0 verdict included 4 follow-up recommendations (admin iframe, similar books cache, facet hints, invalid mode test)

**Release Plan Decisions:**

1. **Scope: Production Hardening & Security (12 issues)**
   - Phase 4 features: Upload endpoint (#49), upload UI (#50), docker hardening (#52)
   - Security scanning: bandit (#88), checkov (#89), zizmor (#90), OWASP ZAP guide (#97), baseline tuning (#98)
   - v0.5.0 polish: 4 new issues for Newt's recommendations (#178-#181)

2. **Deferred to v0.7.0+:**
   - 13 Dependabot issues (LOW severity, transitive deps) — batch into dedicated dependency audit sprint
   - Admin migration (#169) — large scope, not blocking production

3. **Squad Assignments Strategy:**
   - Security foundation (SEC-1/2/3): @copilot parallel, 🟢 good fit
   - Security validation (SEC-4/5): @copilot → Kane review (security judgment required)
   - Upload backend (#49): @copilot → Parker review (API design validation)
   - Upload frontend (#50): @copilot → Dallas review (UX design validation)
   - v0.5.0 polish (#178-#181): @copilot parallel, 🟢 good fit
   - Docker hardening (#52): @copilot → Brett review (production deployment expertise)

4. **Execution Phases:**
   - Week 1: Security foundation (SEC-1/2/3) + validation (SEC-4/5)
   - Week 2: Upload feature (#49 → #50) + polish (#178-#181 parallel)
   - Week 3-4: Hardening (#52) + release validation
   - Total: 3-4 weeks

5. **Key Risks Identified:**
   - Security scanners may find critical issues → triage in SEC-5, may require emergency fixes
   - Upload endpoint design may need iteration → Parker review gate before implementation
   - Dependabot issues may escalate to CRITICAL → monitor advisories, pull into v0.6.0 if needed

**Architectural Principles Applied:**
- Use review gates (Parker/Dallas/Kane/Brett) for domain expertise validation BEFORE copilot implementation
- Batch parallel work (SEC-1/2/3, polish issues) to maximize velocity
- Sequence dependent work (upload endpoint before upload UI, security foundation before validation)
- Defer low-impact work (Dependabot batch, admin migration) to dedicated sprints

**Open Questions for Juanma:**
- Upload scope: single-file or multi-file batch in v0.6.0?
- Any Dependabot issues elevated to must-fix?
- Confirm admin migration deferred to v0.7.0+?
- 3-4 week timeline acceptable or compress to 2 weeks?

**Plan written to:** `.squad/decisions/inbox/ripley-v060-release-plan.md`

### 2026-03-15 — v0.6.0 Security Scanning PR Review (Round 3)

**Context:** Reviewed 4 security scanning PRs implementing the SEC-1/2/3/4 specifications from v0.6.0 release plan.

**PRs Reviewed:**
- **PR #193** (SEC-1 Bandit) — Kane — ✅ APPROVED
- **PR #192** (SEC-3 Zizmor) — Kane — ✅ APPROVED  
- **PR #194** (SEC-4 OWASP ZAP Guide) — Kane — ✅ APPROVED
- **PR #191** (SEC-2 Checkov) — Brett — ✅ APPROVED

**Review Findings:**

**PR #193 (SEC-1 Bandit):**
- Configuration (.bandit): All required skip rules present (S101/S104/S603 from spec + S607/S108/S105/S106 for test scenarios)
- Workflow: Valid YAML, correct triggers (push/PR to dev+main), non-blocking (continue-on-error), SARIF upload configured
- Scans all Python services (document-indexer, document-lister, solr-search, admin, embeddings-server, e2e)
- Artifact retention (30 days), concurrency control, proper permissions

**PR #192 (SEC-3 Zizmor):**
- Workflow: Valid YAML, path-filtered triggers (.github/workflows/**), non-blocking
- Uses official zizmorcore/zizmor-action@v0.1.1 with advanced-security: true (SARIF auto-upload)
- Focuses on P0 findings (template-injection, dangerous-triggers) per spec
- Security best practice: persist-credentials: false on checkout

**PR #194 (SEC-4 OWASP ZAP Guide):**
- Comprehensive 907-line guide covering all spec requirements
- Proxy setup (addresses port 8080 conflict with solr-search)
- Manual explore phase, active scan configuration, complete endpoint inventory
- **Docker Compose IaC review checklist** (compensates for checkov's docker-compose gap — critical addition)
- Result interpretation (severity levels, CWE mapping), triage workflow, baseline exception template
- Professional audit report template with example findings
- Security README created as documentation index

**PR #191 (SEC-2 Checkov):**
- Configuration (.checkov.yml): Skip rules documented (CKV_DOCKER_2/3) with justifications
- Workflow: Dual scans (Dockerfiles + GitHub Actions), soft_fail: true, SARIF upload
- Correct triggers (Dockerfiles, workflows, docker-compose files)
- Concurrency control, proper permissions

**Verdict:** All 4 PRs approved with no changes requested. All workflows validated for:
1. YAML syntax correctness
2. Trigger configuration (push/PR to dev+main)
3. Non-blocking execution (continue-on-error or soft_fail)
4. SARIF upload to Code Scanning
5. Correct permissions (contents read, security-events write)
6. Target branch (all PRs target `dev`)

**Key Observations:**
1. **Kane's security expertise shows:** All 3 Kane PRs (bandit, zizmor, ZAP guide) demonstrate deep understanding of security tooling. The ZAP guide's Docker Compose IaC checklist fills a critical gap.
2. **Brett's IaC knowledge applied:** Checkov skip justifications reference centralized health checks and base image defaults — correct architectural reasoning.
3. **Spec compliance 100%:** All PRs implement exactly what was specified in the SEC-1/2/3/4 decisions, with appropriate baseline exceptions documented.
4. **Documentation quality:** The OWASP ZAP guide (30KB+) is production-ready — actionable for beginners, references actual aithena architecture, includes audit report template.

**Next Steps:**
1. Merge order: Any order (no dependencies between these PRs)
2. After merge: SEC-5 (issue #98) triage of actual findings
3. Monitor CI: First workflow runs will require GitHub UI approval (new workflows)

**Learnings:**

1. **Review efficiency with distributed authorship:** When squad members (Kane, Brett) implement separate specs in parallel, reviews are faster because each PR has narrow scope and clear success criteria from the spec.
2. **Documentation as implementation:** SEC-4 (ZAP guide) is "just docs" but required the same rigor as code — verified endpoint accuracy, architectural alignment, checklist completeness. The Docker Compose IaC review checklist is a critical addition that compensates for tooling gaps.
3. **Non-blocking scanners require dual safeguards:** All workflows use both `continue-on-error: true` (job level) AND `--soft-fail`/`--exit-zero` (tool level) to ensure CI doesn't break. This belt-and-suspenders approach is correct for initial rollout.
4. **Baseline exceptions must be documented upfront:** .bandit and .checkov.yml both include skip rules with justifications. This prevents alert fatigue and makes SEC-5 triage focused on real issues.
5. **Path filtering reduces noise:** Zizmor only triggers on .github/workflows/** changes, checkov on Dockerfiles/workflows/docker-compose — this prevents unnecessary scans and speeds up CI.
1. **Release planning benefits from clear theme** — "Production Hardening & Security" gives focus vs trying to do everything
2. **Defer aggressively** — 13 Dependabot issues are noise if they're all LOW severity transitive deps; batch into dedicated sprint
3. **Review gates prevent rework** — Parker/Dallas/Kane/Brett review on design BEFORE copilot implements saves iteration cycles
4. **Parallel + Sequential balance** — Group 1 (SEC-1/2/3) and Group 5 (polish) can run in parallel; upload and hardening must sequence
5. **New issues for follow-ups** — Newt's recommendations deserve issue tracking (not just decision log) for visibility and PR linking

### 2026-03-15 — v0.6.0 Release Planning Complete

**Summary:** v0.6.0 release plan finalized and recorded in decisions.md. All specs from Parker, Dallas, Brett, Kane reviewed and approved. Ready for Juanma sign-off before Phase 1 issue creation.

**Decisions Merged:**
- Ripley: 12-issue release plan with 6-group dependency order
- Parker: PDF upload endpoint spec (#49) — 202 Accepted, multipart/form-data, RabbitMQ integration
- Dallas: PDF upload UI spec (#50) — Tab-based, 5-state flow, XMLHttpRequest progress
- Brett: Docker hardening spec (#52) — 8 health checks, restart policies, resource limits, graceful shutdown
- Kane: Security scanning plan (#88-98) — 3 CI scanners (non-blocking) + OWASP ZAP guide + baseline tuning

**Next:** Awaiting Juanma approval → Ripley creates issues + milestone → Phase 1 setup
