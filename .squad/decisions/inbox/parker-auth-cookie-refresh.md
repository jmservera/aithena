# Decision: Validate Endpoint Refreshes Auth Cookie

**Author:** Parker (Backend Dev)
**Date:** 2026-03-20
**PRs:** #700, #702
**Status:** PROPOSED

## Context

The auth cookie was only set at login time. The validate endpoint (`/v1/auth/validate`) verified the JWT but did not set or refresh the cookie. This caused admin tabs (which rely on nginx `auth_request` → cookie-based validation) to break when the cookie expired while the JWT in localStorage remained valid.

## Decision

The `/v1/auth/validate` endpoint now sets/refreshes the `aithena_auth` cookie on every successful validation. Since the frontend calls validate on every page load, this keeps the cookie fresh.

Additionally, `set_auth_cookie` now supports `max_age=None` for session cookies (browser closes = logout). The `LoginRequest` model accepts a `remember_me` boolean to control this.

## Impact

- **Dallas (Frontend):** The login form should add a "Remember me" checkbox that sends `remember_me: true` in the login POST body. Cookie-based session recovery is now automatic.
- **Admin (Streamlit):** SSO via cookie should now work reliably — the cookie is refreshed whenever the main UI is active.
- **All team members:** The `apiFetch` function now uses `credentials: 'include'` — any new API client code should do the same.
