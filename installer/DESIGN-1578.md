# Installer Wizard Design Stub (#1578)

This PR is a research spike only. See the full proposal in:

- `.squad/decisions/inbox/parker-1578-installer-wizard-design.md`

Open questions for inline review:

1. Which GHCR namespace/image name should host the installer container?
2. What version-locking strategy should the bootstrap script use?
3. How should existing `/source/volumes/*` deployments migrate to Docker-managed volumes?
4. Is the Docker socket mount acceptable for the default installer-container flow?
5. Should SSL certbot bind mounts be migrated with the base 16 compose volumes?
