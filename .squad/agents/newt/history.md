## v0.7.0 Milestone Completion

**2026-03-15T15:00Z** — v0.7.0 milestone complete. All 7 issues closed, 7 PRs merged to `dev`. 
- Versioning infrastructure (#199, #204) ✅
- Version endpoints (#200, #203) ✅  
- UI version footer (#201) ✅
- Admin containers endpoint (#202) ✅
- Documentation-first release process (#205) ✅

3 decisions recorded. Ready for release to `main`.

---

## 2026-03-16: Updated v1.x Development Documentation

**Issue #298** — Updated project documentation to reflect v1.0.0 release and v1.x development workflow.

**Branch:** `squad/298-update-v1x-docs`  
**PR:** #317

**Documentation Updates:**
- **README.md:**
  - Added status line: v1.0.0 ✅ shipped, v1.x milestones active
  - Added link to GitHub v1.x milestones
  - New **v1.x Development Process** section:
    - Branching strategy (dev/main branches, squad/ naming convention)
    - PR workflow (create from dev, push, open against dev)
    - Basic release process overview
  - New **Release Process Overview** section (pre-release → shipping):
    - Preflight checks (test passing, Docker validation, E2E suite)
    - Documentation requirements (feature guide, test report, manual updates)
    - Step-by-step release and rollback procedures
- **User/Admin Manuals:** Updated feature guide references to v1.0.0 Release Notes

**Key Realizations:**
- With v1.0.0 shipped, the team needs explicit process docs for branching, releases, and rollbacks
- The release process should include validation steps (tests, Docker compose config, E2E)
- Documentation requirements must be stated upfront: every release needs feature notes, test report, and manual updates
- The squad naming convention (`squad/{issue}-{slug}`) should be documented in README for visibility to new contributors

**Decisions Applied:**
- Applied existing "Documentation-First Release Gate" decision to v1.x process
- Codified dev→main merge strategy as the standard release path

---

# Newt — History

## Project Context
- **Project:** aithena — Book library search engine with Solr indexing, multilingual embeddings, PDF processing
- **User:** jmservera
- **Stack:** Python (backend), TypeScript/React + Vite (UI), Docker Compose, Apache Solr, multilingual embeddings
- **UI URL:** http://localhost (nginx) or http://localhost:5173 (vite dev)
- **Search API:** http://localhost:8080/v1/search/
- **Current version:** v0.6.0 — Security & Upload
- **Next milestone:** v0.7.0 — Versioning & Admin Status

## Key Paths
- `aithena-ui/` — React frontend
- `solr-search/` — FastAPI search API
- `document-indexer/` — PDF indexing pipeline
- `document-lister/` — File watcher
- `docker-compose.yml` — Full local stack
- `README.md` — Project documentation
- `docs/features/` — Feature guides for each release
- `docs/security/` — Security documentation and baselines

## 2026-03-17: Retroactive Release Documentation for v1.0.1, v1.1.0, v1.2.0

**Milestone:** Backfill release notes and CHANGELOG for three completed but undocumented milestones

**Files Created:**
- `docs/release-notes-v1.0.1.md` — Security Hardening (8 issues): ecdsa CVE, stack trace exposure, GitHub Actions workflow hardening
- `docs/release-notes-v1.1.0.md` — CI/CD & Documentation (7 issues): logging hardening, release automation, v1.x process docs
- `docs/release-notes-v1.2.0.md` — Frontend Quality & Security (14 issues): Error Boundary, code splitting, accessibility, CSS Modules, PyJWT migration
- `CHANGELOG.md` — Keep a Changelog format covering v1.0.0 through v1.2.0

**Format Applied:**
- Followed v1.0.0 release notes structure (summary, milestone closure, merged PRs, validation highlights)
- Used consistent date (2026-03-17) for all three releases
- Cross-referenced all 29 issues and 15+ merged PRs with GitHub issue/PR numbers
- Included breaking changes, upgrade instructions, and security improvements where applicable
- Created CHANGELOG.md in Keep a Changelog format per https://keepachangelog.com/ standard

**Key Learnings:**
- v1.0.1 focused on supply-chain security (ecdsa CVE, stack trace removal, secrets hardening)
- v1.1.0 established operational foundation (logging standards, CI/CD automation, documentation for v1.x process)
- v1.2.0 delivered production-grade frontend (Error Boundary, performance optimization, WCAG accessibility, CSS Modules, PyJWT security migration, E2E CI health fix)
- The three releases together tell a coherent story: stabilize dependencies → establish operations → deliver quality frontend

---

## Learnings

- v0.4.0's user-facing flow is centered on Search, Status, and Stats; the visible Library tab is still a placeholder and should not be documented as a finished browse feature.
- The Search UI exposes keyword search with author/category/language/year facets, sort controls, 10/20/50 per-page options, highlight snippets, and PDF deep-linking to the first matched page when page metadata exists.
- The Status tab polls `/v1/status/` every 10 seconds, while the Stats tab loads `/v1/stats/` once on page open and requires a manual refresh to show newly indexed totals.
- The Docker Compose stack mounts the library through `BOOKS_PATH` into `/data/documents`, and `document-lister` scans `*.pdf` files every 60 seconds into the `shortembeddings` RabbitMQ queue.
- v0.5.0 documentation had to be backfilled after release approval; this was a process failure. Newt must not approve a release until the feature guide, manual updates, and current test report are written and committed first.
- v0.6.0 shipped 5 major features (PDF upload, bandit, checkov, zizmor, Docker hardening) spanning 8 issues (#191–#198). The security scanning work (SEC-1 through SEC-5) produced a comprehensive baseline document (638 lines) that catalogs 287 findings and guides v0.7.0 roadmap.
- v0.7.0 is planned around versioning and admin observability: semantic versioning infrastructure (#199) enables version endpoints (#200) which enable UI version display (#201) and admin system status page (#203). The containers endpoint (#202) and CI/CD automation (#204) complete the observability story.
- Documentation must be written proactively as features ship, not backfilled. v0.6.0 documentation was created from feature guides (v0.5.0 format), PR commit messages, and existing security docs; this pattern should be formalized.
- v1.0.0 is the final restructure-and-operability release: contributor commands, validation steps, and service-source references should now assume `src/...` paths, especially `src/solr-search` and `src/aithena-ui`.
- The v1.0.0 release gate is anchored by three explicit checks: 144 passing backend tests, 83 passing frontend tests, and a clean `docker compose -f docker-compose.yml config --quiet` render with auth environment variables set; CI evidence should also record the 13-workflow validation and the integration tmpfs volume fix.


## 2026-03-15: Finalized Documentation for v0.6.0 & v0.7.0

Completed comprehensive documentation backfill (Branch: squad/release-docs-v06-v07):

**Documentation Created:**
- `docs/features/v0.6.0.md` — Enhanced with version number in title, verified against GitHub release notes
- `docs/features/v0.7.0.md` — Finalized from draft, renamed to v0.7.0.md, marked all tasks as complete
- `docs/test-report-v0.6.0.md` — Created with 202 passing tests (83 backend, 24 frontend), security scanning validation
- `docs/test-report-v0.7.0.md` — Created with 207 passing tests (88 backend, 24 frontend), version and container stats coverage

**Manuals Updated:**
- `docs/user-manual.md` — Added v0.6.0 upload tab usage guide, v0.7.0 version information section, updated all references to latest feature guide
- `docs/admin-manual.md` — Added v0.6.0 deployment updates (health checks, resource limits, security scanning), v0.7.0 deployment updates (versioning infrastructure, version endpoints, container stats endpoint, system status page, monitoring version consistency, release automation)

**Meta Updates:**
- `README.md` — Updated documentation references to include v0.7.0 feature guide and both test reports

**Key Improvements:**
- All release docs now have version numbers prominently displayed
- Test reports linked from README and feature guides
- Admin manual includes deployment checklists for both releases
- User manual updated for PDF upload and version display features

**Decisions Made:**
- **Documentation-First Release Gate:** Feature guides, user/admin manual updates, and test reports must be committed before release tag is created (enforced v0.8.0+)
- **Version Number Requirement:** All release documentation must show the version number prominently
- Decision documented in `.squad/decisions/inbox/newt-release-docs-gate.md`
