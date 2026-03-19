# Aithena v1.1.0 Release Notes — CI/CD & Documentation

_Date:_ 2026-03-17  
_Prepared by:_ Newt (Product Manager)

Aithena **v1.1.0** is a maintenance release focused on CI/CD infrastructure, logging hardening, and comprehensive v1.x development documentation. This release establishes the operational foundation for sustained development velocity and release automation.

## Summary of shipped changes

- **Updated project documentation** for v1.x development process, including branching strategy, PR workflow, release process overview, and operational runbooks (#298).
- **Fixed stack trace exposure in embeddings-server** by removing verbose exc_info logging that could leak sensitive implementation details (#299).
- **Hardened document-indexer logging** by replacing `logger.exception()` calls with `logger.error()` to prevent uncontrolled exception output (#302).
- **Updated Copilot CLI package references** in release-docs.yml to align with current CLI versions and best practices (#303).
- **Validated release-docs.yml end-to-end** to ensure the workflow executes correctly under real release conditions (#304).
- **Added release milestone labels** for all v1.x milestones to improve issue tracking and visibility (#305).
- **E2E smoke test for release-docs workflow** validates the automated release process (#306).

## Milestone closure

The following milestone issues are complete in **v1.1.0**:

- **#298** — Update project documentation for v1.x development process
- **#299** — Fix embeddings-server exc_info stack trace exposure
- **#302** — Fix document-indexer logging: replace logger.exception with logger.error
- **#303** — Update Copilot CLI package references in release-docs.yml
- **#304** — Fix and validate release-docs.yml end-to-end
- **#305** — Add release milestone labels for v1.x milestones
- **#306** — E2E test: release-docs workflow smoke test

## Merged pull requests

- **#314** — Fix embeddings-server exc_info stack trace exposure
- **#317** — Update v1.x development documentation and release process

## Documentation updates

- **README.md:** Added v1.x Development Process section with branching strategy (squad/ convention), PR workflow, and release process overview
- **README.md:** New Release Process Overview section with preflight checks, documentation requirements, and step-by-step procedures
- **User/Admin Manuals:** Updated feature guide references to align with v1.x documentation structure

## CI/CD improvements

- **release-docs.yml:** Updated to use current Copilot CLI versions and validated against real release workflows
- **Automated milestone labeling:** All v1.x issues now have standardized release-milestone labels for improved tracking
- **E2E release validation:** Smoke test confirms release-docs workflow can execute successfully end-to-end

## Logging hardening

- **embeddings-server:** Removed exc_info parameter from logger calls; exceptions are now logged at error level without verbose tracebacks
- **document-indexer:** Migrated from logger.exception() to logger.error() with explicit exception tracking; improves log cleanliness and security posture

## Upgrade instructions

For contributors and operators moving to **v1.1.0**:

1. Update to the **v1.1.0** release commit or tag once published.
2. No configuration or runtime changes required; this is a maintenance release.
3. Redeploy `embeddings-server` and `document-indexer` for logging hardening.
4. Review the updated v1.x Development Process in README.md for new contribution guidelines.
5. No changes to user-facing behavior or API contracts.

## Validation highlights

- **Logging validation:** embeddings-server and document-indexer output verified for stack trace removal
- **CI/CD validation:** release-docs.yml smoke test passed; automated release workflow is operational
- **Documentation completeness:** v1.x branching, PR, and release processes now fully documented
- **Backend test suite:** All tests passing; no regressions from logging changes

Aithena **v1.1.0** establishes sustainable CI/CD and documentation practices for the v1.x development cycle.
