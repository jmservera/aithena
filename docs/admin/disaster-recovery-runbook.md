# Disaster Recovery Runbook

_Last updated:_ 2025-07-18
_Owner:_ Brett (Infrastructure)
_PRD reference:_ [`docs/prd/bcdr-plan.md`](../prd/bcdr-plan.md) — Section 5

---

## How to use this runbook

This is the operator's guide for responding to any failure in Aithena.
Start at the **Decision Tree** to identify the correct recovery path, then follow
the step-by-step procedure for that path. After every recovery, complete the
**Post-Restore Checklist**. If anything fails, follow the **Escalation** section.

> **Prerequisite knowledge:** familiarity with Docker Compose, the Aithena
> service architecture, and the backup/restore scripts documented in the
> [admin manual](../admin-manual.md) and [BCDR PRD](../prd/bcdr-plan.md).

---

## 1. RPO / RTO targets

| Tier | Data stores | RPO | RTO | Backup frequency | Retention |
|------|-------------|-----|-----|------------------|-----------|
| **Critical** | Auth DB, Collections DB, `.env` secrets | < 1 hour | < 5 min | Every 30 min | 7 days |
| **High** | Solr indexes, ZooKeeper state | < 24 hours | 15–60 min | Daily 02:00 UTC | 30 days |
| **Medium** | Redis RDB, RabbitMQ definitions | < 4 hours | 5–15 min | Daily 03:00 UTC | 14 days |

See [`scripts/backup.sh`](../../scripts/backup.sh) for cron scheduling details.

---

## 2. Service dependency map

Restart and restore operations must respect this dependency order
(infrastructure first, ingress last):

```
Layer 1 — Infrastructure    redis, rabbitmq
Layer 2 — Coordination      zoo1, zoo2, zoo3
Layer 3 — Search cluster    solr, solr2, solr3, solr-init
Layer 4 — ML                embeddings-server
Layer 5 — Indexing pipeline  document-lister, document-indexer
Layer 6 — API / UI          solr-search, aithena-ui, redis-commander, admin
Layer 7 — Ingress           nginx
```

---

## 3. Decision tree

When a failure is detected, start here:

```
Is the failure understood?
├─ YES → Is it a single service crash/exit?
│        ├─ YES ──────────────────────────────────── Path A (< 1 min)
│        └─ NO  → Is data missing or deleted?
│                  ├─ YES ────────────────────────── Path B (15–60 min)
│                  └─ NO  → Is data corrupted?
│                           ├─ YES ───────────────── Path C (30–90 min)
│                           └─ NO  → Full VM lost?
│                                    ├─ YES ──────── Path D (1–4 hours)
│                                    └─ NO ───────── Path E (10–30 min)
└─ NO ─────────────────────────────────────────────── Path E (10–30 min)
```

| Path | Scenario | Est. time |
|------|----------|-----------|
| **A** | Single service failure — restart | < 1 min |
| **B** | Data loss — restore from backup | 15–60 min |
| **C** | Corruption with verification — restore & validate | 30–90 min |
| **D** | Full system recovery — VM reprovision | 1–4 hours |
| **E** | Unknown failure — assessment protocol | 10–30 min |

---

## 4. Recovery procedures

### Path A — Single service failure (< 1 min)

**When to use:** A service has exited, is unhealthy, or is unresponsive, but
its data volumes are intact. Docker's `restart: unless-stopped` policy
usually handles this automatically; use this path if auto-restart did not
recover the service.

**Prerequisites:** Docker Compose is running; host has network access.

#### Steps

```bash
# 1. Identify the failed service
docker compose ps

# 2. Check logs for the root cause
docker compose logs --tail=100 <SERVICE>

# 3. Restart the service
docker compose restart <SERVICE>

# 4. Verify health (wait up to 30 s for health check to pass)
docker compose ps <SERVICE>
```

#### Service-specific notes

| Service | Extra steps after restart |
|---------|--------------------------|
| `solr` / `solr2` / `solr3` | Wait for replica recovery: `curl -s "http://localhost:8983/solr/admin/collections?action=CLUSTERSTATUS&wt=json" \| jq '.cluster.collections.books'` |
| `zoo1` / `zoo2` / `zoo3` | Verify quorum: `docker compose exec zoo1 zkServer.sh status` |
| `embeddings-server` | Model load takes 60–120 s; watch: `docker compose logs -f embeddings-server \| grep -i "loaded\|ready"` |
| `rabbitmq` | After restart, also restart `document-lister` and `document-indexer` |
| `redis` | After restart, also restart `document-lister`, `document-indexer`, and `redis-commander` |
| `solr-init` | Only needed after collection loss: `docker compose up -d solr-init` |

