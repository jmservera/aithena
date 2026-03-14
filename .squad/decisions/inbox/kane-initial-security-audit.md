### Security Audit — Initial Findings
**Date:** 2026-03-14
**Author:** Kane (Security Engineer)

#### Summary
- bandit: 1,688 raw findings (30 HIGH / 54 MEDIUM / 1,604 LOW). All 30 HIGH findings came from the checked-in `document-indexer/.venv/` third-party environment; first-party code triage is 0 HIGH / 4 MEDIUM / 136 LOW.
- checkov: 555 passed, 18 failed on Dockerfiles. `checkov --framework docker-compose` is not supported by local Checkov 3.2.508, so `docker-compose.yml` was reviewed manually.
- Dependabot: 0 open alerts via GitHub API (`gh api repos/jmservera/aithena/dependabot/alerts`).
- Actions: 15 supply chain risks (14 tag-pinned action refs across 5 workflows, plus `ci.yml` missing explicit `permissions:`).
- Dockerfiles: 14 direct hardening issues from manual review (8 images run as root, 6 `pip install` commands missing `--no-cache-dir`; no `latest` tags, no `.env`/secret copies found).

#### Critical (fix immediately)
- No confirmed critical findings in first-party application code.
- Raw Bandit HIGH results are scanner noise from the tracked `document-indexer/.venv/` tree (`pdfminer`, `pip`, `requests`, `redis`, etc.). This should be excluded from CI scanning or removed from the repository so real findings are not buried.

#### High (fix this sprint)
- **Pin GitHub Actions to commit SHAs.** Every workflow uses floating tags (`actions/checkout@v4`, `actions/setup-python@v5`, `actions/github-script@v7`) instead of immutable SHAs, leaving CI vulnerable to supply-chain tag retargeting.
- **Tighten workflow token scope.** `.github/workflows/ci.yml` has no explicit `permissions:` block, so it falls back to repository defaults.
- **Stop running containers as root.** All 8 Dockerfiles lack a `USER` directive (`document-indexer/`, `document-lister/`, `solr-search/`, `qdrant-search/`, `qdrant-clean/`, `embeddings-server/`, `llama-server/`, `llama-base/`).
- **Reduce attack surface in Compose.** `docker-compose.yml` publishes many internal service ports (Redis, RabbitMQ, ZooKeeper, Solr nodes, embeddings API) to the host, and both `zoo1` and `solr-search` map host port `8080`, creating an avoidable exposure/collision.
- **Improve Solr resilience.** `document-indexer` (`SOLR_HOST=solr`) and `solr-search` (`SOLR_URL=http://solr:8983/solr`) are pinned to a single Solr node despite the SolrCloud topology.

#### Medium (fix next sprint)
- **Add container healthchecks.** Checkov’s 18 Dockerfile failures are primarily missing `HEALTHCHECK` instructions across all 8 images; this also weakens Compose readiness.
- **Bandit first-party MEDIUMs:** four `B104` findings for binding FastAPI servers to `0.0.0.0` in `embeddings-server/main.py`, `qdrant-clean/main.py`, `qdrant-search/main.py`, and `solr-search/main.py`. This is expected for containers but should be explicitly accepted/baselined.
- **Harden package installs.** `document-lister/Dockerfile`, `qdrant-search/Dockerfile`, `qdrant-clean/Dockerfile`, `llama-server/Dockerfile`, and two `python3 -m pip install` steps in `llama-base/Dockerfile` omit `--no-cache-dir`.
- **Avoid unnecessary package managers.** Checkov flags `apt` usage in `llama-server/Dockerfile` and `llama-base/Dockerfile`; review whether slimmer/prebuilt bases can remove build tooling from runtime images.
- **Compose hardening gaps.** ZooKeeper/Solr services lack health-based startup ordering and ZooKeeper restart policies; the repo’s SolrCloud operations skill already calls these out as risks.

#### Low / Accepted Risk
- Bandit LOW findings are almost entirely `B101` test assertions in pytest suites; acceptable if tests stay out of production images and CI baselines them.
- No GitHub Actions shell-injection pattern was found using `github.event.*.body` inside `run:` blocks.
- No secrets were obviously echoed in workflow logs, and no Dockerfiles copy `.env` files into images.
- No Dockerfile uses a literal `latest` tag, though most base images are still mutable tags rather than digests.
- The current Dependabot API result is clean, but it conflicts with the historical note in `.squad/agents/kane/history.md`; verify in the GitHub UI if this looks unexpected.

#### Recommended Next Steps
1. Remove or ignore tracked virtualenv/vendor trees (especially `document-indexer/.venv/`) before enabling Bandit in CI; baseline the 4 accepted `B104` findings separately.
2. Pin every GitHub Action to a full commit SHA and add explicit least-privilege `permissions:` to `ci.yml`.
3. Add `USER` and `HEALTHCHECK` instructions to every Dockerfile, then wire Compose `depends_on` to health where possible.
4. Reduce published host ports, move internal services behind the Compose network only, and stop pinning application traffic to a single Solr node.
5. Add `--no-cache-dir` to remaining pip installs and review `llama-*` images for smaller, less privileged runtime stages.
6. Re-run Compose scanning with a supported policy set/tooling path (current Checkov 3.2.508 rejects `docker-compose` as a framework) and reconcile the Dependabot baseline with GitHub UI state.
