# Environment template migration

Date: 2026-06-13T14:54:18+00:00

## What changed

Aithena now treats the root `.env.example` as the only checked-in environment template.

This consolidates three older sources of truth into one file:

1. The historical production-only template `.env.prod.example`
2. The canonical-but-partly-commented `.env.example`
3. Compose-level defaults that previously lived only inside `docker-compose.yml` and `docker/compose.prod.yml`

## What stays the same

- The installer still generates the real `.env` and auth database with `python3 -m installer`.
- Existing `.env` files do not need to be regenerated if they already contain working secrets.
- `docker compose` and the production/offline package layouts still read the same variable names.

## What changed in the canonical template

- Every supported variable now has an explicit default assignment.
- Variables are grouped by concern: general paths, auth, RabbitMQ, embeddings, Solr, and overlays.
- Inline comments explain when a value is dev-only, production-only, compatibility-only, or overlay-specific.
- Historical production-only values were folded into the same file instead of keeping a second template.

## Mapping from old sources

| Old source | New home |
|---|---|
| `.env.prod.example` | Root `.env.example` sections for general paths, auth, RabbitMQ, Solr, and build metadata |
| Commented optional values in old `.env.example` | Now explicit defaults in root `.env.example` |
| Inline defaults in `docker-compose.yml` / `docker/compose.prod.yml` | Mirrored and documented in root `.env.example` |

## How to migrate an existing installation

### If you already have a working `.env`

Keep your current secrets and paths. Compare your file against the new template and only add missing variables you want to tune.

Recommended flow:

1. Review `.env.example`
2. Keep your existing values for:
   - `BOOKS_PATH`, `BOOK_LIBRARY_PATH`
   - `AUTH_DB_DIR`, `AUTH_DB_PATH`
   - All `AUTH_*` secrets and bootstrap values
   - All `RABBITMQ_*` passwords
   - All `SOLR_*` passwords
3. Add new defaults only when you need them (for example `DEVICE`, `BACKEND`, `SEARCH_ARCHITECTURE`, `SOLR_TOPOLOGY`, `NGINX_HOST`)

### If you previously started from `.env.prod.example`

Copy the new `.env.example` to `.env`, then paste your production secrets and host-specific paths into the matching keys.

Pay special attention to:

- `BOOKS_PATH` and `BOOK_LIBRARY_PATH`
- `PUBLIC_ORIGIN` and `CORS_ORIGINS`
- `AUTH_DB_DIR`
- All `AUTH_*`, `RABBITMQ_*`, and `SOLR_*` credentials
- `SOLR_NUM_SHARDS` / `SOLR_REPLICATION_FACTOR`
- `NGINX_HOST` if you use `docker/compose.ssl.yml`

### If you rely on the installer

No workflow change is required. The installer remains the safest way to create `.env`; this migration only removes ambiguity about which checked-in template to read when auditing or troubleshooting configuration.

## Retired or clarified patterns

- `.env.prod.example` is retired in favor of the single canonical `.env.example`.
- Compose inline defaults remain as runtime fallbacks, but they are no longer the only place a setting is documented.
- `SOLR_TOPOLOGY` remains an installer/startup hint: use `docker/compose.single-node.yml` or the generated `start.sh` to apply it to `docker compose up`.
