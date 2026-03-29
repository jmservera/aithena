# Decision: Extract Shared Auth Library (aithena-common)

**Author:** Parker (Backend Dev)
**Date:** 2026-07-09
**Status:** Implemented (PR for #1288)
**Context:** Issue #1288 — installer depended on solr-search internals via sys.path manipulation

## Problem

The installer imported `hash_password` and `init_auth_db` from `src/solr-search/auth.py` by appending solr-search to `sys.path`. This violated the Dependency Rule — an orchestrator (installer) depended directly on a service's internals.

## Decision

Created `src/aithena-common/` as a shared Python package containing:
- `aithena_common.passwords` — `hash_password()`, `verify_password()`, `check_needs_rehash()`
- `aithena_common.auth_db` — `init_auth_db()`, `find_user()`, `get_schema_version()`, `SCHEMA_VERSION`

Both installer and solr-search now depend on aithena-common via uv path sources.

## What Stays in solr-search

- JWT creation/verification, token handling, cookies
- User CRUD (create_user, list_users, update_user, delete_user)
- Migrations framework, default admin seeding
- Password policy validation
- All HTTP/FastAPI-specific auth logic

## Impact

- Installer is now a proper uv project (`installer/pyproject.toml`)
- `ensure_runtime_dependencies()` fallback uses `--project installer` instead of `--project src/solr-search`
- Future services needing auth DB access should depend on `aithena-common`, not import from solr-search
- `reset_password.py` in solr-search is unchanged (still imports from local `auth` module which re-exports from aithena-common)