#### Verification

```bash
docker compose exec -T solr-search wget -qO- http://localhost:8080/v1/status/ | jq
```

All services should report `"up"`. If the service fails to restart, escalate
to **Path B** (data loss) or **Path E** (unknown failure).

#### Rollback

No rollback needed — a restart does not modify data.

---

### Path B — Data loss: restore from backup (15–60 min)

**When to use:** Data has been accidentally deleted, a volume is missing, or
a service reports that its data store is empty or incomplete.

**Prerequisites:**

- Backup directory exists at `/source/backups/` with recent backups
- Encryption key at `/etc/aithena/backup.key` (for critical-tier restores)
- Sufficient disk space for the restore (check with `df -h /source/volumes`)

#### Steps

```bash
# 1. Assess impact — which data is affected?
docker compose ps
docker compose logs --tail=100 <SERVICE>

# For auth DB:
sqlite3 /data/auth/users.db "PRAGMA integrity_check;"

# For Solr:
curl -s "http://localhost:8983/solr/admin/collections?action=CLUSTERSTATUS&wt=json" | jq

# 2. List available backups
ls -lah /source/backups/critical/   # Auth, Collections, .env
ls -lah /source/backups/high/       # Solr snapshots
ls -lah /source/backups/zookeeper/  # ZK state
ls -lah /source/backups/medium/     # Redis, RabbitMQ

# 3. Verify backup integrity
cd /source/backups/critical && sha256sum -c *.sha256

# 4. Stop affected services
docker compose down

# 5. Restore the affected tier
#    The orchestrator creates a safety backup before overwriting.
./scripts/restore.sh --from /source/backups --tier critical          # Auth + secrets
./scripts/restore.sh --from /source/backups --tier high              # Solr + ZK
./scripts/restore.sh --from /source/backups --tier medium            # Redis + RabbitMQ
./scripts/restore.sh --from /source/backups --component all          # Everything

# Or restore a single component:
RESTORE_FROM=/source/backups/critical COMPONENT=auth \
  ./scripts/restore-critical.sh

RESTORE_FROM=/source/backups/high COMPONENT=solr \
  ./scripts/restore-high.sh

RESTORE_FROM=/source/backups/medium COMPONENT=redis \
  ./scripts/restore-medium.sh

# 6. Start services in dependency order
docker compose up -d redis rabbitmq
sleep 5
docker compose up -d zoo1 zoo2 zoo3
sleep 10
docker compose up -d solr solr2 solr3
docker compose up -d solr-init
sleep 15
docker compose up -d embeddings-server document-lister document-indexer
docker compose up -d solr-search aithena-ui redis-commander admin
docker compose up -d nginx

# 7. Run post-restore verification (see Section 6)
./tests/verify-restore.sh
```

#### Verification

Complete the **Post-Restore Checklist** in Section 6.

#### Rollback

The restore orchestrator creates a safety backup of the current state before
overwriting. If the restore made things worse:

```bash
# The safety backup is at /source/backups/pre-restore-YYYYMMDD-HHMMSS/
ls /source/backups/pre-restore-*/

# Restore from the safety backup
docker compose down
./scripts/restore.sh --from /source/backups/pre-restore-<TIMESTAMP> --component all --skip-safety-backup
docker compose up -d
```

---

### Path C — Corruption with verification (30–90 min)

**When to use:** Data corruption is detected or suspected — integrity checks
fail, services return garbled results, or Solr reports index corruption.

**Prerequisites:** Same as Path B, plus: identify which data is corrupted
before beginning (do not blindly restore everything).

#### Symptoms of corruption

| Component | How to detect |
|-----------|---------------|
| Auth DB | `sqlite3 /data/auth/users.db "PRAGMA integrity_check;"` returns anything other than `ok` |
| Collections DB | `sqlite3 /data/auth/collections.db "PRAGMA integrity_check;"` returns anything other than `ok` |
| Solr index | Solr logs show `CorruptIndexException`; search returns unexpected empty results |
| Redis | `docker compose exec redis redis-cli PING` returns `ERROR` instead of `PONG` |
| ZooKeeper | `docker compose exec zoo1 zkServer.sh status` reports errors; Solr cannot connect |

