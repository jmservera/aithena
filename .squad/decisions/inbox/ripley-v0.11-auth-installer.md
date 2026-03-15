# Ripley — v0.11.0 Auth + Installer Plan

**Date:** 2026-03-15  
**Requested by:** Juanma (Product Owner)  
**Scope:** Local authentication and first-run setup installer for milestone `v0.11.0 — New Features`

## Context

Aithena currently exposes the React UI, FastAPI API, Streamlit admin dashboard, Solr admin, RabbitMQ admin, and Redis Commander without authentication. The product owner requested a simple username/password login flow with browser-cached JWTs and a setup installer that removes the need to hand-edit configuration before first run.

## Architecture Decisions

### 1. Authentication lives inside `solr-search`; do not add a new auth microservice

**Decision:** Implement the login, token issuance, and token validation endpoints in `solr-search`.

**Why:**
- `solr-search` is already the public application API behind nginx.
- It already follows environment-driven configuration and is the natural place to centralize auth contracts.
- Adding a separate auth service would increase service count, compose complexity, and operational burden for a v0.11.0 feature that is intentionally simple.

**Resulting endpoints:**
- `POST /v1/auth/login` — validate credentials and mint JWT
- `GET /v1/auth/validate` — lightweight token validation endpoint for nginx `auth_request`
- `GET /v1/auth/me` — optional caller identity endpoint for the UI/admin

### 2. Store users in a local SQLite database with Argon2id password hashes

**Decision:** Use a small SQLite database file for local users; store password hashes with Argon2id.

**Why:**
- SQLite is simple, portable, and persistent without adding a database service.
- It supports more than one user later without redesigning the storage model.
- Argon2id is stronger than bcrypt for a new security feature and is well supported from Python.

**Storage contract:**
- Database path comes from installer-generated configuration.
- Database file lives in a persistent mounted volume, separate from source code.
- Installer seeds the first admin user; password is never stored in plaintext.

### 3. Use signed JWT access tokens only for v0.11.0, transported by both header and secure cookie

**Decision:** Issue signed JWT access tokens with an expiration; do not add refresh tokens in this milestone. After login, cache the token in browser storage for the React app and also set a secure same-site cookie so browser navigations and embedded admin tools can be gated by nginx.

**Why:**
- The requirement is simple username/password login with a browser-cached token.
- Access-token-only keeps the first implementation small and reviewable.
- Browser-only surfaces such as Streamlit, Solr admin, RabbitMQ admin, and Redis Commander cannot rely on local-storage headers alone.
- A hybrid header + cookie transport keeps the React experience simple while making central nginx gating feasible.

**Token contract:**
- Login returns a JWT payload for the React app and sets a secure cookie for same-origin browser requests.
- React stores the token locally and sends `Authorization: Bearer <token>` on API requests.
- nginx validation accepts either the bearer token or the auth cookie.
- JWT signing secret and TTL come from installer-generated configuration.

### 4. Enforcement uses both frontend route guards and nginx `auth_request`

**Decision:**
- Protect React application routes with a login page and client-side route guard.
- Protect `/v1/*`, `/documents/*`, and `/admin/*` at nginx with `auth_request` backed by `solr-search` token validation.
- Keep `/login`, health checks, and ACME challenge paths public.

**Why:**
- nginx can centrally gate API and browser-facing admin surfaces with standard `auth_request` support.
- React route guards still provide the correct UX for SPA navigation and token-expiry handling.
- The combined model closes the current open deployment without introducing a new identity service.

**Protected surfaces for v0.11.0:**
- React UI application routes (via login + protected routes)
- FastAPI endpoints under `/v1/` except auth/login and health/info endpoints explicitly left public
- Document fetches under `/documents/`
- Streamlit admin and admin tool prefixes under `/admin/streamlit/`, `/admin/solr/`, `/admin/rabbitmq/`, `/admin/redis/`

### 5. The installer is a Python CLI that writes `.env` and bootstraps the auth database

**Decision:** Build a Python-based installer CLI for first-run setup.

**Why:**
- The repo is already Python-heavy and the required tasks (prompting, hashing, secret generation, SQLite bootstrap) fit Python well.
- The installer can share validation and hashing logic with backend auth code.
- It avoids manual editing of compose variables and makes first run repeatable.

**Installer responsibilities:**
- Prompt for the book library path
- Prompt for initial admin username and password
- Ask for any required runtime values that do not have safe defaults (for example public origin / CORS origin)
- Generate a JWT signing secret
- Write `.env` for Docker Compose variable substitution
- Create or update the SQLite auth database with the initial admin user
- Be idempotent: re-running updates configuration safely and does not wipe existing data unless explicitly requested

### 6. Docker Compose consumes installer-generated values rather than hardcoded auth defaults

**Decision:** Update compose wiring so services read auth and installer values from `.env` / environment substitution.

**Why:**
- The current stack only expects `BOOKS_PATH` and build metadata in `.env.example`.
- Auth introduces new runtime settings that must be explicit, reproducible, and documentable.
- Keeping configuration in `.env` matches current Docker Compose conventions in the repo.

**Expected new config surface:**
- `BOOKS_PATH`
- `CORS_ORIGINS` or equivalent public-origin setting
- `AUTH_DB_PATH`
- `AUTH_JWT_SECRET`
- `AUTH_JWT_TTL_MINUTES`
- `AUTH_ADMIN_USERNAME` only if needed for bootstrap metadata (not as the source of truth once the database exists)

## Delivery Shape

The implementation should be broken into narrow issues rather than a single auth epic implementation. The architecture and security contract come first; installer work can begin in parallel once the contract is agreed.

## Dependency Graph

```text
#250 Design local authentication and setup installer architecture
├── #251 Build FastAPI auth module with JWT validation and local user store
│   ├── #252 Add login UX and protected routes to the React frontend
│   └── #253 Gate API and document routes in nginx with auth_request
├── #255 Create idempotent setup installer CLI for first-run configuration
│   └── #256 Wire installer-generated environment into docker compose and docs
├── #254 Protect browser-facing admin tools behind the new auth flow
│   ├── depends on #251 backend auth contract
│   ├── depends on #252 login UX
│   └── should land after or alongside #253 ingress gating
└── #257 Add auth and installer end-to-end coverage
    ├── depends on #251 backend auth
    ├── depends on #252 frontend login UX
    ├── depends on #253 nginx API/document gating
    ├── depends on #254 admin browser-surface protection
    └── depends on #255 + #256 installer/compose wiring
```

## Notes for Reviewers

- This milestone intentionally avoids SSO, OAuth, refresh tokens, and a dedicated identity provider.
- If later requirements need server-side token revocation, multi-user roles, or audit trails, extend the local-auth design instead of introducing SSO prematurely.
- For v0.11.0, the priority is closing the current unauthenticated exposure with the smallest architecture that can be operated by a single-node/self-hosted deployment.
