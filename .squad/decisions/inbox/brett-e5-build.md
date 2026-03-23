# Decision: ZK-Solr SASL Auth Model Change

**Date:** 2026-03-23
**Author:** Brett (Infrastructure Architect)
**Context:** E5 migration stack build verification (branch: squad/e5-migration)

## Problem

The ZooKeeper SASL DIGEST-MD5 authentication introduced in PR #955 is incompatible with Solr 9.7. Specifically:

1. Solr 9.7's bundled ZK client jar does not include `org.apache.zookeeper.server.auth.DigestLoginModule`
2. Solr 9.7's Java Security Manager blocks access to `sun.security.provider` (needed by JAAS)
3. The `requireClientAuthScheme=sasl` ZK setting prevents ALL non-SASL client connections

This means Solr cannot authenticate to ZK via SASL, and the entire SolrCloud cluster fails to start.

## Decision

**Drop `requireClientAuthScheme=sasl` from ZK configuration.** Keep all other security layers:

| Layer | Status | Mechanism |
|-------|--------|-----------|
| ZK quorum auth (inter-node) | ✅ Kept | SASL DIGEST-MD5 via JAAS |
| Solr → ZK znode ACLs | ✅ Kept | `DigestZkCredentialsProvider` / `DigestZkACLProvider` |
| Solr BasicAuth | ✅ Kept | security.json with RBAC |
| ZK client SASL requirement | ❌ Removed | Was `requireClientAuthScheme=sasl` |

## Additional Fixes Applied

1. ZK JAAS file: `chown zookeeper:zookeeper` (was root-owned, unreadable after gosu)
2. Solr JAAS path: `/var/solr/solr-jaas.conf` (was `/opt/solr/server/etc/`, not writable by solr user)
3. Solr Security Manager: `SOLR_SECURITY_MANAGER_ENABLED=false` (required for JAAS loading)
4. `SOLR_OPTS` now includes ZK digest creds directly (not just `SOLR_ZK_CREDS_AND_ACLS` which only works for CLI)

## Risk Assessment

- **Docker network isolation** prevents external ZK access (ports are `expose:` only in production)
- **ZK digest ACLs** still protect znode read/write access
- **Solr BasicAuth** still protects the search API
- The removed SASL requirement was defense-in-depth that was never functional with Solr 9.7

## Files Changed

- `docker-compose.yml` — ZK, Solr, solr-init config
- `docker-compose.prod.yml` — Same changes for production
- `src/zookeeper/entrypoint-sasl.sh` — chown fix
- `src/solr/entrypoint-sasl.sh` — path fix