#### Steps

```bash
# 1. Preserve the corrupted state for forensic analysis
docker compose down
./scripts/backup.sh --tier all \
  --dest "/source/backups/diagnostic-corrupted-$(date -u +%Y%m%d-%H%M%S)"

# 2. List available clean backups and pick one that predates the corruption
ls -lah /source/backups/critical/ | head -10
ls -lah /source/backups/high/     | head -10
ls -lah /source/backups/medium/   | head -10

# 3. Verify the selected backup is clean
cd /source/backups/critical && sha256sum -c *.sha256

# For auth DB, decrypt and check integrity without overwriting:
gpg --decrypt --batch --passphrase-file /etc/aithena/backup.key \
  /source/backups/critical/auth-YYYYMMDD-HHMM.db.gpg > /tmp/test-auth.db
sqlite3 /tmp/test-auth.db "PRAGMA integrity_check;"
rm /tmp/test-auth.db

# 4. Restore the corrupted component
./scripts/restore.sh --from /source/backups --component <COMPONENT>
# Where <COMPONENT> is: auth | collections | secrets | solr | zk | redis | rabbitmq | all

# 5. Start services in dependency order (see Path B, step 6)
docker compose up -d

# 6. Run the FULL verification suite
./tests/verify-restore.sh

# 7. If verification passes: recovery is complete
# 8. If verification fails: try an older backup or escalate
```

#### Verification

Run `./tests/verify-restore.sh` **and** manually confirm:

- Auth: log in with a known user account
- Search: run a keyword search and a semantic search
- Indexing: check that the document pipeline is processing

#### Rollback

Same as Path B — use the safety backup or the diagnostic backup of the
corrupted state.

---

### Path D — Full system recovery: VM reprovision (1–4 hours)

**When to use:** The entire VM is lost (disk failure, hardware issue,
accidental destruction). A new VM must be provisioned from scratch and all
data restored from backups.

**Prerequisites:**

- Backup archives exist on **off-host** storage (external disk, NFS,
  S3-compatible store, or another server)
- The encryption key (`/etc/aithena/backup.key`) is stored in a secure
  vault or password manager separate from the VM
- A new VM is provisioned with Docker Engine 24.0+ and Docker Compose V2

#### Steps

```bash
# 1. Prepare the new host
sudo sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf

# 2. Clone the Aithena repository
git clone <REPO_URL> /source/aithena
cd /source/aithena

# 3. Create required directory structure
sudo mkdir -p /source/backups/{critical,high,medium,zookeeper}
sudo mkdir -p /source/volumes/{solr-data1,solr-data2,solr-data3}
sudo mkdir -p /source/volumes/{zoo-data1,zoo-data2,zoo-data3}
sudo mkdir -p /source/volumes/{rabbitmq-data,redis}
sudo mkdir -p /data/auth
sudo chown -R "$(whoami)" /source/backups /source/volumes /data/auth

# 4. Restore encryption key from secure vault
sudo mkdir -p /etc/aithena
# Copy backup.key from vault/password manager into /etc/aithena/backup.key
sudo chmod 600 /etc/aithena/backup.key

# 5. Copy backup archives from off-host storage
scp user@backup-host:/mnt/backups/aithena/* /source/backups/
# or: rsync -avz backup-host:/mnt/backups/aithena/ /source/backups/

# 6. Restore .env secrets first
gpg --decrypt --batch --passphrase-file /etc/aithena/backup.key \
  /source/backups/critical/env-*.gpg > .env
# Verify critical variables exist:
grep -qE "REDIS_PASSWORD|AUTH_JWT_SECRET" .env && echo ".env OK"

# 7. Restore all data tiers
./scripts/restore.sh --from /source/backups --component all --skip-safety-backup

# 8. Start the full cluster
docker compose up -d

# 9. Monitor startup (all services should be healthy within 3–5 min)
watch -n 5 'docker compose ps'

# 10. Run full verification
./tests/verify-restore.sh

# 11. Re-install cron backup schedules
crontab -e
# Add the entries documented in scripts/backup.sh header

# 12. Smoke test
curl -f http://localhost/health && echo "nginx OK"
docker compose exec -T solr-search wget -qO- http://localhost:8080/v1/status/ | jq
```

#### Verification

