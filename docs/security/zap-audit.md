# OWASP ZAP Manual Security Audit Guide

This guide covers how to run a manual OWASP ZAP dynamic application security test (DAST) against the Aithena stack. This is **not** part of CI — the scans are too resource-intensive for GitHub-hosted runners. Run them locally before major releases or on the recommended quarterly cadence.

**Recommended cadence:** quarterly, or before every major release.

---

## Prerequisites

### 1. OWASP ZAP

Install ZAP 2.15 or later. The easiest approach is the official Docker image, which avoids any local Java dependency:

```bash
docker pull ghcr.io/zaproxy/zaproxy:stable
```

Alternatively, download the desktop installer from <https://www.zaproxy.org/download/>.

### 2. Running Aithena stack

The target must be reachable from the machine running ZAP. Start the full stack with the development override so that internal ports are exposed if needed:

```bash
docker compose up -d
```

Confirm the UI is accessible at `http://localhost` before starting a scan.

### 3. Authentication context (optional)

Aithena's current version does not enforce authentication on the public search UI. If authentication is added in a future release, create an authenticated ZAP context before running active scans (see the [ZAP authentication docs](https://www.zaproxy.org/docs/authentication/)).

---

## Scan Types

| Type | Speed | Risk | Purpose |
|------|-------|------|---------|
| Baseline (passive) | Fast (~5 min) | None — read-only | Spider + passive rules; safe for any environment |
| API scan | Medium (~10–20 min) | Low — structured probes only | OpenAPI-driven scan of the FastAPI service; no aggressive probes |
| Active scan | Slow (~30–60 min) | Modifies data | Full DAST including injection probes; run against a dev instance only |

---

## Running a Baseline Passive Scan

The baseline scan spiders the application and runs passive checks only. It does **not** send attack payloads, so it is safe to run against a shared or staging environment.

```bash
docker run --rm \
  --network host \
  -v "$(pwd)/zap-reports:/zap/wrk:rw" \
  ghcr.io/zaproxy/zaproxy:stable \
  zap-baseline.py \
    -t http://localhost \
    -r zap-baseline-report.html \
    -J zap-baseline-report.json \
    -l WARN
```

> **Note:** `--network host` is required so the ZAP container can reach the stack running on `localhost`. On macOS/Windows replace `localhost` with the host IP visible from Docker (typically `host.docker.internal`).

The HTML report is written to `./zap-reports/zap-baseline-report.html`.

---

## Running a Full Active Scan

The active scan sends probes (SQL injection, XSS, path traversal, etc.). **Run against a local or dedicated dev instance only — never against production.**

```bash
docker run --rm \
  --network host \
  -v "$(pwd)/zap-reports:/zap/wrk:rw" \
  ghcr.io/zaproxy/zaproxy:stable \
  zap-full-scan.py \
    -t http://localhost \
    -r zap-active-report.html \
    -J zap-active-report.json \
    -l WARN \
    -z "-config scanner.threadPerHost=5"
```

Reduce `threadPerHost` to 2–3 if the Solr nodes become saturated during scanning.

---

## Scanning the API Directly

`solr-search` exposes a FastAPI service. Scan it separately using the OpenAPI schema to maximize coverage:

```bash
# Download the schema while the stack is running
curl -o /tmp/openapi.json http://localhost/api/openapi.json

docker run --rm \
  --network host \
  -v "/tmp/openapi.json:/zap/openapi.json:ro" \
  -v "$(pwd)/zap-reports:/zap/wrk:rw" \
  ghcr.io/zaproxy/zaproxy:stable \
  zap-api-scan.py \
    -t /zap/openapi.json \
    -f openapi \
    -r zap-api-report.html \
    -J zap-api-report.json \
    -l WARN
```

> If the API is mounted at a sub-path (e.g. `/api`), set the target URL accordingly with `-t http://localhost/api/openapi.json`.

---

## Interpreting Results

### Alert risk levels

| Risk | Label | Meaning |
|------|-------|---------|
| 🔴 High | `HIGH` | Likely exploitable — fix before release |
| 🟠 Medium | `MEDIUM` | Significant risk — fix or formally accept with justification |
| 🟡 Low | `LOW` | Minor hardening gap — address in next maintenance window |
| ℹ️ Informational | `INFO` | Observations only — no immediate action required |

### Common false positives in Aithena

| Alert | Reason likely false positive | Action |
|-------|------------------------------|--------|
| "X-Frame-Options header not set" | nginx serves static assets; framing policy is acceptable for a library UI | Add `X-Frame-Options: SAMEORIGIN` to the nginx config to eliminate |
| "Content-Security-Policy header not set" | Acceptable for internal deployment; CSP tightening is a planned hardening item | Track as future improvement |
| "Server leaks version information" | nginx default; acceptable for internal use | Suppress `server_tokens` in nginx if internet-facing |
| Solr admin UI alerts | Solr admin is proxied through nginx and should be network-restricted; alerts on Solr internals are expected | Verify admin is not publicly reachable |
| RabbitMQ management console alerts | Same as Solr — internal surface, expected | Verify admin is not publicly reachable |

### Triaging a finding

1. Open the HTML report and filter by **Risk = High** first.
2. For each High/Medium alert, check the **Evidence** field — ZAP shows the exact request and response fragment that triggered the rule.
3. Reproduce the finding manually (curl, browser dev tools) to confirm it is real.
4. If confirmed, create a GitHub issue with label `security` and assign to Kane for remediation guidance.
5. If it is a false positive, add a note in `docs/security/zap-exceptions.md` (create as needed) with the rule ID, justification, and reviewer name.

---

## Saving and Sharing Reports

Reports are written to `./zap-reports/` on the host machine. Do **not** commit HTML/JSON reports to the repository — they may contain sensitive path or payload information.

Archive reports in a secure location (e.g. a private shared drive) and reference them in the release notes or security review checklist by filename and date.

---

## Recommended Audit Checklist

Run the following before each major release:

- [ ] Baseline passive scan against staging — zero new High/Medium alerts
- [ ] API scan against `solr-search` OpenAPI schema — zero new High alerts
- [ ] Active scan against local dev instance — all High alerts triaged
- [ ] False positives documented in `docs/security/zap-exceptions.md`
- [ ] All confirmed vulnerabilities have open GitHub issues with `security` label
- [ ] Report archived and referenced in release notes

---

## References

- [OWASP ZAP Documentation](https://www.zaproxy.org/docs/)
- [ZAP Docker Hub / ghcr.io](https://www.zaproxy.org/docs/docker/about/)
- [ZAP Baseline Scan](https://www.zaproxy.org/docs/docker/baseline-scan/)
- [ZAP Full Scan](https://www.zaproxy.org/docs/docker/full-scan/)
- [ZAP API Scan](https://www.zaproxy.org/docs/docker/api-scan/)
- [OWASP Testing Guide v4](https://owasp.org/www-project-web-security-testing-guide/)
