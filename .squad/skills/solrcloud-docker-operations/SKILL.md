---
name: "solrcloud-docker-operations"
description: "How to operate, recover, and harden the project's SolrCloud and ZooKeeper stack in Docker Compose"
domain: "infrastructure, docker, solrcloud, zookeeper"
confidence: "high"
source: "earned — extracted from Brett's SolrCloud Docker operations research, validated during collection bootstrap and admin ingress work (Sessions 2–3)"
author: "Brett"
created: "2026-03-14"
last_validated: "2026-03-14"
---

## Context
Apply this skill when an agent is changing `docker-compose.yml`, operating the SolrCloud stack, planning backup/recovery, or debugging Solr/ZooKeeper incidents. It is specifically grounded in aithena's current topology: a 3-node ZooKeeper ensemble (`zoo1`-`zoo3`), a 3-node SolrCloud cluster (`solr`, `solr2`, `solr3`), and application services that currently talk directly to `solr:8983`.

## Patterns

### 1. Persist the control plane and the data plane separately

**Solr volumes that matter:**
- Persist each node's replica storage under `/var/solr/data`; this holds Lucene index files, core metadata, and transaction logs needed for replica recovery.
- Prefer one dedicated volume per Solr node. Never share a Solr data volume between nodes.
- If persistent Solr logs matter, mount `/var/solr`, not only `/var/solr/data`.

**ZooKeeper volumes that matter:**
- `/data` stores snapshots and persistent ensemble state.
- `/datalog` stores ZooKeeper transaction logs and is quorum-critical.
- `/logs` is not required for quorum, but is valuable for troubleshooting.

**Loss scenarios:**
- Lose one Solr volume, keep ZooKeeper + other replicas healthy: SolrCloud can usually rebuild that replica from a healthy leader.
- Lose all Solr volumes, keep ZooKeeper: collections/configsets/security metadata remain, but shard data is gone; restore from backup or reindex from `/home/jmservera/booklibrary`.
- Lose ZooKeeper, keep Solr volumes: local Lucene files may still exist, but cluster metadata, configsets, and `security.json` are gone; rebuild ZooKeeper, re-upload configsets/security, recreate collections, then restore or reindex.
- Lose both: perform a full rebuild.

**Operational rule:** back up ZooKeeper state and Solr data independently. Solr node disks alone are not enough for a full SolrCloud restore.

### 2. Understand restart behavior before touching the cluster

**Single Solr node restart:**
- The node drops out of `live_nodes`.
- If it was a leader, Solr elects a new leader from remaining leader-eligible replicas.
- On restart, the node recovers via peer sync, tlog replay, or full replication.
- In aithena, if `solr` is the restarted node, `document-indexer` and `solr-search` may still fail because both are pinned to `solr:8983`.

**All Solr nodes restart:**
- If ZooKeeper quorum survives, metadata survives.
- Expect leader election first, then replica recovery.
- Uncommitted but logged updates can recover from persistent tlogs.

**Single ZooKeeper node restart:**
- A 3-node ensemble still has quorum with 2 healthy nodes.
- Solr usually reconnects automatically.

**ZooKeeper quorum loss:**
- In a 3-node ensemble, quorum is 2.
- Losing 2 ZooKeeper nodes means no safe control-plane updates and no reliable write coordination.
- Treat this as a write outage until quorum returns.

**Startup rule:** Solr should wait for *healthy ZooKeeper quorum*, not merely for containers to be started.

### 3. Use a predictable failure-recovery runbook

**Triage first:**
```bash
docker compose exec zoo1 sh -lc 'printf ruok | nc -w 2 localhost 2181'
docker compose exec zoo1 sh -lc 'printf mntr | nc -w 2 localhost 2181'
curl -s 'http://localhost:8983/solr/admin/collections?action=CLUSTERSTATUS&wt=json'
curl -fsS 'http://localhost:8983/solr/books/admin/ping?distrib=true' >/dev/null
```
Expected `ruok` output is `imok`.

**Recover a crashed Solr node when its volume still exists:**
```bash
docker compose restart solr2
curl -s 'http://localhost:8983/solr/admin/collections?action=CLUSTERSTATUS&wt=json'
```
Usually let SolrCloud self-heal before changing replicas.

**Recover a stuck replica that still exists:**
1. Find the replica name in `CLUSTERSTATUS`.
2. Request recovery:
```bash
curl 'http://localhost:8983/solr/admin/collections?action=REQUESTRECOVERY&collection=books&shard=shard1&replica=<core_node_name>'
```
Use this only when the replica exists but failed to self-heal after a node or network event.

**Rebuild a replica after disk loss or corruption:**
```bash
curl -X DELETE 'http://localhost:8983/api/collections/books/shards/shard1/replicas/<core_node_name>'
curl -X POST 'http://localhost:8983/api/collections/books/shards/shard1/replicas' \
  -H 'Content-Type: application/json' \
  -d '{"node":"solr2:8983_solr","type":"nrt","waitForFinalState":true}'
```
Use recreate, not `REQUESTRECOVERY`, when the volume is gone, the replica is corrupt, or the node was rebuilt from scratch.

