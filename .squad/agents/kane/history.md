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
- `docker-compose.yml` currently publishes Redis (`6379`), RabbitMQ (`5672`/`15672`), Solr (`8983`/`8984`/`8985`), ZooKeeper (`18080`/`2181`/`2182`/`2183`), embeddings (`8085`), search (`8080`), and nginx (`80`/`443`) directly on the host; this is broader than the intended nginx-only production ingress.
- `nginx/default.conf` proxies `/admin/streamlit/`, `/admin/solr/`, `/admin/rabbitmq/`, `/admin/redis/`, `/v1/`, `/documents/`, and `/solr/` with no `auth_basic`, `auth_request`, or other access-control layer, so nginx is currently a convenience router rather than a security boundary.
- The admin app defaults `RABBITMQ_USER`/`RABBITMQ_PASS` to `guest`/`guest` (`admin/src/pages/shared/config.py`), while Redis has no password/ACL and Solr has no auth configured; the dominant risk in this stack is insecure defaults plus exposed control-plane services, not leaked API keys in Compose.
