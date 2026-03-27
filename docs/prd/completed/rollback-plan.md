# Rollback Plan — Embedding Model A/B Test (P3-3)

**Author:** Brett (Infrastructure Architect)  
**Requested by:** Juanma (PO)  
**Date:** 2026-03-22  
**Status:** APPROVED  
**Reference Issue:** #878  

---

## Overview

This document defines the rollback procedures for the embedding model A/B test (`multilingual-e5-base` vs `distiluse-base-multilingual-cased-v2`). A rollback may be triggered during the A/B test phase (dev/staging) or after production migration, depending on the findings from P2-4 (metrics dashboard) and operational feedback.

**Key principle:** The baseline `books` collection is **never deleted** during the A/B test. The e5-base `books_e5base` collection can be dropped and recreated if needed.

---

## 1. Rollback Triggers

A rollback is initiated when **any** of the following conditions are detected:

### 1.1 Search Quality Degradation
- **Metric:** nDCG@10 (normalized discounted cumulative gain at top 10 results)
- **Threshold:** ≥ 5% **drop** in nDCG@10 vs baseline (inverse of original goal)
- **Detection:** P2-4 metrics dashboard (`GET /v1/status/?include_metrics`)
- **Action:** Stop serving e5 collections; switch back to baseline

### 1.2 Indexing Failures or Data Inconsistencies
- **Symptom:** document-indexer-e5 in continuous failure loop (e.g., embeddings timeout, Solr connection errors)
- **Metric:** >10 consecutive indexing failures for e5 path; zero successes in 30 minutes
- **Detection:** Docker logs (`docker compose logs document-indexer-e5`) or RabbitMQ queue depth (`shortembeddings_e5base` growing unbounded)
- **Action:** Stop e5 services; investigate before re-enabling

### 1.3 Latency Degradation
- **Metric:** API response time for search queries
- **Baseline (p95):** < 200ms (typical for keyword search in Solr)
- **Threshold:** e5 hybrid search p95 > 500ms (unacceptable UX)
- **Detection:** Metrics dashboard or manual `curl` sampling
- **Action:** Disable hybrid search mode; revert to keyword-only (baseline)

### 1.4 Memory or Resource Exhaustion
- **Symptom:** embeddings-server-e5 or document-indexer-e5 killed by OOM; container restarts
- **Threshold:** >3 OOM kills in 24 hours
- **Detection:** `docker compose stats`, Docker event logs, or memory alerts
- **Action:** Stop e5 services; investigate resource limits

### 1.5 Product Owner Decision
- **Authority:** Juanma (PO) or delegated authority
- **Reason:** Any business reason (user feedback, timeline pressure, roadmap change)
- **Notice:** May be initiated with or without performance data

---

## 2. Rollback During A/B Test (dev/staging)

**Timeline:** < 5 minutes  
**Downtime:** 0 minutes (baseline continues serving)

### 2.1 Immediate Stop (Quick Kill)

```bash
# 1. Stop e5-base services
docker compose stop document-indexer-e5 embeddings-server-e5

# 2. Verify they are down
docker compose ps
# Expected: both services in "Exited" state
```

**Result:** 
- `document-indexer-e5` stops consuming from `shortembeddings_e5base` queue
- `embeddings-server-e5` stops accepting requests
- Baseline `document-indexer` and `embeddings-server` remain untouched
- Search API (`solr-search`) continues serving from `books` collection (no config change needed)

### 2.2 Verify Baseline is Serving

```bash
# Test baseline search endpoint
curl -s "http://localhost:8080/v1/search/?q=python&mode=keyword" | jq '.results | length'
# Expected: >0 results

# Check Solr collection status
curl -s "http://localhost:8983/solr/admin/collections?action=CLUSTERSTATUS&json.nl=newline" | \
  jq '.cluster.collections | keys'
# Expected: ["books", "books_e5base"] (both exist, but only books is serving)
```

### 2.3 Clean Up Stale Data (Optional)

If the test is permanently aborted, drop the e5 collection:

```bash
# Drop e5-base collection
curl -s "http://localhost:8983/solr/admin/collections?action=DELETE&name=books_e5base"

# Verify deletion
curl -s "http://localhost:8983/solr/admin/collections?action=CLUSTERSTATUS&json.nl=newline" | \
  jq '.cluster.collections | keys'
# Expected: ["books"] only

# Purge the e5 queue (if RabbitMQ is still running)
# Note: This step is optional and depends on your monitoring setup
# The queue will naturally drain once document-indexer-e5 is stopped
```

---

## 3. Rollback After Production Migration (P3-2)

