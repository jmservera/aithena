# Newt — Docs Restructure Execution

**Agent:** Newt (Product Manager)  
**Date:** 2026-03-19T11:12Z  
**Task:** Execute approved docs folder restructure (Ripley proposal)  
**Status:** ✅ COMPLETED  

## Outcome

### PR #541 Opened and Staged for Merge
- **Branch:** squad/docs-restructure
- **Base:** dev
- **Status:** READY FOR REVIEW ✅
- **Commits:** Single commit with full restructure (git mv preserves history)

### Execution Summary

#### File Moves (31 total)
- **Release Notes:** v1.0.0–v1.7.0 → docs/release-notes/ (12 files)
- **Test Reports:** v1.0.0–v1.7.0 → docs/test-reports/ (14 files)
- **Guides:** 5 docs → docs/guides/ (frontend-performance, i18n, monitoring, observability, v1-readiness)

#### Image References (10 total)
- Mapped 6 existing screenshots to proper image names (search-page, results, pdf-viewer, etc.)
- Added TODO comments for 4 missing images (login, similar-books, admin-dashboard, upload)

#### Cross-References (15 total)
- Updated 7 release notes with correct internal paths
- Updated v1-readiness-checklist.md table with new document paths
- Validated no broken internal links

#### Workflow Updates (7 paths)
- `.github/workflows/release-docs.yml` updated to output to new file structure
- Format strings in release prompts corrected
- Commit message template paths aligned

## Impact
- **Release automation:** v1.8.0+ will use new structure automatically
- **Documentation clarity:** Version-specific docs isolated from active manuals
- **Team:** Cleaner contributor experience for future doc additions
- **CI/CD:** release-docs.yml will not silently fail on next run

## Validation
✅ All 31 files moved with git history preserved  
✅ Internal links validated  
✅ Workflow integration verified  
✅ PR ready for merge  

## Sign-Off
Restructure executed per approved proposal. All success criteria met. PR #541 ready for review and merge.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
