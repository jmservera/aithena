# Quality Gates

> **Every agent MUST follow these gates. They are enforced by git hooks — violations block commits.**

## Before Committing Code

Run the verify script. It auto-detects which services you changed:

```bash
.squad/scripts/verify.sh
```

Or check specific services:

```bash
.squad/scripts/verify.sh --service solr-search
.squad/scripts/verify.sh --service aithena-ui
.squad/scripts/verify.sh --all
```

## Per-Language Commands

### Python services (document-indexer, document-lister, embeddings-server, solr-search, admin)

```bash
# Lint (from repo root — uses root ruff.toml)
ruff check src/{service}/
ruff format --check src/{service}/

# Auto-fix lint errors
ruff check --fix src/{service}/
ruff format src/{service}/

# Tests (from service directory)
cd src/{service}
uv run pytest --tb=short -q
```

### TypeScript/React (aithena-ui)

```bash
cd src/aithena-ui

# Lint + format
npm run lint
npm run format:check

# Auto-fix
npm run lint -- --fix
npm run format

# Build (catches type errors)
npm run build

# Tests
npx vitest run
```

## Git Hook (Deterministic)

The pre-commit hook at `.github/hooks/pre-commit` automatically runs lint, format checks, and tests for staged files. It blocks the commit if anything fails.

**Setup** (once per clone):
```bash
git config core.hooksPath .github/hooks
```

**The hook MUST NOT be skipped.** Never use `--no-verify`.

## Checklist (copy into PR description)

- [ ] `ruff check` passes for all changed Python files
- [ ] `ruff format --check` passes for all changed Python files
- [ ] `npm run lint` passes (if aithena-ui changed)
- [ ] `npm run format:check` passes (if aithena-ui changed)
- [ ] Tests pass for all changed services
- [ ] No new lint warnings or test failures introduced