**Recover configsets after ZooKeeper loss:**
```bash
docker compose cp ./solr/books solr:/tmp/books
docker compose exec solr solr zk upconfig \
  -zkhost zoo1:2181,zoo2:2181,zoo3:2181 \
  -n books \
  -d /tmp/books
curl 'http://localhost:8983/solr/admin/collections?action=RELOAD&name=books'
```
If runtime overlay settings were lost, re-run `solr/add-conf-overlay.sh`.

**Recreate collection metadata after control-plane loss:**
```bash
curl 'http://localhost:8983/solr/admin/collections?action=CREATE&name=books&numShards=1&replicationFactor=3&collection.configName=books'
```

**Full catastrophic recovery order:**
1. Stop writers/indexers:
   ```bash
   docker compose stop document-indexer solr-search
   ```
2. Restore or rebuild ZooKeeper quorum:
   ```bash
   docker compose up -d zoo1 zoo2 zoo3
   ```
3. Bring up Solr nodes and re-upload configsets.
4. Recreate collections.
5. Restore backups or reindex from `/home/jmservera/booklibrary`.
6. Reload the collection and restart dependents:
   ```bash
   docker compose up -d solr solr2 solr3 document-indexer solr-search
   ```

**Backup commands once `/backup` is mounted identically on all Solr nodes:**
```bash
curl 'http://localhost:8983/solr/admin/collections?action=BACKUP&collection=books&name=books-2026-03-14&repository=local_repo&location=/backup&async=books-backup-001'
curl 'http://localhost:8983/solr/admin/collections?action=REQUESTSTATUS&requestid=books-backup-001'
```

### 4. Harden Docker Compose for stateful SolrCloud services

**Health checks to add:**
```yaml
zoo1:
  healthcheck:
    test: ["CMD-SHELL", "printf ruok | nc -w 2 localhost 2181 | grep imok"]
    interval: 30s
    timeout: 10s
    retries: 5
    start_period: 20s

solr:
  healthcheck:
    test: ["CMD-SHELL", "curl -fsS http://localhost:8983/solr/admin/info/system >/dev/null"]
    interval: 30s
    timeout: 10s
    retries: 5
    start_period: 40s
```
If the `books` collection already exists, a stronger readiness probe is:
```yaml
healthcheck:
  test: ["CMD-SHELL", "curl -fsS http://localhost:8983/solr/books/admin/ping?distrib=true | grep -q OK"]
```

**Dependency ordering:**
Use Compose long syntax so services wait for real readiness, not just container start:
```yaml
depends_on:
  zoo1:
    condition: service_healthy
  zoo2:
    condition: service_healthy
  zoo3:
    condition: service_healthy
```
Serial Solr startup (`solr2` depends on `solr`, `solr3` depends on `solr2`) is not required once ZooKeeper is healthy.

**Restart policy:**
- Use `unless-stopped` for Solr and ZooKeeper.
- `on-failure` is acceptable for workers, not ideal for the search control plane.

**Graceful shutdown and resources:**
```yaml
stop_grace_period: 60s
environment:
  SOLR_HEAP: 1g
```
Pair heap sizing with container memory limits; do not set Docker memory and JVM heap to the same number.

**Other Compose rules:**
- Cap Docker logs to avoid disk exhaustion.
- Mount the same `/backup` path on every Solr node before relying on filesystem backups.
- Prefer an internal network for `zoo*` and `solr*`; only publish ports that operators or external clients truly need.

### 5. Operate ZooKeeper as a quorum service, not a generic dependency

**Current ensemble facts:**
- `ZOO_MY_ID` and `ZOO_SERVERS` are correctly defined for a 3-node ensemble.
- Current 4LW whitelist is `mntr,conf,ruok`; `stat` is not enabled.
- One-node maintenance at a time is safe; two-node loss removes quorum.

**Useful commands:**
```bash
docker compose exec zoo1 sh -lc 'printf ruok | nc -w 2 localhost 2181'
docker compose exec zoo1 sh -lc 'printf mntr | nc -w 2 localhost 2181'
docker compose exec zoo1 sh -lc 'printf conf | nc -w 2 localhost 2181'
```

**Session timeout guidance:**
- If ZooKeeper is unreachable longer than the Solr client/session timeout, Solr nodes lose their sessions, drop out of `live_nodes`, and trigger recovery.
- Small timeouts create false failovers; overly large timeouts delay real failover.

**Data hygiene:**
- Keep `/data` and `/datalog` separate.
- Configure ZooKeeper autopurge (`autopurge.snapRetainCount`, `autopurge.purgeInterval`) to prevent unbounded disk growth.
- Never wipe `/data` or `/datalog` casually. A single failed node should be replaced, not used to justify full ensemble reinitialization.

### 6. SASL Auth Model: Solr 9.7 + Java 17 + ZK 3.9 Incompatibility (v1.14.0+)