**Timeline:** < 15 minutes  
**Downtime:** ~2 minutes (during solr-search restart)

This procedure applies **after** production deployment (P3-2). At that point, the baseline `books` collection contains all current production data, and the e5-base `books_e5base` collection contains the new e5-indexed data.

### 3.1 Pre-Rollback Validation

Before executing rollback steps, confirm:
- Baseline `books` collection has recent data (timestamp of latest doc ≈ now)
- Both collections exist and have document counts (use Solr API)
- solr-search config file is accessible (on the host or via ConfigMap if using K8s)

```bash
# Check collections exist and have docs
curl -s "http://localhost:8983/solr/books/select?q=*:*&rows=0" | jq '.response.numFound'
curl -s "http://localhost:8983/solr/books_e5base/select?q=*:*&rows=0" | jq '.response.numFound'
# Both should show doc counts > 0
```

### 3.2 Revert Configuration

Change the default collection back to baseline:

**If using environment variables (current approach):**

```bash
# In docker-compose.yml or .env:
# Change:
#   SOLR_COLLECTION=books_e5base
# To:
SOLR_COLLECTION=books

# Reload the configuration file into the container
# Option 1: Edit docker-compose.yml, then:
docker compose up -d solr-search
# Option 2: If using hot-config (K8s ConfigMap):
kubectl set env deployment/solr-search SOLR_COLLECTION=books
```

**If using a config file mount:**

```bash
# Edit solr-search config.py or environment file
# Old: SOLR_COLLECTION="books_e5base"
# New: SOLR_COLLECTION="books"

# If using ConfigMap (K8s):
kubectl patch configmap solr-search-config -p '{
  "data": {
    "SOLR_COLLECTION": "books"
  }
}'
```

### 3.3 Restart solr-search

```bash
# Restart the service to pick up the new config
docker compose restart solr-search
# Or in Kubernetes:
kubectl rollout restart deployment/solr-search

# Wait for the service to become healthy
# (Polling example — adjust timeout as needed)
max_wait=60
elapsed=0
while [ $elapsed -lt $max_wait ]; do
  status=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost/health")
  if [ "$status" = "200" ]; then
    echo "✓ solr-search is healthy"
    break
  fi
  echo "Waiting for solr-search health check... (${elapsed}s)"
  sleep 2
  ((elapsed += 2))
done

if [ $elapsed -ge $max_wait ]; then
  echo "✗ solr-search did not become healthy within ${max_wait}s"
  exit 1
fi
```

### 3.4 Stop e5 Services

```bash
# Stop the e5-specific services
docker compose stop document-indexer-e5 embeddings-server-e5
# Or in Kubernetes:
kubectl scale deployment/document-indexer-e5 --replicas=0
kubectl scale deployment/embeddings-server-e5 --replicas=0

# Optionally, remove the pod entirely
docker compose rm -f document-indexer-e5 embeddings-server-e5
```

### 3.5 Verify Baseline Serving

```bash
# Test search endpoint
curl -s "http://localhost/v1/search/?q=python&mode=keyword" | jq '.metadata.collection'
# Expected: "books"

# Verify response time is acceptable
time curl -s "http://localhost/v1/search/?q=python&mode=keyword" > /dev/null
# Expected: ~100-200ms for small result sets

# Check a specific document via API
curl -s "http://localhost/v1/search/?q=title:*&rows=1" | jq '.results[0]'
# Expected: One document from books collection
```

### 3.6 Monitor for Errors

```bash
# Watch logs for any errors during the first 5 minutes
docker compose logs -f solr-search | head -50

# Check Solr collection status
curl -s "http://localhost:8983/solr/admin/collections?action=CLUSTERSTATUS" | \
  jq '.cluster.collections.books'
# Expected: "active" status
```

---

## 4. Data Preservation

### 4.1 What Gets Deleted

**Only the e5 collection is droppable:**
- `books_e5base` Solr collection (can be recreated by re-running document-indexer-e5 and solr-init)
- RabbitMQ `shortembeddings_e5base` queue (will be recreated on next service startup)

**What is NOT deleted:**
- Baseline `books` collection and all its documents (preserved for production recovery)
- Original document files in document library
- RabbitMQ `shortembeddings` queue (still used by baseline indexer)

### 4.2 Collection Naming Convention

The naming scheme ensures no collision:
- **Baseline:** `books` (production standard)
- **Candidate:** `books_e5base` (suffixed with model name)

If multiple A/B tests are needed in the future, use: `books_{variant}` (e.g., `books_e5large`, `books_bge`).

### 4.3 Redis Cache Keys

