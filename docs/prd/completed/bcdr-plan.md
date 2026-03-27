# PRD: Backup, Restore & Disaster Recovery (BCDR) Plan

_Date:_ 2026-04-10  
_Prepared by:_ Brett (Infrastructure Architect)  
_Milestone:_ v1.10.0  
_Requested by:_ Juanma (jmservera)

---

## 1. Problem Statement

Aithena currently has **no backup or disaster recovery system** for its stateful data. A disk failure, corruption, accidental deletion, or misconfiguration could cause:

- **Auth DB loss**: All users locked out; credentials are irreplaceable (no recovery path)
- **Collections DB loss** (v1.10+): User-generated reading lists and notes permanently deleted (irreplaceable)
- **Solr index loss**: Full-text search offline; index rebuild takes hours-to-days from source documents
- **Runtime secrets loss** (JWT, API keys): Cluster unable to start without re-initialization
- **ZooKeeper loss**: SolrCloud quorum lost; cluster offline until restored or rebuilt
- **Redis/RabbitMQ loss**: Indexing pipeline stalls; requires service restart and document re-scan

**Current operational risk:** Single disk failure = complete data loss with no recovery procedure. This violates operational best practices and SLA commitments for critical systems.

---

## 2. Scope & Data Inventory

### Stateful Data Stores

| Data Store | Location | Criticality | Rebuild? | Typical Size | Volume Name |
|---|---|---|---|---|---|
| **Auth SQLite DB** | `~/.local/share/aithena/auth/users.db` | 🔴 **Critical** | ❌ No | < 1 MB | `$AUTH_DB_DIR` |
| **Collections DB** (v1.10) | TBD (suggest `$AUTH_DB_DIR/collections.db`) | 🔴 **Critical** | ❌ No | < 10 MB | `$AUTH_DB_DIR` |
| **Runtime secrets** | `.env` (host-only, not in git) | 🔴 **Critical** | ❌ No | < 1 KB | Host bind-mount |
| **Solr index** (3 nodes) | `/source/volumes/solr-data{1,2,3}` | 🟡 **High** | ✅ Yes | 500 MB–50+ GB | Docker named volumes |
| **ZooKeeper data** (3 nodes) | `/source/volumes/zoo-data{1,2,3}/{data,logs,datalog}` | 🟡 **High** | ✅ Yes (quorum) | < 100 MB | Docker named volumes |
| **RabbitMQ state** | `/source/volumes/rabbitmq-data` | 🟢 **Medium** | ✅ Yes | < 100 MB | Docker named volume |
| **Redis state** | `/source/volumes/redis` | 🟢 **Medium** | ✅ Yes | < 100 MB | Docker named volume |
| **SSL certificates** | `/source/volumes/certbot-data/` | 🟡 **High** | ✅ Yes | < 1 MB | Docker named volume |

### Out of Scope

