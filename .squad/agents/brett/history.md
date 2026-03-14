# Brett — History

## Project Context
- **Project:** aithena — Book library search engine with Solr full-text indexing, multilingual embeddings, PDF processing, and React UI
- **User:** jmservera
- **Stack:** Python (backend services), TypeScript/React + Vite (UI), Docker Compose, Apache Solr (search), multilingual embeddings
- **Joined:** 2026-03-14 as Infrastructure Architect (Docker, Compose, SolrCloud)
- **Current infrastructure:** SolrCloud 3-node cluster + ZooKeeper 3-node ensemble, Redis, RabbitMQ, nginx, 9 Python services in Docker
- **Active initiative:** UV migration across 7 Python services (issues #81-#87), security scanning (#88-#90), CI hardening

## Learnings
- 2026-03-14: Extracted the SolrCloud Docker operations research into `.squad/skills/solrcloud-docker-operations/SKILL.md` so other agents can reuse the runbooks and hardening guidance.
- 2026-03-14: The local SolrCloud compose stack must use the official `solr:9.7` image with `ZK_HOST` and no `solr start -c -f` entrypoint override; keep `solr-search` on host port 8080 and move ZooKeeper AdminServer to a non-conflicting host port instead.
- 2026-03-14: Added a one-shot `solr-init` bootstrap service plus ZooKeeper/Solr health checks so the `books` configset uploads, the `books` collection is recreated idempotently, and `document-indexer` waits for bootstrap completion before indexing.
- 2026-03-14: `buildall.sh` should `uv sync` the uv-managed Python services (`admin`, `document-indexer`, `document-lister`, `solr-search`) and skip `embeddings-server` until it gains a `pyproject.toml`; local end-to-end `docker compose up --build -d` validation can still be blocked by external image pulls (RabbitMQ) or unrelated frontend lockfile drift.

## SolrCloud Docker Operations Reference

### Current Project Setup
- **Cluster topology:** `docker-compose.yml` defines a **3-node ZooKeeper ensemble** (`zoo1`, `zoo2`, `zoo3`) and a **3-node SolrCloud cluster** (`solr`, `solr2`, `solr3`). Every Solr node uses `ZK_HOST="zoo1:2181,zoo2:2181,zoo3:2181"`, enables `SOLR_MODULES=extraction,langid`, and starts in **cloud mode** with `docker-entrypoint.sh solr start -c -f`.
- **Ports currently exposed:**
  - ZooKeeper: `zoo1` exposes `2181:2181` and `8080:8080`; `zoo2` exposes `2182:2181`; `zoo3` exposes `2183:2181`.
  - Solr: `solr` = `8983:8983`, `solr2` = `8984:8983`, `solr3` = `8985:8983`.
  - Practical note: `zoo1` and `solr-search` both claim host port **8080**, so the current compose file has a host-port collision.
- **Application ingress today is not HA:** `document-indexer` and `solr-search` both point to `solr:8983`, not to a load-balanced Solr endpoint. Replica redundancy exists inside SolrCloud, but client traffic still depends on the first Solr node being reachable.
- **Current volume layout:**
  - `solr-data`, `solr-data2`, `solr-data3` → `/var/solr/data` on each Solr node.
  - `document-data` → `/data/documents` (read-only inside Solr and app services, backed by `/home/jmservera/booklibrary`).
  - ZooKeeper per-node volumes:
    - `zoo-data1_data`, `zoo-data2_data`, `zoo-data3_data` → `/data`
    - `zoo-data1_datalog`, `zoo-data2_datalog`, `zoo-data3_datalog` → `/datalog`
    - `zoo-data1_logs`, `zoo-data2_logs`, `zoo-data3_logs` → `/logs`
  - All of these are **bind-backed local volumes** pointing at fixed host paths under `/source/volumes/...` (plus the book library bind at `/home/jmservera/booklibrary`).
- **Health checks today:** only `redis` and `rabbitmq` have health checks. **Solr and ZooKeeper have none**, even though the `books` config includes `/admin/ping`, and ZooKeeper has `ruok/mntr/conf` enabled.
- **Startup ordering today:**
  - `solr` depends on `zoo1/zoo2/zoo3`
  - `solr2` depends on `zoo1/zoo2/zoo3/solr`
  - `solr3` depends on `zoo1/zoo2/zoo3/solr2`
  - This is only **container start order**, not readiness. Compose without `condition: service_healthy` does **not** wait for ZooKeeper quorum or Solr HTTP readiness.
- **Restart policies today:**
  - `solr`, `solr2`, `solr3`: `unless-stopped`
  - `redis`, `rabbitmq`, `embeddings-server`, `document-lister`, `document-indexer`, `solr-search`: `on-failure`
  - `nginx`, `certbot`: `unless-stopped`
  - `zoo1`, `zoo2`, `zoo3`: **no restart policy set**
- **Missing operational hardening today:** no `stop_grace_period`, no Solr/ZK resource limits, no logging caps, no isolated internal search network, and no Solr backup path mounted into Solr nodes.
- **Solr configset structure in repo:**
  - `solr/books/managed-schema.xml`
  - `solr/books/solrconfig.xml`
  - `solr/books/configoverlay.json`
  - `solr/books/synonyms.txt`, `stopwords.txt`, `protwords.txt`
  - `solr/books/lang/*` multilingual language resources
  - `solr/config.json` is an exported effective config snapshot.
  - `solr/add-conf-overlay.sh` re-applies `/update/extract` and `initParams` through the Config API.
- **Important runtime nuance:** in SolrCloud, these repo files are **bootstrap artifacts**, not the live source of truth after upload. Once the configset is in ZooKeeper, the cluster reads it from ZooKeeper.
- **Another current gap:** `solr/add-conf-overlay.sh` defines a backup repository at `/backup`, but the Solr containers do **not** mount `/backup` today; only the ZooKeeper nodes do. Local filesystem Solr backups are therefore not wired up yet.

### Critical Volumes
- **What must be persisted for Solr:**
  - At minimum, each Solr node needs persistent replica storage for its **Lucene index**, **transaction log (tlog / UpdateLog)**, and core metadata under `/var/solr/data`.
  - The official Solr image is designed around **`/var/solr`** as the main persistent area for data and logs. Persisting only `/var/solr/data` preserves shard data, but any logs or other variable files under `/var/solr` remain ephemeral.
- **What must be persisted for ZooKeeper:**
  - `/data` holds persistent ensemble state and snapshots.
  - `/datalog` holds ZooKeeper transaction logs and is operationally critical.
  - `/logs` is not quorum-critical, but it is valuable for troubleshooting and postmortems.
  - Current compose already separates `/data` and `/datalog`, which aligns with ZooKeeper best practice.
- **Solr home vs Solr data vs configsets in containers:**
  - `/opt/solr` = installed Solr distribution in the container image.
  - `/var/solr` = variable runtime state (data + logs in the official image).
  - `/var/solr/data` = replica/core data area used by the current compose file.
  - `solr/books/` in the repo = **bootstrap configset source**, not the runtime authority after upload.
- **Configsets and `security.json` in SolrCloud:**
  - In SolrCloud, **configsets live in ZooKeeper** after upload.
  - `security.json` also lives in ZooKeeper (`/security.json`), not on a Solr node’s local disk.
  - This means Solr node volumes are not enough by themselves for a full cluster restore; ZooKeeper persistence matters just as much.
- **What is recoverable if volumes are lost:**
  - **Lose one Solr node volume:** that node’s local replicas are gone. Recovery is automatic only if another healthy replica for each affected shard exists.
  - **Lose all Solr volumes, keep ZooKeeper:** collections/configsets/security remain defined, but shard data is gone. Restore from Solr backup or reindex from source documents.
  - **Lose ZooKeeper volumes, keep Solr volumes:** Lucene files may still exist, but cluster metadata, configsets, async state, collection definitions, and security are gone. In practice, the fast recovery path is usually: rebuild ZooKeeper → re-upload configsets/security → recreate collections → restore or reindex.
  - **Lose both Solr and ZooKeeper volumes:** full rebuild from backup or reindex.
- **Aithena-specific recovery advantage:** the PDFs under `/home/jmservera/booklibrary` are the real content source of truth for Phase 1 indexing, so full-text can be rebuilt even after catastrophic Solr loss. ZooKeeper metadata still needs backup because collection definitions, configsets, and future `security.json` are not reconstructible from replica data alone.
- **Bind mounts vs named volumes:**
  - **Current pattern:** bind-backed local volumes.
  - **Bind mount pros:** easy host inspection, straightforward filesystem backups, explicit placement, good fit for Linux servers.
  - **Bind mount cons:** path coupling, permissions/SELinux friction, easier accidental host-side tampering, less portability, slower dev performance on macOS.
  - **Named volume pros:** Docker-managed lifecycle, cleaner portability, less host-path coupling.
  - **Named volume cons:** less transparent to inspect/backup, awkward for existing host datasets such as the book library.
- **Brett recommendation for this repo:**
  - Keep the book library as a bind mount.
  - Keep **one dedicated Solr volume per node** and **never share a Solr data volume between nodes**.
  - Consider mounting **all of `/var/solr`** instead of only `/var/solr/data` if persistent Solr logs and image-default layout matter.

### Restart Behavior
- **Why `-f` matters in Docker:** `solr start -f` keeps Solr in the foreground so the JVM stays attached to PID 1 and Docker can supervise it correctly. Without `-f`, the server daemonizes and the container exits even though Solr started.
- **Why `-c` matters:** `-c` starts Solr in **SolrCloud mode**, so every node registers in ZooKeeper, participates in leader election, and serves as a cloud node instead of a standalone core host.
- **Current ZK connection string:** `zoo1:2181,zoo2:2181,zoo3:2181`. Operationally, Brett should consider adding a chroot later (for example `/solr`) if multiple logical clusters ever share the same ensemble.
- **When a single Solr node restarts:**
  - The node disappears from ZooKeeper `live_nodes`.
  - If it hosted a shard leader, a new leader is elected from leader-eligible replicas.
  - When the node comes back, its replicas recover from the active leader using peer sync, tlog replay, or full replication.
  - If the restarted node is the ingress node `solr`, app traffic from `document-indexer` and `solr-search` still breaks even if `solr2`/`solr3` are healthy.
- **When all Solr nodes restart at once:**
  - If ZooKeeper remains healthy, collection metadata survives and nodes can rejoin.
  - Expect a full cluster recovery window: leader election first, then replica recovery.
  - Uncommitted-but-logged updates can be recovered from persistent tlogs; unpersisted/ephemeral container state cannot.
  - If Solr volumes are lost during the restart, the cluster may come back with intact metadata in ZooKeeper but missing shard data.
- **When a single ZooKeeper node restarts:**
  - A 3-node ensemble keeps quorum with 2 healthy nodes.
  - Solr normally reconnects automatically.
  - If the outage exceeds Solr’s ZK client timeout, some Solr sessions may expire and the nodes may briefly disappear from `live_nodes`, then recover.
- **When ZooKeeper loses quorum temporarily:**
  - In a 3-node ensemble, quorum is **2**.
  - Losing 2 ZooKeeper nodes means no leader election, no safe cluster-state updates, and no reliable write coordination.
  - Some already-running replicas may still answer local reads for a while, but SolrCloud control-plane behavior is degraded and should be treated as a write outage.
- **Must ZK be ready before Solr starts?** Yes.
  - Solr startup should wait for **actual ZooKeeper quorum**, not just running containers.
  - The current compose file does not enforce this.
  - The correct Compose pattern is a ZooKeeper health check plus `depends_on: condition: service_healthy`.
- **Current startup sequencing is stricter than necessary:** `solr2` depends on `solr`, and `solr3` depends on `solr2`. SolrCloud itself does not require serial Solr node startup after ZooKeeper is healthy; this only stretches recovery time.
- **Docker entrypoint nuance:** if Brett wants to rely on `/docker-entrypoint-initdb.d` bootstrap scripts, do **not** assume a generic `solr start -f` invocation will run them. The Solr Docker docs explicitly distinguish `solr-foreground` / default entrypoint behavior from generic `solr ...` commands.
- **Useful checks during restart events:**
  ```bash
  curl -s 'http://localhost:8983/solr/admin/collections?action=CLUSTERSTATUS&wt=json'
  curl -fsS 'http://localhost:8983/solr/admin/info/system' >/dev/null
  curl -fsS 'http://localhost:8983/solr/books/admin/ping?distrib=true' >/dev/null
  ```

### Failure Recovery
- **Fast triage checklist:**
  1. Check ZooKeeper quorum first.
  2. Check `CLUSTERSTATUS` for shard health and missing replicas.
  3. Check `books/admin/ping?distrib=true` for end-user query readiness.
  4. Only then decide between restart, `REQUESTRECOVERY`, `ADDREPLICA`, restore, or full reindex.
- **ZooKeeper health commands for the current setup:**
  ```bash
  docker compose exec zoo1 sh -lc 'printf ruok | nc -w 2 localhost 2181'
  docker compose exec zoo1 sh -lc 'printf mntr | nc -w 2 localhost 2181'
  docker compose exec zoo1 sh -lc 'printf conf | nc -w 2 localhost 2181'
  ```
  - Expected `ruok` output: `imok`
  - Current whitelist is `mntr,conf,ruok`, so `stat` is **not** available unless Brett explicitly adds it.
- **Solr node crash: automatic recovery path**
  - If another good replica exists for every affected shard, SolrCloud handles failover automatically.
  - Best action is usually: restart the node, let it recover, and verify `CLUSTERSTATUS` before touching replicas.
- **Manual recovery when a replica is stuck:**
  - Use `REQUESTRECOVERY` when the replica still exists but did not self-heal after a node/network event.
  - Do **not** use it when the disk/volume is gone; in that case recreate the replica instead.
  - Example:
    ```bash
    curl 'http://localhost:8983/solr/admin/collections?action=REQUESTRECOVERY&collection=books&shard=shard1&replica=<core_node_name>'
    ```
  - Find the real replica name from `CLUSTERSTATUS` first.
- **When to recreate instead of recover:**
  - Volume loss
  - Known corrupt index on one replica
  - Replica permanently loops in recovery
  - Node was rebuilt from scratch
  - In these cases, remove the broken replica and add a fresh one from a healthy leader.
- **Example replica rebuild flow:**
  ```bash
  curl -X DELETE 'http://localhost:8983/api/collections/books/shards/shard1/replicas/<core_node_name>'
  curl -X POST 'http://localhost:8983/api/collections/books/shards/shard1/replicas' \
    -H 'Content-Type: application/json' \
    -d '{"node":"solr2:8983_solr","type":"nrt","waitForFinalState":true}'
  ```
- **ZooKeeper node loss in a 3-node ensemble:**
  - Safe threshold: lose **1** node.
  - Unsafe threshold: lose **2** nodes (no quorum).
  - Replacing a single failed ZooKeeper node is **not** an ensemble reinitialization event. Bring back a node with the same identity and let it sync from the leader.
- **Data corruption recovery guidance:**
  - Symptoms: shard health stays `RED`/`ORANGE`, repeated recovery loops, ping failures, corrupt-index errors in Solr logs, or replicas that never go `active`.
  - If another healthy replica exists: delete the corrupt replica and recreate it.
  - If no healthy replica exists: restore from backup or reindex from `/home/jmservera/booklibrary`.
- **Configset recovery:**
  - If ZooKeeper is intact, update the configset in ZK and reload the collection.
  - If ZooKeeper was lost, re-upload the configset from `./solr/books`, reapply the overlay if needed, and recreate collections.
  - Practical bootstrap flow from the repo root:
    ```bash
    docker compose cp ./solr/books solr:/tmp/books
    docker compose exec solr solr zk upconfig \
      -zkhost zoo1:2181,zoo2:2181,zoo3:2181 \
      -n books \
      -d /tmp/books
    curl 'http://localhost:8983/solr/admin/collections?action=RELOAD&name=books'
    ```
  - `solr/add-conf-overlay.sh` exists to reapply the `/update/extract` request handler and `initParams` if the runtime overlay was lost.
- **Collection bootstrap if metadata was lost:**
  ```bash
  curl 'http://localhost:8983/solr/admin/collections?action=CREATE&name=books&numShards=1&replicationFactor=3&collection.configName=books'
  ```
  Adjust shard/replica counts if the topology changes.
- **Index recovery strategy:**
  - **Best case:** recover/rebuild missing replicas from healthy leaders.
  - **If backups exist:** use `BACKUP`/`RESTORE`.
  - **If backups do not exist:** reindex from the mounted book library.
  - Current compose warning: Solr backup repositories are not actually usable yet because Solr nodes do not mount a shared backup path.
- **How Solr backup should look once Brett wires it up:**
  ```bash
  curl 'http://localhost:8983/solr/admin/collections?action=BACKUP&collection=books&name=books-2026-03-14&repository=local_repo&location=/backup&async=books-backup-001'
  curl 'http://localhost:8983/solr/admin/collections?action=REQUESTSTATUS&requestid=books-backup-001'
  ```
  This requires `/backup` to exist at the same path on all Solr nodes.
- **Reindex path for aithena:** if all shard data is gone, the clean operational fallback is to recreate the `books` collection and replay indexing from `/home/jmservera/booklibrary` through `document-lister` + `document-indexer`.
- **Split-brain / network partitions:**
  - ZooKeeper prevents split-brain by allowing only the **majority partition** to keep quorum.
  - Minority-side sessions eventually expire; their ephemeral znodes disappear and Solr nodes fall out of `live_nodes`.
  - When connectivity returns, replicas recover from the majority side.
- **Emergency-only command:** `FORCELEADER`
  - Use only for a truly leaderless shard after verifying the most up-to-date surviving replica.
  - It is a last resort because it can discard updates.
- **Recommended full cluster recovery order after catastrophic control-plane loss:**
  1. Stop indexers/writers.
  2. Restore or rebuild ZooKeeper quorum first.
  3. Re-upload configsets and `security.json`.
  4. Recreate collections.
  5. Restore backups or reindex.
  6. Reload collection, then restart dependent services.

### Docker Compose Best Practices
- **Health checks Brett should add:**
  - Solr node health:
    ```yaml
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:8983/solr/admin/info/system >/dev/null"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 40s
    ```
  - Collection readiness (only after `books` exists):
    ```yaml
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:8983/solr/books/admin/ping?distrib=true | grep -q OK"]
    ```
  - ZooKeeper health:
    ```yaml
    healthcheck:
      test: ["CMD-SHELL", "printf ruok | nc -w 2 localhost 2181 | grep imok"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 20s
    ```
- **Use `depends_on` long syntax with health conditions:**
  - Compose only waits for readiness when `condition: service_healthy` is used.
  - Brett should use this for Solr ← ZooKeeper and for app services that depend on Solr.
  - `restart: true` under dependency entries is also useful when explicit Compose restarts should cascade to dependent services.
- **Restart policy guidance for stateful services:**
  - **`unless-stopped`** is the right default for Solr and ZooKeeper.
  - **`on-failure`** is fine for batch workers, but not ideal for cluster control-plane services that must come back after host reboot or daemon restart.
  - **`always`** behaves like `unless-stopped` except it ignores a previous manual stop after daemon restart; it is usually less operator-friendly.
- **Resource limits matter:**
  - Solr and ZooKeeper are JVM services; heap must be explicitly sized below the container memory limit.
  - Current compose does not set `SOLR_HEAP`, ZooKeeper heap, or memory limits, so OOM-kill risk is real under indexing load.
  - Operational rule: never let Docker memory limit sit near JVM `-Xmx`; leave headroom for off-heap/native memory.
- **Graceful shutdown:**
  - Add `stop_grace_period: 60s` (or longer for large indexes) to Solr and ZooKeeper.
  - Let Docker send SIGTERM first; avoid hard kills for routine maintenance.
  - This reduces the chance of partial flushes, long recoveries, and noisy leader churn.
- **Logging:**
  - Cap Docker logs to avoid disk exhaustion.
  - If Solr logs are important, persist `/var/solr`, not only `/var/solr/data`.
  - Current ZooKeeper `/logs` mounts are a good start.
- **Network isolation:**
  - Put `zoo*` and `solr*` on an internal network.
  - Only expose what operators or external services truly need.
  - In this repo, `2182`, `2183`, `8984`, and `8985` do not need host exposure for normal intra-compose traffic.
  - Fix the current `8080` collision and avoid exposing ZooKeeper AdminServer unless explicitly needed.
- **Shared backup path:**
  - Solr local filesystem backups require a path mounted at the **same location on all Solr nodes**.
  - The current compose file does not satisfy this yet.
- **Config bootstrap pattern:**
  - For fully automated cluster creation, prefer an init/bootstrap step that waits for ZooKeeper health, uploads the configset, creates `books`, and only then marks the stack ready.
  - Do not rely on bare container start order for this.

### ZooKeeper Operations
- **Current ensemble wiring is correct in principle:**
  - `ZOO_MY_ID` is set per node.
  - `ZOO_SERVERS` declares all three peers.
  - 4-letter-word whitelist is set to `mntr,conf,ruok`.
- **Quorum math for this repo:**
  - 3 ZooKeeper nodes tolerate **1** failure.
  - 2 failures = **no quorum**.
  - This is why all rolling maintenance on ZooKeeper must be one node at a time.
- **`myid`, `zoo.cfg`, and image behavior:**
  - In raw ZooKeeper installs, `myid` lives under the data directory and must match the server ID in `zoo.cfg`.
  - In this compose stack, the official image generates that behavior from `ZOO_MY_ID` and `ZOO_SERVERS`.
- **Data directory vs transaction log directory:**
  - `dataDir` stores snapshots and persistent ensemble state.
  - `dataLogDir` stores transaction logs.
  - Keeping them on separate storage reduces fsync contention and improves stability.
  - Current compose already mirrors this with separate `/data` and `/datalog` mounts.
- **Health / observability commands Brett can rely on:**
  ```bash
  docker compose exec zoo1 sh -lc 'printf ruok | nc -w 2 localhost 2181'
  docker compose exec zoo1 sh -lc 'printf mntr | nc -w 2 localhost 2181'
  curl -s http://localhost:8983/solr/admin/collections?action=CLUSTERSTATUS&wt=json
  ```
- **AdminServer nuance:**
  - ZooKeeper 3.9 images expose an HTTP AdminServer (default port 8080).
  - In this repo, `zoo1` publishes that port, but it conflicts with `solr-search`.
  - Unless Brett explicitly needs it, keep AdminServer internal or move it off the shared host port.
- **Session timeout impact on Solr:**
  - Solr defaults matter here: `solr.cloud.wait.for.zk.seconds` controls how long startup waits for ZooKeeper, and `solr.zookeeper.client.timeout` / `zkClientTimeout` controls how long Solr tolerates disconnection.
  - If ZooKeeper is unreachable beyond the session/client timeout, Solr nodes lose their ZooKeeper sessions, fall out of `live_nodes`, and leader election/recovery begins.
  - Too-small timeouts cause false failovers during brief network jitter; too-large timeouts delay real failover.
- **4LW whitelist nuance in the current compose file:**
  - `ruok`, `mntr`, and `conf` are allowed.
  - `stat` is not currently allowed.
  - If Brett wants `stat`-based health checks, add it deliberately to the whitelist.
- **Autopurge / disk hygiene:**
  - ZooKeeper snapshots and transaction logs grow forever unless cleaned.
  - Official guidance is to set `autopurge.snapRetainCount` and `autopurge.purgeInterval`.
  - Current compose does not configure this, so disk growth should be assumed until Brett adds it.
- **When the ensemble needs reinitialization:**
  - Brand-new cluster build.
  - Total loss of all ZooKeeper data directories.
  - Intentional full control-plane reset.
  - A single failed ZooKeeper node in an otherwise healthy ensemble is **not** a reinit scenario.
- **Safe rule for Brett:**
  - Never wipe ZooKeeper `/data` or `/datalog` casually.
  - If one node is bad, replace one node.
  - If the ensemble is truly lost, stop Solr first, rebuild ZooKeeper cleanly, then repopulate configsets/security/collections in that order.

### References Brett should trust first
- Apache Solr Reference Guide: Docker, SolrCloud recovery, shard/replica management, ping, collections API, configsets, authn/authz.
- Apache ZooKeeper docs: ensemble configuration, admin guide, programmer guide.
- Docker Compose docs: `depends_on`, `service_healthy`, restart semantics, and service shutdown ordering.

## 2026-03-14 — nginx admin ingress
- Moved the repo toward a repo-managed nginx entrypoint instead of an external `/etc/nginx/conf.d` bind volume so infra URLs are defined in source control.
- Added an `aithena-ui` container so nginx can serve the React app at `/`, plus a static `/admin/` landing page for operators.
- Exposed Solr Admin, RabbitMQ Management, Streamlit Admin, and Redis Commander under `/admin/solr/`, `/admin/rabbitmq/`, `/admin/streamlit/`, and `/admin/redis/` respectively.
- RabbitMQ now uses the management image with `management.path_prefix=/admin/rabbitmq`; Streamlit uses `--server.baseUrlPath=/admin/streamlit`; Redis Commander uses `URL_PREFIX=/admin/redis`.
- Validation: `docker compose config --quiet`, `npm ci && npm run build` in `aithena-ui/`, `uv run python -m compileall src` in `admin/`, and nginx syntax tests with `docker run ... nginx -t` all succeeded. The `streamlit-admin` image build is still blocked in this environment by an external Docker Hub fetch failure for `python:3.11-slim`, so runtime validation stopped at app-level checks plus config syntax.

## 2026-03-14 — Reskill session: current infrastructure snapshot

### Service Topology & Status
- **9 services built from source:** `aithena-ui`, `admin` (Streamlit), `document-lister`, `document-indexer`, `solr-search`, `embeddings-server`, `redis-commander` (pulled)
- **3-node SolrCloud cluster:** `solr` (8983), `solr2` (8984), `solr3` (8985), all healthy ✓. Collection `books` with 3x replication factor.
- **3-node ZooKeeper ensemble:** `zoo1` (2181, AdminServer 8080), `zoo2` (2182), `zoo3` (2183). All have ruok/mntr/conf 4LW enabled, separate `/data` and `/datalog` volumes.
- **Redis:** port 6379, health check ✓, `on-failure` restart.
- **RabbitMQ:** port 5672 (AMQP), 15672 (management), health check ✓, `on-failure` restart. **Known issue #166:** Khepri timeout on first boot cascades to all dependent services (document-lister, document-indexer, solr-search, admin).
- **nginx:** 80/443, depends on all admin UIs but no health check on them. Reverse-proxy architecture routes `/admin/solr/`, `/admin/rabbitmq/`, `/admin/streamlit/`, `/admin/redis/` to their respective containers.
- **certbot:** automated TLS renewal, `unless-stopped` restart.

### CI/CD & Deployment
- **GitHub Actions workflows:**
  - `ci.yml` — Python unit tests for `document-indexer` (pytest with coverage) and `solr-search` (unit + integration tests), Python linting via ruff (continue-on-error).
  - `lint-frontend.yml` — Frontend linting.
  - `release.yml` — Release workflow (uses uv for Python dependencies).
  - `squad-*.yml` workflows for triage, assignment, heartbeat.
- **Build automation:** `buildall.sh` runs `uv sync` in each uv-managed Python service (`admin`, `document-indexer`, `document-lister`, `solr-search`) then does `docker compose up --build -d`. Skips `embeddings-server` until it gains a `pyproject.toml`.
- **uv migration:** all 4 production Python services now use uv + `pyproject.toml` + `uv.lock`. `embeddings-server` still has raw pip requirements.

### Known Infrastructure Bugs
1. **#166 — RabbitMQ Khepri timeout on cold start:** `timeout_waiting_for_khepri_projections` after 10 retries × 30s. Second `docker compose up` succeeds. Root cause: Khepri (RabbitMQ 4.x metadata store) projection registration race condition or stale state in docker volume. Suggested fixes: (a) increase health check retries + start_period, (b) clear `rabbitmq-data` volume, (c) pin RabbitMQ version, (d) set memory watermark env var, (e) investigate RabbitMQ GitHub for known Khepri bug.
2. **#167 — Document pipeline stall:** new PDFs not detected or indexed after being added to `/home/jmservera/booklibrary` (mounted as `/data/documents`). Likely cascaded from #166 (RabbitMQ unhealthy → services start without queue) + `depends_on: condition: service_started` doesn't wait for health. Related issues: (a) `depends_on` uses `service_started`, not `service_healthy` for RabbitMQ, (b) no Redis or RabbitMQ connection retry logic in services, (c) volume mount may be inaccessible during startup race.

### Volume & Persistence Strategy
- **All volumes are bind-backed local drivers**, pointing to `/source/volumes/...` and `/home/jmservera/booklibrary`.
- **Solr:** 3 separate data volumes (`solr-data`, `solr-data2`, `solr-data3`) → `/var/solr/data` on each node. Not persisting full `/var/solr`, so logs are ephemeral.
- **ZooKeeper:** per-node split of `/data`, `/datalog`, `/logs` on separate volumes. Good practice.
- **Redis:** single `redis-data` volume.
- **RabbitMQ:** single `rabbitmq-data` volume (the Khepri issue may be volume state corruption).
- **Certbot:** two volumes for conf and challenge responses.
- **Application data:** single shared `document-data` volume mount at `/data/documents` (read-only for Solr/apps, writable from host).

### Health Checks & Dependencies
- **Redis:** has health check (`redis-cli ping`, 5s interval, 15s timeout, 1 retry) ✓.
- **RabbitMQ:** has health check (rabbitmqctl ping, 5s interval, 15s timeout, 1 retry), **too aggressive for Khepri cold start** ✗.
- **Solr & ZooKeeper:** **no health checks** ✗. This violates the solrcloud-docker-operations skill. Missing checks are critical because compose uses `depends_on: service_started`, which doesn't wait for readiness.
- **Application services:** use `depends_on: service_started` for RabbitMQ/Redis/Solr. Without health checks on those infra services, apps start before they're ready.
- **nginx:** depends on all admin UIs without health checks on them.

### Docker Compose Gaps vs. Skill Recommendations
- ❌ No health checks for Solr nodes (should be `curl -fsS http://localhost:8983/solr/admin/info/system`).
- ❌ No health checks for ZooKeeper (should be `printf ruok | nc -w 2 localhost 2181 | grep imok`).
- ❌ `depends_on` uses `condition: service_started` instead of `condition: service_healthy` for critical infra (RabbitMQ, Redis, Solr).
- ❌ ZooKeeper nodes have **no restart policy**; others have `on-failure` or `unless-stopped`. Should be `unless-stopped` for ZooKeeper.
- ❌ No `stop_grace_period` for Solr/ZooKeeper; hard kills may cause long recoveries.
- ❌ No `SOLR_HEAP` or memory limits set; OOM-kill risk during indexing.
- ❌ No log caps on Docker logs; unbounded growth risk.
- ❌ ZooKeeper AdminServer port 8080 collides with `solr-search` port 8080 on host (though Docker routing works, it's confusing).
- ❌ Solr node volumes mount `/var/solr/data` only, not full `/var/solr`; persistent logs unavailable for troubleshooting.
- ❌ `/backup` is configured in `solr/add-conf-overlay.sh` but **not mounted** in Solr containers; backups cannot actually be persisted.
- ✓ Solr/ZooKeeper `depends_on` ordering is stricter than necessary but not harmful (serial Solr startup).
- ✓ Current ZooKeeper and Solr image versions (zookeeper:3.9, solr:9.7) are reasonable.

### nginx Reverse-Proxy Ingress
- **Routes defined in `nginx/default.conf`:** static admin landing page at `/admin/`, proxies to Solr Admin UI (`/admin/solr/`), RabbitMQ Management (`/admin/rabbitmq/`), Streamlit (`/admin/streamlit/`), Redis Commander (`/admin/redis/`), React UI (`/`), API endpoints (`/v1/` and `/documents/` → solr-search:8080).
- **Current reverse-proxy patterns:** 
  - `/admin/solr/`: uses `X-Forwarded-Prefix` + path rewrite + sub_filter for CSS/JS URLs ✓.
  - `/admin/rabbitmq/`: WebSocket upgrade support ✓.
  - `/admin/streamlit/`: WebSocket upgrade + proxy buffering off + 24h timeout ✓.
  - `/admin/redis/`: WebSocket upgrade ✓.
  - `/v1/` and `/documents/`: direct API proxies to solr-search ✓.
  - `/`: catch-all routes to aithena-ui React app ✓.
- **No HTTPS or auth enforcement** (cert setup for ACME but HTTP-only in current config).

### RabbitMQ Configuration
- **config file:** `/rabbitmq/rabbitmq.conf` sets `management.path_prefix=/admin/rabbitmq` for upstream compatibility with nginx reverse proxy.
- **env var:** `RABBITMQ_SERVER_ADDITIONAL_ERL_ARGS=-rabbit consumer_timeout 3600000000` (sets 1-hour consumer timeout for long-running indexing jobs).
- **version:** floating tag `rabbitmq:3-management` (likely 4.x with Khepri). Should be pinned to avoid surprise Khepri bugs.

### Recommendations for Next Session (Priority Order)
1. **Fix #166 (RabbitMQ cold-start):** Increase health check retries/start_period, optionally pin RabbitMQ version to known-good 3.13 or 4.0.
2. **Add SolrCloud health checks** per skill: Solr + ZooKeeper readiness probes, switch `depends_on` to `service_healthy`.
3. **Fix #167 (document pipeline stall):** After fixing RabbitMQ, add connection retry logic and service startup ordering fixes.
4. **Harden ZooKeeper:** add restart policy `unless-stopped`, consider adding autopurge config.
5. **Fix port collision:** move ZooKeeper AdminServer to 18080 or disable it.
6. **Mount Solr backup path:** `/backup` on all Solr nodes to enable filesystem backups.
7. **Add resource limits:** `SOLR_HEAP=1g` + memory limits, log caps for all services.
8. **Add graceful shutdown:** `stop_grace_period: 60s` for Solr/ZooKeeper.
9. **Expand Solr volume mounts:** `/var/solr` instead of just `/var/solr/data` for persistent logs.
