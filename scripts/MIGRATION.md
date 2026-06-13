# Legacy scripts migration

The root `scripts/` directory is now **legacy**. Until `./manage.sh` lands via PR #1758, prefer the documented `docker compose ...` entrypoints and runbooks below instead of calling the old helper scripts directly.

- **Current operator entrypoints:** `docker compose ...` commands from `README.md`
- **Current validation entrypoint:** `.squad/scripts/verify.sh`
- **Future operator CLI:** `./manage.sh` (PR #1758, pending merge)
- **Removal timeline:** legacy root-level scripts are deprecated now and are candidates for removal in the **next major version**.

## Mapping table

| Legacy script | Replacement | Notes |
|---|---|---|
| `scripts/backup.sh` | Manual process — see `docs/admin/disaster-recovery-runbook.md` | No consolidated CLI replacement exists for backup orchestration. |
| `scripts/backup-critical.sh` | Manual process — see `docs/admin/disaster-recovery-runbook.md` | Tier-1 BCDR helper; keep only for documented recovery workflows during the deprecation window. |
| `scripts/backup-critical-test.sh` | `.squad/scripts/verify.sh` | Use the standard repo verification entrypoint for routine validation until `./manage.sh test` lands in PR #1758; no dedicated replacement exists for this one-off backup harness. |
| `scripts/backup-high.sh` | Manual process — see `docs/admin/disaster-recovery-runbook.md` | Tier-2 BCDR helper. |
| `scripts/backup-medium.sh` | Manual process — see `docs/admin/disaster-recovery-runbook.md` | Tier-3 BCDR helper. |
| `scripts/cleanup-ghcr.sh` | Manual process — see `docs/deployment/release-checklist.md` | Keep using `gh`/package-admin workflows as documented; no consolidated CLI equivalent exists. |
| `scripts/create-release-tag.sh` | Manual process — use the release steps in `README.md` | Prefer the documented `git tag` / `git push origin vX.Y.Z` release flow. |
| `scripts/export-images.sh` | Manual process — see `docs/deployment/offline-deployment.md` | Offline bundle creation remains a documented release/deployment task, not a routine CLI concern. |
| `scripts/index_test_corpus.py` | Manual process — see `scripts/benchmark/README.md` | Benchmark/indexing workflow remains documented for specialized validation. |
| `scripts/init-volumes.sh` | No replacement needed | Current Compose files use Docker named volumes, so routine setup no longer requires pre-creating host volume directories. |
| `scripts/restore.sh` | Manual process — see `docs/admin/disaster-recovery-runbook.md` | No consolidated CLI replacement exists for restore orchestration. |
| `scripts/restore-critical.sh` | Manual process — see `docs/admin/disaster-recovery-runbook.md` | Tier-1 restore helper. |
| `scripts/restore-high.sh` | Manual process — see `docs/admin/disaster-recovery-runbook.md` | Tier-2 restore helper. |
| `scripts/restore-medium.sh` | Manual process — see `docs/admin/disaster-recovery-runbook.md` | Tier-3 restore helper. |
| `scripts/solr-export.sh` | Manual process — see `docs/migration/solr-9-to-10.md` | Specialized Solr migration/export workflow. |
| `scripts/solr-import.sh` | Manual process — see `docs/migration/solr-9-to-10.md` | Specialized Solr migration/import workflow. |
| `scripts/verify-backup.sh` | Manual process — see `docs/admin/disaster-recovery-runbook.md` | Backup integrity verification is still documented, but not part of the routine compose/verify entrypoints. |
| `scripts/verify_collections.py` | `docker compose ps` for routine checks; see `scripts/benchmark/README.md` for deep validation | Use compose status for normal container checks and the benchmark docs for collection-specific verification until `./manage.sh health` lands in PR #1758. |

## Preferred replacements

### Routine stack lifecycle

Use the maintained entrypoints below while PR #1758 is still pending:

```bash
docker compose -f docker-compose.yml -f docker/compose.dev-ports.yml up -d --build
docker compose -f docker-compose.yml -f docker/compose.dev-ports.yml down
docker compose -f docker-compose.yml -f docker/compose.dev-ports.yml build
docker compose -f docker-compose.yml -f docker/compose.dev-ports.yml logs -f nginx
docker compose -f docker-compose.yml -f docker/compose.dev-ports.yml ps
.squad/scripts/verify.sh
```

### Specialized workflows that remain manual during deprecation

Some legacy scripts encapsulate one-off operational flows that do not belong in the new day-2 CLI surface:

- BCDR backup/restore/integrity tasks → `docs/admin/disaster-recovery-runbook.md`
- Offline image export → `docs/deployment/offline-deployment.md`
- Release package cleanup → `docs/deployment/release-checklist.md`
- Solr migration import/export → `docs/migration/solr-9-to-10.md`
- Corpus indexing and collection verification → `scripts/benchmark/README.md`

When updating docs or automation, point new usage at these runbooks or current maintained entrypoints instead of adding fresh dependencies on the legacy scripts. Once PR #1758 merges, `./manage.sh` becomes the preferred day-2 CLI.
