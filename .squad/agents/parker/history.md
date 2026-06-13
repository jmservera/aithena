# Parker — History

## Core Context

Parker owns Python backend services: search/API, indexing, listing, embeddings, auth/shared utilities, background processing, and backend-side Docker/runtime behavior.

**Primary services:**
- `solr-search` — API gateway, search, upload, auth, admin/status helpers.
- `document-indexer` — RabbitMQ consumer, PDF/Tika extraction, chunk/page generation, embeddings, Redis state, thumbnails.
- `document-lister` — filesystem discovery.
- `embeddings-server` — OpenAI-compatible embeddings, device/backend selection, quantization-aware output.
- `aithena-common` — pure shared utilities only.

**Core flow:** files → lister/upload → RabbitMQ `documents` fanout → indexer → Solr parent docs + chunk docs → search API → UI.

## Key Patterns

- **Auth/SSO is shared behavior.** Browser flows rely on JWT cookies; admin must enforce `role == admin`; machine clients may use `X-API-Key` where appropriate.
- **Single-credential gates create login loops.** Backend auth paths must handle browser and machine credentials deliberately because the UI clears session state on 401/403.
- **Validate passwords before Argon2 hashing.** Length checks are part of both security and backend performance posture.
- **`/v1/upload` is a direct ingest path.** It writes to uploads storage and publishes to RabbitMQ, bypassing the lister.
- **Search semantics depend on parent/chunk discipline.** Semantic and similar-books flows must resolve chunk IDs back to parents; kNN features query chunks, not parent docs.
- **FastAPI ignores undeclared query params.** New filters must be added to every endpoint that is expected to honor them.
- **RabbitMQ fanout is the scalable indexing pattern.** Producers publish to `documents`; consumers bind queues idempotently.
- **Static file serving is a three-way contract.** URL prefix, nginx alias, and Compose volume mount must all align or the SPA masks failures.
- **Embeddings images need isolated runtime envs.** Heavy deps belong in `/app/.venv`, model caches must be writable, and build-only tooling should stay out of runtime layers.
- **Quantization happens after inference.** The embeddings service should return both the vector payload and the field name/path the indexer must write.
- **`aithena-common` should stay pure.** Move only framework-agnostic utilities there; keep FastAPI, migrations, user CRUD, and request-bound auth logic in service code.
- **Manifest merges need manual care.** Do not paper over dependency conflicts with blanket `--ours`/`--theirs`; merge bumps deliberately, regenerate locks, then verify.
- **Backend E2E should run locally when feasible.** Compose + dev ports + e2e overlays catch auth, upload, and routing problems earlier than CI alone.

## Reliable Edge Knowledge

- Similar-books and semantic-result flows need `parent_id` alongside chunk IDs.
- Indexer/search status lives in Redis and is the right polling surface for upload/indexing E2E.
- Solr collection topology/env defaults must be validated against expected node count; stale replication assumptions can create unusable collections.
- `.env.example` is the canonical human-facing template; installer-generated `.env` behavior is separate.

## Skill References

- `.squad/skills/fastapi-patterns/SKILL.md`
- `.squad/skills/pika-rabbitmq-fastapi/SKILL.md`
- `.squad/skills/http-wrapper-services/SKILL.md`
- `.squad/skills/e2e-auth-reuse/SKILL.md`
- `.squad/skills/clean-architecture/SKILL.md`
