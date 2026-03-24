# Architectural Analysis: Extracting Embeddings-Server to Independent Repository

**Author:** Ripley (Lead)  
**Date:** 2026-03-24  
**Status:** ANALYSIS COMPLETE  
**Requested by:** Juanma (jmservera)  
**Objective:** Analyze feasibility and design decoupling embeddings-server from aithena for independent release cadence and genericization.

---

## EXECUTIVE SUMMARY

**Verdict: Extraction is architecturally sound and strategically beneficial.**

Embeddings-server is a **pure HTTP service** with **zero imports from aithena**, making it a clean extraction candidate. The service is already consumed via HTTP-only interfaces (no shared code libraries), enabling straightforward extraction with minimal integration surface.

**Strategic Benefits:**
- Model lifecycle decoupled from Aithena releases (ship e5-large faster)
- Genericization to OpenAI-compatible `/v1/embeddings` API (95% there) unlocks use-cases beyond aithena
- Reduced build time for aithena releases (skip ~2min Dockerfile multi-stage build)
- Faster iteration on embedding model updates (currently gated by aithena release cycle)

**Risks to Mitigate:**
- Version pinning discipline (API contract must stay stable)
- E2E test coverage gap (tests depend on pulling embeddings-server image)
- Developer onboarding (new repo to build/pull from)

---

## 1. CURRENT COUPLING INVENTORY

### 1.1 Code Structure (Zero Tight Coupling)

**Embeddings-Server Files:**
- `main.py` — 115 lines, zero aithena imports
- `model_utils.py` — 30 lines, pure utilities  
- `config/__init__.py` — 18 lines, env-based config
- `Dockerfile` — Multi-stage, no aithena deps
- `pyproject.toml` — sentence-transformers, fastapi, uvicorn only
- `tests/test_embeddings_server.py` — 370 lines, self-contained

**Key Finding:** Zero imports from aithena codebase. No shared libraries, utilities, or models.

### 1.2 Service-to-Service Coupling (HTTP Only)

| Service | Integration | Location |
|---------|-------------|----------|
| solr-search | POST `/v1/embeddings/` | main.py:1078, 1166 |
| document-indexer | POST `/v1/embeddings/` | embeddings.py:31 |
| e2e tests | GET /health + probe | test_search_modes.py:82-91 |

All integration is **stateless HTTP**. No RPC, queue, or database schema coupling.

### 1.3 Docker-Compose References

**docker-compose.yml (dev):**
- Lines 87-120: Service with `build: ./src/embeddings-server`
- Memory: 3GB limit, 2GB + 1CPU reservation
- Healthcheck: `GET /health`
- Network alias: `embeddings-server`
- Build args: `VERSION`, `GIT_COMMIT`, `BUILD_DATE`, `HF_TOKEN`

**docker-compose.prod.yml:**
- Lines 83-110: Uses image `ghcr.io/jmservera/aithena-embeddings-server:${VERSION:-latest}`
- Identical constraints and healthcheck

**docker-compose.override.yml:**
- Line 11: Service reference only

### 1.4 CI/CD Workflow References

**`.github/workflows/release.yml`** — Lines 94-96:
- Matrix entry: `embeddings-server` image
- Context: `./src/embeddings-server`
- Dockerfile: `./src/embeddings-server/Dockerfile`

**`.github/workflows/ci.yml`** — Lines 248-287:
- Job: `embeddings-server-tests` (pytest, coverage)
- Result checked in summary job

**`.github/workflows/dependabot-automerge.yml`** — Lines 110-112:
- Audit step for `requirements.txt`

### 1.5 Configuration (Aithena-Specific Cruft)

**`config/__init__.py` — Lines 3-8 (MUST BE REMOVED):**
```python
QDRANT_HOST = ...              # NOT USED
QDRANT_PORT = ...              # NOT USED
STORAGE_ACCOUNT_NAME = ...     # NOT USED
STORAGE_CONTAINER = ...        # NOT USED
EMBEDDINGS_HOST = ...          # Used by document-indexer only
EMBEDDINGS_PORT = ...          # Used by document-indexer only
```

