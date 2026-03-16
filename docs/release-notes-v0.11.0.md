# Aithena v0.11.0 Release Notes — New Features

_Date:_ 2026-03-16  
_Prepared by:_ Newt (Product Manager)

Aithena v0.11.0 delivers the **New Features** milestone. This release adds a full local authentication flow across the standard nginx surface, introduces an installer-driven first-run setup, and expands validation coverage for the new security and onboarding path.

## Summary of shipped changes

- **Local authentication in `solr-search`** with a SQLite user store, Argon2id password hashing, JWT issuance/validation, and both bearer-token and cookie-based session support.
- **Login UX in the React UI** with `AuthContext`, a dedicated `LoginPage`, protected routes, and automatic bearer-auth injection for protected API calls.
- **nginx `auth_request` gating** for API endpoints, document downloads, and browser-facing admin tools, including redirect handling for interactive pages and JSON `401` responses for API clients.
- **Installer CLI for first-run setup** that writes `.env`, generates auth secrets, creates the auth storage directory, seeds the initial admin user, and supports idempotent re-runs.
- **Comprehensive auth-focused test coverage** with 140 backend tests and 83 frontend tests covering login, session handling, protected navigation, and installer behavior.

## Merged pull requests

- **#263** — `feat: add local auth module with JWT and SQLite user store`
- **#265** — `feat: add idempotent setup installer CLI`
- **#268** — `Wire installer-generated auth/env into Docker Compose and operator docs`
- **#272** — `feat: gate API and document routes with nginx auth_request`
- **#273** — `feat: protect admin tool routes with auth_request`
- **#274** — `test: add auth and installer E2E coverage`

## Breaking changes

**Yes.**

- All standard nginx-exposed API, document, and admin routes now require authentication.
- Browser users should expect a redirect to `/login` until they authenticate successfully.
- First-run setup must be completed with the installer before `docker compose up`, because the auth database path and JWT secret are now required runtime inputs.

## Upgrade instructions

1. Update to the v0.11.0 release commit or tag once it is published.
2. Run the installer before starting or restarting the stack:

   ```bash
   python3 -m installer
   # or: python3 installer/setup.py --library-path /absolute/path/to/books \
   #       --admin-user admin --admin-password 'change-me' --origin http://localhost
   ```

3. Confirm the generated `.env` now includes installer-managed auth settings such as:
   - `AUTH_DB_DIR`
   - `AUTH_DB_PATH`
   - `AUTH_JWT_SECRET`
   - `AUTH_ADMIN_USERNAME`
4. Start or restart the stack with Docker Compose:

   ```bash
   docker compose up -d
   ```

5. Sign in with the installer-seeded admin account, then verify access to the UI, `/v1/*`, `/documents/*`, and `/admin/*` through the nginx entrypoint.
6. Update any scripts, integrations, or reverse-proxy consumers to authenticate before calling protected routes.
7. Add `AUTH_DB_DIR` to your backup and restore plan alongside the document library and other persistent data.
