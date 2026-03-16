# Decision: upload-artifact audit & secret scanning recommendation

**Date:** 2026-03-15  
**Author:** @copilot (as Kane / Security Engineer)  
**Related:** Issue #243 (sub-issue of #241 security audit)

## Finding: upload-artifact already compliant

Full audit of all 12 `.github/workflows/*.yml` files for `actions/upload-artifact` usages:

| Workflow file | Usage | Version | Has `name:` | Status |
|---|---|---|---|---|
| `security-bandit.yml` | 1 | `@v4` | ✅ `bandit-sarif` | Compliant |
| All others (11 files) | 0 | — | — | N/A |

**Conclusion:** Only one `upload-artifact` usage exists in the repository and it is already at `@v4` with an explicit `name:` parameter. No CVE-2024-42471 exposure. The 13 open zizmor/artipacked alerts referenced in the issue were likely based on an earlier state of the repository before prior cleanups.

## Recommendation: Enable Secret Scanning

Secret scanning is currently **disabled** on this repository. This is a missing security control recommended for v0.10.0.

**Action required (admin only):**  
Enable via: **Settings → Security → Code security and analysis → Secret scanning**

- Free feature for public repositories  
- Protects against accidental credential commits  
- Only repository admins can enable this feature  

**Tagging @jmservera (Product Owner) for action.**