**Critical finding (v1.14.0):** SASL DIGEST-MD5 client auth from Solr to ZooKeeper is fundamentally broken in this stack:
- **Root cause:** Solr 9.7's bundled ZooKeeper client JAR is missing `org.apache.zookeeper.server.auth.DigestLoginModule`, required for SASL DIGEST-MD5
- **Additional blocker:** Solr 9.7 security manager enabled by default, denies access to `sun.security.provider` needed by JAAS
- **Expected behavior:** `requireClientAuthScheme=sasl` in ZK config should enforce client auth; does not work

**Workaround & Current Architecture (v1.14.0+):**
- **Disabled:** `requireClientAuthScheme=sasl` (doesn't work with Solr 9.7's client)
- **Enabled:** ZK quorum SASL (inter-node auth between zoo1/zoo2/zoo3) — ✅ works
- **Enabled:** ZK digest ACLs (Solr znodes restricted to `DigestZkCredentialsProvider`) — ✅ works
- **Security boundary:** Docker network isolation + ZK digest ACLs on znodes sufficient for production
- **File path gotcha:** JAAS config must be owned by container user (ZK runs as UID 1000 via gosu; file unreadable if root-owned). Solr writable path is `/var/solr/` only.

**Reference:** `.squad/agents/brett/history.md` section "SASL Auth Broken in Solr 9.7 + Java 17 + ZK 3.9"

### 7. Account for aithena-specific operational risks

The current `docker-compose.yml` has the following important infrastructure risks:
- `zoo1` publishes `8080:8080`, which collides with `solr-search` publishing `8080:8080`.
- `document-indexer` (`SOLR_HOST=solr`) and `solr-search` (`SOLR_URL=http://solr:8983/solr`) depend on a single Solr node instead of a resilient Solr entry path.
- Solr and ZooKeeper have no health checks.
- Compose ordering uses `depends_on` start order only; it does not wait for ZooKeeper quorum or Solr HTTP readiness.
- ZooKeeper services do not currently set a restart policy.
- No `stop_grace_period`, JVM sizing, memory limits, or log caps are set for Solr/ZooKeeper.
- Solr backup configuration exists in `solr/add-conf-overlay.sh`, but Solr containers do not mount `/backup`; only ZooKeeper nodes do.
- More host ports are published than normal intra-compose traffic requires (`2182`, `2183`, `8984`, `8985`, and ZooKeeper AdminServer on `8080`).

## Examples

### Example: verify the cluster is healthy after maintenance
```bash
docker compose exec zoo1 sh -lc 'printf ruok | nc -w 2 localhost 2181'
curl -fsS 'http://localhost:8983/solr/admin/info/system' >/dev/null
curl -fsS 'http://localhost:8983/solr/books/admin/ping?distrib=true' >/dev/null
curl -s 'http://localhost:8983/solr/admin/collections?action=CLUSTERSTATUS&wt=json'
```

### Example: recover after one Solr node loses its local disk
```bash
docker compose up -d solr2
curl -s 'http://localhost:8983/solr/admin/collections?action=CLUSTERSTATUS&wt=json'
curl -X DELETE 'http://localhost:8983/api/collections/books/shards/shard1/replicas/<old_core_node_name>'
curl -X POST 'http://localhost:8983/api/collections/books/shards/shard1/replicas' \
  -H 'Content-Type: application/json' \
  -d '{"node":"solr2:8983_solr","type":"nrt","waitForFinalState":true}'
```

### Example: rebuild the control plane after ZooKeeper data loss
```bash
docker compose stop document-indexer solr-search
docker compose up -d zoo1 zoo2 zoo3 solr solr2 solr3
docker compose cp ./solr/books solr:/tmp/books
docker compose exec solr solr zk upconfig \
  -zkhost zoo1:2181,zoo2:2181,zoo3:2181 \
  -n books \
  -d /tmp/books
curl 'http://localhost:8983/solr/admin/collections?action=CREATE&name=books&numShards=1&replicationFactor=3&collection.configName=books'
```
Then reindex from `/home/jmservera/booklibrary` if shard data is gone.

## Anti-Patterns

- **Do not share one Solr data volume across multiple Solr nodes** — each node needs its own replica storage.
- **Do not treat ZooKeeper data as disposable** — in SolrCloud it holds configsets, collection state, and `security.json`.
- **Do not rely on Compose start order as readiness** — use health checks and `condition: service_healthy`.
- **Do not serially restart or wipe multiple ZooKeeper nodes at once** — two-node loss kills quorum in this 3-node ensemble.
- **Do not use `REQUESTRECOVERY` after a volume is lost** — recreate the replica instead.
- **Do not assume local Solr backups work until `/backup` is mounted on every Solr node at the same path**.
- **Do not pin all application traffic to one Solr node in a cluster you expect to survive single-node failure**.

## References
- `.squad/agents/brett/history.md`
- `.squad/templates/skill.md`
- `docker-compose.yml`
- `solr/add-conf-overlay.sh`
- `solr/books/`
- Apache Solr Reference Guide — Docker, SolrCloud recovery, collections API, configsets
- Apache ZooKeeper documentation — ensemble configuration, admin guide, operational maintenance
- Docker Compose documentation — `depends_on`, `service_healthy`, restart semantics, shutdown ordering
