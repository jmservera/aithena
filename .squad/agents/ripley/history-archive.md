# Ripley — History Archive

## Archived snapshot — 2026-06-13T21:10:43+00:00

Source: `history.md` before active-context trim.

---

# Ripley — History

## Core Context

**Role:** Project Lead for architecture, roadmap, release planning, coordination, and final gates.

**Architecture:** On-prem book-library search: SolrCloud 3-node for Tika PDF extraction/full-text/metadata; FastAPI search/embeddings; RabbitMQ listing/indexing workers; React/Vite UI; Redis, RabbitMQ, Nginx. No runtime cloud APIs, telemetry, or external auth.

**Search/data model:** Parent/chunk hierarchy. Embeddings live on chunks; kNN must query chunks; group by `parent_id_s` for book results. Hybrid search uses RRF keyword+semantic fusion. Schema moved from 512-dim distiluse to 768-dim multilingual-e5; docs/env names must track code (`VECTOR_QUANTIZATION`). Tika handles full text/metadata; pdfplumber handles per-page chunks. Chunking is word/overlap based; sentence/section awareness remains.

**Ownership:** Parker backend; Dallas UI; Brett infra/CI/Docker; Ash Solr/search/schema; Kane security; Lambert tests; Newt release/docs; Copilot scoped implementation; Ripley architecture/review.

**Release baseline:** v1.x shipped security, CI, admin consolidation, stats/filtering, infra, i18n, UI/UX, BCDR, collections, metadata editing, e5 migration, GPU docs, and Clean Architecture audit; v2.x focuses on release hardening.

## Key Patterns

- **Phase-gated execution:** Research → implementation → validation → merge. Parallelize inside phases only.
- **Wave milestones:** For 15–20+ issues, run bugs/foundations/build/integration/polish with retrospectives.
- **Pragmatic incrementalism:** Ship quick value, then track Phase 2 cleanup explicitly.
- **Load balancing:** 20+ issues on one agent is a bottleneck; redistribute with single owners.
- **Domain knowledge as deliverable:** Data-model assumptions must be documented before code; parent/chunk confusion was the highest-risk near miss.
- **Research first:** Short code-reading caught RabbitMQ competing consumers, mostly-built chunk preview, dual-extraction semantics, and schema coupling.
- **Scientific debugging:** Reproduce, root-cause, then patch. Mechanical guardrails beat verbal coaching.
- **No silent degradation:** Search/error handlers must not change modes or drop results silently; warn and return clear errors unless Lead/PO approves.
- **Branch hygiene:** Always branch from fresh `origin/dev`; cross-branch contamination silently reverts work.
- **Rulesets/threads:** `--admin` does not bypass rulesets; checks and resolved conversations still gate merge. Resolve threads via GraphQL.
- **Release gate:** Commit artifacts to `dev`, bump `VERSION`, merge dev→main, then tag/publish. Never move published tags; use patch releases with Newt/PO approval.
- **Docs gate the tag:** README, changelog, notes, manuals, screenshots, and validation evidence must be current before promotion.
- **Clean Architecture:** Prefer dependency inversion/shared packages over `sys.path` or duplicated framework-bound code. `aithena-common` owns auth/password DB; JWT/TTL/user/logging migration remains.
- **Schema ownership:** Ash owns Solr schema; schema/query/UI contracts must be coordinated.
- **Security exceptions:** Unpatched CVEs require mitigation evidence, risk assessment, and follow-up issue.
- **Actions security:** Least privilege, pinned actions where appropriate, `persist-credentials: false`; no PR-head code in `pull_request_target`.
- **CI security:** Regression scripts protecting auth/ports/secrets belong in required CI, not manual evidence.
- **Dependabot batching:** Batch low/medium bumps, regenerate lockfiles once, close superseded PRs manually, and document held-back bumps.
- **Manifest conflicts:** `git checkout --theirs` can silently revert prior dependency bumps; regenerate `uv.lock` after stacked Python merges.
- **Flakes:** Separate product signal from infrastructure noise; fix chronic E2E/auth-rate-limit issues centrally.
- **Generated issues:** Pre-release warnings and heartbeat-token issues need success-path closure to prevent stale backlog.

## Learnings

### PR #1649 final gate (2026-06-04)
- Merge waited for Solr readiness auth fail-fast review thread resolution; green checks alone were insufficient.
- Missing PR checklists can be appended by Ripley before merge.
- ZooKeeper exposure and Solr auth regression scripts belong in required `All tests passed`.