Complete the **Post-Restore Checklist** (Section 6) plus:

- [ ] Cron backup schedules are installed (`crontab -l`)
- [ ] First backup runs successfully (`./scripts/backup.sh --tier all`)
- [ ] Off-host backup copy mechanism is re-enabled

#### Rollback

If the restored data does not work, try an older backup set. If no clean
backup exists, follow the **Last resort** procedure in Section 7.

---

### Path E — Unknown failure: assessment protocol (10–30 min)

**When to use:** The failure is not understood. Multiple services may be
affected, or the root cause is unclear. This path collects diagnostics
before committing to a recovery action.

**Prerequisites:** SSH access to the host.

#### Steps

```bash
# 1. Collect diagnostic snapshot
mkdir -p /tmp/aithena-diag
docker compose ps                          > /tmp/aithena-diag/compose-ps.txt
docker compose logs --tail=200             > /tmp/aithena-diag/compose-logs.txt 2>&1
df -h                                      > /tmp/aithena-diag/disk-usage.txt
free -h                                    > /tmp/aithena-diag/memory.txt
docker system df                           > /tmp/aithena-diag/docker-disk.txt 2>&1
du -sh /source/volumes/* /data/auth        > /tmp/aithena-diag/volume-sizes.txt 2>&1

# 2. Check each service individually
for svc in redis rabbitmq zoo1 zoo2 zoo3 solr solr2 solr3 \
           embeddings-server document-lister document-indexer \
           solr-search aithena-ui nginx; do
    echo "=== $svc ===" >> /tmp/aithena-diag/health.txt
    docker compose ps "$svc" >> /tmp/aithena-diag/health.txt 2>&1
done

# 3. Look for common problems
# Disk full?
df -h /source/volumes | awk 'NR>1 && $5+0 > 90 {print "DISK FULL:", $0}'

# OOM kills?
dmesg | grep -i "oom\|killed" | tail -10

# Obvious errors in logs?
grep -iE "error|fatal|oom|corrupt|panic" /tmp/aithena-diag/compose-logs.txt | tail -30

# 4. Determine root cause from diagnostics:
#    - Disk full         → Free space, then restart (Path A)
#    - Data missing       → Path B (restore from backup)
#    - Data corrupted     → Path C (restore with verification)
#    - Hardware failure   → Path D (full VM recovery)
#    - Multiple services  → Ordered restart (see Section 2 dependency map)
#    - Still unclear      → Escalate (see Section 8)

# 5. If ordered restart is needed:
docker compose down
docker compose up -d redis rabbitmq
sleep 5
docker compose up -d zoo1 zoo2 zoo3
sleep 10
docker compose up -d solr solr2 solr3
docker compose up -d solr-init
sleep 15
docker compose up -d embeddings-server document-lister document-indexer
docker compose up -d solr-search aithena-ui redis-commander admin
docker compose up -d nginx

# 6. Verify
docker compose exec -T solr-search wget -qO- http://localhost:8080/v1/status/ | jq
```

#### Verification

After determining and executing the correct recovery path, run:

```bash
./tests/verify-restore.sh
```

#### Rollback

If a restart worsens the situation, stop all services (`docker compose down`)
and escalate.

---

## 5. Monthly restore drill

**Purpose:** Validate that backups are complete, encryption works, and
restores actually succeed — before you need them in a real emergency.

**Schedule:** First Monday of each month, 02:00 UTC.

**Owner:** Infrastructure team (Brett) with PM review (Newt).

### Drill procedure

```bash
# ── On a STAGING environment (separate from production) ──

# 1. Select the latest backup from production
LATEST_CRITICAL=$(ls -t /source/backups/critical/auth-*.db.gpg 2>/dev/null | head -1)
LATEST_HIGH=$(ls -t /source/backups/high/books-*.tar.gz 2>/dev/null | head -1)
echo "Testing critical: $LATEST_CRITICAL"
echo "Testing high:     $LATEST_HIGH"

# 2. Stop staging environment
docker compose down

# 3. Restore all tiers
./scripts/restore.sh --from /source/backups --component all --skip-safety-backup

# 4. Start the cluster
docker compose up -d
sleep 120  # Wait for all services to initialise

# 5. Run the automated verification suite
./tests/verify-restore.sh
RESULT=$?

# 6. Record the result
echo "$(date -u +%Y-%m-%d) | exit=$RESULT" >> /var/log/aithena-restore-drill.log

# 7. Report
if [ "$RESULT" -eq 0 ]; then
    echo "✅ PASS — Monthly restore drill succeeded"
else
    echo "❌ FAIL — Monthly restore drill failed (exit $RESULT)"
    echo "Action: investigate failures, fix, and re-run before next month"
fi
```

