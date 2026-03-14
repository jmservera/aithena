# Kane — History

## Project Context
- **Project:** aithena — Book library search engine
- **User:** jmservera
- **Joined:** 2026-03-14 as Security Engineer
- **Current security state:** CodeQL configured (JS/TS + Python), Mend/WhiteSource for dependency scanning, 64 Dependabot vulnerabilities flagged on default branch (3 critical, 12 high)
- **Planned work:** Issues #88 (bandit CI), #89 (checkov CI), #90 (zizmor CI), #97 (OWASP ZAP guide), #98 (security baseline tuning)

## Learnings
- Initial Bandit sweeps against this repo pick up the tracked `document-indexer/.venv/` tree and generate third-party HIGH findings; exclude `.venv`/`site-packages` when triaging first-party code.
- Local Checkov 3.2.508 does not accept `--framework docker-compose`; Dockerfile scanning works, but `docker-compose.yml` currently needs manual review or an alternate supported scan mode.
- GitHub code scanning currently shows three open medium-severity CodeQL alerts on `.github/workflows/ci.yml`, all for missing `permissions:` blocks on CI jobs.
- GitHub Dependabot currently exposes four open alerts: two critical `qdrant-client` findings (`qdrant-search`, `qdrant-clean`), one high `braces` finding in `aithena-ui/package-lock.json`, and one medium `azure-identity` finding in `document-lister/requirements.txt`.
- GitHub secret scanning API returns 404 for this repository, which strongly suggests the feature is disabled rather than merely empty.
