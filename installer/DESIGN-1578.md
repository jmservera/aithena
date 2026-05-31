# Installer Wizard Design (#1578)

This was a research spike. The architectural proposal — including the open questions resolved by jmservera on 2026-05-31 — lives in:

- `.squad/decisions/inbox/parker-1578-installer-wizard-design.md`

**Resolved decisions (summary, see proposal for details):**

1. **Registry:** `ghcr.io/jmservera/aithena-*` (existing release namespace).
2. **Version-locking:** bootstrap script regenerated each release with the matching versioned installer image tag — no floating `latest`.
3. **Migration:** none — v2.2.0 starts from scratch. Release notes call out the clean-install policy.
4. **Volumes:** not a breaking migration; clean-install policy means there is nothing to migrate.
5. **Docker socket mount:** acceptable for the default flow, documented as a known requirement.
6. **SSL certbot paths:** same clean-install policy.

Next implementation PR: **Phase 1a — convert Redis + RabbitMQ bind mounts to Docker-managed named volumes**.