### Interpreting results

| Exit code | Meaning | Action |
|-----------|---------|--------|
| `0` | All checks passed | Log result; no action needed |
| `1` | One or more checks failed | Investigate which check failed (the script prints details); fix the root cause and re-run |

### Common drill failures and remediation

| Failure | Likely cause | Fix |
|---------|-------------|-----|
| Decryption fails | Encryption key mismatch or corruption | Verify `/etc/aithena/backup.key` matches the key used at backup time |
| Checksum mismatch | Backup file was truncated or corrupted during transfer | Re-copy from source; check disk health |
| Auth DB integrity check fails | Backup was taken during a write (unlikely with SQLite online backup) | Try an older backup |
| Solr collection not found after restore | Solr snapshot is incompatible with current schema | Re-run `docker compose up -d solr-init` to recreate the collection, then re-index |
| Semantic search unavailable | Embeddings model not loaded | Wait 2–3 min for model load; check `embeddings-server` logs |
| Disk space insufficient | Staging VM too small | Expand storage or prune old Docker images |

### Success criteria

The drill passes when:

- Restore completes within 30 minutes
- All `verify-restore.sh` checks pass
- Keyword search and semantic search return results
- Users can log in

---

## 6. Post-restore checklist

Complete this checklist after **every** recovery operation (Paths A–E).

```
☐  All containers healthy                docker compose ps
☐  Status endpoint OK                    docker compose exec -T solr-search \
                                           wget -qO- http://localhost:8080/v1/status/ | jq
☐  Auth functional                       Log in via the UI or API with a known account
☐  Keyword search returns results        curl "http://localhost/v1/search?q=test&mode=keyword" | jq '.results | length'
☐  Semantic search returns results       curl "http://localhost/v1/search?q=test&mode=semantic" | jq '.degraded'
                                         (should be false)
☐  Redis responding                      docker compose exec redis redis-cli PING
                                         (expect: PONG)
☐  RabbitMQ accessible                   curl -sf http://localhost:15672/api/healthchecks/node | jq '.status'
                                         (expect: "ok")
☐  Solr replicas healthy                 curl -s "http://localhost:8983/solr/admin/collections?action=CLUSTERSTATUS&wt=json" \
                                           | jq '.cluster.collections.books.shards'
☐  ZooKeeper quorum                      docker compose exec zoo1 zkServer.sh status
☐  No errors in recent logs              docker compose logs --tail=100 2>&1 | grep -ci "error\|fatal"
                                         (expect: 0 or very low)
☐  Disk usage reasonable                 df -h /source/volumes /data/auth
                                         (expect: < 90 % used)
☐  Indexing pipeline operational         docker compose exec -T solr-search \
                                           wget -qO- http://localhost:8080/v1/status/ | jq '.indexing'
```

**Automated alternative:** run [`tests/verify-restore.sh`](../../tests/verify-restore.sh)
which checks all of the above programmatically.

If any check fails, investigate the specific service before declaring
recovery complete. If the failure cannot be resolved, escalate.

---

## 7. Last resort: full reindex without backups

If **all** backups are lost or unrecoverable:

```bash
# 1. Stop everything
docker compose down

# 2. Remove corrupted volumes
rm -rf /source/volumes/solr-data{1,2,3}/*
rm -rf /source/volumes/zoo-data{1,2,3}/*
rm -rf /source/volumes/redis/*
rm -rf /source/volumes/rabbitmq-data/*

# 3. Start infrastructure
docker compose up -d redis rabbitmq zoo1 zoo2 zoo3
sleep 15

# 4. Start Solr and bootstrap the collection
docker compose up -d solr solr2 solr3
sleep 10
docker compose up -d solr-init

# 5. Start the indexing pipeline — document-lister will re-scan
#    the book library and re-index every document
docker compose up -d embeddings-server document-lister document-indexer

# 6. Start remaining services
docker compose up -d solr-search aithena-ui redis-commander admin nginx

# NOTE: Auth DB and Collections DB are IRREPLACEABLE.
# If these are lost without backup, users must be re-created manually.
# Re-indexing from source documents can take hours to days depending on
# library size.
```

