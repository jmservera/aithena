---
name: "nginx-reverse-proxy"
description: "nginx reverse proxy patterns for Docker Compose multi-service apps: routing, health checks, startup ordering, SSL overlay"
domain: "nginx, docker, infrastructure, networking"
confidence: "high"
source: "earned — aithena nginx config managing 9+ upstream services, SSL extraction to overlay"
author: "Brett"
created: "2026-07-25"
last_validated: "2026-07-25"
---

## Context

nginx is the single entry point for all aithena traffic. It reverse-proxies the React frontend, FastAPI backend, Solr admin, RabbitMQ management, Streamlit admin, and Redis Commander. Getting the configuration right is critical for zero-downtime startup and clean service isolation.

## Pattern 1: Single Port Publisher

**Rule:** Only nginx publishes host ports. All other services use `expose:` only.

```yaml
# docker-compose.yml
nginx:
  ports:
    - "80:80"
    - "443:443"   # only in ssl overlay

solr-search:
  expose:
    - "8080"       # internal only — no host binding

solr1:
  expose:
    - "8983"       # internal only
```

**Why:** Prevents port collisions (e.g., zoo1 admin-server on 8080 vs solr-search on 8080), simplifies firewall rules, and centralizes TLS termination.

## Pattern 2: Health Endpoint

nginx includes a lightweight health endpoint for Docker health checks:

```nginx
location /health {
    access_log off;
    return 200 "healthy\n";
    add_header Content-Type text/plain;
}
```

Docker Compose health check:
```yaml
nginx:
  healthcheck:
    test: ["CMD-SHELL", "curl -fsS http://localhost/health || exit 1"]
    interval: 10s
    timeout: 5s
    retries: 5
    start_period: 10s
```

## Pattern 3: Upstream Routing Map

| Path | Upstream | Notes |
|------|----------|-------|
| `/` | `aithena-ui:5173` | React dev server (Vite) |
| `/v1/` | `solr-search:8080` | FastAPI search API |
| `/admin/solr/` | `solr1:8983` | Solr admin UI |
| `/rabbitmq/` | `rabbitmq:15672` | RabbitMQ management |
| `/streamlit/` | `admin:8501` | Streamlit admin dashboard |
| `/redis/` | `redis-commander:8081` | Redis Commander UI |
| `/health` | local | nginx health check |

**Key:** Each upstream path must handle trailing slashes and websocket upgrades (for Vite HMR and Streamlit).

## Pattern 4: Startup Ordering (Last-to-Start)

nginx depends on all upstream services being healthy. It must start **last** to avoid 502 errors during cold start.

```yaml
nginx:
  depends_on:
    solr-search:
      condition: service_healthy
    aithena-ui:
      condition: service_healthy
    admin:
      condition: service_healthy
    rabbitmq:
      condition: service_healthy
```

**Rationale:** If nginx starts before upstreams are ready, clients see 502 Bad Gateway. The `service_healthy` condition prevents this.

## Pattern 5: SSL as Compose Overlay

SSL/TLS (certbot) is optional. The base compose file runs HTTP-only. SSL is added via overlay:

```bash
# HTTP-only (default):
docker compose up -d

# With SSL:
docker compose -f docker-compose.yml -f docker-compose.ssl.yml up -d
```

**Why overlay instead of profiles:** Docker Compose profiles can disable the certbot service but can't conditionally add volume mounts or port bindings to nginx. The overlay cleanly isolates:
- certbot service definition
- nginx SSL volume mounts (`/etc/letsencrypt`, `/var/www/certbot`)
- Port 443 binding
- SSL-specific nginx config snippets

## Anti-Patterns

- **Don't publish host ports on backend services** — route everything through nginx
- **Don't start nginx before upstreams are healthy** — causes 502 errors
- **Don't use `proxy_pass` without trailing slash consistency** — causes path rewriting bugs
- **Don't put SSL config in the base compose file** — use overlay for optional features
- **Don't skip `access_log off` on health endpoints** — pollutes logs with high-frequency noise

## References

- `src/nginx/` — nginx configuration files
- `docker-compose.yml` — nginx service definition and dependencies
- `docker-compose.ssl.yml` — SSL overlay with certbot
- Skill `docker-health-checks` — health check patterns for all services
