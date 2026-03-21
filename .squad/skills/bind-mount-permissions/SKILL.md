---
name: "bind-mount-permissions"
description: "Correctly set host directory ownership for Docker bind-mount volumes to avoid permission failures"
domain: "docker, infrastructure, permissions"
confidence: "high"
source: "earned — recurring production issue across Solr (UID 8983), Python app (UID 1000), Redis, RabbitMQ"
author: "Brett"
created: "2026-07-25"
last_validated: "2026-07-25"
---

## Context

Bind-mount permission mismatches are the **#1 recurring infrastructure issue** in aithena. The problem: Docker bind mounts use the host filesystem's ownership, ignoring any `RUN chown` in the Dockerfile. If the host directory is owned by `root:root` but the container process runs as a non-root user, the process can't write and crashes.

This has caused failures in:
- Solr data volumes (UID 8983)
- Auth DB directory (UID 1000)
- Collections DB directory (UID 1000)
- RabbitMQ Mnesia data (UID 100)

## Pattern: Match Host UID to Container UID

### Step 1: Identify the Container User's UID

| Service | Container User | UID | Volume Path |
|---------|---------------|-----|-------------|
| Solr (solr1/2/3) | `solr` | 8983 | `/var/solr/data` |
| Redis | `redis` | 999 | `/data` |
| RabbitMQ | `rabbitmq` | 100 | `/var/lib/rabbitmq` |
| nginx | `nginx` | 101 | `/etc/nginx/` (read-only) |
| Python services (app) | `app` | 1000 | `/data/auth`, `/data/collections` |

**How to find UID when unknown:**
```bash
docker image inspect <image> | grep -i user
# or
docker run --rm <image> id
```

### Step 2: Set Host Directory Ownership

```bash
# Before docker compose up:
sudo chown -R 8983:8983 ./volumes/solr-data{1,2,3}
sudo chown -R 1000:1000 ./volumes/auth-db ./volumes/collections
sudo chown -R 100:100 ./volumes/rabbitmq-data
```

### Step 3: Verify Before Starting Containers

```bash
ls -lan ./volumes/ | awk '{print $3, $4, $NF}'
# Expected: 8983 8983 solr-data1, 1000 1000 auth-db, etc.
```

## Named Volumes vs Bind Mounts

| | Named Volumes | Bind Mounts |
|---|---|---|
| Ownership | Docker initializes from image layer | Host filesystem ownership |
| `RUN chown` | ✅ Respected | ❌ Ignored |
| Portability | ✅ Works anywhere | ❌ Requires host setup |
| Use case | Stateless data, caches | Persistent data that survives `docker volume rm` |

**Rule:** If you must use bind mounts for persistence, the installer/setup script **must** create directories with correct UIDs.

## Anti-Patterns

- **Don't rely on Dockerfile `RUN chown` for bind-mounted paths** — it only applies to the image layer
- **Don't use `chmod 777`** — it "works" but violates least-privilege and masks real ownership issues
- **Don't forget to re-chown after `rm -rf volumes/`** — recreating directories defaults to the current user's UID
- **Don't assume `docker compose down -v` clears bind-mount dirs** — it only removes named volumes; bind-mount directories persist

## Installer Integration

Any setup script (`installer/setupdev.sh`, `installer/setup.sh`) that creates bind-mount directories must:

```bash
# Create with correct ownership
mkdir -p "$VOLUMES_DIR/solr-data"{1,2,3}
sudo chown -R 8983:8983 "$VOLUMES_DIR/solr-data"{1,2,3}

mkdir -p "$AUTH_DB_DIR"
sudo chown -R 1000:1000 "$AUTH_DB_DIR"
```

## Diagnostic Checklist

When a container crashes with permission errors:
1. Check container logs: `docker compose logs <service> | grep -i "permission\|denied\|unable to open"`
2. Check host directory ownership: `ls -lan <host-path>`
3. Compare UID with container user: `docker inspect <container> --format '{{.Config.User}}'`
4. Fix ownership: `sudo chown -R <uid>:<uid> <host-path>`
5. Restart: `docker compose restart <service>`

## References

- `docker-compose.yml` — volume mount definitions
- `installer/setupdev.sh` — dev environment setup
- Skill `docker-compose-operations` — broader container lifecycle
- Brett's history: Auth DB UID 1000 failure, Solr UID 8983 failure (recurring)
