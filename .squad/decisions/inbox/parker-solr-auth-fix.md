# Decision: Solr auth bootstrap requires explicit role assignment

**Author:** Parker (Backend Dev)
**Date:** 2026
**Status:** Implemented (#1287)
**Context:** solr-init entrypoint in docker-compose.yml and docker-compose.prod.yml

## Problem

`solr auth enable` creates a BasicAuth user but does not assign the admin role to it. All RBAC-gated operations (collection-admin-edit, etc.) fail with "does not have the right role." Additionally, the readonly user was assigned a `search` role that doesn't exist in security.json — the correct role name is `readonly`.

## Decision

1. After `solr auth enable`, explicitly call `set-user-role` to assign `["admin"]` to the admin user.
2. Assign `["readonly"]` (not `["search"]`) to the readonly user.
3. Add Solr credentials to the installer's credential generation pipeline so production deployments don't use hardcoded default passwords.

## Impact

- All team members modifying solr-init entrypoints must ensure role assignments match the role names in security.json permissions.
- The installer now generates 4 additional env vars (SOLR_ADMIN_USER, SOLR_ADMIN_PASS, SOLR_READONLY_USER, SOLR_READONLY_PASS). Existing .env files with insecure defaults will be rotated on next installer run.
