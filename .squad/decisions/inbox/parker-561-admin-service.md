# Decision: Restore Admin Streamlit Service Deployment

**Date:** 2026-03-20  
**Author:** Parker (Backend Dev)  
**Issue:** #561 — Admin page infinite login loop  
**PR:** #628

## Context

The admin Streamlit dashboard service was removed from `docker-compose.yml` in v1.8.2, but:
- The service code still existed in `src/admin/`
- The HTML landing page at `/admin/` still linked to `/admin/streamlit/`
- PR #570 had implemented cookie-based SSO auth for the service (reading the `aithena_auth` JWT cookie)

This created a redirect loop: clicking "Streamlit Admin" on `/admin/` redirected to `/admin/streamlit/`, which nginx redirected back to `/admin/`.

## Decision

**Re-deploy the admin Streamlit service** with proper Docker Compose configuration.

### Service Configuration

```yaml
admin:
  build: ./src/admin/Dockerfile
  expose: ["8501"]
  depends_on:
    - redis (healthy)
    - rabbitmq (healthy)
    - solr-search (healthy)
  healthcheck:
    test: wget -qO /dev/null http://localhost:8501/admin/streamlit/healthz
  environment:
    - AUTH_JWT_SECRET (required for cookie SSO)
    - AUTH_COOKIE_NAME (default: aithena_auth)
    - AUTH_ADMIN_USERNAME (fallback login, default: admin)
    - AUTH_ADMIN_PASSWORD (fallback login, required)
    - REDIS_HOST, RABBITMQ_HOST, etc.
```

### Nginx Routing

```nginx
location /admin/streamlit/ {
    auth_request /_auth;  # Validate JWT via solr-search
    proxy_set_header Cookie $http_cookie;  # Forward auth cookie
    proxy_pass http://admin:8501;
}
```

### Authentication Flow

1. User logs into main app at `/` → receives `aithena_auth` JWT cookie (24h TTL)
2. User clicks "Streamlit Admin" link → `/admin/streamlit/`
3. Nginx validates JWT via `auth_request /_auth` (calls solr-search `/v1/auth/validate`)
4. If valid, nginx forwards request to `admin:8501` with cookies
5. Admin service reads cookie via `st.context.cookies`, validates JWT, checks `role == "admin"`
6. If cookie auth succeeds → auto-login via SSO, no second login needed
7. If cookie auth fails (expired, non-admin role) → show Streamlit login form (fallback)

## Rationale

- The admin dashboard provides operational visibility (Redis keys, RabbitMQ queue stats)
- The SSO auth implementation from PR #570 was solid, just needed deployment
- Deploying the service is safer than removing the link (users expect admin tools)
- Health check ensures the service is ready before nginx routes to it
- Resource limits (256MB) keep it lightweight

## Alternatives Considered

1. **Remove the /admin/streamlit/ link entirely** → Rejected: loses operational visibility
2. **Build a new admin UI in React** → Rejected: Streamlit app works, just needs deployment
3. **Merge admin into solr-search service** → Rejected: separate concerns, easier to debug

## Impact

- **Users:** Can now access the admin dashboard via cookie-based SSO
- **Ops:** No change to deployment flow (`./buildall.sh` includes admin service)
- **Security:** Admin dashboard requires `admin` role (non-admin JWTs rejected)

## Testing

- All 95 admin tests pass (auth, JWT, cookie SSO, role enforcement)
- docker-compose.yml validates as proper YAML
- Service dependencies ensure correct startup order
