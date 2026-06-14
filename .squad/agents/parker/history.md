# Parker — History

## Core Context

Parker owns Python backend services: PDF processing, metadata extraction, file watching, APIs, indexing flow, and backend Docker service behavior.

- Primary services: `solr-search`, `document-indexer`, `document-lister`, `embeddings-server`, `admin`, and shared package `aithena-common`.
- Core flow: files → lister/RabbitMQ fanout → indexer → Solr parent + chunk docs → embeddings-server → Redis indexing state → API/UI.
- Auth posture: admin/browser flows need JWT cookie support, machine flows may use `X-API-Key`, and mixed gates prevent login loops.
- Search posture: keyword = BM25, semantic = chunk-kNN, hybrid = BM25 + kNN + RRF; parent docs hold metadata, chunk docs hold vectors and `parent_id_s`.
- RabbitMQ producers/consumers should use the `documents` fanout exchange for multi-indexer pipelines.

## Active Patterns

- FastAPI drops undeclared query params silently; wire new filters through every endpoint that should honor them.
- Reuse `E2E_API_TOKEN` in CI/local E2E and keep upload-specific rate limits isolated.
- Keep heavy Python/image dependencies in `/app/.venv`; provide writable HF/OpenVINO cache locations even when model files are read-only.
- Manifest conflict resolution must be manual; never blanket `--ours` / `--theirs` dependency files.

## Recent Learnings

### 2026-06-13 — Root test orchestration
- Root verification stays maintainable when Python services are discovered from `src/*/pyproject.toml` and optional Playwright/stress targets are gated on directory presence.
- Validate orchestration changes with `make help` plus a focused backend run.

### 2026-06-07 — `.env.example` as canonical template (#1452)
- Treat `.env.example` as the shared dev/prod/offline template and keep installer-generated `.env` behavior separate.
- Release/offline packages should carry the example template, not a production-only duplicate.

### 2026-06-06 — v2.5.1 board completion
- #1345 (`efSearchScaleFactor`) merged; #1351 (admin/metrics OpenTelemetry migration) was already satisfied by existing metrics behavior/tests.

### 2026-06-06 — `efSearchScaleFactor` behavior
- `efSearchScaleFactor` is a Solr 10 local-param, not a precomputed backend value.
- Omit the default `1.0` to preserve Solr 9 compatibility and require live corpus validation before claiming recall/latency gains.
