# Decision: Health Check Strategy for Non-HTTP Workers

**Author:** Brett (Infrastructure Architect)
**Date:** 2026-03-24
**Status:** IMPLEMENTED
**PR:** #1055 (Closes #1009)

## Context

document-lister and document-indexer are pure message-queue workers (RabbitMQ producer/consumer). They expose no HTTP server and no ports. Issue #1009 requested upgrading them from `pgrep` to HTTP health checks.

## Decision

Keep `pgrep` for non-HTTP workers but tighten the pattern from generic `python` to the actual module name (`document_lister`, `document_indexer`). Adding HTTP endpoints would require application code changes and a new dependency (e.g., a health-check sidecar thread), which is disproportionate for these simple workers.

For services that already serve HTTP (aithena-ui, nginx, solr-search, embeddings-server), dedicated `/health` endpoints are the standard — aithena-ui now has one.

## Implication for Future Services

If a new Python worker service is added without an HTTP server, use `pgrep -f <module_name>` as the health check. If the team wants deeper liveness checks (e.g., RabbitMQ connection alive), that requires an application-level health mechanism and should be a Parker task.
