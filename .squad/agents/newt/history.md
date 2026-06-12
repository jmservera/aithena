# Newt — History

## Core Context

**Aithena** is an on-prem book-library search engine: Python/FastAPI services, React/Vite UI, Docker Compose, Solr full-text search, multilingual embeddings, PDF processing, upload, filtering, highlighting, and admin operations. Deployment docs and operator constraints are product requirements.

**Newt role:** Product Manager for release validation, docs, manual QA, changelog/user-facing quality, and release-gate sign-off. Newt may reject releases for docs, validation, or UX gaps; code/tests are delegated.

**Stable architecture:** `aithena-ui/` talks to `solr-search/`, embeddings, document-indexer, and document-lister. Runtime includes Compose services, Solr, Redis, RabbitMQ, Nginx, and compose health checks.

**Documentation structure:**
- `docs/release-notes/vX.Y.Z.md` — versioned release notes.
- `docs/test-reports/vX.Y.Z.md` — versioned validation evidence.
- `docs/guides/` — feature/ops guides, including GPU/WSL2 and monitoring.
- `docs/user-manual.md` and `docs/admin-manual.md` — authoritative user/operator manuals.
- `docs/images/` — release screenshots; Tier 1 screenshots are release-readiness assets.

**Release baseline:** Docs-first gates are enforced since v0.8.0. v1.x shipped infra, ops, quality, admin, CI, embeddings, and docs releases. Tests grew from ~467 (v1.4.0) to 1,939 (v1.15.0); drops or unexplained jumps require investigation.

**Current state (2026-06):** v2.5.0 shipped as the Solr 10 infrastructure release. Post-v2.5 follow-up tracks include evidence-gated quantization, topology hardening, and docs/source-of-truth cleanup.

**Active PRDs / product tracks:**
1. **Pre-Release Containers (v1.16+)** — RC workflow before main merge; manual/auto triggers; production compose validation.
2. **Admin React Migration (v2.0, completed)** — Streamlit → React `/admin/*`; shipped in v2.0.0 and archived at `docs/prd/completed/admin-react-migration.md`.
3. **Infrastructure hardening (v2.3.0)** — publish operator responsibilities for ZooKeeper/Solr posture and accepted risks.

## Product Patterns

1. **Release = docs + tests + manuals + PM sign-off.** Required: release notes, test report, CHANGELOG, user/admin manuals, and explicit verdict. No dev→main release without Newt approval.

2. **Scope before gates.** Gate issues follow defined milestone scope. Creating them before Ripley defines feature/patch/infra/maintenance scope causes ambiguous acceptance criteria.

3. **Infrastructure releases need feature-level rigor.** Dependencies, deployment, CI, and config posture still need migration guidance, validation evidence, rollback notes, and operator docs.

4. **Operator constraints are product contracts.** Constraints like private ZooKeeper or Solr BasicAuth belong in release notes/admin manual, ideally with compose/YAML examples.

5. **Framework-first test reports scale.** Draft prerequisites/checklists before CI evidence; fill results after merge. This exposes blockers and decouples PM docs from engineering.

6. **Maintenance patches need compact honesty.** Focus on changed issues; disclose missing artifacts or validation limits rather than padding with unrelated proof.

7. **Breaking changes require justification and migration.** Document why, impact, migration path, and rollback in release notes/admin manual; prefer auto-migration.

8. **Deployment procedures live in admin manual.** Each operator-impacting release adds a deployment/operator subsection as the production quick reference.

9. **Docs restructures must trace automation.** Use `git mv`, then update workflow paths, cross-references, image mappings, and link validation.

10. **Screenshots are release evidence.** Tier 1: login, search results, admin dashboard, upload. Tier 2: feature states. Tier 3: admin/ops consoles.

11. **Sequential versioning matters.** Ship milestones in order; close all issues before tag. Dev→main PRs, tags, and GitHub Releases are separate.

12. **Human-judgment PR checklists become follow-up issues.** Keep docs assessment separate from CI/ruleset failures.

13. **Branch protection is release workflow.** Release/version commits go through PRs to `dev`; use release branches and verify commit contents after stashes.

14. **Separate product and technical blockers.** Docs may be approved while CI/rulesets still block merge; record both.

15. **Release history enables credible narrative.** Engineers respond to honest struggle + metrics, not AI marketing fluff.

## Learnings

1. **2026-06-04 — v2.3.0 gate prep:** Maintenance/infrastructure releases need explicit operator-responsibility sections in both release notes and admin manual. Accepted-risk decisions only hold if constraints are published where operators will see them.

2. **2026-06-04 — Product constraints:** “Do not publish ZooKeeper ports” and “maintain Solr BasicAuth” are product-level release constraints, not just deployment tips. Add a gate checklist item: all production constraints documented?

3. **2026-06-04 — Test report coordination:** Lambert’s framework-first/evidence-later pattern is reusable for complex releases because PM, infra, and test blockers are visible before final CI evidence exists.

4. **2026-06-04 — Scope alignment:** v2.3.0 showed that release type determines artifact shape. Ripley must define scope before Newt creates release-gate issues for v2.4+.

