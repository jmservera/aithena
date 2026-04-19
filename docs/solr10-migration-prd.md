# PRD: Solr 10 Migration for Aithena v2.0

> **Status**: Draft — Research & Analysis  
> **Target Release**: v2.0  
> **Author**: Squad (Copilot)  
> **Last Updated**: 2026-03-31  
> **References**: [Solr 10 Major Changes](https://solr.apache.org/guide/solr/latest/upgrade-notes/major-changes-in-solr-10.html)

---

## 1. Executive Summary

Solr 10 is a major release that brings transformative capabilities directly relevant to aithena's architecture: native NLP/embedding generation via ONNX models, GPU-accelerated vector search (cuVS), vector quantization for memory reduction, standalone mode without ZooKeeper, and an overhauled CLI. This PRD analyzes every Solr 10 change against aithena's current 16-service compose topology (12 service roles) to produce a prioritized migration plan.

**Key opportunities:**
- **Eliminate the embeddings-server** — Solr 10's `language-models` module can generate embeddings at index and query time
- **Eliminate 3 ZooKeeper nodes** — Standalone mode or simplified single-node SolrCloud removes ZK entirely
- **Reduce Solr from 3 nodes to 1** — For dev/small deployments; keep 3-node option for production HA
- **GPU-accelerate vector search** — cuVS codec moves kNN from CPU to GPU (40×+ faster index builds)
- **4× memory reduction** — Scalar/binary vector quantization for the 768D embeddings
- **Simplify auth bootstrap** — New Security UI + improved `bin/solr auth` CLI

**Key risks:**
- Java 21 requirement (current: Java 17 via Solr 9.7)
- HNSW parameter renames require schema migration
- CLI double-dash syntax breaks all init scripts
- `blockUnknown` default change (false→true) affects unauthenticated health checks
- `language-models` module depends on external API services (latency, cost, privacy)

---

## 2. Current Architecture Inventory

### 2.1 Service Map (16 compose services / 12 service roles)

| Service | Type | Purpose | Solr 10 Impact |
|---------|------|---------|----------------|
| **solr** (×3 nodes) | Solr 9.7 | Vector DB + full-text search | 🔴 Major: version upgrade, schema migration |
| **zoo1/zoo2/zoo3** (×3) | ZooKeeper 3.9 | Cluster coordination | 🟢 Potentially **removable** |
| **solr-init** | Init container | Auth bootstrap + collection creation | 🔴 Major: CLI syntax rewrite |
| **embeddings-server** | Python/FastAPI | E5-base 768D embedding generation | 🟢 Potentially **removable** |
| **document-indexer** | Python | PDF→chunks→embeddings→Solr | 🟡 Medium: embedding call changes |
| **document-lister** | Python | FS scan → RabbitMQ | ⚪ None |
| **solr-search** | Python/FastAPI | Search API (keyword/semantic/hybrid) | 🟡 Medium: query embedding changes |
| **aithena-ui** | React/TypeScript | Frontend | ⚪ None |
| **nginx** | Reverse proxy | Routing + SSL | ⚪ None |
| **rabbitmq** | Message broker | Document pipeline | ⚪ None |
| **redis** | Cache | Dedup + rate limiting | ⚪ None |
| **redis-commander** | Debug UI | Redis inspection | ⚪ None |

### 2.2 Current Vector Search Architecture

```
┌──────────────┐    PDF     ┌──────────────┐   embed    ┌──────────────────┐
│ document-    │──────────▶│ document-    │──────────▶│ embeddings-      │
│ lister       │  RabbitMQ │ indexer       │  HTTP     │ server           │
└──────────────┘           └──────┬───────┘           │ (E5-base, 768D)  │
                                  │                    └──────────────────┘
                                  │ index (doc + 768D vector)
                                  ▼
                           ┌──────────────┐
                           │ Solr 9.7     │◄──── ZooKeeper (×3)
                           │ (×3 nodes)   │
                           └──────┬───────┘
                                  │ query + kNN
                                  ▼
┌──────────────┐  search   ┌──────────────┐   embed    ┌──────────────────┐
│ aithena-ui   │──────────▶│ solr-search  │──────────▶│ embeddings-      │
│              │           │ (hybrid/kNN) │  HTTP     │ server           │
└──────────────┘           └──────────────┘           └──────────────────┘
```

### 2.3 Key Metrics

| Metric | Current Value |
|--------|--------------|
| Vector dimensions | 768 (multilingual-e5-base) |
| Vector fields | `book_embedding`, `embedding_v` |
| Similarity function | cosine |
| Index algorithm | HNSW |
| HNSW params | `hnswMaxConnections`, `hnswBeamWidth` |
| Solr nodes | 3 (replicationFactor=3, numShards=1) |
| ZooKeeper nodes | 3 |
| Embeddings server memory | 3GB limit |
| Solr per-node memory | 2GB limit |
| Total infra memory | ~18GB (3×Solr + 3×ZK + embeddings + indexer + search + ...) |

---

## 3. Solr 10 Feature Analysis

### 3.1 🟢 Eliminable: Embeddings Server → `language-models` Module

**Current**: aithena runs a dedicated Python embeddings-server (FastAPI + sentence-transformers + multilingual-e5-base) that:
- Serves `POST /v1/embeddings/` for both document-indexer (at index time) and solr-search (at query time)
- Requires 3GB RAM, 1 CPU reserved
- Has separate Docker image with PyTorch/OpenVINO, ~5GB compressed
- Supports "query:" and "passage:" prefixes for E5 models

**Solr 10 alternative**: The `language-models` module (renamed from `llm`) integrates LangChain4j to call external embedding APIs:
- `TextToVectorQParserPlugin` — generates embeddings at query time
- `DocumentCategorizerUpdateProcessorFactory` — performs ONNX-based document classification/sentiment analysis at index time
- Supports HuggingFace, MistralAI, OpenAI, Cohere, and custom endpoints

**Analysis**:

| Factor | Keep embeddings-server | Use language-models module |
|--------|----------------------|---------------------------|
| **Latency** | Local inference (~50ms) | External API call (variable) |
| **Privacy** | All data stays local | Text sent to external API |
| **Cost** | Hardware only | API usage costs |
| **Complexity** | Separate service to maintain | Solr-native, less infra |
| **GPU support** | CUDA/OpenVINO | Depends on provider |
| **Model control** | Full control | Provider-dependent |
| **Offline support** | ✅ Works offline | ❌ Requires API connectivity |

**Recommendation**: **Hybrid approach**
- **Option A (recommended for on-prem)**: Keep embeddings-server for local/private deployments, but refactor to be optional. The `language-models` module can be used for cloud deployments where privacy isn't a concern.
- **Option B (cloud-first)**: Replace embeddings-server with the `language-models` module + self-hosted model server (e.g., TEI). This keeps data private while using Solr-native integration.
- **Option C (full migration)**: For maximum simplification, use the `language-models` module with HuggingFace Inference Endpoints (dedicated, private). Eliminates the embeddings-server entirely.

**Migration effort**: 🟡 Medium — requires changes to document-indexer (remove embedding calls, configure Solr URP) and solr-search (replace direct embedding calls with `{!knn_text_to_vector}` query parser).

### 3.2 🟢 Eliminable: ZooKeeper Ensemble

**Current**: 3 ZooKeeper nodes (512MB each = 1.5GB total) coordinate a 3-node Solr cluster.

**Solr 10 options**:

| Deployment mode | ZK needed? | Solr nodes | HA? | Use case |
|----------------|------------|-----------|-----|----------|
| **Standalone (user-managed)** | ❌ No | 1 | ❌ | Dev, small production |
| **SolrCloud (no Overseer)** | ✅ Yes | 1-N | ✅ | Large production |
| **SolrCloud (Overseer disabled)** | ✅ Yes | 1-N | ✅ | Medium production |

**Recommendation**: Provide **two deployment profiles**:
1. **`docker-compose.yml` (dev/small)**: Single Solr node, standalone mode, **no ZooKeeper** — saves 1.5GB RAM and 3 containers
2. **`docker-compose.prod.yml` (production HA)**: 3 Solr nodes + ZooKeeper with Overseer disabled (Solr 10 recommendation for simpler operations)

**Migration effort**: 🟡 Medium — solr-init script must handle both modes; configset upload changes from `solr zk upconfig` to file-based config in standalone mode.

### 3.3 🟢 New: GPU-Accelerated Vector Search (cuVS)

**Current**: Vector search uses CPU-only HNSW via Lucene. The NVIDIA override only affects the embeddings-server (CUDA for model inference), not Solr's vector indexing/search.

**Solr 10**: The `cuVS` module provides GPU-accelerated approximate nearest neighbor search:
- NVIDIA GPU builds HNSW graphs **40×+ faster** than CPU
- Indexes built on GPU can be searched on CPU (or GPU)
- Uses CAGRA algorithm for HNSW construction
- Configured via codec in schema

**Recommendation**: Add a **new `docker-compose.nvidia-solr.override.yml`** that:
- Runs Solr with NVIDIA GPU passthrough
- Enables the cuVS codec for vector fields
- Supplements the existing NVIDIA override (which only GPU-accelerates embeddings)

**Architecture with full GPU acceleration**:
```
┌──────────────────────────────────────────────────┐
│              NVIDIA GPU                           │
│  ┌────────────────┐  ┌─────────────────────────┐ │
│  │ embeddings-    │  │ Solr 10 + cuVS codec    │ │
│  │ server (CUDA)  │  │ (GPU HNSW build+search) │ │
│  └────────────────┘  └─────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

**Requirements**: NVIDIA GPU, CUDA drivers, cuVS-Lucene JARs in Solr image, `nvidia-container-runtime`.

**Migration effort**: 🟡 Medium — new Solr Dockerfile variant with cuVS JARs, schema codec configuration, override compose file.

### 3.4 🟢 New: Vector Quantization (Memory Reduction)

**Current**: 768D float32 vectors stored as `DenseVectorField`. Each vector = 768 × 4 bytes = 3,072 bytes.

**Solr 10 options**:

| Quantization | Bytes/vector | Memory savings | Accuracy loss |
|-------------|-------------|---------------|---------------|
| None (float32) | 3,072 | Baseline | None |
| Scalar (int8) | 768 | **4× reduction** | Minimal |
| Binary (1-bit) | 96 | **32× reduction** | Moderate |

**Recommendation**: Use **scalar quantization** (int8) by default — 4× memory savings with minimal accuracy loss. Offer binary quantization as an option for very large collections.

**Schema change**:
```xml
<!-- Current (Solr 9.7) -->
<fieldType name="knn_vector_768" class="solr.DenseVectorField"
           vectorDimension="768" similarityFunction="cosine"
           knnAlgorithm="hnsw"/>

<!-- Solr 10: Scalar quantized -->
<fieldType name="knn_vector_768" class="solr.ScalarQuantizedDenseVectorField"
           vectorDimension="768" similarityFunction="cosine"
           knnAlgorithm="hnsw" bits="8"/>
```

**Impact**: For 100K documents × 10 chunks each = 1M vectors:
- Current: 1M × 3,072 = **~3GB** vector data
- Scalar quantized: 1M × 768 = **~750MB**
- Binary quantized: 1M × 96 = **~96MB**

**Migration effort**: 🟢 Low — schema field type change + full reindex required.

### 3.5 🟢 New: `efSearchScaleFactor` (Search Accuracy Tuning)

**Current**: kNN accuracy is tuned only via `topK` — increasing accuracy also increases result count.

**Solr 10**: New `efSearchScaleFactor` parameter allows tuning search accuracy independently of result count. `efSearch = efSearchScaleFactor × topK`.

**Recommendation**: Expose as a configurable parameter in solr-search's semantic search mode. Default `1.0`, allow overriding per-query.

**Migration effort**: 🟢 Low — optional query parameter addition in solr-search.

### 3.6 🟢 New: NLP Classification (DocumentCategorizerUpdateProcessorFactory)

**Current**: Language detection uses Solr's `langid` module. No automatic content classification.

**Solr 10**: `DocumentCategorizerUpdateProcessorFactory` (from Apache OpenNLP) performs sentiment analysis and classification using ONNX models at index time.

**Recommendation**: Evaluate for:
- Automatic document topic classification (replace manual metadata)
- Sentiment analysis for search result ranking
- Language detection upgrade (from langid to OpenNLP ONNX)

**Migration effort**: 🟢 Low — add to URP chain in solrconfig.xml, provide ONNX model.

---

## 4. Breaking Changes & Required Migrations

### 4.1 🔴 CLI Double-Dash Syntax

**Impact**: All init scripts in `docker-compose.yml` and `docker-compose.prod.yml`.

**Current auth bootstrap command shape (both compose files):**
```bash
solr auth enable --type basicAuth \
  -u "$SOLR_ADMIN_USER:$SOLR_ADMIN_PASS" \
  --block-unknown false \
  --solr-include-file /dev/null \
  -z "$ZK_HOST"
```

**Solr 10 equivalent command shape:**
```bash
solr auth enable --type basicAuth \
  --credentials "$SOLR_ADMIN_USER:$SOLR_ADMIN_PASS" \
  --block-unknown false \
  --solr-include-file /dev/null \
  --zk-host "$ZK_HOST"
```

| Changed flag only | Solr 9.7 | Solr 10 | Location |
|-------------------|----------|---------|----------|
| Credentials flag | `-u "user:pass"` | `--credentials "user:pass"` | solr-init entrypoint |
| ZooKeeper flag | `-z "$ZK_HOST"` | `--zk-host "$ZK_HOST"` | solr-init entrypoint |
| zk upconfig flags | `-z ... -n ... -d ...` | `--zk-host ... --name ... --dir ...` | solr-init entrypoint |
| zk ls flag | `-z ...` | `--zk-host ...` | solr-init entrypoint |

**Action**: Update all `solr` CLI invocations in both compose files. Test thoroughly.

### 4.2 🔴 HNSW Parameter Renames

**Impact**: `src/solr/books/managed-schema.xml`

| Current | Solr 10 |
|---------|---------|
| `hnswMaxConnections` | `hnswM` |
| `hnswBeamWidth` | `hnswEfConstruction` |

**Action**: Update schema field type definitions. Requires reindex.

### 4.3 🔴 `blockUnknown` Default Change

**Impact**: Auth bootstrap and health checks.

| | Solr 9.7 | Solr 10 |
|-|---------|---------|
| Default `blockUnknown` | `false` | `true` |
| Unauthenticated `/admin/info/system` | ✅ Allowed | ❌ Blocked |

**Current behavior**: Our init script sets `--block-unknown false` explicitly, so this should still work. But verify that Docker health checks (which use `curl -sf -u $SOLR_AUTH_USER:$SOLR_AUTH_PASS`) are compatible.

**Action**: Verify explicit `--block-unknown false` still works in Solr 10. Consider switching to `true` for better security (requires all health checks to authenticate).

### 4.4 🟡 Java 21 Requirement

**Impact**: Solr Docker image base change.

| | Solr 9.7 | Solr 10 |
|-|---------|---------|
| Base image | eclipse-temurin:17-jre | eclipse-temurin:25-jre-noble |
| Minimum Java | 17 | 21 |
| OS | Ubuntu 22 | Ubuntu 24 |

**Action**: Update `src/solr/Dockerfile` to `FROM solr:10`. The `apt-get install fonts-*` should still work on Ubuntu 24.

### 4.5 🟡 Module Rename: `llm` → `language-models`

**Impact**: If using the text-to-vector module, reference the new name.

**Action**: Use `language-models` in any Solr module configuration.

### 4.6 🟡 Removed: `solr.xml` from ZooKeeper

**Impact**: `solr.xml` can no longer be loaded from ZK. Solr startup will fail if present.

**Action**: Ensure `solr.xml` is only on local filesystem (current behavior is correct — we use built-in defaults).

### 4.7 🟡 Removed Language-Specific Response Writers

**Impact**: `wt=python`, `wt=ruby`, `wt=php`, `wt=phps` removed.

**Action**: Verify solr-search only uses `wt=json` (current behavior — no impact).

### 4.8 🟡 OpenTelemetry Migration (Metrics)

**Impact**: `/admin/metrics` now returns Prometheus format by default, not JSON.

**Action**: If any monitoring queries `/admin/metrics` expecting JSON, update to parse Prometheus format or add `wt=prometheus` explicitly.

### 4.9 🟡 Security: Trusted ConfigSets Removed

**Impact**: All configsets now treated as trusted. Security relies on auth/authz.

**Action**: No code change needed — our auth setup already protects config endpoints via RBAC.

### 4.10 🟡 `PathHierarchyTokenizer` Behavior Change

**Impact**: Token position increments changed from 0 to 1.

**Action**: Check if `ancestor_path` or `descendent_path` field types are used in the books schema (they exist as definitions but may not be used by any fields). If unused, no action needed.

---

## 5. Migration Phases

### Phase 1: Core Upgrade (Required)

**Goal**: Get aithena running on Solr 10 with feature parity.

| Task | Effort | Risk |
|------|--------|------|
| Update `src/solr/Dockerfile` to `FROM solr:10` | Low | Low |
| Update HNSW params in schema (`hnswM`, `hnswEfConstruction`) | Low | Medium (reindex) |
| Rewrite solr-init CLI commands (double-dash syntax) | Medium | High (test thoroughly) |
| Verify `--block-unknown false` behavior | Low | Low |
| Verify health checks work with Java 21 / Jetty 12 | Low | Low |
| Update `src/solr/security.json` for Solr 10 defaults | Low | Low |
| Verify `wt=json` still works for all Solr queries | Low | Low |
| Run full E2E test suite | Medium | — |
| Update CI/CD for Solr 10 image | Low | Low |

### Phase 2: Simplify Infrastructure (High Value)

**Goal**: Reduce container count and resource usage.

| Task | Effort | Savings |
|------|--------|---------|
| Add standalone Solr mode for dev (no ZK) | Medium | -3 containers, -1.5GB RAM |
| Reduce to 1 Solr node for dev | Low | -2 containers, -4GB RAM |
| Keep 3-node SolrCloud for prod (Overseer disabled) | Low | Faster cluster ops |
| Add vector quantization (scalar int8) | Low | 4× vector memory reduction |
| Expose `efSearchScaleFactor` in search API | Low | Better search tuning |

### Phase 3: AI-Native Features (Transformative)

**Goal**: Leverage Solr 10's AI capabilities to simplify or eliminate services.

| Task | Effort | Impact |
|------|--------|--------|
| Evaluate `language-models` module for embedding generation | High | Could eliminate embeddings-server |
| Prototype `DocumentCategorizerUpdateProcessorFactory` | Medium | Auto-classification at index time |
| Add cuVS GPU codec for NVIDIA deployments | Medium | 40×+ faster vector indexing |
| Create `docker-compose.nvidia-solr.override.yml` | Medium | GPU-accelerated search |
| Evaluate hybrid search improvements (if any in Solr 10) | Low | Better search quality |

### Phase 4: Polish & Optimize

| Task | Effort | Impact |
|------|--------|--------|
| OpenTelemetry integration for Solr observability | Medium | Better monitoring |
| Explore new Admin UI (`/solr/ui/`) | Low | Dev experience |
| Review Security UI for simplified user management | Low | Easier admin |
| Update all documentation | Medium | User experience |
| Performance benchmarks (Solr 9.7 vs 10) | Medium | Validation |

---

## 6. Proposed v2.0 Architecture

### 6.1 Development (Simplified)

```
┌──────────────┐    PDF     ┌──────────────┐   embed    ┌──────────────────┐
│ document-    │──────────▶│ document-    │──────────▶│ embeddings-      │
│ lister       │  RabbitMQ │ indexer       │  HTTP     │ server (optional)│
└──────────────┘           └──────┬───────┘           └──────────────────┘
                                  │                         OR
                                  │ index (doc + vector)    Solr generates
                                  ▼                         embeddings via
                           ┌──────────────┐                language-models
                           │ Solr 10      │                module
                           │ (standalone) │ ◄── NO ZooKeeper
                           │ (1 node)     │
                           └──────┬───────┘
                                  │ query + kNN (+ efSearchScaleFactor)
                                  ▼
┌──────────────┐  search   ┌──────────────┐
│ aithena-ui   │──────────▶│ solr-search  │
└──────────────┘           └──────────────┘
```

**Container count**: 8 (from 15) — solr, rabbitmq, redis, document-lister, document-indexer, solr-search, aithena-ui, nginx

### 6.2 Production (Full HA + GPU)

```
┌──────────────────────────────────────────────────────────┐
│                    NVIDIA GPU (optional)                   │
│  ┌────────────────────┐  ┌─────────────────────────────┐ │
│  │ embeddings-server  │  │ Solr 10 + cuVS codec        │ │
│  │ (CUDA inference)   │  │ (GPU HNSW build + search)   │ │
│  └────────────────────┘  └─────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘

                   Solr 10 SolrCloud (Overseer disabled)
                   ┌───────┐ ┌───────┐ ┌───────┐
                   │ solr1 │ │ solr2 │ │ solr3 │
                   └───┬───┘ └───┬───┘ └───┬───┘
                       └────┬────┘────┬────┘
                            │ ZooKeeper (still needed for SolrCloud HA)
                       ┌────┴───┐
                       │ zoo1-3 │  (or embedded ZK in single-node SolrCloud)
                       └────────┘

Vectors: ScalarQuantizedDenseVectorField (int8, 4× memory savings)
```

---

## 7. Resource Savings Estimate

| Resource | Current (Solr 9.7) | v2.0 Dev (Solr 10) | v2.0 Prod (Solr 10) |
|----------|-------------------|--------------------|---------------------|
| **Containers** | 15 | 8 (-47%) | 12-15 |
| **RAM (Solr)** | 6GB (3×2GB) | 2GB (1×2GB) | 6GB (3×2GB) |
| **RAM (ZooKeeper)** | 1.5GB (3×512MB) | 0 | 1.5GB (3×512MB) |
| **RAM (embeddings)** | 3GB | 0-3GB (optional) | 3GB |
| **Vector memory (1M docs)** | ~3GB | ~750MB (int8) | ~750MB (int8) |
| **Total RAM** | ~18GB | ~6-9GB | ~15-18GB |
| **Docker images** | ~8GB total | ~5GB total | ~8GB total |

---

## 8. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| HNSW reindex required | Certain | Medium | Schedule during maintenance window |
| CLI syntax changes break init | High | High | Comprehensive script testing |
| `blockUnknown` default breaks health checks | Low | Medium | Explicit `--block-unknown false` |
| cuVS codec instability | Medium | Low | Optional, CPU fallback always available |
| `language-models` module latency | Medium | Medium | Keep embeddings-server as option |
| Java 21 compatibility issues | Low | Low | Using official Solr 10 Docker image |
| Vector quantization accuracy loss | Low | Low | Benchmark before enabling |
| Data migration (Solr 9→10) | Certain | Medium | Full reindex (collections are rebuildable from source PDFs) |

---

## 9. Decision Points (Require Team Input)

1. **Embeddings strategy**: Keep embeddings-server (local inference) vs. migrate to `language-models` module (Solr-native)? Or both as options?

2. **ZooKeeper elimination**: Remove ZK from dev compose? What about single-machine production deployments?

3. **Vector quantization default**: Scalar (int8, 4× savings, minimal loss) vs. full precision (current)? Make it configurable?

4. **GPU strategy**: Add cuVS support for Solr vector search alongside existing CUDA/OpenVINO embeddings support?

5. **Standalone vs. SolrCloud for dev**: True standalone (cores, no collections) vs. single-node SolrCloud (embedded ZK)?

6. **Auth simplification**: Leverage Solr 10's enhanced Security UI for easier user management? Switch to `blockUnknown: true` for stricter security?

---

## 10. Out of Scope

- Migration to a different search engine (Elasticsearch, Meilisearch, etc.)
- Changes to the document pipeline (RabbitMQ → Kafka, etc.)
- Frontend (aithena-ui) redesign
- Multi-tenancy / multi-collection architecture changes (tracked separately)
- OpenTelemetry distributed tracing across all services (can be a follow-up)

---

## 11. Success Criteria

1. ✅ All existing E2E tests pass on Solr 10
2. ✅ Dev environment starts with ≤8 containers (no ZK)
3. ✅ Vector search quality maintained (benchmark cosine similarity recall@10)
4. ✅ Auth bootstrap works cleanly on fresh start (no role assignment bugs)
5. ✅ Production HA mode still supports 3-node replication
6. ✅ Memory usage reduced by ≥30% for vector-heavy workloads
7. ✅ GPU-accelerated vector search available as opt-in for NVIDIA users

---

## Appendix A: Solr 10 Features Not Applicable to Aithena

| Feature | Why N/A |
|---------|---------|
| SolrJ changes | aithena uses HTTP API, not Java SolrJ client |
| Service installer (systemd) | Docker-only deployment |
| HDFS removal | Not used |
| ExternalFileField removal | Not used |
| CurrencyField removal | Not used |
| EnumField removal | Not used |
| PreAnalyzedField removal | Not used |
| XLSX writer removal | Not used (`wt=json` only) |
| Prometheus exporter removal | Not currently monitoring Solr metrics |
| JaspellLookupFactory removal | Not using suggester |
| ManagedSynonymFilterFactory removal | Not used (using SynonymGraphFilter) |
| LowerCaseTokenizer removal | Not used directly |
| TikaLanguageIdentifier removal | Using `langid` module, not Tika |
| `<lib/>` directive removal | Using module system |

## Appendix B: File Change Inventory

| File | Changes Required |
|------|-----------------|
| `src/solr/Dockerfile` | `FROM solr:10`, verify `apt-get` for Ubuntu 24 |
| `src/solr/books/managed-schema.xml` | Rename HNSW params, optionally add quantized field types |
| `src/solr/security.json` | Align with Solr 10 defaults (already done for Solr 9.7) |
| `docker-compose.yml` | solr-init CLI syntax, optional standalone mode |
| `docker-compose.prod.yml` | solr-init CLI syntax, Overseer disabled config |
| `docker-compose.nvidia.override.yml` | Add cuVS codec support for Solr |
| `src/solr-search/` | `efSearchScaleFactor` support, optional text-to-vector |
| `src/document-indexer/` | Optional: remove embedding calls if using Solr-native |
| `src/solr-search/tests/test_solr_init_script.py` | Update CLI syntax assertions |
| `docs/` | Update deployment guides, add Solr 10 migration notes |