**Verdict:** 4 unused variables (legacy architecture). Delete during extraction.

### 1.6 Integration Tests

**E2E tests** (`e2e/test_search_modes.py`):
- Fixture `embeddings_available()` — HTTP probe
- Tests gated on availability (pytest skip)
- No aithena-specific logic

**No breaking coupling.** Tests can pull from external registry.

---

## 2. API CONTRACT ANALYSIS

### 2.1 Current Endpoints

```
GET  /health
  → { "status": "healthy", "model": "intfloat/multilingual-e5-base", "embedding_dim": 768 }

GET  /version
  → { "service": "embeddings-server", "version": "1.14.1", ... }

GET  /v1/embeddings/model
  → { "model": "...", "embedding_dim": 768, "model_family": "e5", "requires_prefix": true }

POST /v1/embeddings/
  Input:  { "input": ["text1", "text2"], "input_type": "query" | "passage" }
  Output: { "object": "list", "data": [...], "model": "...", "usage": {...} }
```

### 2.2 OpenAI Compatibility

**Compliant:**
- ✅ POST `/v1/embeddings/`
- ✅ Input: `{ "input": string | string[] }`
- ✅ Output structure: `{ "object": "list", "data": [...], "model": "..." }`

**Extensions (Aithena-Specific):**
- `input_type` — Non-standard, required for e5 models (opt-in)
- `GET /v1/embeddings/model` — Custom metadata endpoint

**Verdict: Already 95% OpenAI-compatible. No breaking changes needed for genericization.**

---

## 3. EXTRACTION STRATEGY

### 3.1 What Moves

**New Repository: `github.com/jmservera/embeddings-server`**

```
├── src/main.py, model_utils.py, config/, tests/
├── Dockerfile
├── pyproject.toml, uv.lock, requirements.txt
├── README.md, CONTRIBUTING.md, LICENSE, VERSION
├── buildall.sh
├── .github/workflows/ci.yml, release.yml, dependabot.yml
├── .gitignore, .env.example
```

### 3.2 Aithena Changes

**docker-compose.yml:**
```yaml
embeddings-server:
  image: ghcr.io/jmservera/embeddings-server:${EMBEDDINGS_SERVER_VERSION:-latest}
  expose:
    - "8080"
  environment:
    - MODEL_NAME=${EMBEDDINGS_MODEL_NAME:-intfloat/multilingual-e5-base}
    - PORT=8080
  # ... rest of config unchanged
```

**Changes from current:**
- Remove `build:` section
- Add `image:` pointing to external registry
- New env: `EMBEDDINGS_SERVER_VERSION` (pin to specific release)

**Remove from aithena:**
- `src/embeddings-server/` entire directory
- From `buildall.sh`: embeddings-server build section
- From `release.yml`: embeddings-server matrix entry
- From `ci.yml`: embeddings-server-tests job
- From `dependabot-automerge.yml`: embeddings-server audit

### 3.3 Image Naming

**Current:** `ghcr.io/jmservera/aithena-embeddings-server:1.14.1`  
**Proposed:** `ghcr.io/jmservera/embeddings-server:1.14.1`

Removes `aithena-` prefix, signals genericization and reusability.

---

## 4. VERSION PINNING & CONSUMPTION

### 4.1 Pinning Strategy

**Recommended: Exact version pin**
```bash
# .env.example
EMBEDDINGS_SERVER_VERSION=1.14.1
```

Reproducible, no surprise upgrades. Update when:
1. New model available (e5-large)
2. API changes
3. Critical security fix

### 4.2 Dependabot Integration

aithena can monitor external repo:
```yaml
version: 2
updates:
  - package-ecosystem: "docker"
    directory: "/"
    schedule:
      interval: "weekly"
    ignore:
      - dependency-name: "jmservera/embeddings-server"
        update-types: ["version-update:semver-minor"]
```

