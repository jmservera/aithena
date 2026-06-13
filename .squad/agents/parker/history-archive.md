# Parker — History Archive

Preserved during the 2026-06-13 reskill trim. This file keeps the pre-trim detailed history snapshot.

---

# Parker — History

## Core Context

Parker owns Python backend services: PDF processing, metadata extraction, file watching, APIs, Docker services, and backend utilities.

**Stack:** Python 3.12, FastAPI, uv, Ruff, pytest, Docker Compose, Solr/SolrCloud, Redis, RabbitMQ, React/Vite UI, multilingual embeddings (`distiluse-base-multilingual-cased-v2`, 512D). Most Python services use uv; `embeddings-server` still uses `requirements.txt`.

**Services:** `solr-search` (search/API gateway, upload, auth, admin, health); `document-indexer` (RabbitMQ consumer, Tika indexing, chunks/pages, embeddings, Redis state, thumbnails); `document-lister` (filesystem scanner); `embeddings-server` (OpenAI-compatible embeddings, GPU/OpenVINO/device/backend, quantization); `admin` (Streamlit SSO); `aithena-common` (pure shared auth utilities).

**Flow:** files → lister/RabbitMQ `documents` fanout → indexer → Solr parent docs + chunk docs → embeddings-server → vector fields → Redis indexing state → solr-search → UI.

**Scale:** solr-search 274+ tests; document-indexer 200+; document-lister 12; admin 81; embeddings-server 76; UI 800+; full repo verification has exceeded 1900 tests.

## Key Patterns

- **Auth/SSO:** solr-search and admin share JWT cookie config. Admin reads `aithena_auth` via `st.context.cookies` and must enforce `role == "admin"`. Use `require_role(*roles)` directly in route dependencies; validate passwords before Argon2 hashing.
- **Credential paths:** Admin/API gates must accept X-API-Key for machines and JWT/cookies for browsers. `apiFetch` clears session on 401/403, so single-credential gates create login loops.
- **Cookies/rate limits:** Validation endpoints refresh cookies to avoid nginx expiry loops. `/v1/upload` has a separate limiter; CI/E2E should mint one token and reuse `E2E_API_TOKEN`.
- **Search:** keyword = BM25/edismax + facets/highlighting; semantic = kNN on chunk embeddings; hybrid = BM25+kNN with RRF. kNN failures should degrade to keyword where possible.
- **Solr data model:** parent docs hold metadata; chunk docs hold `embedding_v`/quantized vectors and `parent_id_s`. kNN features query chunks, dedupe/return parents, and tolerate parent or chunk IDs.
- **Filters/API params:** FastAPI silently drops undeclared query params. Add new UI filters to every endpoint that should honor them and reuse shared Solr filter escaping.
- **Solr auth:** `solr auth enable` creates users but not RBAC mappings. Always call `set-user-role`; role names must match `security.json` (`readonly`, not `search`).
- **Static/nginx:** URL prefix, nginx `alias`, and Docker volume mount must align across base/prod/SSL compose files or the SPA catch-all hides missing files.
- **RabbitMQ:** Use `documents` fanout exchange for multi-indexer pipelines. Producers declare/publish exchange; consumers declare/bind queues. Declarations are idempotent.
- **Infra/config:** Pass credentials into `ConnectionPool`, rebuild containers after code changes, handle root-owned bind mounts with `gosu`, keep Solr volumes UID 8983, and check all Solr node logs.
- **Embeddings images:** Heavy deps belong in `/app/.venv`; set `VIRTUAL_ENV` for `uv pip install`; use transient BuildKit uv mounts. Read-only model files still need writable HF/OpenVINO cache dirs.
- **Testing:** `object.__setattr__` helps frozen dataclass tests; mock `st.context` errors with scoped `@property`; Ruff B904 needs `raise ... from exc`; limit tests should assert exact IDs/counts.
- **Dependabot:** Never solve multi-branch manifest conflicts with blanket `--ours`/`--theirs`; manually merge all bumps, regenerate locks, verify.

## Learnings

