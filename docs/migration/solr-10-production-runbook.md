# Solr 10 Production Migration Runbook

_Last updated:_ 2026-06-05  
_Owner:_ Ash (Search Engineer) / Brett (Infrastructure)  
_PRD reference:_ [`docs/prd/solr10-migration-prd.md`](../prd/solr10-migration-prd.md) — Sections 5-8  
_Related issues:_ [#1353](https://github.com/jmservera/aithena/issues/1353) (docs), [#1359](https://github.com/jmservera/aithena/issues/1359) (runbook)  
_Related migration guide:_ [`docs/migration/solr-9-to-10.md`](./solr-9-to-10.md)

---

## How to use this runbook

This is the operator's guide for migrating **production Aithena deployments from Solr 9.7 to Solr 10**. It covers:
- Pre-migration verification and backup procedures
- Coordinated upgrade steps for SolrCloud and standalone modes
- Rollback triggers and procedures
- Post-migration validation and performance tuning

**Read the full [Solr 9→10 Migration Plan](./solr-9-to-10.md) first** — this runbook focuses on execution, not the technical details.

> **Prerequisite knowledge:**  
> - Familiarity with Docker Compose (`docker compose` commands)
> - Understanding of [Aithena architecture](../architecture/) and service dependencies
> - Shell scripting and basic Solr CLI commands
> - Your site's backup procedures and infrastructure

> **Migration time estimate:**
> - **Maintenance window**: 2–8 hours (depending on index size and reindex strategy)
> - **Post-validation**: 1–2 hours
> - **Total**: Plan for a 12-hour maintenance window

---

## 1. Pre-Migration Checklist

Complete these steps **at least 24 hours before the maintenance window**.

### 1.1 Verify Current Deployment

```bash
# Check current Solr version
docker compose exec solr solr --version

# Expected: Apache Solr 9.7.X

# Verify all 3 nodes are healthy
docker compose exec solr curl -s -u "$SOLR_ADMIN_USER:$SOLR_ADMIN_PASS" \
  http://solr:8983/api/cluster/status | jq '.responseHeader.status, .cluster | keys'

# Verify replication is current (all nodes synced)
docker compose exec solr curl -s -u "$SOLR_ADMIN_USER:$SOLR_ADMIN_PASS" \
  http://solr:8983/api/collections/books | jq '.collection.shards | to_entries[] | .value'
```

Expected output: All 3 nodes in `live_nodes`, all shards with `active` status.

### 1.2 Document Baseline Metrics

```bash
# Create a baseline report
cat > /tmp/solr-9-baseline.txt << 'REPORT'
Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)
Solr Version: $(docker compose exec -T solr solr --version 2>/dev/null | grep "Apache Solr" || echo "MANUAL")
Cluster Status: $(docker compose exec -T solr curl -s -u "$SOLR_ADMIN_USER:$SOLR_ADMIN_PASS" http://solr:8983/api/cluster/status | jq -r '.cluster | "live=" + ((.live_nodes | length | tostring)) + ", down=" + ((.down_nodes | length | tostring))')
REPORT

cat /tmp/solr-9-baseline.txt
```

Store this for post-migration comparison.

### 1.3 Create Pre-Migration Backup

```bash
# Create a full snapshot (this may take 10–30 min for large indexes)
BACKUP_NAME="books-pre-solr10-$(date +%Y%m%d-%H%M%S)"

docker compose exec -T solr curl -u "$SOLR_ADMIN_USER:$SOLR_ADMIN_PASS" \
  "http://solr:8983/solr/admin/collections?action=BACKUP" \
  -d "name=$BACKUP_NAME" \
  -d "collection=books" \
  -d "repository=local_repo" \
  -d "wt=json" | jq '.'

# Verify backup completed
docker compose exec -T solr curl -u "$SOLR_ADMIN_USER:$SOLR_ADMIN_PASS" \
  "http://solr:8983/solr/admin/collections?action=REQUESTSTATUS&requestid=0&wt=json"

echo "Backup '$BACKUP_NAME' created. Verify it exists on disk or backup destination."
```

### 1.4 Verify Dependent Services Can Be Stopped

```bash
# Document current state of indexing
docker compose logs --tail=20 document-indexer | grep -E "processed|error"

# Verify no active indexing jobs in Redis
docker compose exec -T redis redis-cli KEYS "doc:*" | wc -l

# If any active jobs exist, wait for them to complete or drain manually
if [ $(docker compose exec -T redis redis-cli KEYS "doc:*" | wc -l) -gt 0 ]; then
  echo "⚠️  Active indexing jobs found. Wait for completion before proceeding."
  exit 1
fi
```

### 1.5 Check Disk Space

```bash
# Ensure at least 2× current index size available for reindex operations
SOLR_VOLUME=$(docker volume inspect aithena_solr-data | jq -r '.[0].Mountpoint')
du -sh "$SOLR_VOLUME" || echo "⚠️  Cannot measure volume size — verify manually"
```

### 1.6 Notify Team & Users

- Announce maintenance window: **24 hours before**
- Disable indexing jobs (pause document-lister if needed)
- Put up a maintenance banner on the UI
- Have a rollback plan ready

---

## 2. Migration Procedure

### Phase 1: Prepare (Pre-cutover, downtime not yet required)

#### Step 1.1: Stop Document Indexing

```bash
# Stop the document indexer (but keep Solr, UI, and search running)
docker compose stop document-indexer document-lister

# Verify no new indexing is being attempted
sleep 5
docker compose exec -T redis redis-cli KEYS "doc:*" | wc -l

# Expected: 0 (or existing but non-growing count)
```

#### Step 1.2: Update Docker Compose Files

**For single-node deployment** (`docker-compose.yml`):
- Update Solr image: `solr:10` (from `solr:9.7`)
- Update `luceneMatchVersion` in `src/solr/books/solrconfig.xml`: `10.0` (from `9.10`)
- Update `solr-init` CLI commands to use `--` syntax (see [migration plan § 2.3](./solr-9-to-10.md#step-23-update-solr-init-cli-commands))

**For production 3-node deployment** (`docker/compose.prod.yml`):
- Same updates as above for all 3 Solr nodes

> **STATUS**: All CLI updates are merged in PR #1673 and related commits. Verify by checking current `docker-compose.yml`.

#### Step 1.3: Review Schema Compatibility

The existing `src/solr/books/managed-schema.xml` has been pre-updated with Solr 10 HNSW parameter names and scalar quantization support (see PR #1667 and commit 72f2122). Verify:

```bash
# Check for Solr 10-compatible field types
grep -A3 "knn_vector_768" src/solr/books/managed-schema.xml
```

Expected:
```xml
<fieldType name="knn_vector_768" class="solr.DenseVectorField"
           vectorDimension="768" similarityFunction="cosine"
           knnAlgorithm="hnsw" hnswMaxConnections="32" hnswBeamWidth="40"/>
```

If your schema still uses old `maxconn` / `beamWidth` names, apply the migration from [solr-9-to-10.md § 2.2](./solr-9-to-10.md#22-hnsw-parameter-renames--requires-configset-upload--reindex).

#### Step 1.4: Verify Security Configuration

Check that `src/solr/security.json` is Solr 10 compatible:

```bash
# Must have blockUnknown=false for health checks to work unauthenticated
jq '.blockUnknown' src/solr/security.json
# Expected: false

# Health and metrics endpoints must allow null role
jq '.authorization.rules[] | select(.name == "health" or .name == "metrics-read")' src/solr/security.json
# Expected: Both have "role": null or "role": ["null"]
```

> **PENDING**: Solr 10 changes blockUnknown default to `true`. If not explicitly set to `false`, health checks will fail. This is addressed in PR #1663.

### Phase 2: Cutover (Maintenance window begins)

> **⚠️ MAINTENANCE WINDOW STARTS HERE**

#### Step 2.1: Announce Service Maintenance

```bash
# Disable external traffic
docker compose stop nginx

# Notify any monitoring
echo "MAINTENANCE: Solr upgrade in progress" | wall

# Stop the UI
docker compose stop aithena-ui
```

#### Step 2.2: Drain Active Connections

```bash
# Wait for any in-flight requests to complete
sleep 10

# Verify no active database locks
docker compose logs --tail=5 solr-search | tail -1
```

#### Step 2.3: Stop Application Services

```bash
# Dependent services
docker compose stop solr-search redis-commander

# Keep Redis and RabbitMQ running (needed for init)
```

#### Step 2.4: Stop Solr Cluster

```bash
# SolrCloud (3-node)
docker compose stop solr solr2 solr3

# Stop ZooKeeper (cluster coordination)
docker compose stop zoo1 zoo2 zoo3

# Single-node: just docker compose stop solr
```

#### Step 2.5: Upgrade Solr Image

```bash
# Pull the new image
docker compose pull solr

# For 3-node production:
# docker pull solr:10
# or build your custom Solr 10 image if you have one

# Verify the new image
docker compose images solr | grep -E "DIGEST|solr:10"
```

#### Step 2.6: Start Cluster in Solr 10

```bash
# Start ZooKeeper (cluster mode) or skip for standalone
docker compose up -d zoo1 zoo2 zoo3

# Wait for quorum (30–60 sec)
sleep 30

# Start Solr nodes one at a time
docker compose up -d solr
sleep 20
docker compose up -d solr2
sleep 20
docker compose up -d solr3

# Verify cluster is forming
docker compose logs solr | grep -E "live_nodes|CLUSTERSTATUS" | tail -5
```

Expected:
```
solr    | 2026-06-05T12:34:56Z INFO ... registered as live_nodes: 3
```

#### Step 2.7: Run solr-init

```bash
# Re-bootstrap auth and collections (idempotent)
docker compose up solr-init

# Watch for completion
docker compose logs -f solr-init

# Expected output:
# ✓ Security enabled
# ✓ Users created
# ✓ Collection 'books' created or already exists
```

> **PENDING IMPLEMENTATION**: solr-init logic for Solr 10 is in PR #1673 (now merged). If initialization fails, check `docker compose logs solr-init` for error messages.

#### Step 2.8: Verify Cluster Health

```bash
# Check cluster status
docker compose exec -T solr curl -u "$SOLR_ADMIN_USER:$SOLR_ADMIN_PASS" \
  http://solr:8983/api/cluster/status | jq '.cluster | {live_nodes, down_nodes}'

# Expected: 3 live nodes, 0 down

# Check collection shards
docker compose exec -T solr curl -u "$SOLR_ADMIN_USER:$SOLR_ADMIN_PASS" \
  http://solr:8983/api/collections/books/shards | jq '.shards | to_entries[] | .value | {replicas}'

# Expected: All replicas in "active" state
```

#### Step 2.9: Verify Index Integrity

```bash
# Query the books collection to verify index exists and is readable
docker compose exec -T solr curl -u "$SOLR_ADMIN_USER:$SOLR_ADMIN_PASS" \
  "http://solr:8983/solr/books/select?q=*:*&rows=1" | jq '.response.numFound'

# Expected: Same numFound as pre-migration baseline
```

> **CRITICAL**: If numFound is 0, the index was not migrated. Check Solr logs and consider rollback (§ 3).

#### Step 2.10: Restart Application Services

```bash
# Restart Redis and dependent services
docker compose up -d redis

# Give Redis time to load
sleep 5

# Restart the search API
docker compose up -d solr-search

# Restart the UI
docker compose up -d aithena-ui redis-commander

# Wait for UI to be ready
sleep 10
docker compose logs aithena-ui | grep -i "listen\|ready" | tail -1
```

#### Step 2.11: Bring External Traffic Back Online

```bash
# Re-enable the reverse proxy
docker compose up -d nginx

# Verify nginx can reach the UI
curl -s http://localhost/health | jq '.' || echo "nginx not ready yet"

# Wait up to 30 sec for nginx to proxy correctly
for i in {1..6}; do
  if curl -s http://localhost/health > /dev/null 2>&1; then
    echo "✓ UI is healthy"
    break
  fi
  echo "Waiting for UI... ($i/6)"
  sleep 5
done
```

> **⚠️ MAINTENANCE WINDOW ENDS HERE**

### Phase 3: Post-Migration Validation

#### Step 3.1: Verify Search Functionality

```bash
# Test basic keyword search
curl -s -H "Authorization: Bearer $(cat .env | grep BEARER_TOKEN | cut -d= -f2)" \
  http://localhost/v1/search?q=test | jq '.results | length'

# Expected: Non-zero result count if books exist in index

# Test semantic/hybrid search (if embeddings are working)
curl -s -H "Authorization: Bearer $(cat .env | grep BEARER_TOKEN | cut -d= -f2)" \
  http://localhost/v1/search?q=machine%20learning&mode=hybrid | jq '.results | length'
```

#### Step 3.2: Check Solr Version

```bash
# Verify Solr 10 is running
docker compose exec -T solr solr --version | grep "Apache Solr"

# Expected: Apache Solr 10.X.X
```

#### Step 3.3: Document Post-Migration Metrics

```bash
# Create a post-migration report (compare with baseline from step 1.2)
cat > /tmp/solr-10-postmig.txt << 'REPORT'
Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)
Solr Version: $(docker compose exec -T solr solr --version 2>/dev/null | grep "Apache Solr" || echo "MANUAL")
Cluster Status: $(docker compose exec -T solr curl -s -u "$SOLR_ADMIN_USER:$SOLR_ADMIN_PASS" http://solr:8983/api/cluster/status | jq -r '.cluster | "live=" + ((.live_nodes | length | tostring)) + ", down=" + ((.down_nodes | length | tostring))')
Index Size: $(docker volume inspect aithena_solr-data 2>/dev/null | jq -r '.[0].Mountpoint' | xargs du -sh)
REPORT

cat /tmp/solr-10-postmig.txt
```

#### Step 3.4: Restart Indexing Pipeline

```bash
# Resume document indexing
docker compose up -d document-indexer document-lister

# Monitor for errors
sleep 10
docker compose logs document-indexer | grep -E "Error|exception" || echo "✓ No immediate errors"

# Check Redis indexing queue
docker compose exec -T redis redis-cli KEYS "doc:*" | wc -l

# Should show growing count as indexing resumes
```

#### Step 3.5: Performance Validation (Optional)

**PENDING**: Create benchmark suite (to be added in v2.5.1). For now, manual spot-checks:

```bash
# Sample 10 random searches and note response times
for i in {1..10}; do
  curl -w "Response time: %{time_total}s\n" -s \
    -H "Authorization: Bearer $(cat .env | grep BEARER_TOKEN | cut -d= -f2)" \
    "http://localhost/v1/search?q=test&rows=5" > /dev/null
  sleep 1
done

# Expected: < 200ms per query (adjust threshold based on hardware)
```

---

## 3. Rollback Procedure

If validation fails, you have two options:

### 3.1 Immediate Rollback (< 30 min recovery)

Use this if Solr 10 doesn't start or index is corrupted.

#### Step 1: Stop Solr 10 cluster

```bash
docker compose stop solr solr2 solr3 zoo1 zoo2 zoo3
```

#### Step 2: Remove Solr 10 data volumes

```bash
# ⚠️ WARNING: This deletes all Solr 10 index state. Only do this for rollback.
docker volume rm aithena_solr-data aithena_solr2-data aithena_solr3-data
```

#### Step 3: Restore original Dockerfile

```bash
# Revert Dockerfile to Solr 9.7
git checkout HEAD -- src/solr/Dockerfile docker-compose.yml docker/compose.prod.yml

# Rebuild image
docker compose build solr
```

#### Step 4: Restore from backup

```bash
# List available backups
docker compose exec -T solr ls /var/solr/data/backup-restore/

# Restore the pre-migration snapshot
BACKUP_NAME="books-pre-solr10-YYYYMMDD-HHMMSS"  # Use the actual backup name
docker compose exec -T solr curl -u "$SOLR_ADMIN_USER:$SOLR_ADMIN_PASS" \
  "http://solr:8983/solr/admin/collections?action=RESTORE" \
  -d "name=$BACKUP_NAME" \
  -d "collection=books" \
  -d "repository=local_repo" \
  -d "wt=json"
```

#### Step 5: Bring the system back online

```bash
# Start Solr 9.7 cluster
docker compose up -d solr solr2 solr3

# Wait for cluster to form (30–60 sec)
sleep 30

# Verify
docker compose exec -T solr curl -u "$SOLR_ADMIN_USER:$SOLR_ADMIN_PASS" \
  http://solr:8983/api/cluster/status | jq '.cluster.live_nodes | length'

# Expected: 3

# Restart dependent services
docker compose up -d solr-search aithena-ui redis-commander nginx
```

### 3.2 Full Index Reindex (1–4 hours recovery)

Use this if Solr 10 starts but the index is incomplete or corrupted.

```bash
# 1. Restore Solr 9.7 backup to get original data
# (Follow steps 1–4 from § 3.1)

# 2. Downgrade to Solr 9.7 and verify index
docker compose up -d solr solr2 solr3
docker compose exec -T solr curl -u "$SOLR_ADMIN_USER:$SOLR_ADMIN_PASS" \
  http://solr:8983/solr/books/select?q=*:*&rows=1 | jq '.response.numFound'

# 3. Run full reindex via document-indexer
docker compose up -d document-indexer
docker compose logs -f document-indexer | grep -E "processed|completed"

# Once reindex is complete and verified, you can retry Solr 10 upgrade.
```

---

## 4. Troubleshooting

### Issue: Solr 10 nodes fail to start

**Symptoms**: `docker compose logs solr` shows `OutOfMemory` or startup errors.

**Resolution**:
1. Check Java version: `docker compose exec -T solr java -version`
   - Solr 10 requires Java 21+ (Solr 9 used Java 17)
   - Update base image if needed
2. Increase memory limit in `docker-compose.yml`: `mem_limit: 4gb` (from 2gb)
3. Check disk space: `docker volume ls | grep solr-data | xargs -I {} docker volume inspect {}`

### Issue: Auth fails with "blockUnknown" error

**Symptoms**: Health checks fail with `401` or `403` even with valid credentials.

**Resolution**:
1. Verify security.json: `jq '.blockUnknown' src/solr/security.json`
2. Must be `false` for unauthenticated health checks
3. If missing, Solr 10 defaults to `true`
4. Apply fix from [PR #1663](https://github.com/jmservera/aithena/pull/1663)

### Issue: Collection doesn't exist after upgrade

**Symptoms**: `numFound = 0` after starting Solr 10, or collection query returns 404.

**Resolution**:
1. Check solr-init logs: `docker compose logs solr-init`
2. Manually create collection: 
   ```bash
   docker compose exec -T solr curl -u "$SOLR_ADMIN_USER:$SOLR_ADMIN_PASS" \
     "http://solr:8983/api/collections?action=CREATE" \
     -d "name=books" \
     -d "numShards=1" \
     -d "replicationFactor=3" \
     -d "collection.configName=books" \
     -d "wt=json"
   ```
3. Restore data from backup (see § 3.1, step 4)

### Issue: Vector search returns 0 results

**Symptoms**: Keyword search works, but embedding-based queries fail.

**Resolution**:
1. Verify embeddings-server is running:
   ```bash
   docker compose logs embeddings-server | tail -10
   docker compose exec -T embeddings-server curl -s http://localhost:5000/version
   ```
2. Verify field type in schema:
   ```bash
   grep -A2 "knn_vector_768" src/solr/books/managed-schema.xml
   ```
3. If field type changed, a **full reindex** is required

### Issue: Indexing is very slow after upgrade

**Symptoms**: document-indexer processes documents at 1/10th the previous rate.

**Resolution**:
1. Check if quantization is enabled (4× less memory, 5–10% slower queries):
   - This is normal and expected (trades memory for speed)
   - Tune via `efSearchScaleFactor` if accuracy suffers
2. Monitor Solr CPU/memory: `docker stats solr solr2 solr3`
3. If CPU maxed: increase `solr.jvm.memory` or `solrMaxHeap` in `.env`

### Issue: Rollback failed, Solr 9 data volumes corrupted

**Symptoms**: Even after restore, numFound stays 0 or index is missing.

**Resolution**:
1. Verify backup exists and is readable:
   ```bash
   docker volume inspect aithena_solr-data | jq '.[0].Mountpoint'
   ls -la <mountpoint>/backup-restore/
   ```
2. If backup is corrupted, restore from off-node backup (tape, cloud storage, etc.)
3. If no backup: data is irrecoverable — restart from latest document source

---

## 5. Post-Upgrade Tuning (Optional, can be deferred to v2.5.1)

These optimizations are **not required** for v2.5.0 release but can improve performance:

### 5.1 Enable Vector Quantization

Reduce Solr memory footprint by 4× with scalar quantization:

**Edit `src/solr/books/managed-schema.xml`:**
```xml
<!-- Keep the existing float32 field type for baseline/rollback paths. -->
<fieldType name="knn_vector_768" class="solr.DenseVectorField"
           vectorDimension="768" similarityFunction="cosine" knnAlgorithm="hnsw"/>

<!-- Add a separate scalar-quantized byte field type for int8 routing. -->
<fieldType name="knn_vector_768_byte" class="solr.ScalarQuantizedDenseVectorField"
           vectorDimension="768" similarityFunction="cosine" knnAlgorithm="hnsw" bits="7"/>
```

**Route embeddings to the byte field:** set `VECTOR_QUANTIZATION=int8` so indexing/search use
the `embedding_byte_v` dynamic field backed by `knn_vector_768_byte`. Do not replace
`knn_vector_768`; keep it as the float32 vector field.

**Then reindex:** Full index reindex required (estimated 30–120 min for 100k+ docs).

> **STATUS**: Vector quantization bits logic is validated in PR #1670 (scalar 7-bit fix).

### 5.2 Configure `efSearchScaleFactor`

Tune vector search accuracy independently of result count (Solr 10 only):

**In `solr-search` query logic:**
```python
# Allow per-query tuning of accuracy vs. speed
efSearchScaleFactor = request_params.get('efSearchScaleFactor', 1.0)
# Use in query: {!knn f=book_embedding topK=10 efSearchScaleFactor=2.0}
```

> **PENDING**: Add `efSearchScaleFactor` parameter to `/v1/search` API (deferred to v2.5.1).

### 5.3 Monitor Solr Metrics

Set up monitoring dashboards for:
- Query latency (p50, p95, p99)
- Indexing rate (docs/sec)
- Memory usage (JVM heap, OS swap)
- Index size growth

Use existing observability stack (Prometheus + Grafana if configured).

---

## 6. Escalation & Support

### During Migration

- **Pre-migration**: Contact Ash (search) if schema questions arise
- **During cutover**: Contact Brett (infrastructure) for cluster issues
- **Search errors**: Contact Ripley (lead) for escalation

### After Migration

For persistent issues:
1. Check [Solr 10 breaking changes](../migration/solr-9-to-10.md#2-breaking-changes-in-solr-10)
2. Review [troubleshooting guide](https://solr.apache.org/guide/solr/latest/upgrade-notes/) on Apache Solr docs
3. File an issue: Reference this runbook section + logs from `docker compose logs --all`

### Known Limitations (v2.5.0)

- ⚠️ Language-models module (embeddings in Solr) deferred to v2.6 (requires upstream work)
- ⚠️ GPU acceleration (cuVS codec) deferred to v2.5.1
- ⚠️ Binary vector quantization not yet tested, scalar quantization is supported

---

## 7. Appendix: Quick Reference

### Health Check Commands

```bash
# Cluster status
docker compose exec -T solr curl -u "$SOLR_ADMIN_USER:$SOLR_ADMIN_PASS" \
  http://solr:8983/api/cluster/status | jq '.cluster | {live_nodes, down_nodes}'

# Collection status
docker compose exec -T solr curl -u "$SOLR_ADMIN_USER:$SOLR_ADMIN_PASS" \
  http://solr:8983/api/collections/books | jq '.collection.shards'

# Index stats
docker compose exec -T solr curl -u "$SOLR_ADMIN_USER:$SOLR_ADMIN_PASS" \
  http://solr:8983/solr/books/select?q=*:*&rows=0 | jq '.response.numFound'

# Solr version
docker compose exec -T solr solr --version
```

### Backup/Restore Commands

```bash
# List backups
docker compose exec -T solr ls /var/solr/data/backup-restore/

# Create backup
docker compose exec -T solr curl -u "$SOLR_ADMIN_USER:$SOLR_ADMIN_PASS" \
  "http://solr:8983/solr/admin/collections?action=BACKUP&name=books-$(date +%Y%m%d-%H%M%S)&collection=books&repository=local_repo&wt=json"

# Restore backup
docker compose exec -T solr curl -u "$SOLR_ADMIN_USER:$SOLR_ADMIN_PASS" \
  "http://solr:8983/solr/admin/collections?action=RESTORE&name=<BACKUP_NAME>&collection=books&repository=local_repo&wt=json"
```

### Docker Compose Quick Refs

```bash
# Restart Solr cluster without losing data
docker compose restart solr solr2 solr3

# View live logs
docker compose logs -f solr

# Execute command in container
docker compose exec -T solr <command>

# Check service health
docker compose ps
```

---

**Version**: v2.5.0-rc1  
**Next review**: After first production deployment  
**Changes in this version**:
- Initial runbook for Solr 10 migration (v2.5.0 release)
- Marked pending sections for v2.5.1+ optimization work
