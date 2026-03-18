---
name: "docker-health-checks"
description: "Design and debug Docker Compose health checks with start_period tuning"
domain: "docker, infrastructure, reliability"
confidence: "high"
source: "Brett's PR #356 (solr-search), #424 (redis-commander), #403 (ZooKeeper) experience"
author: "Brett"
created: "2026-07-24"
last_validated: "2026-07-24"
---

## Context

Health checks are critical for orchestration reliability. Aithena uses them to:
- Gate service startup order (depends_on conditions)
- Detect hung/degraded containers before problems cascade
- Support zero-downtime deployments

This skill captures patterns proven on 8 aithena services.

## Pattern: Design Health Checks

### Step 1: Choose Health Check Type

| Scenario | Command Pattern | Example |
|----------|-----------------|---------|
| HTTP service (curl/wget available) | `CMD-SHELL "wget http://localhost:PORT/endpoint"` | solr-search, embeddings-server |
| HTTP service (no curl/wget) | `CMD-SHELL "node -e 'http.get(...)'"` | redis-commander, nodejs services |
| Python worker (no HTTP) | `CMD "pgrep -f python"` | document-lister, document-indexer |
| Distributed system | `CMD-SHELL "echo ruok \| nc localhost 2181"` | zoo1, zoo2, zoo3 |

### Step 2: CMD vs CMD-SHELL

**❌ WRONG — CMD with complex one-liner:**
```yaml
healthcheck:
  test:
    - CMD
    - node
    - -e
    - "require('http').get(...)"
```
Problem: Array format, no shell expansion, escaping chaos.

**✅ RIGHT — CMD-SHELL for one-liners:**
```yaml
healthcheck:
  test:
    - CMD-SHELL
    - |
      node -e "
        require('http').get('http://localhost:8080', res => process.exit(res.statusCode === 200 ? 0 : 1))
        .on('error', () => process.exit(1))
      " || exit 1
  timeout: 5s
  retries: 5
  start_period: 30s
  interval: 10s
```

### Step 3: Tune start_period by Service Type

| Service | Load Time | start_period |
|---------|-----------|--------------|
| Embeddings (ML model) | 30-60s | 60s |
| SolrCloud (cluster formation) | 20-40s | 30s |
| Database migrations | 10-15s | 20s |
| HTTP API (basic) | 3-5s | 10s |
| Worker process | 2-3s | 10s |
| Redis/cache | <1s | 10s |
| CI cold-start (2-3x slower) | add overhead | multiply by 2-3x |

**Key insight:** Measure worst-case initialization, pad by 50%, test in CI.

### Step 4: Handle Timeouts

**Problem:** Network requests with no timeout block health checks indefinitely.

**Solution:** Always set explicit timeout:

```yaml
healthcheck:
  test:
    - CMD-SHELL
    - "curl --max-time 5 http://localhost:8080/health || exit 1"
  timeout: 10s
```

## Anti-patterns & Pitfalls

### ❌ Broken Pipe in Health Checks

**Problem:** Piping to grep causes SIGPIPE:
```yaml
test:
  - CMD-SHELL
  - "echo ruok | nc localhost 2181 | grep -Eq 'imok|leader'"
```

**Fix:** Simpler check:
```yaml
test:
  - CMD-SHELL
  - "echo ruok | nc localhost 2181 | grep -q imok || exit 1"
```

### ❌ No Timeout on Network Calls

**Fix:** Add `--max-time` for curl or timeout handling for custom scripts.

### ❌ start_period Too Short

**Fix:** Measure initialization, pad by 50-100%:
- Embeddings: 30-60s → `start_period: 60s`
- SolrCloud: 20-40s → `start_period: 30s`
- HTTP API: 3-5s → `start_period: 10s`

## Real-World Examples

### embeddings-server (ML Model)

```yaml
embeddings-server:
  healthcheck:
    test:
      - CMD-SHELL
      - "wget --quiet --tries=1 --spider http://localhost:8080/health || exit 1"
    timeout: 5s
    interval: 10s
    retries: 5
    start_period: 60s
```

### redis-commander (Node.js, no wget)

```yaml
redis-commander:
  healthcheck:
    test:
      - CMD-SHELL
      - |
        node -e "const req = require('http').get({hostname: 'localhost', port: 8081, path: '/'}, res => {
          process.exit([200, 301, 302, 401].includes(res.statusCode) ? 0 : 1);
        });
        req.setTimeout(5000, () => { req.abort(); process.exit(1); });
        req.on('error', () => process.exit(1));" || exit 1
    timeout: 10s
    interval: 10s
    retries: 5
    start_period: 30s
```

### ZooKeeper (Distributed System)

```yaml
zoo1:
  healthcheck:
    test:
      - CMD-SHELL
      - "echo ruok | nc localhost 2181 | grep -q imok || exit 1"
    timeout: 5s
    interval: 10s
    retries: 5
    start_period: 30s
```

## References

- Docker Compose healthcheck: https://docs.docker.com/compose/compose-file/compose-file-v3/#healthcheck
- Aithena docker-compose.yml (8 live examples)
- PR #356: solr-search timing fix
- PR #424: redis-commander debugging
- PR #403: ZooKeeper improvements