### 4.3 Release Coordination Example

**Week 3:** embeddings-server releases v1.1.0 (e5-large, 1024D)
**Week 4:** Aithena releases v1.15.0, pins v1.1.0, updates Solr schema

**Decoupling:** embeddings-server can ship 2-3 releases while aithena ships 1.

---

## 5. GENERICIZATION ROADMAP

### 5.1 Current State (95% Generic)

**Already:**
- ✅ MODEL_NAME fully runtime configurable (Dockerfile ARG)
- ✅ model_utils.py detects model family dynamically
- ✅ Zero aithena, books, documents references
- ✅ Pure HTTP service, runs anywhere
- ✅ No Solr, RabbitMQ, Redis dependencies

### 5.2 Cleanup Required (Minimal)

**Remove from `config/__init__.py`:**
- QDRANT_HOST, QDRANT_PORT (legacy)
- STORAGE_ACCOUNT_NAME, STORAGE_CONTAINER (legacy)
- EMBEDDINGS_HOST, EMBEDDINGS_PORT, CHAT_HOST, CHAT_PORT (aithena-specific)

**Keep:**
- PORT, VERSION, GIT_COMMIT, BUILD_DATE, MODEL_NAME

**Result:** Config file shrinks to pure embeddings-server concerns.

### 5.3 Future Extensions (Phase 2)

Optional, post-extraction:
- Multiple model formats (ONNX, vLLM)
- Request batching/queuing
- Quantization support (INT8)
- Cache-control headers

---

## 6. CI/CD CHANGES (Aithena)

### 6.1 release.yml

**Remove:** embeddings-server from matrix (lines 94-96)

**Impact:** Release job 2-3 minutes faster (no embeddings Dockerfile build).

### 6.2 ci.yml

**Remove:** embeddings-server-tests job (lines 248-287)

**Impact:** Aithena CI depends only on aithena services. embeddings-server has own CI in own repo.

### 6.3 Integration Test Coverage

**Current:** E2E tests require local embeddings-server build.

**After:** E2E tests pull `ghcr.io/jmservera/embeddings-server` image.

**To work after extraction:**
1. `.env` must pin correct EMBEDDINGS_SERVER_VERSION
2. Image must be built/pushed to ghcr.io
3. CI runner must have internet access

**Risk:** Image unavailable → E2E tests fail. **Mitigation:** embeddings-server own CI must pass before push; aithena E2E gracefully skips if unavailable.

---

## 7. INDEPENDENT RELEASE RHYTHM

### 7.1 When to Release

**Critical (immediate):**
- Security fix (sentence-transformers, fastapi, uvicorn)
- API-breaking bug

**High-priority (1 sprint):**
- New model (e5-large)
- Significant performance gain
- Dependency deprecation warning

**Low-priority (batch):**
- Docs, refactoring, logging, test coverage

**Strategy:** Release independently, on-demand. Zero forced coordination.

### 7.2 Versioning

**Recommended: Semantic Versioning**
```
v1.0.0 — multilingual-e5-base
v1.1.0 — e5-large (breaking schema: 768D → 1024D)
v1.1.1 — Patch
v2.0.0 — Multi-model support
```

**Tagging:**
```bash
git tag v1.1.0
git push origin v1.1.0
# Release workflow triggers → image pushed
```

### 7.3 Version Independence Timeline

| Week | embeddings-server | Aithena |
|------|-------------------|---------|
| 1 | v1.0.0 | v1.14.0 (pins v1.0.0) |
| 3 | v1.1.0 (e5-large) | — |
| 4 | — | v1.15.0 (pins v1.1.0) |
| 5 | v1.1.1 patch | — |
| 6 | — | v1.15.1 (pins v1.1.1) |

**Flexibility:** Aithena can skip or selectively adopt releases.

---

## 8. RISKS & MITIGATION

### Risk 1: API Contract Drift
**Mitigation:** Semantic versioning; breaking changes → major version only; compatibility tests in embeddings-server.

