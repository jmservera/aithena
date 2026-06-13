# Brett — History

## Core Context

Brett owns Docker Compose, containers, Solr/SolrCloud, ZooKeeper, nginx, CI/CD release plumbing, backup/restore, and infra validation.

**Standard topology:** multi-service Compose stack with Solr, ZooKeeper, Redis, RabbitMQ, nginx, backend services, and UI. Only nginx should publish host ports in normal prod/CI flows; other services should stay internal unless an explicit dev/test overlay exposes them.

## Key Patterns

- **Use overlays when optional behavior changes mounts, ports, or service wiring.** Profiles are good for disabling services/topologies; overlays are for structural changes such as SSL, GPU, CI ports, or production variants.
- **Bind-mount ownership comes from the host.** Dockerfile `chown` does not fix host-mounted directories; setup scripts must create/chown paths to the service UID/GID.
- **Named volumes avoid many permission failures.** Prefer them for Solr/ZooKeeper/stateful infra when host-path inspection is not required.
- **RabbitMQ credentials are first-boot state.** Changing env vars later does not rewrite existing Mnesia data; clear or migrate state intentionally.
- **Health checks must be shell-aware and startup-tolerant.** Use `CMD-SHELL` when variables need expansion, pad `start_period` in CI, and fail fast when required auth env vars are missing.
- **ZooKeeper quorum is the real HA boundary.** Losing two of three nodes means write outage; back up ZooKeeper state and Solr data separately.
- **Keep ZooKeeper private.** CI and production overlays should preserve internal-only ZK access while still wiring Solr auth/init correctly.
- **nginx is the only public ingress.** `/health` should stay cheap and deterministic; service routes should not surface backend ports directly.
- **Build-time dependency drift needs in-image verification.** If a Dockerfile uses `uv sync --inexact`, add a post-sync import/version check inside the built image so drift fails the build immediately.
- **Validate infra changes locally when feasible.** Docker + Playwright + compose config checks catch most regressions earlier than CI.
- **Review-thread resolution is part of mergeability.** Branch protection cares about resolved threads, not just green checks.

## Operating Notes

- Search capacity shifted materially once page chunking and byte/int8 quantization entered the picture; standalone Solr on 32GB NVMe can be viable for moderate scale, while SolrCloud remains the HA/topology answer.
- Build contexts matter: some services build from repo root, others from `src/{service}`. Keep Dockerfile assumptions aligned with actual Compose context.
- Backup tiers remain useful: auth/secrets first, Solr/ZK next, Redis/RabbitMQ after that.

## Skill References

- `.squad/skills/docker-compose-operations/SKILL.md`
- `.squad/skills/bind-mount-permissions/SKILL.md`
- `.squad/skills/nginx-reverse-proxy/SKILL.md`
- `.squad/skills/solr-operations/SKILL.md`
- `.squad/skills/dependabot-batch-sweep/SKILL.md`
