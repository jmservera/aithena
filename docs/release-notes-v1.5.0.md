# Aithena v1.5.0 Release Notes — Production Deployment & Infrastructure

_Date:_ 2026-03-17  
_Prepared by:_ Newt (Product Manager)

Aithena **v1.5.0** is a major production deployment and infrastructure release. It establishes the complete tooling required for production-grade deployments: Docker image publishing to GHCR (GitHub Container Registry), production-ready Docker Compose configuration with pre-built images, automated installation scripts, comprehensive smoke test suite for validating deployments, production environment configuration, and detailed deployment/rollback documentation. This release transforms Aithena from a development-focused project into a production-ready platform with industry-standard deployment practices.

## Summary of shipped changes

### Production Infrastructure & Image Management (PI-1 through PI-4)

- **Docker image tagging and versioning strategy** defines semantic versioning tags for GHCR, aligning with release versions and build metadata (#358).
- **GitHub Actions CI/CD workflow** automates building and pushing production-grade Docker images to GHCR with multi-architecture support and security scanning (#359).
- **Production docker-compose.yml** uses pre-built GHCR images instead of local builds, enabling reproducible production deployments without source code (#360).
- **Production install script** automates initial deployment configuration, secret management, volume setup, and runtime environment provisioning (#361).

### Production Configuration & Artifacts (PI-5 through PI-7)

- **Production environment variables and secrets configuration** establishes secure defaults, credential management patterns, and environment-specific overrides for production deployments (#362).
- **GitHub Release package** bundles production artifacts (compose file, install script, documentation, checksums) for distribution and version control (#363).
- **Production deployment and rollback procedures documentation** provides operators with step-by-step deployment, health validation, and rollback workflows (#364).

### Quality Assurance & Validation (PI-8 through PI-9)

- **Smoke test suite** validates production deployments end-to-end: container startup, health checks, service connectivity, search functionality, and data persistence (#365).
- **Production nginx image and build process** ensures the UI build process generates optimized production artifacts for the nginx reverse proxy (#366).

### Operational Documentation (PI-10 through PI-12)

- **GHCR authentication documentation** guides developers and operators through credential setup, image pulling, and registry access for private deployments (#367).
- **Production volume mounts and data persistence validation** ensures all persistent data (Solr indexes, Redis state, RabbitMQ queues, application config) survives container restarts (#368).
- **Release checklist and automation integration** documents pre-release validation steps and integrates release gates with CI/CD workflows (#369).

## Milestone closure

The following milestone issues are complete in **v1.5.0**:

- **#358** — PI-1: Define image tagging and versioning strategy for GHCR
- **#359** — PI-2: Create GitHub Actions workflow for building and pushing Docker images
- **#360** — PI-3: Create production docker-compose.yml with pre-built images
- **#361** — PI-4: Create production install script
- **#362** — PI-5: Configure production environment variables and secrets
- **#363** — PI-6: Create GitHub Release package with production artifacts
- **#364** — PI-7: Document production deployment and rollback procedures
- **#365** — PI-8: Create smoke test suite for production deployments
- **#366** — PI-9: Update UI build process for production nginx image
- **#367** — PI-10: Add GHCR authentication documentation for developers
- **#368** — PI-11: Validate production volume mounts and data persistence
- **#369** — PI-12: Create release checklist and automation integration

## Merged pull requests

- **#425** — Image tagging and versioning strategy definition
- **#426** — GitHub Actions Docker image build and push workflow
- **#427** — Production docker-compose.yml with GHCR image references
- **#428** — Production install script with configuration automation
- **#429** — Production environment configuration and secrets management
- **#430** — GitHub Release artifact bundling and checksums
- **#431** — Production deployment and rollback procedures documentation
- **#432** — Smoke test suite for deployment validation
- **#433** — Production nginx image and UI build optimization
- **#434** — GHCR authentication and registry access documentation
- **#435** — Production volume mount and data persistence validation
- **#436** — Release checklist automation and CI/CD integration

## Breaking changes

**Installation and deployment workflow:**

- New deployments should use the production install script (`installer/setup.py`) to automatically configure environment variables, secrets, and storage. Manual .env setup is deprecated but still supported for development.
- Production deployments now use pre-built GHCR images instead of local Docker builds. The `docker-compose.yml` references versioned images from `ghcr.io/jmservera/aithena-*:v1.5.0`. Administrators must authenticate with GHCR to pull images from private repositories.
- The production docker-compose.yml no longer includes the `docker-compose.override.yml` pattern. Use explicit `-f` flags to select dev or production configuration.

**Volume and data persistence:**

- All persistent data paths must be correctly mounted and validated before deployment. The smoke test suite now validates volume mounts and ensures data survives container restarts. Misconfigured volumes will cause smoke tests to fail.

**Release artifacts:**

- GitHub Releases now include production deployment artifacts (docker-compose.yml, install script, smoke tests). Operators should download these from the release page rather than cloning the repository for production deployments.

## User-facing improvements

- **Zero-downtime install:** Production install script automates configuration with sensible defaults, enabling new deployments in minutes without manual setup.
- **Deployment validation:** Smoke test suite provides operators with automated validation that all services are healthy and interconnected after deployment.
- **Version traceability:** All Docker images include version metadata in OCI labels, enabling operators to verify image provenance and track deployments.

## Operator-facing improvements

- **Production composition:** Pre-built GHCR images eliminate the need for source code on production servers. Deployments are lightweight and fast.
- **Automated configuration:** Install script removes manual .env setup, secret generation, and volume configuration. Environment-specific overrides are centralized.
- **Comprehensive deployment guide:** Step-by-step procedures with health checks, service connectivity validation, and rollback workflows eliminate guesswork.
- **Smoke test validation:** After deployment, run smoke tests to automatically verify all services, data persistence, and search functionality are operational.
- **GHCR authentication:** Centralized documentation for credentials, image pulling, and registry access eliminates trial-and-error for operators.

## Infrastructure improvements

- **Docker image distribution:** Docker images published to GHCR with semantic version tags, enabling version control, supply-chain security scanning, and rollback to previous releases.
- **CI/CD automation:** GitHub Actions workflow builds images on every release, ensuring images are fresh and consistent with source code.
- **Data persistence validation:** Production docker-compose.yml includes health checks and volume mount validation to ensure persistent data survives restarts.
- **Security scanning:** GHCR images include SBOM (Software Bill of Materials) and container security scanning results.

## Security improvements

- **Image signing and provenance:** GitHub Actions workflow produces signed image attestations for supply-chain security (SLSA framework).
- **Environment variable hardening:** Production configuration supports secrets stored in external vaults; .env files can reference environment variables instead of hardcoding secrets.
- **GHCR authentication:** Private image repositories support RBAC (role-based access control) for image pulling. Operators authenticate with personal access tokens (PATs).
- **Smoke test security validation:** Smoke tests verify no default credentials remain, no debug endpoints are exposed, and all services require authentication where appropriate.

## Upgrade instructions

For operators moving to **v1.5.0**:

1. Download production artifacts from the **v1.5.0** GitHub Release page (docker-compose.yml, install script, smoke tests).
2. Authenticate with GHCR using your GitHub PAT:
   ```bash
   echo "$GITHUB_TOKEN" | docker login ghcr.io -u username --password-stdin
   ```
3. Run the production install script to configure the deployment:
   ```bash
   python3 installer/setup.py --library-path /absolute/path/to/books \
     --admin-user admin --admin-password 'secure-password' \
     --origin https://your-domain.example.com
   ```
4. Start the production stack with pre-built images:
   ```bash
   docker compose -f docker-compose.yml up -d
   ```
5. Run the smoke test suite to validate the deployment:
   ```bash
   docker compose -f docker-compose.smoke.yml up --abort-on-container-exit
   ```
6. Verify the deployment in your browser: `https://your-domain.example.com/`
7. No database migrations required; all changes are backward-compatible at the API level.
8. For rollback, see `docs/deployment.md` for detailed rollback procedures.

## Validation highlights

- **Docker image tagging:** All images tagged with semantic version (v1.5.0) and Git commit SHA; images stored in GHCR and validated by security scanning.
- **CI/CD workflow:** GitHub Actions workflow successfully builds all service images (aithena-ui, solr-search, embeddings-server, document-indexer, document-lister, admin, nginx) and publishes to GHCR.
- **Production composition:** docker-compose.yml references pre-built GHCR images and includes all services (Solr, Redis, RabbitMQ, nginx, Python services, admin dashboard).
- **Install script:** Automates .env generation, secret provisioning, volume setup, and admin account creation. Re-running the script updates credentials or resets configuration.
- **Environment configuration:** Production .env template includes all required variables, supports environment-variable substitution for secrets, and includes documentation for each setting.
- **Release package:** GitHub Release includes docker-compose.yml, install script, smoke tests, and checksums for all artifacts.
- **Deployment procedures:** Step-by-step instructions cover initial deployment, health checks, service connectivity validation, and data migration scenarios.
- **Smoke tests:** Automated validation checks service startup, health endpoints, inter-service connectivity, search functionality, and data persistence.
- **Volume mount validation:** All persistent volumes mounted correctly; data persists across container restarts (Solr indexes, Redis snapshots, RabbitMQ queues, config files).
- **nginx production build:** UI built with production optimizations (minification, tree-shaking, vendor chunk splitting); nginx serves static assets with cache headers.
- **GHCR authentication:** Documentation covers credential setup, image pulling with docker, Docker Compose authentication, and private registry access.
- **Release checklist:** Pre-release validation includes smoke tests, version consistency checks, artifact generation, and deployment procedure walkthrough.

## Documentation updated for this release

- `docs/release-notes-v1.5.0.md` (this file)
- `docs/deployment.md` — New comprehensive guide for production deployment, configuration, health checks, and rollback procedures
- `docs/deployment/GHCR-authentication.md` — GHCR credential setup, image pulling, and authentication workflows
- `docs/deployment/production-environment.md` — Production environment configuration, secrets management, and required variables
- `docs/test-report-v1.5.0.md` — Smoke test and integration test results validating deployment procedures
- `docs/admin-manual.md` — Updated with production deployment, install script usage, image versioning, and volume configuration
- `README.md` — Updated with v1.5.0 status and production deployment overview

---

Aithena **v1.5.0** establishes the complete infrastructure required for production-grade deployments. With Docker image publishing, automated installation, smoke test validation, and comprehensive deployment documentation, operators now have industry-standard tooling to deploy Aithena in production environments with confidence.