### Risk 2: Integration Test Blind Spot
**Mitigation:** embeddings-server own CI must pass before push; aithena E2E checks availability.

### Risk 3: Version Pinning Discipline
**Mitigation:** `.env.example` documents pinning; CI check: `EMBEDDINGS_SERVER_VERSION` not `latest`.

### Risk 4: Dependency Conflicts
**Mitigation:** Services don't share code, only HTTP API. Dep versions can diverge freely.

### Risk 5: Large Image Size
**Mitigation:** Intentional pre-baking (no runtime download). ~500MB acceptable for modern CI.

### Risk 6: Supply Chain Security
**Mitigation:** Branch protection + required review; pin to image SHA256 if strict; verify signatures.

---

## 9. MIGRATION PLAN (4 Weeks)

**Phase 1 (Week 1):** Preparation
- Decide repo name
- Clean config in aithena (remove QDRANT, etc.)
- Add `.env.example` with EMBEDDINGS_SERVER_VERSION

**Phase 2 (Week 2):** New Repo
- Create `github.com/jmservera/embeddings-server`
- Copy files, add docs/CI/workflows
- Set GitHub Actions secrets (HF_TOKEN)
- Release v1.14.1

**Phase 3 (Week 3):** Aithena Cleanup
- Remove `src/embeddings-server/`
- Update docker-compose.yml (pull external image)
- Update buildall.sh, workflows
- Commit to dev

**Phase 4 (Week 4):** Validation & Docs
- Test aithena with external image
- Test embeddings-server standalone
- Write deployment guides

---

## 10. FILE CHECKLIST

### Move to New Repo
- ✓ src/embeddings-server/* (all files)
- ✓ LICENSE (copy)

### Create in New Repo
- ✓ README.md, CONTRIBUTING.md
- ✓ VERSION, .env.example, buildall.sh
- ✓ .github/workflows/ci.yml, release.yml, dependabot.yml
- ✓ .gitignore, .github/CODEOWNERS

### Delete from Aithena
- ✓ src/embeddings-server/ (entire)

### Modify in Aithena
- ✓ docker-compose.yml (remove build, add image + env)
- ✓ .env.example (add EMBEDDINGS_SERVER_VERSION)
- ✓ buildall.sh (remove embeddings-server loop)
- ✓ .github/workflows/release.yml (remove matrix entry)
- ✓ .github/workflows/ci.yml (remove test job)
- ✓ .github/workflows/dependabot-automerge.yml (skip audit)
- ✓ README.md (mention external dependency)

---

## 11. DECISION POINTS FOR RIPLEY

**Decision 1: Go or No-Go?** → **GO** (low-risk, clear benefits)

**Decision 2: Repo Name?** → `embeddings-server` (no aithena prefix, genericized)

**Decision 3: Versioning?** → Independent semver for both repos

**Decision 4: Maintenance?** → jmservera primary; Copilot handles PRs for deps/models

---

## APPENDIX: SERVICE IMPACT

**solr-search:** Uses `EMBEDDINGS_URL=http://embeddings-server:8080/v1/embeddings/`
- No code changes; points to external image
- Risk: Low

**document-indexer:** Uses `EMBEDDINGS_HOST/PORT`
- No code changes; points to external image
- Risk: Low

**document-lister, aithena-ui, admin:** No changes needed
- Risk: None to Low

---

## COST-BENEFIT SUMMARY

| Factor | Impact |
|--------|--------|
| Build time | ↓ 2-3 min faster per release |
| Release frequency | ↑ Model updates decoupled |
| Model reuse | ↑ Generic, reusable beyond aithena |
| API stability | ↔️ More explicit contract |
| E2E test risk | ↔️ Requires internet + version discipline |
| Developer experience | ↓ Two repos, offset by speed |
| Dependency updates | ↑ Faster security response |

**Net: Moderately positive. Extraction pays for itself in faster iteration and reusability.**