Redis cache keys are collection-prefixed to avoid cross-contamination:

```
Baseline queries cached under: cache:books:{query_hash}
E5 queries cached under:       cache:books_e5base:{query_hash}
```

Rollback automatically isolates cache by collection name — **no manual cache purge needed**.

---

## 5. Rollback Verification

After executing rollback steps, verify the following:

### 5.1 Run Verification Script

Use the provided verification script to confirm baseline collection status:

```bash
# Run verification against baseline collection
python3 scripts/verify_collections.py \
  --collection books \
  --expected-docs $(curl -s "http://localhost:8983/solr/books/select?q=*:*&rows=0" | jq '.response.numFound') \
  --skip-e5

# Expected output:
# ✓ Collection 'books' exists
# ✓ Document count matches expected value
# ✓ Embedding field (embedding_v) is absent (baseline uses keyword only)
# ✓ All shards are healthy
```

### 5.2 Run Benchmark Suite Against Baseline

Execute the benchmark suite to ensure query performance is acceptable:

```bash
# Navigate to benchmarks directory
cd tests/benchmarks

# Run baseline-only tests
python3 benchmark_runner.py \
  --collection books \
  --mode keyword \
  --skip-hybrid \
  --output rollback-baseline-metrics.json

# Check results
cat rollback-baseline-metrics.json | jq '.summary'
# Expected:
#   "p50_latency_ms": ~100
#   "p95_latency_ms": ~150
#   "error_rate": 0
#   "queries_per_second": >100
```

### 5.3 Check Metrics Endpoint

```bash
# Query the metrics endpoint
curl -s "http://localhost/v1/status/?include_metrics" | jq '.metrics | {
  collection,
  search_requests_total,
  search_errors_total,
  search_latency_p95_ms
}'

# Expected:
#   "collection": "books"
#   "search_requests_total": >1000 (since deployment)
#   "search_errors_total": 0
#   "search_latency_p95_ms": <200
```

### 5.4 Confirm Search Results Quality

Spot-check search results against a set of known queries:

```bash
# Example: Search for a known title
curl -s "http://localhost/v1/search/?q=introduction+to+python" | jq '{
  total_found: .metadata.total_found,
  top_result: .results[0] | {title, author, score}
}'

# Expected:
#   - total_found: >0
#   - top_result should match the known document
#   - score should be reasonable (e.g., 15.0+)
```

### 5.5 Health Check

```bash
# Full health check
curl -s "http://localhost/health" | jq '.'
# Expected: 200 OK, all services "healthy"

# Service-specific health
curl -s "http://localhost:8080/health" | jq '.solr_collection'
# Expected: "books"
```

---

## 6. Rollback Runbook (Copy-Paste Ready)

### For Dev/Staging Quick Kill

```bash
#!/bin/bash
set -e

echo "🔴 Rolling back A/B test (dev/staging)..."

# 1. Stop e5 services
echo "Stopping e5 services..."
docker compose stop document-indexer-e5 embeddings-server-e5

# 2. Verify baseline is serving
echo "Verifying baseline is healthy..."
max_wait=30
elapsed=0
while [ $elapsed -lt $max_wait ]; do
  status=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8080/health")
  if [ "$status" = "200" ]; then
    echo "✓ Baseline is serving"
    break
  fi
  echo "  Waiting... (${elapsed}s)"
  sleep 1
  ((elapsed += 1))
done

# 3. Test search
echo "Testing search endpoint..."
results=$(curl -s "http://localhost:8080/v1/search/?q=python" | jq '.results | length')
if [ "$results" -gt 0 ]; then
  echo "✓ Search returned $results results"
else
  echo "✗ Search failed"
  exit 1
fi

echo "✅ Rollback complete. Baseline A/B test halted."
```

### For Production Rollback

```bash
#!/bin/bash
set -e

echo "🔴 Rolling back from e5-base to baseline (PRODUCTION)..."

# 1. Edit config
echo "Reverting SOLR_COLLECTION to 'books'..."
# Edit docker-compose.yml or your production config
# SOLR_COLLECTION=books_e5base  →  SOLR_COLLECTION=books
# Then:

# 2. Restart solr-search
echo "Restarting solr-search..."
docker compose up -d solr-search

# 3. Wait for health
echo "Waiting for solr-search to become healthy..."
max_wait=120
elapsed=0
while [ $elapsed -lt $max_wait ]; do
  status=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost/health")
  if [ "$status" = "200" ]; then
    echo "✓ solr-search is healthy"
    break
  fi
  echo "  Waiting... (${elapsed}s)"
  sleep 2
  ((elapsed += 2))
done

# 4. Stop e5 services
echo "Stopping e5 services..."
docker compose stop document-indexer-e5 embeddings-server-e5

# 5. Verify baseline collection
echo "Verifying baseline collection..."
collection=$(curl -s "http://localhost/v1/status/" | jq -r '.solr_collection')
if [ "$collection" = "books" ]; then
  echo "✓ Baseline collection active: $collection"
else
  echo "✗ Unexpected collection: $collection"
  exit 1
fi

# 6. Test search
echo "Testing search..."
results=$(curl -s "http://localhost/v1/search/?q=test" | jq '.results | length')
if [ "$results" -gt 0 ]; then
  echo "✓ Search working: $results results"
else
  echo "⚠ Warning: No search results (index may be empty)"
fi

echo "✅ Production rollback complete. Baseline serving."
```

