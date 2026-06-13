# Newt — History

## Core Context

Newt owns release validation, documentation quality, changelog/manual completeness, screenshots, and product-facing release sign-off.

- Aithena is an on-prem book-library search product: Python/FastAPI services, React/Vite UI, Docker Compose, Solr full-text search, multilingual embeddings, PDF processing, upload, filtering, highlighting, and admin flows.
- Docs layout matters: release notes in `docs/release-notes/`, validation in `docs/test-reports/`, guides in `docs/guides/`, manuals in `docs/user-manual.md` and `docs/admin-manual.md`, screenshots in `docs/images/`.
- Release gates are docs-first: release notes, test report, changelog, manuals, screenshots, and explicit PM verdict.
- Operator constraints are product contracts and must be published where operators will read them.

## Active Patterns

- Scope must be defined before release-gate issues are created.
- Infrastructure releases need the same migration/rollback/operator rigor as feature releases.
- Test reports scale best when the checklist/framework exists before final CI evidence.
- Breaking changes require justification, migration, rollback guidance, and honest limitations.
- Separate product sign-off from technical merge blockers; document both.

## Recent Learnings

### 2026-06-04 — v2.3.0 gate prep
- Maintenance/infrastructure releases still need explicit operator-responsibility sections in release notes and the admin manual.
- Accepted-risk decisions only count if the constraints are published in operator-facing docs.

### 2026-06-04 — Product constraints
- "Do not publish ZooKeeper ports" and "maintain Solr BasicAuth" are product-level release constraints, not mere deployment tips.
- Add a gate check that every production constraint is documented.

### 2026-06-04 — Test report coordination
- Lambert’s framework-first / evidence-later reporting pattern is reusable for complex releases because it exposes blockers before final CI evidence exists.

### 2026-06-04 / 2026-06-03 — Scope and sign-off timing
- Ripley should define scope before Newt opens release-gate issues.
- Human sign-off can block a release without freezing unrelated engineering work on the next cycle.
