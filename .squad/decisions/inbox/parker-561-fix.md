# Decision: Admin SSO via shared JWT cookie

**Author:** Parker  
**Date:** 2025-07  
**Issue:** #561  
**PR:** #570

## Context

The admin Streamlit app had its own independent auth system (env-var credentials + session state JWT), completely separate from the main app's auth (SQLite + Argon2id + `aithena_auth` cookie). This caused an infinite login loop because users had to authenticate twice through different systems.

## Decision

Added SSO cookie-based authentication to the admin Streamlit app. `check_auth()` now falls back to reading the `aithena_auth` HTTP cookie (forwarded by nginx) and validating the JWT using the shared `AUTH_JWT_SECRET`. If valid, the user is auto-authenticated without a second login.

## Implications

- **AUTH_JWT_SECRET must be identical** between `solr-search` and `streamlit-admin` services (already the case in docker-compose.yml).
- **AUTH_COOKIE_NAME must match** between services (default: `aithena_auth`, added to admin's docker-compose env).
- The Streamlit fallback login form still works for direct access without nginx (e.g., local dev on port 8501).
- Solr-search JWTs contain `user_id` which admin ignores — this is fine since admin only needs `sub` and `role`.

## Affects

- Brett: nginx config remains unchanged; `auth_request` still validates before forwarding to Streamlit.
- Dallas: no frontend changes needed; the React app's login sets the `aithena_auth` cookie that now flows through to Streamlit.
