# 2026-03-22T17:06Z — Brett Security Hardening Orchestration

**Milestone:** Infrastructure Security Hardening  
**Status:** COMPLETE (3 PRs merged)

## Accomplishments

### 1. ZooKeeper AdminServer Hardening (Issue #913)
- **PR:** #928
- **Status:** Merged to dev
- **Changes:**
  - Added `ZOO_CFG_EXTRA: "admin.enableServer=false"` to all 3 ZK nodes
  - Applied to both docker-compose.yml and docker/compose.prod.yml
  - Removed port 8080 expose and host mapping from ZK services
- **Rationale:** AdminServer exposes cluster topology and operational commands; not needed for SolrCloud operations

### 2. Non-Root Container Standard (Issue #912)
- **PR:** #930
- **Status:** Merged to dev
- **Services Updated:**
  - document-indexer: Alpine → addgroup/adduser pattern
  - document-lister: Alpine → addgroup/adduser pattern
  - aithena-ui: Non-root user pattern
  - solr-search: Already used gosu for bind-mount ownership
- **Standard Patterns Established:**
  - Alpine: `addgroup -S -g 1000 app && adduser -S -u 1000 -G app app` + `USER app`
  - Debian: `groupadd --system --gid 1000 app && useradd --system --uid 1000 --gid app --create-home app` + `USER app`
  - nginx: Built-in `nginx` user with non-privileged port (8080)
- **Rationale:** Container security hardening; reduces attack surface per D-2 finding

### 3. HSTS and Security Headers (Issue #917)
- **PR:** #932
- **Status:** Merged to dev
- **Changes:**
  - Created new `ssl.conf.template` with dedicated HTTPS server block
  - Added Strict-Transport-Security header (HSTS)
  - Added Referrer-Policy header
  - Set `server_tokens off` to hide nginx version
  - All location blocks re-declare security headers to prevent nginx suppression
  - HSTS only sent over HTTPS (separate server block, not HTTP)
  - **Required:** NGINX_HOST environment variable when using SSL overlay
- **Rationale:** Prevents SSL stripping attacks; hardens response headers per infrastructure security audit

## Metrics

- **Issues closed:** 3 (#913, #912, #917)
- **PRs merged:** #928, #930, #932
- **Docker containers hardened:** 5+ services (all non-root, all security headers enforced)
- **New standardization:** Non-root container patterns now codified for future development

## Decision Recorded

Brett established container security standards (`.squad/decisions.md`) for future Dockerfiles:
- Non-root user enforcement
- Bind-mount ownership patterns
- nginx TLS configuration requirements
