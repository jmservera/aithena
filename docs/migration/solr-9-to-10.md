# Solr 9 → 10 Migration Plan

> **Status**: Ready for review
> **Created**: 2026-04-01
> **Based on**: [Solr 10 Migration PRD](../prd/solr10-migration-prd.md)
> **Issue**: [#1364](https://github.com/jmservera/aithena/issues/1364)
> **Target Release**: v2.0

---

## Table of Contents

1. [Pre-Migration Assessment](#1-pre-migration-assessment)
2. [Breaking Changes in Solr 10](#2-breaking-changes-in-solr-10)
3. [Migration Steps](#3-migration-steps)
4. [Rollback Plan](#4-rollback-plan)
5. [Testing Strategy](#5-testing-strategy)
6. [Timeline and Dependencies](#6-timeline-and-dependencies)

---

## 1. Pre-Migration Assessment

### 1.1 Current Solr Version and Configuration

| Component | Current |
|-----------|---------|
| Solr version | 9.7 (`FROM solr:9.7` in `src/solr/Dockerfile`) |
| Java version | 17 (eclipse-temurin:17-jre via Solr 9.7 base image) |
| Lucene match version | 9.10 (`solrconfig.xml`) |
| Deployment mode | SolrCloud (3 nodes: `solr`, `solr2`, `solr3`) |
| ZooKeeper | 3 nodes (`zoo1`, `zoo2`, `zoo3`) at port 2181 |
| Modules loaded | `extraction`, `langid` (`SOLR_MODULES` env var) |
| Collection | `books` (1 shard, replication factor 3) |
| Solr per-node memory | 2 GB limit |

### 1.2 Schema Analysis (`src/solr/books/managed-schema.xml`)

**Field types (notable)**:

| Field Type | Class | Notes |
|-----------|-------|-------|
| `knn_vector_768` | `solr.DenseVectorField` | 768-dim, cosine, HNSW (default params) |
| `text_general` | `solr.TextField` | Standard + stopwords + lowercase + ASCII folding |
| `text_en` | `solr.TextField` | English with stemming, synonyms |
| `text_es` | `solr.TextField` | Spanish light stemmer |
| `text_ca` | `solr.TextField` | Catalan with Snowball porter |
| `text_fr` | `solr.TextField` | French light stemmer |
| `string` | `solr.StrField` | Used for faceting fields (`*_s`) |
| `pint`/`plong`/`pdate` | Point types | Numeric/date fields with docValues |

**Vector fields**:

| Field | Type | Purpose |
|-------|------|---------|
| `book_embedding` | `knn_vector_768` | Book-level semantic search (768D, cosine) |
| `embedding_v` | `knn_vector_768` | Chunk-level embedding for granular search |

**HNSW configuration**: Uses defaults — `hnswMaxConnections` and `hnswBeamWidth` are **not** explicitly set in the schema. This simplifies migration since the Solr 10 parameter renames (`hnswM`, `hnswEfConstruction`) do not require a schema edit.

**Key fields** (book metadata, ADR-002):
- `title_s`/`title_t`, `author_s`/`author_t`, `year_i`, `category_s`, `language_detected_s`, `series_s`
- `file_path_s`, `folder_path_s`, `page_count_i`, `file_size_l`
- Chunk fields: `parent_id_s`, `chunk_index_i`, `chunk_text_t`, `page_start_i`, `page_end_i`

**Dynamic fields**: 40+ dynamic field patterns (`*_s`, `*_i`, `*_txt_en`, `*_txt_es`, etc.)

**Copy fields**: `title_t` → `_text_`, `author_t` → `_text_`, `_text_` → `content`, plus various `*_str` copies for docValues.

### 1.3 Custom Configurations (`src/solr/books/solrconfig.xml`)

The `solrconfig.xml` lives inside the `books` configset directory. Key settings:

| Setting | Value | Impact |
|---------|-------|--------|
| `luceneMatchVersion` | `9.10` | Must update to `10.x` for Solr 10 |
| `dataDir` | `${solr.data.dir:}` | No change needed |
| Request handlers | Default + `/update/extract` (added via overlay) | Overlay script unchanged |
| Update processor | `langid` chain (via `add-conf-overlay.sh`) | Verify langid module compatibility |

The `add-conf-overlay.sh` script adds at runtime:
- `/update/extract` request handler (Tika extraction with langid chain)
- `my-init` initParams (sets default `df=content`)
- `local_repo` backup repository

### 1.4 Security Configuration

**File**: `src/solr/security.json`

| Setting | Value |
|---------|-------|
| Auth plugin | `solr.BasicAuthPlugin` |
| `blockUnknown` | `false` (explicitly set) |
| Authorization | `solr.RuleBasedAuthorizationPlugin` |
| Roles | `superadmin`, `admin`, `search`, `index` |
| Health endpoint | `role: null` (unauthenticated access) |
| Metrics endpoint | `role: null` (unauthenticated access) |

**Users** (bootstrapped by `solr-init`):
- Admin user (`solr_admin`): roles `superadmin`, `admin`, `search`, `index`
- Readonly user (`solr_read`): role `search`

### 1.5 SolrCloud Topology

| Parameter | Dev (`docker-compose.yml`) | Prod (`docker-compose.prod.yml`) |
|-----------|---------------------------|----------------------------------|
| Solr nodes | 3 (`solr`, `solr2`, `solr3`) | 3 (`solr`, `solr2`, `solr3`) |
| ZooKeeper nodes | 3 (`zoo1`, `zoo2`, `zoo3`) | 3 (`zoo1`, `zoo2`, `zoo3`) |
| Shards | 1 (`SOLR_NUM_SHARDS`) | 1 |
| Replication factor | 3 (`SOLR_REPLICATION_FACTOR`) | 3 |
| ZK connection | `zoo1:2181,zoo2:2181,zoo3:2181` | `zoo1:2181,zoo2:2181,zoo3:2181` |
| Init container | `solr-init` (runs once) | `solr-init` (runs once) |

### 1.6 Dependent Services

| Service | How it uses Solr | Migration impact |
|---------|-----------------|------------------|
| `solr-search` (Python/FastAPI) | HTTP queries via `SOLR_URL=http://solr:8983/solr`, uses `wt=json` | 🟡 Verify query compatibility |
| `document-indexer` (Python) | Indexes documents + 768D vectors via HTTP | 🟡 Verify indexing compatibility |
| `nginx` | Proxies to `solr-search`, reads Solr auth from `docker-entrypoint-solr-auth.sh` | ⚪ No change |
| Backup scripts (`scripts/backup*.sh`) | Uses Solr Collections API for snapshots | 🟡 Verify API compatibility |

---

## 2. Breaking Changes in Solr 10

### 2.1 CLI Double-Dash Syntax (🔴 High Impact)

All `solr` CLI commands now require full double-dash flags. This breaks every `solr` invocation in our `solr-init` entrypoint.

| Command | Solr 9.7 Syntax | Solr 10 Syntax |
|---------|-----------------|----------------|
| Auth enable credentials | `-u "user:pass"` | `--credentials "user:pass"` |
| ZooKeeper host | `-z "$ZK_HOST"` | `--zk-host "$ZK_HOST"` |
| ZK upconfig name | `-n books` | `--name books` |
| ZK upconfig dir | `-d /configsets/books` | `--dir /configsets/books` |
| ZK ls host | `-z "$ZK_HOST"` | `--zk-host "$ZK_HOST"` |
| ZK cp host | `-z "$ZK_HOST"` | `--zk-host "$ZK_HOST"` |

**Affected files**:
- `docker-compose.yml` — solr-init entrypoint (lines ~710–798)
- `docker-compose.prod.yml` — solr-init entrypoint (lines ~658–736)

### 2.2 HNSW Parameter Renames (🟢 Low Impact for Us)

| Solr 9 | Solr 10 |
|--------|---------|
| `hnswMaxConnections` | `hnswM` |
| `hnswBeamWidth` | `hnswEfConstruction` |

**Our impact**: **None** — our schema uses defaults and does not explicitly set these parameters. If custom HNSW tuning is added later, use the Solr 10 names.

### 2.3 `blockUnknown` Default Change (🟡 Medium Impact)

| | Solr 9.7 | Solr 10 |
|-|---------|---------|
| Default `blockUnknown` | `false` | `true` |

**Our impact**: We explicitly set `--block-unknown false` in the init script and have `"blockUnknown": false` in `security.json`. Verify this explicit setting is still honored in Solr 10. Docker health checks authenticate with credentials, so they should work either way.

### 2.4 Java 21 Requirement (🟡 Medium Impact)

| | Solr 9.7 | Solr 10 |
|-|---------|---------|
| Base image | `eclipse-temurin:17-jre` | `eclipse-temurin:25-jre-noble` |
| Minimum Java | 17 | 21 |
| OS base | Ubuntu 22 | Ubuntu 24 |

**Our impact**: Update `src/solr/Dockerfile` from `FROM solr:9.7` to `FROM solr:10`. The `apt-get install fonts-liberation fonts-dejavu-core` should still work on Ubuntu 24.

### 2.5 `luceneMatchVersion` Update

The `solrconfig.xml` setting `<luceneMatchVersion>9.10</luceneMatchVersion>` must be updated to the Solr 10 Lucene version. Solr 10 ships with Lucene 10.x.

**Action**: Update to `<luceneMatchVersion>10.0</luceneMatchVersion>` (or the exact version bundled with Solr 10). A full reindex is recommended after changing this setting.

### 2.6 Module Rename: `llm` → `language-models`

If the `language-models` module is used in a future phase, reference the new module name. Current `SOLR_MODULES: extraction,langid` is unaffected.

### 2.7 Removed: `solr.xml` from ZooKeeper

`solr.xml` can no longer be loaded from ZK. Our setup uses built-in defaults (no custom `solr.xml` in ZK), so **no impact**.

### 2.8 Removed Language-Specific Response Writers

`wt=python`, `wt=ruby`, `wt=php`, `wt=phps` are removed. Our `solr-search` service uses `wt=json` exclusively — **no impact**.

### 2.9 OpenTelemetry Metrics Format

`/admin/metrics` now returns Prometheus format by default instead of JSON. If any monitoring fetches this endpoint expecting JSON, update accordingly.

### 2.10 `PathHierarchyTokenizer` Behavior Change

Token position increments changed from 0 to 1. The `ancestor_path` and `descendent_path` field types are defined in our schema but not used by any concrete fields — **no impact**.

### 2.11 Trusted ConfigSets Removed

All configsets are now treated as trusted. Our auth/RBAC setup already protects config endpoints — **no impact**.

### 2.12 `language-models` Module: Remote-Only Embeddings

Solr 10's `language-models` module supports remote API embedding providers only (OpenAI, Cohere, HuggingFace, Mistral). There is **no** local/in-process ONNX embedding runtime. SOLR-17446 tracks future in-process support. This means our `embeddings-server` cannot be eliminated via Solr-native embeddings unless we use an external API or self-hosted inference endpoint.

---

## 3. Migration Steps

### Phase 1: Pre-Migration Preparation (on Solr 9.7)

#### Step 1.1: Full Backup

Run the existing BCDR backup scripts to capture the current state:

```bash
# Full backup — all tiers
./scripts/backup.sh --tier all --dest /source/backups/pre-solr10-migration

# Verify backup integrity
./scripts/verify-backup.sh /source/backups/pre-solr10-migration
```

This captures:
- **Tier 1 (Critical)**: Auth DBs + secrets
- **Tier 2 (High)**: Solr indexes + ZooKeeper state
- **Tier 3 (Medium)**: Redis RDB + RabbitMQ definitions

#### Step 1.2: Export Collection Data

Use the Solr Collections API to create a snapshot (prerequisite: #1362 export tooling):

```bash
# Create Solr backup of the books collection
curl -u "$SOLR_ADMIN_USER:$SOLR_ADMIN_PASS" \
  "http://solr:8983/solr/admin/collections?action=BACKUP&name=books-pre-solr10&collection=books&repository=local_repo&wt=json"
```

#### Step 1.3: Record Current Metrics

Capture baseline performance metrics before migration for comparison:

```bash
# Run the benchmark suite
cd scripts/benchmark
python run_benchmark.py --output pre-migration-baseline.json
```

### Phase 2: Configuration Updates

#### Step 2.1: Update Dockerfile

**File**: `src/solr/Dockerfile`

```dockerfile
# Before (Solr 9.7)
FROM solr:9.7

# After (Solr 10)
FROM solr:10
```

Verify that `apt-get install fonts-liberation fonts-dejavu-core` still works on the Ubuntu 24 base.

#### Step 2.2: Update `luceneMatchVersion`

**File**: `src/solr/books/solrconfig.xml`

```xml
<!-- Before -->
<luceneMatchVersion>9.10</luceneMatchVersion>

<!-- After -->
<luceneMatchVersion>10.0</luceneMatchVersion>
```

#### Step 2.3: Update `solr-init` CLI Commands

**Files**: `docker-compose.yml`, `docker-compose.prod.yml`

Replace all Solr 9 CLI syntax with Solr 10 double-dash equivalents in the `solr-init` entrypoint:

```bash
# Before (Solr 9.7)
solr zk cp file:/tmp/empty-security.json zk:/security.json -z "$ZK_HOST"

solr auth enable --type basicAuth \
  -u "$SOLR_ADMIN_USER:$SOLR_ADMIN_PASS" \
  --block-unknown false \
  --solr-include-file /dev/null \
  -z "$ZK_HOST"

solr zk upconfig -z "$ZK_HOST" -n books -d /configsets/books

solr zk ls /configs -z "$ZK_HOST"

# After (Solr 10)
solr zk cp file:/tmp/empty-security.json zk:/security.json --zk-host "$ZK_HOST"

solr auth enable --type basicAuth \
  --credentials "$SOLR_ADMIN_USER:$SOLR_ADMIN_PASS" \
  --block-unknown false \
  --solr-include-file /dev/null \
  --zk-host "$ZK_HOST"

solr zk upconfig --zk-host "$ZK_HOST" --name books --dir /configsets/books

solr zk ls /configs --zk-host "$ZK_HOST"
```

#### Step 2.4: Verify Security Configuration

Confirm `src/solr/security.json` is compatible with Solr 10:
- `"blockUnknown": false` — still supported, but Solr 10 defaults to `true` when not set
- `"health"` and `"metrics-read"` permissions with `"role": null` — verify unauthenticated access still works
- RBAC rules — verify `solr.RuleBasedAuthorizationPlugin` API is unchanged

#### Step 2.5: Optional Schema Enhancements (Post-Upgrade)

These are not required for the core upgrade but can be done after verification:

**Vector quantization** (4× memory savings):
```xml
<!-- Replace in managed-schema.xml -->
<!-- Before -->
<fieldType name="knn_vector_768" class="solr.DenseVectorField"
           vectorDimension="768" similarityFunction="cosine"
           knnAlgorithm="hnsw"/>

<!-- After (scalar quantized) -->
<fieldType name="knn_vector_768" class="solr.DenseVectorField"
           vectorDimension="768" similarityFunction="cosine"
           knnAlgorithm="hnsw" vectorEncoding="INT8"/>
```

> **Note**: Vector quantization requires a full reindex.

### Phase 3: Docker Image Swap

#### Step 3.1: Stop All Services

```bash
docker compose down
```

#### Step 3.2: Build New Solr Image

```bash
docker compose build solr
```

#### Step 3.3: Start Infrastructure Services First

```bash
# Start ZooKeeper ensemble first
docker compose up -d zoo1 zoo2 zoo3

# Wait for ZK to be healthy, then start Solr nodes
docker compose up -d solr solr2 solr3

# Wait for all Solr nodes to be healthy
docker compose up -d solr-init
```

#### Step 3.4: Verify Solr Startup

```bash
# Check Solr version
curl -u "$SOLR_ADMIN_USER:$SOLR_ADMIN_PASS" \
  http://localhost:8983/solr/admin/info/system?wt=json | jq '.lucene["solr-spec-version"]'

# Verify all 3 nodes joined the cluster
curl -u "$SOLR_ADMIN_USER:$SOLR_ADMIN_PASS" \
  "http://localhost:8983/solr/admin/collections?action=CLUSTERSTATUS&wt=json" | jq '.cluster.live_nodes'

# Verify books collection exists
curl -u "$SOLR_ADMIN_USER:$SOLR_ADMIN_PASS" \
  "http://localhost:8983/solr/admin/collections?action=LIST&wt=json"
```

### Phase 4: Data Migration / Re-Indexing

Solr 10 uses Lucene 10, which may not be backward-compatible with Lucene 9 index segments. A full reindex is the safest approach.

#### Step 4.1: Reindex from Source

Since all documents originate from source PDFs, trigger a full reindex:

```bash
# Start the document pipeline
docker compose up -d rabbitmq document-lister document-indexer embeddings-server

# The document-lister will scan the book library and queue all PDFs
# The document-indexer will process them and index into Solr 10
```

Alternatively, if the export/import tooling (#1362/#1363) is available:

```bash
# Import from a previously exported JSON dump
python scripts/import_collection.py --source /source/backups/books-export.json
```

#### Step 4.2: Verify Document Count

```bash
# Check document count matches pre-migration
curl -u "$SOLR_ADMIN_USER:$SOLR_ADMIN_PASS" \
  "http://localhost:8983/solr/books/select?q=*:*&rows=0&wt=json" | jq '.response.numFound'
```

### Phase 5: Verification

#### Step 5.1: Start Remaining Services

```bash
docker compose up -d
```

#### Step 5.2: Run Verification Suite

```bash
# Run the collection verification script
python scripts/verify_collections.py

# Run the benchmark suite and compare with pre-migration baseline
cd scripts/benchmark
python run_benchmark.py --output post-migration-solr10.json
```

#### Step 5.3: Functional Verification

| Test | Command / Check | Expected |
|------|----------------|----------|
| Health check | `curl http://localhost:8983/solr/admin/info/system` | 200 OK |
| Auth works | `curl -u solr_admin:... http://localhost:8983/solr/books/select?q=*:*` | 200 OK |
| Readonly user | `curl -u solr_read:... http://localhost:8983/solr/books/select?q=*:*` | 200 OK |
| Keyword search | Search via `solr-search` API for a known title | Results returned |
| Semantic search | kNN vector search via `solr-search` API | Results with scores |
| Hybrid search | Combined keyword + semantic search | Fused results |
| Facets | Request facets on `author_s`, `category_s`, `year_i` | Correct facet counts |
| Document indexing | Upload a test PDF via `document-indexer` | Document appears in search |
| Highlighting | Search with highlighting on `content`, `_text_` | Highlighted snippets |
| Backup | `curl .../admin/collections?action=BACKUP&...` | Backup created |
| UI search | Open aithena-ui, perform a search | Results displayed |

---

## 4. Rollback Plan

### 4.1 Rollback Decision Criteria

Trigger rollback if any of these occur after migration:
- Solr nodes fail to start or form a cluster
- `solr-init` cannot bootstrap security or create collections
- Document indexing fails (pipeline broken)
- Search quality regression > 10% on benchmark queries
- Unrecoverable data corruption

### 4.2 Rollback Procedure

#### Quick Rollback (< 30 minutes)

1. **Stop all services**:
   ```bash
   docker compose down
   ```

2. **Revert Dockerfile**:
   ```bash
   git checkout HEAD -- src/solr/Dockerfile
   # Also revert solrconfig.xml luceneMatchVersion and compose file CLI changes
   ```

3. **Restore Solr data volumes from backup**:
   ```bash
   ./scripts/restore.sh --from /source/backups/pre-solr10-migration --tier high
   ```

4. **Rebuild and restart with Solr 9.7**:
   ```bash
   docker compose build solr
   docker compose up -d
   ```

5. **Verify restoration**:
   ```bash
   python scripts/verify_collections.py
   ```

### 4.3 Data Compatibility Notes

- **Solr 10 → Solr 9 index**: Lucene 10 indexes are **not** backward-compatible with Solr 9. You must restore from backup or reindex.
- **ZooKeeper state**: ZK data should be compatible, but restore from backup to be safe.
- **Security config**: The `security.json` format is compatible between versions.

---

## 5. Testing Strategy

### 5.1 Dual-Stack Testing (Recommended)

Run Solr 9 and Solr 10 in parallel to validate before cutting over:

```bash
# Start a Solr 10 test instance on a different port
docker run -d --name solr10-test \
  -p 8984:8983 \
  -e SOLR_MODULES=extraction,langid \
  solr:10 solr-fg

# Create a test collection and index a subset of documents
# Run verification queries against both instances and compare results
```

### 5.2 Automated Test Suite

Run existing tests that exercise Solr interactions:

```bash
# solr-search unit/integration tests
cd src/solr-search && uv run pytest --tb=short -q

# Benchmark tests
cd scripts/benchmark && uv run pytest --tb=short -q

# Collection verification
python scripts/verify_collections.py
```

### 5.3 Verification Queries

Test these query patterns against Solr 10:

| Query Type | Example | What to Verify |
|-----------|---------|----------------|
| Simple keyword | `q=machine learning` | BM25 scoring, result count |
| Filtered | `q=*:*&fq=language_detected_s:en` | Filter queries work |
| Faceted | `facet=true&facet.field=author_s` | Facet counts correct |
| kNN vector | `{!knn f=book_embedding topK=10}[0.1, 0.2, ...]` | Vector search returns results |
| Hybrid | Keyword + kNN reranking | Fused scores reasonable |
| Highlighting | `hl=true&hl.fl=content,_text_` | Snippets returned |
| Tika extraction | POST PDF to `/update/extract` | Content extracted, langid detected |
| Sort | `sort=year_i desc` | Correct ordering |
| Pagination | `start=10&rows=10` | Offset works |

### 5.4 Performance Benchmarks

Compare these metrics before and after migration:

| Metric | Tool | Acceptable Threshold |
|--------|------|---------------------|
| Keyword search p95 latency | `scripts/benchmark/run_benchmark.py` | ≤ 1.5× pre-migration |
| kNN search p95 latency | `scripts/benchmark/run_benchmark.py` | ≤ 1.5× pre-migration |
| Indexing throughput (docs/sec) | Manual test with `index_test_corpus.py` | ≥ 0.8× pre-migration |
| Memory usage per node | `docker stats` | ≤ pre-migration |
| Startup time (cold) | Time from `docker compose up` to healthy | ≤ 2× pre-migration |

---

## 6. Timeline and Dependencies

### 6.1 Prerequisites

| Dependency | Issue | Status | Required For |
|-----------|-------|--------|-------------|
| Schema field pre-definition (Tika fields) | [#1360](https://github.com/jmservera/aithena/issues/1360) | ✅ Done | Phase 1 |
| Collection export tooling | [#1362](https://github.com/jmservera/aithena/issues/1362) | 🔄 In progress | Phase 4 (optional, for data export) |
| Collection import tooling | [#1363](https://github.com/jmservera/aithena/issues/1363) | 🔄 In progress | Phase 4 (optional, for data import) |
| Solr 9/10 compatibility layer | [#1365](https://github.com/jmservera/aithena/issues/1365) | 📋 Planned | Phase 2 (CLI abstraction) |

### 6.2 Execution Phases

| Phase | Description | Effort | Depends On |
|-------|-------------|--------|-----------|
| **Phase 1** | Pre-migration backup + baseline metrics | Low (1 day) | — |
| **Phase 2** | Configuration updates (Dockerfile, CLI syntax, solrconfig) | Medium (2–3 days) | #1365 (compatibility layer) |
| **Phase 3** | Docker image swap + cluster startup | Low (1 day) | Phase 2 |
| **Phase 4** | Reindex / data migration | Medium (1–3 days, depends on corpus size) | Phase 3, optionally #1362/#1363 |
| **Phase 5** | Verification + benchmarking | Medium (1–2 days) | Phase 4 |
| **Total** | | **6–10 days** | |

### 6.3 Future Phases (Post-Migration)

These are tracked separately and not required for the core Solr 9 → 10 upgrade:

| Phase | Description | Issue/Tracking |
|-------|-------------|---------------|
| ZooKeeper removal (dev) | Standalone Solr mode for `docker-compose.yml` | PRD Phase 2 |
| Vector quantization | Scalar int8 encoding for 4× memory savings | PRD Phase 2 |
| `efSearchScaleFactor` | Expose search accuracy tuning in `solr-search` | PRD Phase 2 |
| GPU vector search (cuVS) | NVIDIA-accelerated HNSW for Solr | PRD Phase 3 |
| `language-models` module evaluation | Solr-native embeddings (remote API only) | PRD Phase 3 |

### 6.4 File Change Summary

| File | Change Type | Description |
|------|------------|-------------|
| `src/solr/Dockerfile` | Edit | `FROM solr:9.7` → `FROM solr:10` |
| `src/solr/books/solrconfig.xml` | Edit | `luceneMatchVersion` 9.10 → 10.0 |
| `docker-compose.yml` | Edit | solr-init CLI double-dash syntax |
| `docker-compose.prod.yml` | Edit | solr-init CLI double-dash syntax |
| `src/solr/security.json` | Verify | Confirm `blockUnknown: false` compat |
| `src/solr/books/managed-schema.xml` | No change (Phase 1) | HNSW defaults are fine; quantization is Phase 2 |
| `src/solr-search/` | No change (Phase 1) | Uses `wt=json`, HTTP API unchanged |
| `src/solr/add-conf-overlay.sh` | No change | Uses HTTP API, not CLI |
| `scripts/backup*.sh` / `scripts/restore*.sh` | Verify | Confirm Collections API compat |
