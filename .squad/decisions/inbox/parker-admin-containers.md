# Parker — Admin Containers Aggregation Decision

## Context
Issue #202 adds `GET /v1/admin/containers` in `solr-search` to summarize the running stack without using Docker SDK access.

## Decision
- Reuse the existing `/v1/status` probing approach inside `solr-search`: TCP reachability for infrastructure, Solr cluster probing for Solr, and direct HTTP `/version` calls for HTTP services.
- For non-HTTP repo services (`streamlit-admin`, `aithena-ui`, `document-indexer`, `document-lister`), report shared build metadata from `VERSION` and `GIT_COMMIT` injected into the repo's container builds.
- Mark worker processes as `status: "unknown"` instead of `down` because they do not expose stable network probes in this environment and Docker runtime label inspection is intentionally unavailable.

## Why
This keeps the endpoint fast, deterministic, and compatible with codespaces where Docker is unavailable, while still surfacing useful release metadata for the whole stack.
