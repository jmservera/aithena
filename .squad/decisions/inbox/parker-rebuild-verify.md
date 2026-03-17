# Decision: Solr Host Volume Ownership Must Match Container UID

**Author:** Parker (Backend Dev)
**Date:** 2026-03-17
**Status:** Applied and verified

## Problem

The `solr-init` container repeatedly failed to create the `books` collection with HTTP 400 ("Underlying core creation failed"). The root cause was that host bind-mounted volumes at `/source/volumes/solr-data*` were owned by `root:root`, but Solr containers run as UID 8983. This prevented writing `core.properties` during replica creation.

## Decision

Host-mounted Solr data directories (`/source/volumes/solr-data`, `solr-data2`, `solr-data3`) must be owned by UID 8983:8983 (the `solr` user inside the container).

```bash
sudo chown -R 8983:8983 /source/volumes/solr-data /source/volumes/solr-data2 /source/volumes/solr-data3
```

## Rationale

- The `solr:9.7` Docker image runs as non-root user `solr` (UID 8983)
- Docker bind mounts preserve host ownership — they don't remap UIDs
- Without write access to the data directory, Solr cannot persist core configurations, which causes collection creation to fail silently (400 error with no clear cause)

## Impact

- Fixes collection creation for all SolrCloud nodes
- Must be applied on any fresh deployment or after volume directory recreation
- Consider adding this to the deployment guide or `buildall.sh` setup script

## Prevention

Add a pre-flight check to `buildall.sh` or a setup script that verifies Solr volume ownership before starting the stack. Example:

```bash
for dir in /source/volumes/solr-data /source/volumes/solr-data2 /source/volumes/solr-data3; do
  if [ "$(stat -c '%u' "$dir")" != "8983" ]; then
    echo "Fixing Solr data directory ownership: $dir"
    sudo chown -R 8983:8983 "$dir"
  fi
done
```

## Related

- Companion to the RabbitMQ volume credential mismatch issue (Brett's infrastructure decision)
- Both are "stale volume" problems that surface as cryptic service failures
