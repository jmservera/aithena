### 2026-03-19T13:10: User directive — Certbot optional
**By:** jmservera (via Copilot)
**What:** Make the certbot container optional in docker-compose. Most deployments run behind a general reverse proxy or on local networks and don't need Let's Encrypt certificate management.
**Why:** User request — simplifies default deployment, reduces unnecessary container overhead.