---

## 7. Decision Tree

Use this decision tree to determine the rollback path:

```
[Rollback Triggered]
    │
    ├─→ Still in A/B test (P2-4 not complete)?
    │       YES → Use Section 2 (Quick Kill, <5 min, no downtime)
    │       NO  → Continue
    │
    └─→ Production e5 services deployed (P3-2 complete)?
            YES → Use Section 3 (Full Rollback, ~15 min, ~2 min downtime)
            NO  → Use Section 2 (fallback)

[After Rollback]
    │
    └─→ Run verification suite (Section 5)
            ├─→ All checks pass? → ✅ Rollback successful
            └─→ Any failures?   → ⚠️  Debug & escalate
```

---

## 8. Communication & Escalation

### Escalation Path

1. **First responder:** On-call engineer detects issue, initiates quick kill (Section 2)
2. **Team lead:** Notified within 5 minutes; reviews P2-4 metrics
3. **PO / Product:** Notified within 15 minutes for business decision
4. **System architect:** Engaged if root cause is unclear

### Communication Template

```
🔴 [ROLLBACK INITIATED] — Embedding A/B Test

Trigger: [Select one: Quality Degradation | Latency Spike | Indexing Failure | PO Decision]
Impact: [e.g., "E5 search disabled; baseline active"]
Timeline: [e.g., "Quick kill ~5 min | Full rollback ~15 min"]
Status: [In Progress | Complete]

Evidence:
- Metric: [e.g., nDCG@10 -7% vs baseline]
- Detection time: [timestamp]
- Affected users: [Staging only | Prod users]

Next: [Investigating root cause | Proceeding to production rollback | Monitoring baseline]
```

---

## 9. Post-Rollback Actions

### 9.1 Root Cause Analysis

If rollback was triggered, schedule a brief post-incident review:

1. **What was the trigger?** (Metric, user report, automated alert)
2. **Why did it happen?** (Model, chunking, resource, query mismatch)
3. **Could it have been prevented?** (Better monitoring, stress test)
4. **How do we fix it?** (Model adjustment, hyperparameter tuning, infra scaling)

### 9.2 Decision: Retry or Abandon

After RCA, the PO decides:
- **Retry:** Make adjustments (model, chunking, resources), restart A/B test
- **Abandon:** Close P3 as deferred; stay on baseline
- **Pivot:** Switch to a different model (e5-large, bge, etc.)

### 9.3 Restore E5 (if Retrying)

To restart the A/B test after fixes:

```bash
# 1. Remove stale e5 collection (if dropped)
# Already gone — solr-init will recreate

# 2. Restart e5 services
docker compose up -d document-indexer-e5 embeddings-server-e5

# 3. Monitor logs
docker compose logs -f document-indexer-e5

# 4. Wait for indexing to complete, then re-run P2-4 evaluation
```

---

## 10. Appendix: Related Issues & PRs

| Phase | Issue | PR | Description |
|-------|-------|-----|-----------|
| **P1-1** | #863 | | Input type prefix handling (query vs passage) |
| **P1-4** | #870 | | Docker Compose A/B config (this PR) |
| **P2-4** | #876 | | Metrics dashboard & evaluation criteria |
| **P3-1** | #877 | | Evaluation runbook (test harness) |
| **P3-2** | TBD | | Production deployment (deferred) |
| **P3-3** | #878 | | **Rollback plan (this document)** |

---

## 11. Approval & Sign-Off

| Role | Name | Date | Sign-Off |
|------|------|------|----------|
| Infrastructure Architect | Brett | 2026-03-22 | ✅ |
| PO / Product Lead | Juanma | TBD | — |
| Tech Lead / Release Manager | TBD | TBD | — |

---

**Last Updated:** 2026-03-22  
**Next Review:** After P2-4 completion (metrics evaluation)
