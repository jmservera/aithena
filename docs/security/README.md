# Security Documentation

**Owner:** Kane (Security Engineer)  
**Last Updated:** 2025-03-15

This directory contains security-related documentation for the aithena project.

---

## Documents

### Audit Guides

- **[OWASP ZAP Manual Audit Guide](owasp-zap-audit-guide.md)** — Step-by-step instructions for conducting dynamic application security testing (DAST) with OWASP ZAP, plus Docker Compose infrastructure-as-code (IaC) security review checklist.
- **[Baseline Exceptions](baseline-exceptions.md)** — Security findings accepted as baseline with documented risk assessment and mitigation strategies.

---

## Security Practices

### CI/CD Security Scanning

The aithena project uses the following automated security scanners:

| Tool | Purpose | CI Integration | Status |
|------|---------|----------------|--------|
| **CodeQL** | SAST (JS/TS + Python) | GitHub Actions | ✅ Active |
| **Bandit** | Python SAST | GitHub Actions | 🟡 Planned (issue #88) |
| **Checkov** | IaC (Dockerfiles + GitHub Actions) | GitHub Actions | 🟡 Planned (issue #89) |
| **Zizmor** | GitHub Actions supply chain security | GitHub Actions | 🟡 Planned (issue #90) |
| **Dependabot** | Dependency vulnerability scanning | GitHub | ✅ Active |
| **Mend (WhiteSource)** | Dependency scanning | GitHub | ✅ Active |

### Manual Security Audits

| Activity | Frequency | Guide |
|----------|-----------|-------|
| **OWASP ZAP Audit** | Before major releases (v0.X.0) | [owasp-zap-audit-guide.md](owasp-zap-audit-guide.md) |
| **Docker Compose IaC Review** | Before major releases | [owasp-zap-audit-guide.md#docker-compose-iac-security-review](owasp-zap-audit-guide.md#docker-compose-iac-security-review) |
| **Dependency Review** | Monthly | (TBD) |

---

## Known Security Issues

**Tracked in GitHub Issues:**

| Issue | Severity | Description | Status |
|-------|----------|-------------|--------|
| #98 | High | Missing authentication on admin endpoints (`/admin/solr`, `/admin/rabbitmq`, etc.) | Deferred to v0.7.0 |
| #98 | High | Insecure defaults (RabbitMQ `guest/guest`, Redis no password) | Deferred to v0.7.0 |
| Dependabot | Critical/High | 64 total vulnerabilities (3 critical, 12 high) | Ongoing triage |

**Documented Baseline Exceptions:**

See individual audit reports in `docs/security/audit-reports/` (directory to be created when first audit is performed).

---

## Security Contacts

- **Security Engineer:** Kane (@kane)
- **Product Owner:** Juanma (@jmservera)
- **Lead Engineer:** Ripley (@ripley)

For security vulnerabilities, contact Kane directly or create a private security advisory on GitHub.

---

## Related Documentation

- **[Admin Manual](../admin-manual.md)** — Deployment and administration guide (includes security considerations)
- **[User Manual](../user-manual.md)** — End-user documentation
- **CI/CD Configuration:** `.github/workflows/` (CodeQL, Bandit, Checkov, Zizmor)

---

## Future Enhancements

Planned security documentation:

- [ ] Security baseline document (after SEC-5 triage, issue #98)
- [ ] Incident response playbook
- [ ] Secure deployment checklist (production hardening)
- [ ] Dependency update policy
- [ ] Vulnerability disclosure policy

---

**Document Version:** 1.0  
**Next Review:** 2025-09-15
