# Aithena v1.0.0 Release Notes — Source Restructure Complete

_Date:_ 2026-03-16  
_Prepared by:_ Newt (Product Manager)

Aithena **v1.0.0** is the final release for the current operability program. It marks the completion of the repository restructure into `src/`, confirms that local validation and CI/CD path updates were completed after the move, and closes the last release-readiness items needed before the project can advance from `dev` toward a production `main` release.

## Summary of shipped changes

- **Major repository restructure** moved **9 service directories** under `src/`, giving the codebase a cleaner top-level layout and a clearer separation between application code, infrastructure, and documentation (**#222 / PR #287**).
- **Documentation was updated for the new `src/` layout** so contributor instructions, validation commands, and path references now consistently point to `src/...` instead of the old root-level service paths (**#225 / PR #288**).
- **Local build and test validation after the restructure completed successfully**, with the backend and frontend release-gate suites both passing from their new `src/` locations (**#223**).
- **CI/CD validation after the restructure confirmed all 13 GitHub Actions workflows were still correct**, ensuring the path move did not leave stale workflow references behind (**#224**).
- **The integration test workflow received a CI volume fix** using the required tmpfs override, preserving operability for release-critical integration runs after the directory move.
- **v1.0.0 closes the restructure-and-operability milestone**: the source tree has been normalized, documentation has caught up, and release validation evidence is now in place.

## Milestone closure

The following milestone issues are complete in **v1.0.0**:

- **#222** — Move microservices into `src/`
- **#223** — Validate all local builds after restructure
- **#224** — Validate CI/CD pipelines after restructure
- **#225** — Update documentation for new `src/` layout

## Merged pull requests

- **#287** — Move 9 service directories into `src/`
- **#288** — Update documentation for the new `src/` layout

## Breaking changes

**Yes — this release introduces contributor-facing path changes.**

- Source code for the services now lives under `src/` (for example, `src/solr-search`, `src/aithena-ui`, `src/document-indexer`, and related services).
- Local scripts, editor run configurations, validation commands, and workflow `working-directory` references must use the new `src/...` paths.
- The runtime Compose entry points and user-facing URLs remain the same; this release changes repository structure and release readiness, not the product surface.

## Upgrade instructions

For contributors, operators, and release engineers moving to **v1.0.0**:

1. Update to the **v1.0.0** release commit or tag once published.
2. Review any local scripts, CI snippets, shell aliases, or IDE run configurations that referenced service directories at the repository root and change them to `src/...`.
3. Use the release-validated local commands from the new layout:

   ```bash
   cd src/solr-search && uv run pytest -v --tb=short
   cd src/aithena-ui && npm run lint && npm run build && npx vitest run
   AUTH_DB_DIR=/tmp/auth AUTH_DB_PATH=/tmp/auth/users.db AUTH_JWT_SECRET=test \
     docker compose -f docker-compose.yml config --quiet
   ```

4. If you maintain GitHub Actions or local automation around the integration workflow, preserve the tmpfs volume override that was added to keep CI volume mounts valid after the restructure.
5. Re-check the README and release docs when onboarding contributors: the repository root is now primarily infrastructure/documentation, while application services live under `src/`.

## Validation highlights

- **Backend release-gate suite:** `144 passed`
- **Frontend release-gate suite:** `83 passed`
- **Frontend quality gates:** lint ✅, production build ✅, Vitest ✅
- **Compose configuration validation:** `docker compose ... config --quiet` completed successfully with release-gate auth environment variables set
- **Workflow validation evidence:** all **13 GitHub Actions workflows** confirmed correct for the post-restructure layout

## Documentation updated for this release

- `README.md`
- `docs/release-notes-v1.0.0.md`
- `docs/test-report-v1.0.0.md`

Aithena **v1.0.0** is the release that turns the `src/` restructure from a code move into a verified, documented, and operable baseline.