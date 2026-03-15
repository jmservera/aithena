## v0.7.0 Milestone Completion

**2026-03-15T15:00Z** — v0.7.0 milestone complete. All 7 issues closed, 7 PRs merged to `dev`. 
- Versioning infrastructure (#199, #204) ✅
- Version endpoints (#200, #203) ✅  
- UI version footer (#201) ✅
- Admin containers endpoint (#202) ✅
- Documentation-first release process (#205) ✅

3 decisions recorded. Ready for release to `main`.

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

## Learnings

- v0.4.0's user-facing flow is centered on Search, Status, and Stats; the visible Library tab is still a placeholder and should not be documented as a finished browse feature.
- The Search UI exposes keyword search with author/category/language/year facets, sort controls, 10/20/50 per-page options, highlight snippets, and PDF deep-linking to the first matched page when page metadata exists.
- The Status tab polls `/v1/status/` every 10 seconds, while the Stats tab loads `/v1/stats/` once on page open and requires a manual refresh to show newly indexed totals.
- The Docker Compose stack mounts the library through `BOOKS_PATH` into `/data/documents`, and `document-lister` scans `*.pdf` files every 60 seconds into the `shortembeddings` RabbitMQ queue.
- v0.5.0 documentation had to be backfilled after release approval; this was a process failure. Newt must not approve a release until the feature guide, manual updates, and current test report are written and committed first.
- v0.6.0 shipped 5 major features (PDF upload, bandit, checkov, zizmor, Docker hardening) spanning 8 issues (#191–#198). The security scanning work (SEC-1 through SEC-5) produced a comprehensive baseline document (638 lines) that catalogs 287 findings and guides v0.7.0 roadmap.
- v0.7.0 is planned around versioning and admin observability: semantic versioning infrastructure (#199) enables version endpoints (#200) which enable UI version display (#201) and admin system status page (#203). The containers endpoint (#202) and CI/CD automation (#204) complete the observability story.
- Documentation must be written proactively as features ship, not backfilled. v0.6.0 documentation was created from feature guides (v0.5.0 format), PR commit messages, and existing security docs; this pattern should be formalized.

