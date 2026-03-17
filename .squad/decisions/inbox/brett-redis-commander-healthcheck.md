# Decision: Docker Health Check Best Practices for Node.js Containers

**Date:** 2026-03-17  
**Author:** Brett (Infrastructure Architect)  
**Context:** Fixing redis-commander health check failures in E2E CI tests (PR #424)

## Problem

The redis-commander container was consistently failing health checks in GitHub Actions CI, blocking E2E test execution. The error was:
```
dependency failed to start: container aithena-redis-commander-1 is unhealthy
```

This affected PRs #418, #419, and #411.

## Root Cause Analysis

The original health check configuration had several issues that worked locally but failed in CI:

1. **CMD vs CMD-SHELL:** Used `CMD` format with Node.js inline code, which requires each argument as a separate array element. The complex one-liner wasn't executing properly.

2. **No timeout handling:** The HTTP request in the health check had no timeout, causing checks to potentially hang indefinitely if redis-commander was in a partial initialization state.

3. **Insufficient start_period:** `start_period: 10s` was too short for redis-commander to fully initialize in resource-constrained CI environments.

4. **Too few retries:** Only 3 retries meant transient initialization delays would fail the health check before the service became ready.

## Decision

**Standard for Node.js container health checks in this project:**

1. **Use CMD-SHELL for complex checks:** When health checks require shell features or complex inline code, use `CMD-SHELL` instead of `CMD`:
   ```yaml
   healthcheck:
     test: ["CMD-SHELL", "node -e \"...complex code...\""]
   ```

2. **Always include timeouts:** Network requests in health checks must have explicit timeouts to prevent hanging:
   ```javascript
   const req = http.get({..., timeout: 5000}, callback);
   req.on('timeout', () => { req.destroy(); process.exit(1); });
   ```

3. **Pad start_period for CI:** Services should have `start_period` 2-3x longer than local testing suggests, accounting for CI cold-start and resource constraints:
   - Local: 10s might work
   - CI: Use 30s minimum for admin/management services

4. **Generous retries for warmup:** Use at least 5 retries for services that need initialization time (connecting to other services, loading config, etc.)

5. **Accept non-5xx responses:** For admin UI services, accept any 2xx-4xx status code. Redirects (302) and client errors (404) indicate the HTTP server is running, which is sufficient for dependency gating.

## Implementation

Applied to redis-commander service in `docker-compose.yml`:

```yaml
healthcheck:
  test:
    [
      "CMD-SHELL",
      "node -e \"const http = require('http'); const req = http.get({host: 'localhost', port: 8081, path: '/admin/redis/', timeout: 5000}, (res) => { process.exit(res.statusCode >= 200 && res.statusCode < 500 ? 0 : 1); }); req.on('error', () => process.exit(1)); req.on('timeout', () => { req.destroy(); process.exit(1); });\"",
    ]
  interval: 30s
  timeout: 10s
  retries: 5
  start_period: 30s
```

## Impact

- **Immediate:** Unblocks E2E tests for PRs #418, #419, #411
- **Future:** Provides template for other Node.js-based admin services (if added)
- **Maintenance:** More resilient health checks reduce false-positive failures in CI

## Alternatives Considered

1. **Remove health check entirely:** Would unblock CI but removes dependency gating. nginx would start before redis-commander is ready, causing 502 errors.

2. **Use curl/wget:** These aren't available in the redis-commander Node.js-based image. Would require custom Dockerfile to add them.

3. **TCP-only check:** Could just check if port 8081 is listening. Rejected because it doesn't verify the HTTP server is actually serving requests.

## Related

- PR #424: Fix redis-commander health check
- Pattern also applies to streamlit-admin (Python-based, but similar health check principles)