### Ralph closeout and v2.3.0 setup (2026-06-04)
- Board ended with no implementation PRs or review blockers; remaining work was release-gate/async only.
- v2.3.0 was narrow maintenance/infra: #1631 plus release notes, test evidence, manuals, validation.
- Human-only v2.2.1 signoff (#1639) should not block AI-owned v2.3.0 work.

### v2.2.1 patch release (2026-06-03)
- Published tags are immutable; shipped v2.2.1 instead of moving v2.2.0.
- Metadata landed on `dev`, then dev→main, then tag/GitHub Release.
- Release-doc review threads were real blockers.

### Assignment automation (2026-06-03)
- PR routing comments need `pull_request_target` plus explicit PR/issue write permissions.
- Keep that context to trusted metadata scripts and base-branch checkout only.

### Pre-release blockers (2026-06-03)
- `VERSION=*-dev` changes must check every workflow reading `VERSION`.
- If shared-account identity blocks formal approval, record lead approval in a PR comment.

### Project review (2026-05-12)
- v2.1 shipped while docs advertised older versions; docs freshness belongs in gates.
- `SEARCH_ARCHITECTURE`, `/v1/capabilities`, and UI capability gating are shipped features.
- Architecture docs must track vector dimensions and quantization env vars.
- Active security findings outrank release-noise cleanup.

### Dependabot sweeps (2026-05-31)
- Batch sweeps need lockfile discipline, ruleset compliance, and manual superseded-PR closure.
- npm locks often merge cleanly; uv locks usually need one final regeneration.
- Code scanning can add legitimate new threads each push, including stale inline version comments.
- Document pre-existing `dev` test failures separately.

### Reskill consolidation (2026-05-31)
- Skills shrank from 38 to 28; quality beats accumulation.
- `e2e-auth-reuse` gained confidence after CI and production-path validation.
- Repeated manifest-conflict rediscovery proved key patterns must move from history into skills.

### PR #1580 review (2026-05-31)
- Valid installer fix was masked by E2E 429 flake; rebase isolated product change from infra noise.

### PR #1614 volume migration (2026-05-31)
- Docker volumes fit Solr/ZooKeeper/collections/certbot; user books stay bind-mounted.
- SSL bootstrap needs volume existence plus test-container inspection.
- `.env.example` credential completeness is part of infra review.

### Clean Architecture audit (2026-03-27)
- Found `sys.path`, duplicated auth/JWT/TTL/user/logging, and framework-mixed correlation violations.
- `aithena-common` validates the direction; migrate consumers incrementally.

### v1.18.1 orchestration (2026-03-29)
- IPEX extras, Solr roles, credentials, shared auth, tests, and architecture audit integrated with 1026+ tests passing.
- Clear dependencies plus deduplicated decisions enabled scalable multi-agent orchestration.

### Search/embedding research (2026-03)
- R1 chunk preview mostly existed (`chunk_text_t`) and needed retrieval wiring.
- Similar-books UI must decouple from PDF viewer state/z-index.
- A/B indexers need fanout/separate queues; one queue creates competing consumers.
- New embedding collections need matching vector fields (`knn_vector_768`, not hardcoded 512).

### v1.10.1 gate/security (2026-03)
- Parameterized SQL, justified S608 suppressions, RFC 7235 auth, and safe shell patterns passed gate.
- Sequential admin batches around 100s/5000 docs were acceptable for admin scope; async chunking recommended later.

### Skills pruning (2026-03)
- Aggressive pruning of unvalidated/overlapping skills produced a more usable set.
- Consolidated skills should preserve examples and anti-patterns while staying short enough for active work.

### Nap/Reskill maintenance pass (2026-06-04)
- Compressed 6 agent histories (parker, newt, ripley, brett, dallas, lambert) from 188KB → 48KB (74% reduction).
- Charters were already optimized — no action needed (avg 1,344 bytes, all under 2.5KB).
- Total context savings: 251KB → 81KB (67% reduction, 170KB saved).
- No new skills created — all patterns already extracted to .squad/skills/ (27 existing skills).
- Compression preserved all unique insights, consolidated duplicates, removed verbose timestamps/session metadata.
- Pattern: History bloat happens when detailed session logs aren't consolidated into patterns. Target ≤8KB per history, ≤1.5KB per charter.

### 2026-06-05 — OpenVINO Post-Mortem Coordination (Issue #1662)
- **Failed run:** 27022717607 (Pre-release smoke test embeddings-server-openvino)
- **Successful fix:** 27026253418 (a8a5cb5)
- **Post-mortem:** Root cause was `uv sync --inexact` drift not caught by CI `--frozen` assumption; prevention is post-sync verification inside built image
- **Prevention:** Build-time version check (Python import + `__version__` query) fails immediately if transitive versions don't match expectations
- **Rubber Duck critique:** Confirmed that verification must run inside the built image; CI environment assumptions are insufficient
- **Decision documented:** `.squad/decisions.md` (OpenVINO Smoke Failure section)
- **Pattern:** Future GPU/accelerator builds should follow post-sync verification pattern for all critical dependencies

### 2026-06-06 — v2.5.1 validation dispatch
- Start only active validation now: #1356 Phase 2 (Lambert), #1354 Solr 9.7 vs 10 benchmarks (Ash+Lambert), and #1344 scalar-quantization evidence (Bishop+Lambert).
- Defer `release:backlog`/optional feature work (#1452, #1357, #1348, #1347) until Phase 2 and benchmark evidence exists; DocumentCategorizer remains disabled without a real model fixture.
- #1344 should not stay Ripley-owned once architecture is settled; route implementation/validation to Bishop + Lambert, with Ash consulted for schema/search details.

### 2026-06-06 — Lead quality review for PRs #1712/#1711/#1710
- #1712 correctly moves Solr 10 scalar quantization to supported `bits=7`, preserves Solr 9 `DenseVectorField vectorEncoding=BYTE` rewrites, and keeps `VECTOR_QUANTIZATION=int8` optional pending #1344 recall/memory evidence; required checks were green and the addressed PRD review thread was resolved.
- #1711 adds the right same-host/same-corpus benchmark evidence gate; follow-up risk recorded on #1354 to validate `run_metadata.solr_version` and vector-quantization run profiles before release claims.
- #1710 is acceptable as Phase 2 preflight/live-opt-in validation; it does not replace true standalone/no-ZK or paired quantization benchmark evidence.
