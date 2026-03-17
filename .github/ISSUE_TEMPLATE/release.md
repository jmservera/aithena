---
name: Release Checklist
about: Checklist for releasing a new version of Aithena
title: "Release vX.Y.Z"
labels: release
---

## Release Checklist — vX.Y.Z

> Replace **X.Y.Z** with the actual version number throughout this checklist.

### Pre-release

- [ ] All milestone issues closed (check [milestone](../../milestones) and `release` label)
- [ ] Trigger `release-docs` workflow (Actions → **Release Docs** → Run workflow, version=`X.Y.Z`, milestone=`vX.Y.Z`)
- [ ] Review and merge the generated docs PR (release notes, test report, manual updates)
- [ ] Update user manual and admin manual — Newt reviews with screenshots
- [ ] Run full test suite — all services pass (`solr-search`, `document-indexer`, `document-lister`, `embeddings-server`, `aithena-ui`, `admin`)

### Release

- [ ] Bump `VERSION` file to `X.Y.Z`
- [ ] Merge `dev` → `main` via PR
- [ ] Create and push tag: `git tag vX.Y.Z && git push origin vX.Y.Z`

### Post-release

- [ ] Verify GitHub Release published (automated by `release.yml`)
- [ ] Close milestone on GitHub