- **Book library** (`$BOOKS_PATH`): Requires separate large-file backup strategy (deduplication, incremental snapshots, offsite replication). Tracked separately ([future issue](#)).
- Pre-release media assets (screenshots, build artifacts): Managed by release workflow, not persisted beyond release cycle.

---

## 3. Requirements & MTTR Targets

### 3.1 Recovery Point Objective (RPO) & Recovery Time Objective (RTO)

| Tier | Data Stores | RPO | RTO | Backup Frequency | Retention |
|---|---|---|---|---|---|
| **Critical** | Auth DB, Collections DB, .env secrets | < 1 hour | < 5 min | Every 30 min | 7 days rolling |
| **High** | Solr + ZooKeeper volumes | < 24 hours | 15–60 min | Daily (off-peak) | 30 days rolling |
| **Medium** | Redis RDB, RabbitMQ Mnesia | < 4 hours | 5–15 min | Daily | 14 days rolling |

### 3.2 Service-Level Availability Targets

| Failure Scenario | Impact | MTTR Estimate | Recovery Method |
|---|---|---|---|
| **Single service crash** (OOM, bug) | 1 service down | < 1 min | Docker auto-restart (`restart: unless-stopped`) |
| **Auth DB corrupted** | All users locked out | 5–15 min | Restore from latest backup, restart solr-search |
| **Solr single-node failure** | Degraded search (2/3 replicas online) | < 5 min | Docker restart; Solr auto-recovers from replicas |
| **Solr full cluster loss** | Search completely down | 4–24 hours | Restore volumes from backup OR full reindex from documents |
| **Redis/RabbitMQ loss** | Indexing pipeline stalls | 5–30 min | Restart services; document-lister re-scans library |
| **Secrets lost** | Cluster won't start | 15–30 min | Restore `.env` from secure vault, restart services |
| **Full VM loss** | Everything down | 1–4 hours | Provision new VM, restore all backups in sequence, health-check cluster |
| **Full disaster** (no backups) | Complete data loss | **Days** | Reprovision, recreate users manually, reindex documents from scratch |

### 3.3 System-Level SLOs

| Metric | Target | Validation |
|---|---|---|
| **RTO (all critical data)** | < 1 hour | Automated monthly restore drill |
| **RPO (auth/collections)** | < 1 hour | Backup timestamp audit in admin UI |
| **Backup success rate** | ≥ 99% | Alert on backup failure |
| **Backup window impact** | < 5% latency increase | Monitoring during backup execution |
| **Monthly restore drill pass rate** | 100% | Automated test suite |

---

## 4. Architecture & Implementation Strategy

### 4.1 Backup System Design

#### Tier 1: Critical Data (SQLite DBs + Secrets) — Every 30 Minutes

**Owner:** Brett (Infra)

**Backup mechanism:** SQLite online backup API (non-blocking, no downtime).

**Implementation:**
- Host-side `scripts/backup.sh` script runs via cron every 30 minutes
- Uses SQLite `.backup` command to atomically copy DB files
- Encrypts sensitive backups (auth DB, secrets) with GPG AES256
- Stores locally in `/source/backups/critical/` directory
- Purges backups older than 7 days
- Logs to `/var/log/aithena-backup-critical.log`

**Files to backup:**
```
$AUTH_DB_DIR/users.db                    → /source/backups/critical/auth-YYYYMMDD-HHMM.db.gpg
$AUTH_DB_DIR/collections.db              → /source/backups/critical/collections-YYYYMMDD-HHMM.db.gpg
.env (host root)                         → /source/backups/critical/env-YYYYMMDD-HHMM.gpg
```

**Encryption:**
- Key file: `/etc/aithena/backup.key` (generated during setup, excluded from git)
- Use `gpg --symmetric --cipher-algo AES256 --batch --passphrase-file /etc/aithena/backup.key`

**Script location:** `scripts/backup-critical.sh`

#### Tier 2: High-Priority Data (Solr + ZooKeeper) — Daily

**Owner:** Brett (Infra)

**Backup mechanism:** Solr Collections API snapshot (clean, API-driven). ZooKeeper `zkServer.sh` export (uses built-in admin tools).

**Implementation:**
- Host-side script runs daily at 2 AM UTC (off-peak)
- Uses Solr REST API to trigger collection snapshots
- Snapshots stored in `/source/backups/solr/` on host
- Compresses and catalogs snapshot metadata
- Stores ZooKeeper data via tar + compression
- Purges backups older than 30 days
- Logs to `/var/log/aithena-backup-high.log`

**Backup process:**
```bash
# Solr snapshot via API
curl -X POST "http://solr:8983/solr/admin/collections?action=BACKUP&name=books-$(date +%Y%m%d-%H%M)&location=/var/solr/backups"

# ZooKeeper export (from zkServer.sh)
docker exec zoo1 zkServer.sh status
docker exec zoo1 zkDump /var/lib/zookeeper/data > /source/backups/zookeeper/zk-dump-$(date +%Y%m%d-%H%M).txt

# Tar volume snapshots (quiescent, no writes expected)
tar --sparse -czf /source/backups/zookeeper/zoo-data{1,2,3}-$(date +%Y%m%d-%H%M).tar.gz /source/volumes/zoo-data{1,2,3}/
```

**Script location:** `scripts/backup-high.sh`

#### Tier 3: Medium-Priority Data (Redis + RabbitMQ) — Daily

**Owner:** Brett (Infra)

**Backup mechanism:** Redis RDB dump export + RabbitMQ definitions export (no Mnesia snapshot needed; state rebuilds automatically).

**Implementation:**
- Host-side script runs daily at 3 AM UTC
- Copies Redis RDB dump from volume
- Exports RabbitMQ definitions via REST API
- Purges backups older than 14 days
- Logs to `/var/log/aithena-backup-medium.log`

**Backup process:**
```bash
# Redis RDB (Redis handles atomic dump)
docker exec redis redis-cli BGSAVE
sleep 2
cp /source/volumes/redis/dump.rdb /source/backups/redis/dump-$(date +%Y%m%d-%H%M).rdb

# RabbitMQ definitions (JSON export, no data)
curl -u "$RABBITMQ_USER:$RABBITMQ_PASS" \
  http://rabbitmq:15672/api/definitions > /source/backups/rabbitmq/definitions-$(date +%Y%m%d-%H%M).json
```

**Script location:** `scripts/backup-medium.sh`

#### Central Orchestrator

**Location:** `scripts/backup.sh`

```bash
#!/bin/bash
# Aithena BCDR Backup Orchestrator
# Usage: ./scripts/backup.sh [--tier critical|high|medium|all] [--dest /path] [--dry-run]

set -euo pipefail

TIER="${1:-all}"
DEST="${2:-.}"
DRY_RUN="${DRY_RUN:-0}"

case "$TIER" in
  critical|all) bash scripts/backup-critical.sh ;;
  high|all) bash scripts/backup-high.sh ;;
  medium|all) bash scripts/backup-medium.sh ;;
esac
```

### 4.2 Restore System Design

**Owner:** Brett (Infra) + Parker (Backend)

#### Restore Orchestrator

**Location:** `scripts/restore.sh`

```bash
#!/bin/bash
# Aithena BCDR Restore Orchestrator
# Usage: ./scripts/restore.sh --from /path/to/backup [--component auth|collections|solr|zk|redis|rabbitmq|all] [--dry-run]

set -euo pipefail

BACKUP_PATH="${1:?--from /path/to/backup required}"
COMPONENT="${2:-all}"
DRY_RUN="${DRY_RUN:-0}"

# Pre-flight checks
echo "=== Pre-Restore Checks ==="
[ -d "$BACKUP_PATH" ] || { echo "Backup path not found: $BACKUP_PATH"; exit 1; }

# Verify backup integrity (checksums)
# — implementation in helper function

# Stop affected services (in dependency order, reverse of startup)
echo "=== Stopping Services ==="
docker-compose down

# Create safety backup of current state before overwriting
echo "=== Creating Pre-Restore Safety Backup ==="
bash scripts/backup.sh --tier all --dest "/source/backups/pre-restore-$(date +%Y%m%d-%H%M%S)"

case "$COMPONENT" in
  auth|all) restore_auth_db "$BACKUP_PATH" ;;
  collections|all) restore_collections_db "$BACKUP_PATH" ;;
  solr|all) restore_solr "$BACKUP_PATH" ;;
  zk|all) restore_zookeeper "$BACKUP_PATH" ;;
  redis|all) restore_redis "$BACKUP_PATH" ;;
  rabbitmq|all) restore_rabbitmq "$BACKUP_PATH" ;;
esac

# Restart services (in correct dependency order)
echo "=== Starting Services ==="
docker-compose up -d

# Post-restore verification
echo "=== Verifying Restore ==="
verify_restore "$COMPONENT"
```

#### Restore Functions (by component)

**Auth DB:**
```bash
restore_auth_db() {
  local backup_path=$1
  local backup_file=$(find "$backup_path" -name "auth-*.db.gpg" -type f | sort -r | head -1)
  [ -n "$backup_file" ] || { echo "No auth backup found"; return 1; }
  
  # Decrypt and restore
  gpg --decrypt --batch --passphrase-file /etc/aithena/backup.key "$backup_file" \
    | gunzip > "$AUTH_DB_DIR/users.db"
  
  # Verify restore
  sqlite3 "$AUTH_DB_DIR/users.db" "SELECT COUNT(*) FROM users;" > /dev/null
  echo "✓ Auth DB restored: $(date)"
}
```

**Solr:**
```bash
restore_solr() {
  local backup_path=$1
  local snapshot_dir=$(find "$backup_path" -type d -name "books-*" | sort -r | head -1)
  [ -n "$snapshot_dir" ] || { echo "No Solr snapshot found"; return 1; }
  
  # Via Solr Collections API RESTORE action
  curl -X POST "http://solr:8983/solr/admin/collections?action=RESTORE&name=books&location=$backup_path" \
    -H "Content-Type: application/json"
  
  # Wait for restore completion
  sleep 5
  curl -s "http://solr:8983/solr/admin/collections?action=CLUSTERSTATUS&wt=json" | grep -q '"books"'
  echo "✓ Solr collection restored: $(date)"
}
```

**ZooKeeper:**
```bash
restore_zookeeper() {
  local backup_path=$1
  
  # Extract ZK data volumes from tarball
  tar -xzf "$backup_path/zoo-data1-*.tar.gz" -C /source/volumes/
  tar -xzf "$backup_path/zoo-data2-*.tar.gz" -C /source/volumes/
  tar -xzf "$backup_path/zoo-data3-*.tar.gz" -C /source/volumes/
  
  # Restart ZK cluster (services already stopped in pre-restore)
  echo "✓ ZooKeeper data restored; cluster will rebuild on startup"
}
```

### 4.3 Admin UI Controls (v1.10.1+)

**Owner:** Dallas (Frontend) + Parker (Backend)

#### API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/v1/admin/backups` | List all available backups with timestamps, sizes, components |
| `POST` | `/v1/admin/backups` | Trigger immediate backup of selected tier (critical/high/medium/all) |
| `GET` | `/v1/admin/backups/{id}` | Backup details: creation time, size, file list, checksum |
| `POST` | `/v1/admin/backups/{id}/restore` | Start restore wizard for selected backup |
| `GET` | `/v1/admin/backups/status` | Current backup status per tier: last backup time, success/failure, next scheduled |
| `PUT` | `/v1/admin/backups/config` | Update backup schedule/retention/encryption settings |
| `POST` | `/v1/admin/backups/test-restore` | Run automated restore drill (creates temporary test environment) |

#### Admin Dashboard Features (React)

**Location:** `src/aithena-ui/src/pages/Admin/BackupDashboard.tsx`

Features:
- **Backup Status Panel**: Per-tier status (last backup, age, size, success/failure indicator)
- **"Backup Now" Button**: Trigger immediate backup, show progress/result
- **Backup History Table**: Sortable list of available backups with size, timestamp, components, "restore" action
- **Restore Wizard**: Multi-step form
  - Step 1: Select backup to restore
  - Step 2: Preview what will be restored (components, timestamps)
  - Step 3: Confirm warnings ("This will overwrite current data", "A safety backup will be created first")
  - Step 4: Restore progress and result
- **Backup Configuration Panel**: Schedule (cron), retention (days), encryption (on/off), destination path (for remote backups, future)
- **Restore Drill Results**: Historical record of monthly restore drill runs with pass/fail status

#### API Implementation (Python)

**Location:** `src/solr-search/backup_service.py` (new module)

```python
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from datetime import datetime
import os
import subprocess
from pathlib import Path

router = APIRouter(prefix="/v1/admin/backups", tags=["admin", "backups"])

class BackupStatus(BaseModel):
    tier: str
    last_backup: datetime | None
    next_scheduled: datetime
    size_mb: float
    success: bool
    message: str

class BackupListResponse(BaseModel):
    critical: BackupStatus
    high: BackupStatus
    medium: BackupStatus

@router.get("/status")
async def get_backup_status() -> BackupListResponse:
    """Return current backup status per tier."""
    # Scan /source/backups/{critical,high,medium}/ directories
    # Return newest backup timestamp, size, status
    pass

@router.post("/")
async def trigger_backup(tier: str = "all", background_tasks: BackgroundTasks = None) -> dict:
    """Trigger immediate backup."""
    valid_tiers = ["critical", "high", "medium", "all"]
    if tier not in valid_tiers:
        raise HTTPException(status_code=400, detail=f"Invalid tier: {tier}")
    
    # Enqueue backup script as background task
    background_tasks.add_task(run_backup_script, tier)
    return {"status": "backup_started", "tier": tier}

@router.get("/{backup_id}")
async def get_backup_details(backup_id: str) -> dict:
    """Get backup metadata: components, size, checksum, restore options."""
    pass

@router.post("/{backup_id}/restore")
async def restore_backup(backup_id: str, background_tasks: BackgroundTasks = None) -> dict:
    """Start restore from selected backup."""
    # Validate backup exists
    # Enqueue restore script with safeguards
    background_tasks.add_task(run_restore_script, backup_id)
    return {"status": "restore_started", "backup_id": backup_id}
```

---

## 5. Disaster Recovery Runbook

**Location:** `docs/admin/disaster-recovery-runbook.md`

### 5.1 Assessment & Decision Tree

**Step 1: Identify the Failure**
- Single service down (e.g., solr-search)? → **Path A: Service Restart**
- Disk/volume error? → **Path B: Restore from Backup**
- Data corruption detected? → **Path C: Restore with Verification**
- Complete VM loss? → **Path D: Full System Recovery**
- Unknown/uncertain? → **Path E: Assessment Protocol**

### 5.2 Recovery Paths

#### Path A: Single Service Failure — Auto-Restart (< 1 min)

**Scenario:** Service exited or crashed (visible in `docker-compose logs -f SERVICE`).

**Action:**
```bash
docker-compose up -d SERVICE_NAME
docker-compose logs SERVICE_NAME  # Verify healthy

# For worker processes (document-lister, document-indexer):
docker-compose restart SERVICE_NAME
```

**Verify:** Health check passes; service logs show normal startup.

#### Path B: Data Loss — Restore from Backup (15–60 min)

**Scenario:** Accidental deletion or corruption detected (e.g., auth DB corrupted, Solr unresponsive after crash).

**Action:**
```bash
# 1. Assess impact
docker-compose logs solr  # Check for errors
sqlite3 ~/.local/share/aithena/auth/users.db "PRAGMA integrity_check;"  # Check DB

# 2. List available backups
ls -lah /source/backups/critical/
ls -lah /source/backups/high/

# 3. Stop services (gracefully, with timeout)
docker-compose down

# 4. Restore affected component
bash scripts/restore.sh --from /source/backups/critical/ --component auth

# 5. Start services
docker-compose up -d

# 6. Verify restore
curl http://localhost/api/v1/health  # Should return 200
sqlite3 ~/.local/share/aithena/auth/users.db "SELECT COUNT(*) FROM users;"
```

**Verify:** All services healthy; no data loss; functionality restored.

#### Path C: Corruption with Verification — Restore & Validate (30–90 min)

**Scenario:** Corruption detected; need to confirm restore doesn't contain corruption.

**Action:**
```bash
# 1. Create diagnostic backup of current (corrupted) state
bash scripts/backup.sh --tier all --dest "/source/backups/diagnostic/corrupted-$(date +%Y%m%d-%H%M%S)"

# 2. Restore from clean backup
bash scripts/restore.sh --from /source/backups/critical/ --component auth

# 3. Run verification suite
bash tests/verify-restore.sh

# 4. If verification passes: commit restore
# 5. If verification fails: revert to diagnostic backup and investigate
```

#### Path D: Full System Recovery — VM Reprovision (1–4 hours)

**Scenario:** Entire VM lost (disk failure, hardware issue); need to recover on new VM.

**Prerequisites:**
- Backup tarball exists on external storage or S3
- New VM provisioned with Docker + Docker Compose installed
- Network access to backup storage

**Action:**
```bash
# 1. On new VM, prepare directories
mkdir -p /source/volumes/{solr-data{1,2,3},zoo-data{1,2,3},rabbitmq-data,redis}
mkdir -p /source/backups

# 2. Copy backup tarball from external storage
scp user@backup-host:/mnt/backups/aithena-backup-latest.tar.gz /source/backups/

# 3. Extract backups
cd /source/backups && tar -xzf aithena-backup-latest.tar.gz

# 4. Restore all components in sequence
bash scripts/restore.sh --from /source/backups/latest/ --component all

# 5. Start cluster
docker-compose up -d

# 6. Monitor health (all services should be green within 2 min)
docker-compose ps
docker-compose logs -f
```

**Verify:** All services healthy; admin UI accessible; search functional; users can login.

#### Path E: Assessment Protocol (10–30 min)

**Scenario:** Uncertain what failed; need diagnostic data before attempting recovery.

**Action:**
```bash
# 1. Collect diagnostic data
docker-compose ps > /tmp/status.txt
docker-compose logs --tail=100 > /tmp/docker-compose.logs.txt
df -h > /tmp/disk-usage.txt
docker system df > /tmp/docker-disk.txt

# 2. Check each service health
for svc in redis rabbitmq solr solr-search aithena-ui; do
  echo "=== $svc ==="
  curl -s http://localhost:8080/health || echo "UNREACHABLE"
done

# 3. Check volumes for corruption/errors
find /source/volumes -name "*.corrupt" -o -name "*.lock" -o -name "*.wal"

# 4. Review recent logs for errors/warnings
docker-compose logs --tail=50 2>&1 | grep -i "error\|warn\|fatal"

# 5. Document findings and decide on path (A, B, C, or D)
```

### 5.3 Post-Restore Verification Checklist

After any restore, verify:

- [ ] All services report healthy in `docker-compose ps`
- [ ] Admin UI loads at `http://localhost/admin`
- [ ] Auth: Login works with known username/password
- [ ] Search: Keyword and semantic search return results
- [ ] Redis: `redis-cli ping` returns PONG
- [ ] RabbitMQ: Management UI accessible at `http://localhost:15672`
- [ ] Solr: Collection status shows replicas healthy
- [ ] No errors in `docker-compose logs` (last 100 lines)
- [ ] Disk usage reasonable (not grown unexpectedly)

### 5.4 Monthly Restore Drill

**Owner:** Newt (PM) + Brett (Infra)

**Schedule:** First Monday of each month, 2 AM UTC

**Procedure:**
```bash
# 1. Select a random backup from last 7 days
BACKUP=$(ls -t /source/backups/critical/ | head -1)

# 2. On staging environment (separate VM), restore
docker-compose -f docker-compose.yml -f docker-compose.staging.yml down
bash scripts/restore.sh --from "/source/backups/$BACKUP" --component all

# 3. Run smoke tests
bash tests/verify-restore.sh

# 4. Report results (PASS/FAIL) to team
# 5. Document any issues found and plan remediation
```

**Success criteria:** Restore completes in < 30 min, all verification checks pass.

---

## 6. Implementation Timeline & Deliverables

### Phase 1: Core Backup/Restore Scripts (v1.10.0)

| Task | Owner | Duration | Deliverable |
|---|---|---|---|
| Backup script: critical tier (SQLite + .env) | Brett | 3 days | `scripts/backup-critical.sh` |
| Backup script: high tier (Solr + ZK) | Brett | 4 days | `scripts/backup-high.sh` |
| Backup script: medium tier (Redis + RabbitMQ) | Brett | 2 days | `scripts/backup-medium.sh` |
| Orchestrator & cron setup | Brett | 2 days | `scripts/backup.sh`, crontab integration |
| Restore orchestrator | Brett + Parker | 4 days | `scripts/restore.sh` |
| Verify & test restore functions | Lambert | 3 days | `tests/verify-restore.sh` integration tests |
| Disaster recovery runbook | Newt | 3 days | `docs/admin/disaster-recovery-runbook.md` |
| **Phase 1 Total** | — | **21 days** | **v1.10.0 release** |

### Phase 2: Admin UI & API (v1.10.1)

| Task | Owner | Duration | Deliverable |
|---|---|---|---|
| Backup API endpoints | Parker | 3 days | `src/solr-search/backup_service.py` |
| Admin UI dashboard | Dallas | 4 days | `src/aithena-ui/src/pages/Admin/BackupDashboard.tsx` |
| Backup status indicator | Dallas | 2 days | Status badge in main admin page |
| **Phase 2 Total** | — | **9 days** | **v1.10.1 release** |

### Phase 3: Hardening & Testing (v1.10.2)

| Task | Owner | Duration | Deliverable |
|---|---|---|---|
| Automated restore drill (monthly) | Lambert | 3 days | `.github/workflows/monthly-restore-drill.yml` |
| Backup integrity verification | Brett | 2 days | `scripts/verify-backup.sh` (checksums, encryption validation) |
| Performance testing (backup window impact) | Lambert | 3 days | Load test results: latency delta < 5% |
| Documentation review & updates | Newt | 2 days | Updated deployment, admin manuals |
| **Phase 3 Total** | — | **10 days** | **v1.10.2 release** |

### Milestone Dependencies

- **v1.10.0:** Collections DB path finalized (depends on #591)
- **v1.10.1:** Admin page framework ready (assume exists)
- **v1.10.2:** Integration with monitoring/alerting (separate issue)

---

## 7. Deployment & Operational Procedures

### 7.1 Initial Setup (One-Time)

After deploying v1.10.0:

```bash
# 1. Create backup directories
sudo mkdir -p /source/backups/{critical,high,medium,diagnostic}
sudo chmod 700 /source/backups

# 2. Generate encryption key (keep secret, not in git)
openssl rand -hex 32 | tee /etc/aithena/backup.key
sudo chmod 600 /etc/aithena/backup.key
sudo chown aithena:aithena /etc/aithena/backup.key

# 3. Install cron jobs (as root or aithena user)
sudo crontab -e
# Add:
#   0 */6 * * * /home/aithena/aithena/scripts/backup-critical.sh
#   0 2 * * * /home/aithena/aithena/scripts/backup-high.sh
#   0 3 * * * /home/aithena/aithena/scripts/backup-medium.sh

# 4. Test backup execution (manually)
bash scripts/backup.sh --tier all
ls -la /source/backups/

# 5. Verify backups are encrypted
file /source/backups/critical/auth-*.db.gpg  # Should show "GPG encrypted data"
```

### 7.2 Ongoing Monitoring

**Backup Success Monitoring:**
- Cron job logs: `/var/log/aithena-backup-*.log` (check daily for errors)
- Admin UI: Backup status dashboard shows last backup age
- Alert: If last backup > RPO target, send alert (implement in v1.10.2)

**Restore Drill:**
- Monthly automated drill via GitHub Actions workflow
- Results logged; failures trigger investigation
- Report to team after each successful drill

### 7.3 Retention Policy & Cleanup

| Tier | Retention | Cleanup Method |
|---|---|---|
| Critical | 7 days | `find /source/backups/critical -mtime +7 -delete` |
| High | 30 days | `find /source/backups/high -mtime +30 -delete` |
| Medium | 14 days | `find /source/backups/medium -mtime +14 -delete` |

Cleanup runs automatically in backup scripts (at end of each tier's backup job).

---

## 8. Security & Access Control

### 8.1 Encryption

- **Critical tier**: GPG AES256 symmetric encryption (passphrase in `/etc/aithena/backup.key`)
- **High/Medium tiers**: Unencrypted (metadata only, no credentials); stored on trusted host
- **Key management**: Backup key generated during installer setup, stored in `/etc/aithena/backup.key` (not in git, not in `.env`)

### 8.2 Access Control

- **Backup files**: Read-only (644), owned by `aithena` user
- **Encryption key**: Owner-only (600), owned by `aithena` user
- **Admin API**: Requires authenticated user (existing auth system)
- **Restore operations**: Only executable by cluster admins (authorization TBD in Parker's API implementation)

### 8.3 Backup Validation

- Checksums stored alongside backups (MD5, SHA256)
- Restore script validates checksum before restore
- Encryption integrity checked (GPG verify) before decryption

---

## 9. Open Questions for Team Discussion

1. **Remote backup destination**: Should we support S3-compatible, NFS, or rsync to remote host? (v1.10.2+)
2. **Backup frequency tweaking**: Are the RPO targets (30 min critical, 24 hour high, 4 hour medium) reasonable for your SLO?
3. **Solr snapshot method**: Collections API BACKUP (recommended) or volume-level tar? Collections API is cleaner but slower.
4. **Book library backup**: Separate issue or part of future phase? Recommend separate (large-file dedup strategy).
5. **Alerting integration**: Should backup failures trigger webhooks, email alerts, Slack notifications?
6. **Admin API auth scope**: Restore operations should require what level of authorization? (Admin-only? Backup operator role?)
7. **Staging environment**: Should we maintain a separate staging Docker environment for restore drills, or use a flag?
8. **Documentation format**: Runbook in Markdown (docs/admin/) or as Streamlit page in admin dashboard?

---

## 10. Success Criteria & Acceptance

✅ **Backup System:**
- Critical-tier backups run every 30 min, stored encrypted
- High-tier backups run daily, stored unencrypted
- Medium-tier backups run daily, stored unencrypted
- Retention policies auto-enforced
- All backup operations logged to `/var/log/aithena-backup-*.log`

✅ **Restore System:**
- Restore scripts validate backup integrity before restore
- Services stopped, safety backup created, restore executed, services restarted
- Post-restore verification checks pass
- Manual restore from CLI works (tested)

✅ **Admin UI (v1.10.1):**
- Backup status dashboard shows per-tier status and history
- "Backup now" button works
- Restore wizard guides users through restore process
- Backup configuration settings editable

✅ **Disaster Recovery:**
- Runbook documented with clear decision tree and procedures
- Monthly restore drill automated and passing
- Team trained on assessment and recovery procedures

✅ **Testing:**
- Unit tests for backup script functions (checksum, encryption, compress)
- Integration tests for restore (full lifecycle: backup → restore → verify)
- Chaos testing: simulate service failures and verify recovery

---

## 11. References & Appendices

### A. Related Issues
- #591: Collections SQLite DB (v1.10) — defines DB location
- #590: Stress testing — backup window must not degrade performance
- #363: Release packaging — related to tarball distribution

### B. External References
- SQLite backup: https://www.sqlite.org/backup.html
- Solr Collections API: https://solr.apache.org/guide/solr/latest/configuration-guide/collections-api.html
- ZooKeeper backup: https://zookeeper.apache.org/doc/current/
- GPG encryption: https://www.gnu.org/software/gpg/gph/en/manual/x110.html

### C. Glossary
- **RPO**: Recovery Point Objective (how much data loss is acceptable)
- **RTO**: Recovery Time Objective (how long to recover)
- **MTTR**: Mean Time To Recovery (average time to recover from failure)
- **Quorum**: Majority of ZooKeeper ensemble (2 of 3 nodes)
- **Replication Factor**: Number of Solr replicas (3 = copies on all 3 nodes)

---

_Document Version: 1.0_  
_Last Updated: 2026-04-10_  
_Status: Draft (awaiting team review)_