---

## 8. Escalation

### When to escalate

- Recovery path fails after two attempts
- Encryption key is lost
- Multiple backups are corrupted
- Hardware failure suspected
- Root cause cannot be determined within 30 minutes
- Data loss exceeds RPO targets

### Escalation paths

| Severity | Scenario | Primary contact | Channel | Response target |
|----------|----------|-----------------|---------|-----------------|
| **P1 — Critical** | Auth DB lost, full system down, secrets lost | Infrastructure lead (Brett) | `#incident` Slack channel | 15 min |
| **P2 — High** | Solr cluster down, search unavailable | Backend lead (Parker) | `#ops` Slack channel | 30 min |
| **P3 — Medium** | Single service degraded, indexing stalled | On-call engineer | `#ops` Slack channel | 1 hour |
| **P4 — Low** | Backup job failed, non-critical service restart | Infrastructure team | `#ops` Slack channel | Next business day |

### Communication template

When escalating, include:

```
Subject: [Aithena DR] P{1-4} — {brief description}

Impact:     {which services/users are affected}
Started at: {UTC timestamp}
Path tried: {A/B/C/D/E}
Diagnostics: {attach /tmp/aithena-diag/ files if available}
Current state: {what has been attempted, what is the current service status}
Help needed: {what the responder should do}
```

---

## 9. Quick reference: script CLI options

### Backup orchestrator — `scripts/backup.sh`

```
./scripts/backup.sh                           # all tiers
./scripts/backup.sh --tier critical           # tier 1 only
./scripts/backup.sh --tier high               # tier 2 only
./scripts/backup.sh --tier medium             # tier 3 only
./scripts/backup.sh --tier all --dry-run      # preview, no writes
./scripts/backup.sh --tier all --dest /mnt/x  # custom destination
```

**Environment variables:** `BACKUP_DEST`, `PROJECT_ROOT`, `DRY_RUN`, `LOG_FILE`

### Restore orchestrator — `scripts/restore.sh`

```
./scripts/restore.sh --from /source/backups                             # all tiers
./scripts/restore.sh --from /source/backups --tier critical             # tier 1
./scripts/restore.sh --from /source/backups --component auth            # single component
./scripts/restore.sh --from /source/backups --component solr --dry-run  # preview
./scripts/restore.sh --from /source/backups --component all --skip-safety-backup
```

**Components:** `auth`, `collections`, `secrets`, `solr`, `zk`, `redis`, `rabbitmq`, `all`

**Environment variables:** `BACKUP_DEST`, `PROJECT_ROOT`, `DRY_RUN`, `LOG_FILE`

### Tier-specific scripts

| Script | Environment variables |
|--------|----------------------|
| `scripts/backup-critical.sh` | `AUTH_DB_DIR`, `BACKUP_DIR`, `BACKUP_KEY`, `BACKUP_RETENTION_DAYS` |
| `scripts/backup-high.sh` | `SOLR_URL`, `SOLR_COLLECTION`, `SOLR_BACKUP_DIR`, `ZK_BACKUP_DIR`, `BACKUP_RETENTION_DAYS` |
| `scripts/backup-medium.sh` | `REDIS_CONTAINER`, `RABBITMQ_URL`, `BACKUP_DIR`, `BACKUP_RETENTION_DAYS` |
| `scripts/restore-critical.sh` | `RESTORE_FROM`, `COMPONENT`, `AUTH_DB_DIR`, `BACKUP_KEY` |
| `scripts/restore-high.sh` | `RESTORE_FROM`, `COMPONENT`, `SOLR_URL`, `ZK_RESTORE_FROM` |
| `scripts/restore-medium.sh` | `RESTORE_FROM`, `COMPONENT`, `REDIS_CONTAINER`, `RABBITMQ_URL` |

### Verification — `tests/verify-restore.sh`

```
./tests/verify-restore.sh
VERIFY_USERNAME=admin VERIFY_PASSWORD=secret ./tests/verify-restore.sh
```

**Environment variables:** `SOLR_URL`, `SEARCH_API_URL`, `ADMIN_URL`,
`RABBITMQ_API_URL`, `VERIFY_TIMEOUT`, `DISK_MAX_PERCENT`

---

## 10. Revision history

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2025-07-18 | 1.0 | Brett | Initial runbook |
