# Brett — Docker Hardening Implementation (#52)

**Date:** 2026-03-15  
**Author:** Brett (Infrastructure Architect)  
**Status:** Implemented (PR #196)

## Decision

Implemented production Docker hardening specification for all 20+ services in docker-compose.yml per Phase 4 #52 requirements.

## What Changed

### 1. Critical Port Conflict Fix
- Standardized embeddings-server internal port to 8080 (removed conflicting PORT=8085 env var)
- Updated all references: EMBEDDINGS_PORT, EMBEDDINGS_URL
- Resolves health check failures caused by port mismatch

### 2. Health Checks (8 new)
Added health checks to all user-facing services:
- embeddings-server, solr-search: HTTP health endpoints (wget)
- document-lister, document-indexer: Process checks (pgrep)
- aithena-ui, streamlit-admin, redis-commander, nginx: HTTP checks

### 3. Production Hardening (all services)
- **Restart policies**: unless-stopped for critical services, on-failure for workers
- **Resource limits**: Memory 128m-2g, CPU reservations 0.5-1.0 core
- **Graceful shutdown**: 60s Solr/ZK, 30s Redis/RabbitMQ, 10s others
- **Log rotation**: json-file driver, 10m × 3 files (30MB max per service)
- **Dependency fixes**: 5 services upgraded to service_healthy conditions

### 4. Production Deployment Guide
Created comprehensive docs/deployment/production.md covering startup order, resource requirements, troubleshooting, backup/restore, and production checklist.

## Key Design Decisions

1. **Tiered Startup Order**: 5-tier dependency graph ensures correct initialization (infra → search → apps → UIs → ingress)
2. **Conservative Health Checks**: 60s start_period for embeddings (model loading), 30s for ZK/Solr (cluster formation)
3. **Resource Headroom**: 2-2.5x observed usage limits prevent OOM while allowing bursting
4. **nginx Last**: Reverse proxy starts LAST after all upstreams healthy → zero 502 errors on cold start
5. **Log Rotation**: 30MB cap per service (600MB total) prevents disk exhaustion in production

## System Requirements

- **Memory**: ~15GB limits, ~8GB reserved (16GB+ host recommended)
- **CPU**: 8+ cores (3 Solr + 1 embeddings + 0.5 search + overhead)
- **Disk**: 100GB+ SSD for infrastructure + library size

## Rationale

Production deployments require:
- **Resilience**: Health checks + restart policies prevent silent failures
- **Resource control**: Limits prevent memory exhaustion cascade
- **Observability**: Log rotation + graceful shutdown enable debugging
- **Zero-downtime**: Dependency ordering eliminates 502 errors on startup

Without these protections, production systems experience:
- Silent service failures (no health monitoring)
- OOM cascade (one service kills neighbors)
- Disk fill from unbounded logs
- 502 errors during restarts

## Impact

- **Operators**: Full production deployment guide with troubleshooting
- **Developers**: No changes to docker-compose.override.yml (dev workflow intact)
- **CI/CD**: Longer startup time (3-5min cold start vs 1-2min), but deterministic
- **Production**: Zero-downtime deployments, predictable resource usage

## Future Considerations

1. **Security hardening** (deferred to v0.7.0):
   - RabbitMQ credentials (change from guest/guest)
   - Redis password (add requirepass)
   - Admin endpoint auth (nginx /admin/* protection)

2. **Monitoring integration** (future):
   - Export health check metrics to Prometheus
   - Alert on service_unhealthy events
   - Dashboard for resource usage trends

3. **Horizontal scaling** (future):
   - Document how to add Solr nodes 4-N
   - Load balancer config for multi-replica solr-search
   - Queue autoscaling for document-indexer

## References

- Spec: `.squad/decisions.md` section "Infrastructure Specification — Docker Hardening (#52)"
- PR: #196 (squad/52-docker-hardening → dev)
- Docs: `docs/deployment/production.md`
- History: `.squad/agents/brett/history.md` (2026-03-15 entry)