- **2026-06-03:** Pre-release connection-warning analyzers can false-positive on `reconnect` in filenames/search URLs or expected Solr readiness loops. Require reconnect language to describe connection behavior, while keeping real dependency failures visible.
- **2026-05-31:** CI E2E 429s came from duplicate `/v1/auth/login`; Playwright should reuse workflow-minted `E2E_API_TOKEN`. Retry only exact transient 429s, not catch-all failures.
- **2026-05-31:** Local backend E2E validation is expected when Docker/Playwright are available. Compose chain: base + `compose.single-node.yml` + `compose.dev-ports.yml` + `compose.e2e.yml`; installer must generate auth/Solr/Rabbit secrets first.
- **2026-05-31:** Dependabot batch #1608 proved `git checkout --theirs` can drop earlier manifest bumps. Enumerate incoming + prior changes, regenerate lockfiles, then verify.
- **2026-05-24:** Solr init must clamp `SOLR_REPLICATION_FACTOR` to `EXPECTED_NODES`; stale single-node values like 3 create zero-active-replica collections. Installer status variables with `secret`/`password` names can trigger CodeQL even when logging only literals.
- **2026-05-24:** Installer remains a host-Python wizard with bind-backed volumes. Proposed v2 shape is host bootstrap shell → versioned installer container; settle storage/volume migration before containerizing.
- **2026-05-12:** `/v1/upload` writes to `/data/documents/uploads` and publishes directly to RabbitMQ, bypassing lister. Indexer sets Redis `text_indexed`, `embedding_indexed`, `chunk_count`; poll `/v1/admin/indexing-status` in E2E.
- **2026-04-20:** Vector quantization belongs after embedding inference in embeddings-server. Return vector plus `field_name` so indexer writes `embedding_v` or `embedding_byte_v`; warn if cosine degradation exceeds 0.01.
- **2026-03-31:** Embeddings base images should install heavy deps in `/app/.venv`, create `app:1000`, keep uv out of runtime, and provide writable cache/lock dirs for HF/OpenVINO even with read-only models.
- **2026-03-30:** Refactoring heartbeat JS lost Dependabot PR triage because issue classification ignored PRs. Use git history to audit secondary paths, not only the main issue flow.
- **2026-03-29:** Extract only pure utilities into `aithena-common`; keep JWT, migrations, seeding, user CRUD, password policy, and FastAPI logic in solr-search. Editable uv path sources work well.
- **2026-03-28:** Semantic results and similar-books need chunk ID plus parent ID. Add `parent_id` to normalized results and resolve `"_chunk_"` IDs server-side. Collection item enrichment is the backend Solr metadata join point; `PdfViewer` only needs `document_url`, `title`, `pages`.
- **2026-03-26:** Similar-books must query vectors from chunks, not parents: sort first chunk by `chunk_index_i`, over-fetch kNN candidates, dedupe by `parent_id_s`, return parent IDs, and assert exact IDs/counts in tests.
- **2026-03-24/25:** Thumbnail serving required nginx alias + volume + API URL prefix alignment. HF_TOKEN belongs in GitHub Actions build secrets, isolated by multi-stage Dockerfiles and never persisted at runtime.
- **2026-03-16–22:** Admin login loops came from API-key-only auth plus nginx `/admin/` interception; add JWT fallback and let React SPA routes pass through. Earlier backend fixes: `EMBEDDINGS_URL` must default to port 8080; semantic/hybrid wrap kNN failures; metadata PATCH uses Solr atomic updates plus Redis overrides; seed admin with lazy imports; status helpers degrade; root-owned bind mounts need privilege drop; Python 3.12 removes `async-timeout`/`tomli`; logging uses `logger.error()` plus `logger.debug(exc_info=True)`.

## 2026-06-06 — v2.5.1 Board Completion

Completed #1345 (Expose efSearchScaleFactor parameter) via PR #1701, merged to dev. Reassessed #1351 (Migrate admin/metrics to OpenTelemetry) and closed as already satisfied by current metrics behavior/tests.

Related: v2.5.1 board
- **2026-06-06:** `efSearchScaleFactor` is a Solr 10 local-param for kNN queries, not a precomputed `efSearch` value in solr-search. Keep the default `1.0` omitted from local params to preserve Solr 9 compatibility, and require live corpus validation before claiming recall/latency gains.
- **2026-06-07:** For #1452 env-template consolidation, treat `.env.example` as the canonical dev/prod/offline template. Keep installer-generated `.env` behavior separate from template documentation; release/offline packages should carry `.env.example`, not a production-only duplicate.
