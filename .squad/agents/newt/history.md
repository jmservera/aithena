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

**Current state (2026-06):** v2.2.1 shipped. v2.3.0 is maintenance/infrastructure hardening: milestone exists, target 2026-06-11, notes/manuals prepared in #1645/#1647, validation in #1648, final evidence pending implementation/tests. v2.5 is Solr 10 research.

**Active PRDs / product tracks:**
1. **Pre-Release Containers (v1.16+)** — RC workflow before main merge; manual/auto triggers; production compose validation.
2. **Admin React Migration (v2.0)** — Streamlit → React `/admin/*`; unify auth; remove docker.sock exposure; phase-gated API/UI/tests/removal.
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
