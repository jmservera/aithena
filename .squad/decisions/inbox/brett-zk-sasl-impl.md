# Decision: ZooKeeper SASL DIGEST-MD5 Implementation

**Author:** Brett (Infrastructure Architect)
**Date:** 2026-03-22
**Issue:** #904
**Status:** Implemented

## Context

ZooKeeper ensemble was previously unauthenticated — any container on the Docker network could connect and read/write znodes. This is a security hardening requirement for v1.13.0.

## Decision

1. **SASL DIGEST-MD5** chosen over Kerberos — no KDC infrastructure needed, supported natively by ZK 3.9 and Solr 9.7.
2. **Template + entrypoint wrapper pattern** for JAAS files — JAAS doesn't support env vars natively, so entrypoint scripts use `sed` to substitute `${ZK_SASL_USER}` and `${ZK_SASL_PASS}` at startup. This follows the same pattern as RabbitMQ's `init-definitions.sh`.
3. **Shared credentials** between ZK quorum auth and client auth — single `ZK_SASL_USER`/`ZK_SASL_PASS` pair for simplicity. Can be split later if needed.
4. **Dev defaults** follow project convention: `ZK_SASL_USER=solr`, `ZK_SASL_PASS=SolrZkPass_dev`. Production must override via `.env`.
5. **DigestZkCredentialsProvider + DigestZkACLProvider** on Solr side to enforce znode ACLs matching the SASL user.
6. **Explicit `command: []`** on ZK services to prevent the entrypoint override from losing the default command.
7. **Explicit `command: ["solr-foreground"]`** on Solr services for the same reason.

## Affected Services

- zoo1, zoo2, zoo3 — JAAS template mount, entrypoint wrapper, `ZOO_CFG_EXTRA` quorum SASL props, `SERVER_JVMFLAGS`
- solr, solr2, solr3 — JAAS template mount, entrypoint wrapper, `SOLR_ZK_CREDS_AND_ACLS`, `SOLR_OPTS`
- solr-init — inline JAAS generation + `SOLR_ZK_CREDS_AND_ACLS`, `SOLR_OPTS`
- Both `docker-compose.yml` and `docker-compose.prod.yml`

## Risks

- **Existing ZK data:** If upgrading an existing deployment, ZK znodes created before SASL won't have ACLs. A migration step may be needed to re-ACL existing znodes.
- **Credential rotation:** Requires restarting all ZK and Solr containers simultaneously. Document in operations runbook.

## Team Impact

- Parker/Dallas: No app code changes needed — Solr HTTP API is unchanged.
- Ash: Solr query logic unaffected — SASL is transport-level between Solr ↔ ZK only.
- Lambert: No new test requirements — SASL is infra-level, not testable without Docker daemon.
