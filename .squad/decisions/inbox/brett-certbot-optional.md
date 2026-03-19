# Decision: Certbot container is optional via docker-compose.ssl.yml

**Author:** Brett (Infrastructure Architect)
**Date:** 2025-07-18
**Status:** Implemented

## Context

The certbot service and its Let's Encrypt volumes were always started by
`docker compose up`, even for deployments that run behind a reverse proxy or
on local networks without TLS. This forced operators to create
`/source/volumes/certbot-data/{conf,www}` directories even when they had no
use for them.

## Decision

All certbot/SSL configuration has been moved to `docker-compose.ssl.yml`:

- **HTTP-only (default):** `docker compose up -d`
- **With SSL:** `docker compose -f docker-compose.yml -f docker-compose.ssl.yml up -d`

The overlay adds port 443, certbot volume mounts on nginx, the periodic nginx
reload command, and the certbot sidecar container.

## Rationale

Docker Compose profiles (`profiles: ["ssl"]`) can disable services but cannot
conditionally add volume mounts or ports to other services. Since nginx needed
certbot's bind-mount volumes, profiles alone would still require the host
directories to exist. A compose overlay file cleanly isolates all SSL config.

## Impact

- **New HTTP deployments:** No change needed — `docker compose up` works.
- **Existing SSL deployments:** Add `-f docker-compose.ssl.yml` to all
  `docker compose` commands.
- Docs updated: production.md, quickstart.md, admin-manual.md,
  failover-runbook.md.
