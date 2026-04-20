# Production Migration Plan: e5-base Embedding Model

**Author:** Brett (Infrastructure Architect)  
**Requested by:** Juanma (PO)  
**Date:** 2026-03-26  
**Issue:** #876  
**Status:** DRAFT — Awaiting PO Approval of A/B Test Results

---

## 1. Overview

This plan defines the step-by-step process for migrating Aithena's production search from `distiluse-base-multilingual-cased-v2` (128-token, 512D) to `multilingual-e5-base` (512-token, 768D) after successful A/B testing (Phase 1+2 complete).

**When to use this plan:** After PO confirms A/B test results (issue #877) and approves migration via approval gate in #876.

**Scope:** Production environment (`docker/compose.prod.yml`), full library re-indexing, blue/green cutover strategy, 48-hour monitoring window.

---

## 2. Pre-Migration Checklist

All items below **must** be completed before the migration window begins.

### 2.1 A/B Test Results Review
- [ ] **PO approval:** A/B test results (issue #877) reviewed and approved by Juanma
  - Baseline metrics (NDCG, latency, user satisfaction) vs e5-base performance
  - No regressions in critical query categories (multilingual, long-context)
  - Improvement in semantic relevance vs keyword-only baseline
- [ ] **Benchmark metrics:** e5-base meets or exceeds baseline across all modes (keyword, semantic, hybrid)
  - Verify with: `python scripts/benchmark/run_benchmark.py`
  - Generate final report with production-equivalent library sample
  - Document any query types with lower overlap (expected for improved relevance)

### 2.2 Infrastructure Readiness
- [ ] **Disk space:** Verify sufficient Solr disk for re-indexed collection
  - Current `books` collection size: `<estimated from du>`
  - e5-base `books_e5base` collection size: ~55% smaller (fewer chunks, 768D vectors)
  - Total required: `2 × (current size)` during re-indexing (old + new collections coexist)
- [ ] **Memory capacity:** Verify embeddings-server-e5 fits in production resource envelope
  - e5-base embeddings-server requires ~3GB RAM
  - document-indexer-e5 requires ~512MB RAM
  - Validate with cluster monitoring: `docker stats --no-stream`
- [ ] **Network capacity:** RabbitMQ fanout topology tested with full production document volume
  - Simulated with: `python scripts/index_test_corpus.py --all`
  - Verified indexing throughput: _X_ docs/minute baseline vs _Y_ docs/minute e5-base
- [ ] **Rollback plan tested:** See issue #XXX (P3-3)
  - Verified ability to revert `SOLR_COLLECTION=books` in solr-search config
  - Tested ZK restore from backup taken pre-migration
  - Documented RTO/RPO metrics

### 2.3 Configuration Review
- [ ] **Chunking parameters finalized:**
  - `CHUNK_SIZE=300` words (e5-base, from CHUNK_SIZE=90 distiluse)
  - `CHUNK_OVERLAP=50` words (from CHUNK_OVERLAP=10 distiluse)
  - Rationale: Proportional scaling maintains semantic continuity; 512-token context window supports 300+ word chunks
- [ ] **Solr schema validated:**
  - `knn_vector_768` field type deployed to ZK configset (from Phase 1-2 infrastructure)
  - Verified schema compatibility across all 3 Solr nodes
  - No analyzer or similarity function changes needed (same cosine distance)
- [ ] **embeddings-server-e5 image ready:**
  - Built with `MODEL_NAME=intfloat/multilingual-e5-base` baked in (HF_HUB_OFFLINE=1)
  - Tested prefix handling: `"query: "` and `"passage: "` auto-applied by server
  - Health check validated (responds to `/health` and `/v1/embeddings/model` within 10s)

---

## 3. Migration Steps (Sequential)

**Timeline:** ~12–48 hours depending on library size (see Section 4).

Each step must complete successfully before proceeding. Monitor logs at each stage.

### Step 1: Prepare Production Compose (1 hour, no downtime)

Update `docker/compose.prod.yml` to include e5-base indexing pipeline.

**Changes:**
1. **Add `embeddings-server-e5` service** (from dev `docker-compose.yml`)
   - Image: `ghcr.io/jmservera/aithena-embeddings-server:${VERSION}`
   - Build arg: `MODEL_NAME=intfloat/multilingual-e5-base`
   - Environment: `HF_HUB_OFFLINE=1` (pre-baked model)
   - Port: `8085` (internal only, no expose to host)
   - Memory limit: `3g`
   - Healthcheck: `wget -qO /dev/null http://localhost:8085/health`
   - Depends on: `solr` (service_healthy)

2. **Add `document-indexer-e5` service** (from dev `docker-compose.yml`)
   - Image: `ghcr.io/jmservera/aithena-document-indexer:${VERSION}`
   - Environment:
     - `QUEUE_NAME=shortembeddings_e5base`
     - `EXCHANGE_NAME=documents`
     - `SOLR_COLLECTION=books_e5base`
     - `CHUNK_SIZE=300`
     - `CHUNK_OVERLAP=50`
     - `EMBEDDINGS_HOST=embeddings-server-e5`
     - `EMBEDDINGS_PORT=8085`
   - Memory limit: `512m`
   - Depends on: `embeddings-server-e5` (service_healthy), `solr-init` (service_completed_successfully)

3. **Validate compose syntax:**
   ```bash
   python3 -c "import yaml; yaml.safe_load(open('docker/compose.prod.yml'))"
   ```

4. **Commit and tag:**
   - Create branch: `squad/876-prod-migration-prep`
   - PR to `dev` with reference to #876
   - Merge before proceeding to Step 2

### Step 2: Deploy Dual-Indexing Configuration (2–4 hours, live migration begins)

**Action:** Restart production with both baseline and e5-base indexing.

```bash
docker-compose -f docker/compose.prod.yml up -d embeddings-server-e5 document-indexer-e5
```

**Verification:**
- Both indexers healthy: `docker ps` shows both services running
- RabbitMQ fanout topology confirmed:
  - `documents` exchange routes to both `shortembeddings` and `shortembeddings_e5base` queues
  - Verify with: `docker exec rabbitmq rabbitmqctl list_bindings | grep documents`
- Both Solr collections initialized:
  - `books` (baseline, still receiving documents)
  - `books_e5base` (candidate, indexing in parallel)

### Step 3: Re-Index Full Library into `books_e5base` (12–36 hours, depends on library size)

**Action:** Publish all documents to RabbitMQ fanout exchange. Both indexers consume in parallel.

```bash
# From production host (or via kubectl job if k8s):
docker exec document-lister python scripts/index_test_corpus.py --all
```

**Monitoring during indexing:**
- **RabbitMQ queue depth:** Both `shortembeddings` and `shortembeddings_e5base` should stay shallow (0–10 msgs)
  - If `shortembeddings_e5base` grows unbounded → `document-indexer-e5` is unhealthy
  - Check logs: `docker logs document-indexer-e5`
- **Solr collection sizes:** Monitor via Solr admin UI
  - `books` parent docs should remain stable (no net change in duplicate indexing)
  - `books_e5base` parent docs should grow from 0 to match `books`
  - Expected time per 1000 docs: ~2–5 minutes (embeddings inference is the bottleneck)
- **Disk usage:** Monitor `/var/solr/data` volume growth
  - Expected: ~55% smaller than baseline per collection (fewer chunks due to larger window)
  - Alert if free space drops below 20GB (adjust for your disk size)
- **CPU/Memory:** Both `document-indexer-e5` and `embeddings-server-e5`
  - Embeddings server should max out at ~2.5–3GB RAM
  - Indexer should stay under 512MB
  - Expect high CPU during embedding phase (HuggingFace transformer inference)

**Estimated time breakdown** (for a 100K-book library with ~10M chunks):
| Phase | Baseline | e5-base | Notes |
|-------|----------|---------|-------|
| Fetch docs from disk (document-lister) | 5 min | — | Single pass, same for both |
| Chunk documents | 10 min | 10 min | Sentence-aware chunking; e5-base = 90w → 300w reduces chunk count 3.3× |
| Embed chunks (distiluse + e5-base in parallel) | 360 min (6h) | 360 min (6h) | Parallel via fanout; bottleneck is slower indexer |
| Index into Solr | 20 min | 20 min | Same Solr cluster, writes are fast |
| **Total parallel time** | — | **~400 min (6.7h)** | Slower indexer determines total; overlapping I/O |

**Re-indexing commands for manual testing (if needed):**
```bash
# Watch indexing progress:
docker logs -f document-indexer-e5 | grep "Indexed\|ERROR\|Exception"
docker logs -f embeddings-server | grep "request\|error"

# Query both collections to verify parallel indexing:
# Baseline:
curl -s "http://localhost:8983/solr/books/select?q=*:*&rows=0" | jq '.response.numFound'
# Candidate:
curl -s "http://localhost:8983/solr/books_e5base/select?q=*:*&rows=0" | jq '.response.numFound'
```

### Step 4: Verify Collection Parity (30 minutes)

**Action:** Run collection verification script to ensure both collections indexed identically.

```bash
python scripts/verify_collections.py --verbose
```

**Expected output:**
```
Collection: books
  Total docs: 100000
  Parent docs: 9500
  Chunk docs: 1000000
  Embedding dimension: 512
  Status: PASS

Collection: books_e5base
  Total docs: 100000
  Parent docs: 9500
  Chunk docs: 302000
  Embedding dimension: 768
  Status: PASS

Cross-collection checks:
  Parent docs match: PASS
  Parent IDs match: PASS
  Baseline embedding dim correct: PASS
  Candidate embedding dim correct: PASS

Overall: PASS (exit code 0)
```

**If verification fails:**
- Incomplete indexing: Wait for `document-indexer-e5` to finish. Check logs for stalled workers.
- Dimension mismatch: Verify `knn_vector_768` field type deployed to ZK configset.
- ID mismatch: Rare—indicates corrupted documents or partial re-indexing. Delete `books_e5base` and retry from Step 3.

### Step 5: Run Benchmark Suite on Production Data (1 hour)

**Action:** Execute benchmark against both collections using production library sample.

```bash
python scripts/benchmark/run_benchmark.py \
  --base-url http://localhost:8080 \
  --output /tmp/prod-migration-benchmark.json
```

**Expected metrics:**
- **Jaccard similarity:** Min 0.5 (some top-10 result changes expected due to improved relevance)
- **Latency:** e5-base ≤ 50ms slower than baseline (acceptable for better results)
- **Query category breakdown:**
  - Keyword searches: Parity (semantic model doesn't improve keyword-only queries)
  - Semantic searches: ≥10% improvement in Jaccard or explicit review by PO
  - Multilingual: ≥5% improvement (expected from e5-base's superior multilingual training)
  - Long-context: Largest improvement (e5-base uses 512-token window vs 128)

**If metrics regress:**
- **Minor regressions** (<5% latency increase, Jaccard >0.5): Acceptable, proceed to Step 6
- **Major regressions** (Jaccard <0.4 on critical queries, latency >100ms slower): **HALT**
  - Review PO A/B test approval; confirm e5-base was the chosen model
  - Verify schema field types correct (768D in collections, not 512D)
  - Troubleshoot embeddings-server-e5 performance (may be underthrottled or memory-constrained)

**Save benchmark report for documentation:**
```bash
cp /tmp/prod-migration-benchmark.json docs/prd/migration-benchmarks/
git add docs/prd/migration-benchmarks/
git commit -m "docs: production migration benchmark (Step 5)"
```

### Step 6: Switch Default Collection in solr-search Config (5 minutes, downtime <30s)

**Action:** Update `solr-search` configuration to query `books_e5base` instead of `books`.

**Changes to `src/solr-search/config/__init__.py` or environment override:**

```python
# Before:
SOLR_COLLECTION = "books"  # distiluse baseline

# After:
SOLR_COLLECTION = "books_e5base"  # e5-base candidate (post-migration)
```

**OR via environment variable (preferred for prod):**
```bash
# docker/compose.prod.yml or kubectl secret:
environment:
  - SOLR_COLLECTION=books_e5base
```

**Deployment:**
```bash
# Option A: Update environment variable and restart solr-search
docker-compose -f docker/compose.prod.yml up -d solr-search

# Option B: Deploy via kubectl if using k8s
kubectl set env deployment/solr-search SOLR_COLLECTION=books_e5base
```

**Verification (immediate post-switch):**
```bash
# Health check:
curl http://localhost:8080/health

# Verify collection is responding:
curl -s "http://localhost:8080/search?q=test&mode=semantic&limit=10" | jq '.results | length'

# Check logs for errors:
docker logs solr-search | tail -20 | grep -i "error\|exception\|connect"
```

### Step 7: Monitor Performance for 48 Hours

**Critical window:** First 48 hours post-cutover.

**Metrics to monitor (automated dashboard recommended):**

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| API response time (p95) | <100ms | >250ms |
| Solr query latency (p95) | <50ms | >150ms |
| Search error rate | <0.1% | >1% |
| User complaints (support tickets) | — | >3 in first 24h about "search broken" |
| Embeddings-server-e5 CPU | <70% | >90% sustained |
| Embeddings-server-e5 memory | <2.5GB | >3GB (OOM risk) |
| Solr disk usage | <70% of max | >80% |
| RabbitMQ queue depth (`shortembeddings_e5base`) | ~0 | >100 (indexer lagging) |

**Daily health check tasks:**
- Day 1 (6h post-cutover): Run benchmark again, compare against Step 5 baseline. Should be identical.
- Day 1 (24h post-cutover): Sample 50–100 user queries; spot-check for unexpected ranking changes.
- Day 2 (48h post-cutover): Confirm no regressions vs Step 5 benchmark. If green, proceed to post-migration cleanup.

**If critical issue found during monitoring:**
- **Immediate action:** Revert to baseline (`SOLR_COLLECTION=books`) and restart solr-search
  - Revert time: <5 minutes
  - User-visible downtime: ~30 seconds (service restart)
  - Data loss: None (both collections exist, baseline unmodified)
- **Root cause analysis:** Check Solr logs, benchmark report, and query patterns for regressions
- **Recovery:** Do not proceed to Step 8 until issue is resolved and approved by PO

---

## 4. Cutover Strategy

### 4.1 Blue/Green Deployment Pattern

**Baseline (Blue):** `books` collection remains indexed and queryable throughout migration.

**Candidate (Green):** `books_e5base` indexed in parallel during Steps 2–3.

**Benefits:**
- Zero downtime during re-indexing (Steps 2–3)
- Single cutover moment (Step 6) is fast and reversible
- If issues found post-cutover, rollback is instantaneous (change one config variable)
- Baseline collection preserved for 48-hour confidence window (can delete after Step 7 if confident)

### 4.2 Configuration Switch Mechanism

**solr-search reads `SOLR_COLLECTION` environment variable at startup.**

```bash
# View current collection:
docker exec solr-search python -c "from config import SOLR_COLLECTION; print(SOLR_COLLECTION)"

# Update for production (in docker/compose.prod.yml):
solr-search:
  environment:
    - SOLR_COLLECTION=books_e5base  # Changed from books
```

**Why not DNS/load-balancer switch?**
- Solr doesn't support per-request collection routing via reverse proxy
- Solr Client Library (`pysolr`) binds to a single collection at module load time
- Configuration change + restart is simplest, most testable approach

### 4.3 Timeline Estimate

| Step | Duration | Notes |
|------|----------|-------|
| Step 1: Prepare Compose | 1h | Configuration review, no downtime |
| Step 2: Deploy Dual Indexing | 0.5h | Service start, RabbitMQ topology check |
| Step 3: Re-Index Library | 6–24h | Depends on library size; see breakdown in Step 3 |
| Step 4: Verify Parity | 0.5h | Script runs in seconds, quick validation |
| Step 5: Benchmark | 1h | 90 queries × 2 collections × 3 modes |
| Step 6: Switch Collection | 0.25h | Config change + restart, <30s downtime |
| **Total (Steps 1–6)** | **9–26h** | Mostly waiting for indexing to complete |
| Step 7: Monitor | 48h | Continuous, no user-visible work |
| **Grand Total** | **2–4 days** | (Assuming 100K-book library; scale linearly with size) |

**Parallel vs Sequential:**
- Steps 2–3 can overlap if done atomically (deploy services and start indexing in one window)
- All other steps must complete in order
- Recommend scheduling migration window during low-traffic hours (e.g., 2 AM–2 PM UTC)

---

## 5. Post-Migration Cleanup

Execute after Step 7 monitoring period (48 hours) confirms no regressions.

### 5.1 Remove A/B Test Infrastructure

**When:** After 48-hour confidence window (Step 7) and PO sign-off.

**Action: Delete A/B-specific services from `docker/compose.prod.yml`**

```yaml
# Remove entirely:
- embeddings-server-e5
- document-indexer-e5

# Remove from docker-compose.yml (dev):
- embeddings-server-e5
- document-indexer-e5 (keep for future A/B testing)
```

**Rationale:** Once migration is confirmed stable, no need to keep dual indexing running. Saves ~3.5GB memory (3GB + 0.5GB) on production host.

### 5.2 Remove Comparison Endpoint

**If implemented (from Phase 2):** Remove `/search?compare=true` mode from solr-search API.

```python
# In src/solr-search/main.py, remove:
@app.get("/v1/search")
def search(..., compare: bool = False):
    if compare:
        # Query both books and books_e5base
        # Return side-by-side comparison
        pass
```

**Rationale:** Comparison endpoint was for PO evaluation. Post-migration, only single default collection should be queried.

### 5.3 Optional: Archive Baseline Collection

**Decision:** Keep or delete `books` collection after migration?

| Option | Pros | Cons | Recommendation |
|--------|------|------|-----------------|
| **Keep (48h → indefinite)** | Preserves rollback option indefinitely; useful for future A/B tests | Uses disk space; index grows stale | **KEEP** — cost is one disk mount; allows fast rollback if bugs found in v1.x |
| **Delete after 48h** | Frees disk space immediately | Rollback requires 6–24h re-indexing; data may be lost if deleted by accident | Delete if disk-constrained; requires PO sign-off |

**Recommended approach:** Keep `books` for minimum 1 week (covers any delayed bug reports from users), then delete after confirming no regressions in production metrics.

### 5.4 Update VERSION File

**When:** After migration confirmed stable (post-Step 7).

**Action:**
1. Bump minor version (e.g., `v1.8.0` → `v1.9.0`)
2. Update `VERSION` file at repo root
3. Rebuild and push images with new version tag to GHCR
4. Update `docker/compose.prod.yml` to reference new version

```bash
# In VERSION file:
1.9.0

# Rebuild and push:
./buildall.sh
# buildall.sh reads VERSION, tags images as ghcr.io/jmservera/aithena-*:1.9.0
```

**Rationale:** Tracks e5-base migration as a discrete release. Users can reference exact version in docs and release notes.

### 5.5 Update Documentation

**Files to update after migration:**

1. **docs/prd/embedding-model-ab-test.md**
   - Add section: "Post-Migration Status" → "Migration completed, e5-base is now production model"
   - Update "Current State" table to reflect `books_e5base` as baseline

2. **README.md**
   - Search model section: Update from distiluse to e5-base
   - Link to this migration plan for reference

3. **CHANGELOG.md**
   - Entry: `## [1.9.0] - 2026-03-27` (adjust date)
   - Highlight: "Migrated to multilingual-e5-base embedding model for improved semantic search"
   - Include migration duration and benchmark improvements

4. **Release notes (docs/releases/v1.9.0.md)**
   - User-visible changes: "More relevant search results, especially for semantic and multilingual queries"
   - Admin changes: Chunk size increased from 90 to 300 words
   - Performance notes: Slightly slower indexing (inference-heavy), same query latency

---

## 6. Risk Assessment

### 6.1 Identified Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|-----------|
| **Re-indexing takes >24h** | Extends cutover window; increases chance of issues found after go-live | Medium | Pre-test with production library sample; adjust chunk pipeline parallelism if needed |
| **Solr collection is corrupted during indexing** | books_e5base is unusable; must restart from Step 3 | Low | Incremental verification via `verify_collections.py` at 25%, 50%, 75% marks |
| **Embeddings-server-e5 OOM crashes during indexing** | Indexing stalls; must increase memory and restart (Step 2) | Low | Stress-test embeddings-server-e5 with peak memory profile from Phase 2 before go-live |
| **e5-base search quality is worse than expected** | Users complain; revert to baseline; debug model selection | Low | A/B test (Phase 1–2) confirms quality; benchmark (Step 5) is final sanity check |
| **RabbitMQ queue topology not configured correctly** | Document-indexer-e5 doesn't receive documents; books_e5base stays empty | Low | Manual test of fanout topology before Step 2; verify via `rabbitmqctl list_bindings` |
| **solr-search doesn't connect to books_e5base after config change** | Queries fail with 500 error; users see broken search | Low | Smoke test in Step 6 before declaring success |
| **Disk space runs out during indexing** | Solr stops writing; index is corrupted; must restart from disk wipe | Medium | Monitor `df -h /var/solr/data` every 30 min during Step 3; alert at 70% |
| **Network partition between solr-search and Solr cluster** | Query timeouts; users see errors | Very low | Test network connectivity after Step 6 before claiming success |
| **Baseline collection (`books`) is accidentally deleted** | Rollback becomes impossible; requires 6–24h re-indexing | Very low | Apply `readonly: true` or rename collection to `books_backup` after 48h; require PO approval to delete |

### 6.2 Rollback Procedure

**Scenario:** Production issue discovered during Step 7 monitoring; must revert to baseline.

**Time to rollback:** <5 minutes  
**User-visible downtime:** ~30 seconds (solr-search restart)  
**Data loss:** None (both collections unmodified)

**Steps:**
1. **Stop new indexing** (prevents corruption of baseline):
   ```bash
   docker-compose -f docker/compose.prod.yml stop document-lister document-indexer-e5
   ```

2. **Revert collection config:**
   ```bash
   # In docker/compose.prod.yml or kubectl secret:
   - SOLR_COLLECTION=books  # Back to baseline
   ```

3. **Restart solr-search:**
   ```bash
   docker-compose -f docker/compose.prod.yml up -d solr-search
   ```

4. **Verify baseline is responding:**
   ```bash
   curl -s "http://localhost:8080/search?q=test&mode=keyword&limit=5"
   ```

5. **Document incident:**
   - Create GitHub issue: "Post-migration rollback (e5-base)" with timestamp and logs
   - Attach benchmark report from Step 5 and monitoring data from Step 7
   - Schedule root cause analysis

**Prevention:** Comprehensive monitoring (Step 7) is the best rollback prevention. Do not skip.

---

## 7. Sign-Off and Approval Gates

### 7.1 Pre-Migration Approvals (Required Before Step 1)

- [ ] **PO (Juanma):** A/B test results reviewed; confirm e5-base is production choice
- [ ] **Infrastructure Lead (Brett):** Production environment readiness confirmed; disk/memory adequate
- [ ] **Search Lead (Ash):** Solr schema and embeddings-server configuration reviewed
- [ ] **QA Lead (Lambert):** Test data and benchmark suite ready; rollback procedure tested

### 7.2 Post-Step 6 Approval (Required Before Step 7 Monitoring)

- [ ] **SRE on-call:** Monitoring dashboard configured; alert thresholds set
- [ ] **PO:** Spot-check 10–20 queries; confirm ranking looks correct

### 7.3 Post-Step 7 Approval (Required Before Step 8 Cleanup)

- [ ] **PO:** 48-hour monitoring window shows no regressions
- [ ] **Infrastructure Lead:** Benchmark metrics meet targets; no alerts triggered

---

## Appendix A: Environment Configuration

### A.1 docker/compose.prod.yml Additions

```yaml
embeddings-server-e5:
  image: ghcr.io/jmservera/aithena-embeddings-server:${VERSION:-latest}
  build:
    context: .
    dockerfile: src/embeddings-server/Dockerfile
    args:
      MODEL_NAME: intfloat/multilingual-e5-base
  expose:
    - "8085"
  environment:
    - HF_HUB_OFFLINE=1
    - PYTHONUNBUFFERED=1
  healthcheck:
    test: ["CMD", "wget", "-qO", "/dev/null", "http://localhost:8085/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 60s
  restart: unless-stopped
  stop_grace_period: 10s
  deploy:
    resources:
      limits:
        memory: 3g
      reservations:
        memory: 2g
  depends_on:
    solr:
      condition: service_healthy

document-indexer-e5:
  image: ghcr.io/jmservera/aithena-document-indexer:${VERSION:-latest}
  environment:
    - RABBITMQ_HOST=rabbitmq
    - RABBITMQ_USER=${RABBITMQ_USER:?Set RABBITMQ_USER in .env}
    - RABBITMQ_PASS=${RABBITMQ_PASS:?Set RABBITMQ_PASS in .env}
    - REDIS_HOST=redis
    - REDIS_PASSWORD=${REDIS_PASSWORD:?Set REDIS_PASSWORD in .env}
    - QUEUE_NAME=shortembeddings_e5base
    - EXCHANGE_NAME=documents
    - BASE_PATH=/data/documents/
    - SOLR_HOST=solr
    - SOLR_COLLECTION=books_e5base
    - CHUNK_SIZE=300
    - CHUNK_OVERLAP=50
    - EMBEDDINGS_HOST=embeddings-server-e5
    - EMBEDDINGS_PORT=8085
    - PYTHONUNBUFFERED=1
  restart: on-failure
  stop_grace_period: 10s
  deploy:
    replicas: 1
    resources:
      limits:
        memory: 512m
      reservations:
        memory: 256m
  depends_on:
    embeddings-server-e5:
      condition: service_healthy
    solr-init:
      condition: service_completed_successfully
```

### A.2 Environment Variables for solr-search Post-Migration

```bash
# docker/compose.prod.yml (solr-search service)
environment:
  - SOLR_HOST=solr
  - SOLR_COLLECTION=books_e5base  # Changed from books
```

---

## Appendix B: Monitoring Dashboard Metrics

**Recommended tools:** Prometheus + Grafana, Datadog, or CloudWatch (if self-hosted).

**Key metrics to plot (48-hour window post-Step 6):**

```
solr_search_request_duration_seconds (histogram, p50/p95/p99)
solr_search_errors_total (counter)
embeddings_server_memory_usage_bytes (gauge)
embeddings_server_request_duration_seconds (histogram)
solr_document_count{collection="books_e5base"} (gauge)
rabbitmq_queue_messages_unacked{queue="shortembeddings_e5base"} (gauge)
host_disk_available_bytes{mount="/var/solr/data"} (gauge)
```

---

## Appendix C: Pre-Migration Test Checklist

**Execute 1 week before migration window:**

- [ ] Re-index 10% of library using test data; verify parity
- [ ] Run benchmark suite; confirm results match Phase 2
- [ ] Simulate 48-hour monitoring window with live traffic logs (replay against staging)
- [ ] Execute rollback procedure on staging; time it; document exact steps
- [ ] Brief on-call team; ensure escalation path documented
- [ ] Reserve 5GB disk space on production host (verified with `df -h`)
- [ ] Backup ZK and Solr state pre-migration (separate from operational backups)

---

## Appendix D: Rollback Decision Tree

```
Production issue detected during Step 7?
│
├─ YES, critical (search broken, latency >500ms, error rate >10%)
│   └─ Execute rollback immediately (see Section 6.2)
│       └─ Schedule incident review within 24 hours
│
├─ MAYBE, degraded (latency +20%, some queries slower)
│   └─ Wait 2 hours, re-run benchmark, compare vs Step 5
│       ├─ Consistent degradation? Rollback.
│       └─ Transient (network spike, Solr GC pause)? Continue monitoring.
│
└─ NO, all metrics green
    └─ Proceed to Step 8 cleanup after 48 hours
```

---

## Appendix E: References

- **Phase 1–2 Documentation:** `docs/prd/embedding-model-ab-test.md`
- **A/B Test Results:** Issue #877 (PO approval required)
- **Rollback Plan:** Issue #XXX (P3-3)
- **Verification Script:** `scripts/verify_collections.py`
- **Benchmark Suite:** `scripts/benchmark/run_benchmark.py`
- **Solr Schema:** `src/solr/books/managed-schema.xml` (knn_vector_768 field type)
- **embeddings-server-e5:** `src/embeddings-server/Dockerfile` with MODEL_NAME=intfloat/multilingual-e5-base

---

**Document Status:** DRAFT  
**Ready for Implementation:** After PO approves A/B test results (issue #877)  
**Next Step:** P3-3 (Rollback plan detail) and review with ops team before migration window
