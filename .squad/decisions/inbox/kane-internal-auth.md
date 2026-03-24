# Decision: Simplify internal service authentication

**Author:** Kane (Security Specialist)
**Date:** 2026-03-24
**Status:** APPROVED by Juanma (2026-03-24)

## Context

Aithena runs Redis, ZooKeeper, and Solr as internal services in a Docker Compose network. None expose ports to the host by default. The current auth setup:
- **Redis:** Password auth via REDIS_PASSWORD env var
- **ZooKeeper:** SASL DIGEST-MD5 auth (BROKEN on ZK 3.9 + Java 17 — causes NullPointerException)
- **Solr:** BasicAuth plugin with admin/readonly users

ZK SASL has been the #1 source of release failures across v1.12–v1.14, responsible for ~30% of all release blocks.

## Threat Model

Internal services communicate over a Docker bridge network. Attack surface:
- **Host compromise:** If the host is compromised, all container secrets are already exposed via env vars and Docker inspect. Internal passwords add no defense.
- **Container escape:** Same — the attacker has access to all env vars.
- **Network sniffing:** Docker bridge traffic is local. An attacker who can sniff it already has host access.

## Recommendations

| Service | Current | Recommendation | Rationale |
|---------|---------|---------------|-----------|
| Redis | Password auth | **DROP** | No external ports, password in env vars anyway |
| ZooKeeper | SASL DIGEST-MD5 | **DROP** | Broken, causes release failures, no security benefit |
| Solr | BasicAuth | **KEEP** | Solr exposes the admin UI which may be port-forwarded for debugging; BasicAuth prevents accidental writes |

## Impact

- Remove: docker-compose.nosasl.yml (no longer needed)
- Remove: ZK JAAS configs, entrypoint-sasl.sh scripts
- Remove: Redis password from all service configs
- Keep: Solr security.json, BasicAuth credentials
- Estimated cleanup: ~200 lines of YAML/shell removed
- Release stability improvement: eliminates SASL-related failure mode entirely