5. **2026-06-04 — Board rescan:** v2.2.1 could proceed while v2.3.0 scope was pending. Development can continue on unrelated warnings/research without blocking final human sign-off.

6. **2026-06-03 — v2.2.1 docs review:** A documentation PR can be product-approved while still technically blocked. Newt should state “approve after CI/ruleset passes” and route checklist sign-off to a follow-up issue.

7. **2026-06-03 — Release-gate timing:** v2.3.0 development started before scope/milestone existed; Newt correctly held gate issue creation until scope was defined, preserving clear acceptance criteria.

8. **2026-06-03 — Human sign-off pattern:** v2.2.1 sign-off assigned to Ripley/Juanma can coexist with AI agents continuing next-cycle work. Human validation is a release gate, not a global work stop.

9. **2026-03-26 — Intel GPU on WSL2 docs:** WSL2 GPU setup differs from native Linux: `/dev/dxg`, Windows host driver, `/usr/lib/wsl` mount, no render group. Complex OS-specific setup belongs in a dedicated guide linked from admin manual.

10. **2026-03-24 — v1.15.0 release prep:** Pre-existing test failures can be non-blockers only when documented with scope and rationale. Admin coverage below the usual 70% threshold was flagged for follow-up.

11. **2026-03-22 — v1.12.1 release:** Branch protection blocks direct release pushes; use PRs for version bumps. CI integration tests can be flaky due to embeddings-server health timeouts, so distinguish infra flake from code regression.

12. **2026-03-22 — Release decision:** v1.14.0 A/B UI should depend on benchmark need: if e5-base quality loss is negligible, skip UI and migrate; only build comparison UI when human quality judgment is needed.

13. **2026-06-04 — v2.3.0 release docs:** Infrastructure maintenance releases require explicit operator-responsibility sections (ZooKeeper ACLs, Redis memory overcommit) in BOTH release notes and admin manual. Accepted-risk posture only holds when published where operators will find it during deployment. Release validation checklist should document framework first (accept blockers and constraints as legit) before test evidence arrives, reducing PM/infra/test interdependencies and making bottlenecks visible early.

14. **2026-06-06 — Milestone triage:** When only two active milestones exist (v2.5 and v2.5.1), apply product judgment to sort research/enhancement/infrastructure issues into v2.5 (longer-term post-release work) and test/validation/release issues into v2.5.1 (active validation phase). Issues prefixed with "[v2.5]" tag go into v2.5 unless they are explicit test phases or pre-release validation, which go into v2.5.1. All 14 open issues now assigned: v2.5 = 8 (research, infra, enhancements), v2.5.1 = 6 (test phases, validation gates).

## 2026-06-06 — v2.5.1 Board Triage Complete

Triaged remaining v2.5.1 board items. All issues now assigned or in-progress. Remaining work blocked on external dependencies: external corpus, hardware, model/runtime fixtures, benchmark execution, or broader design planning. Recommended Ralph idle until external unblocking.

Related: v2.5.1 board, v2.5 epic

15. **2026-06-07 — Docs consistency cleanup:** Release notes, manuals, test reports, and topology docs must align to shipped code, not planned issue titles. For v2.5, the shipped source of truth is single-node SolrCloud (not ZooKeeper-free standalone), `blockUnknown=false` compatibility posture, Solr 10 HNSW names `hnswM`/`hnswEfConstruction`, and evidence-gated int8 quantization (#1344).

16. **2026-06-12 — Complexity Reduction PRD Complete:** Wrote comprehensive PRD for #1452 decomposing infrastructure consolidation work into 13 GitHub issues across 3 phases. Research findings: 5 duplicate Dockerfiles, 18 shell scripts, 3 env templates, 3 test frameworks, scattered config docs, fragile build scripts. Phase 1 (foundation, weeks 1–2) targets `manage.sh` CLI + `.env.example` consolidation (5d effort). Phase 2 (docs & robustness, weeks 3–4) targets config centralization + dynamic build system (5d effort). Phase 3 (Docker, weeks 5–6) targets shared base image + refactored service Dockerfiles (5d effort). Total: 15 person-days. Created issues #1739–#1751 with squad member assignments (Brett: infra/Docker, Lambert: testing, Newt: docs). Key decision: dynamically discover services to avoid manual list maintenance and establish patterns for new services.

17. **2026-06-12 — 13 Issues Created for #1452:** Issues #1739–#1751 are now live for complexity reduction 3-phase plan. Sequencing: Phase 1 (foundation, weeks 1–2) unblocks operators immediately; Phase 2 (documentation & robustness, weeks 3–4) centralizes config and establishes dynamic build; Phase 3 (Docker, weeks 5–6) consolidates Dockerfiles. v2.6 release gates all three phases: script count ≤4 (from 18), Docker complexity reduction 15%, single .env.example template, unified `make test` entrypoint, centralized config docs, no build time regression. Squad assignments finalized: Brett (7d), Lambert (3d), Newt (3d), Dallas (1.5d). Release target: v2.6 post-v2.5.1 validation.
