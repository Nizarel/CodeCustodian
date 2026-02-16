# Security Policy

## Supported Versions

| Version | Supported |
| --- | --- |
| 0.8.x+ | ✅ |
| < 0.8.0 | ❌ |

## Reporting a Vulnerability

If you discover a security issue, please do not open a public GitHub issue.

- Email: **security@codecustodian.local**
- Include: affected version, reproduction steps, impact, and suggested remediation
- Response target: **within 2 business days**
- Status updates: every **5 business days** until closure

## Disclosure Process

1. We acknowledge receipt and begin triage.
2. We reproduce and assess severity.
3. We prepare a fix and validate with tests and security scans.
4. We coordinate disclosure timing with reporters.
5. We publish the fix and release notes.

## Security Controls in CodeCustodian

- Secrets are fetched from Azure Key Vault through managed identity.
- Structured logs redact sensitive values (tokens, API keys, connection-string secrets).
- Refactoring execution blocks dangerous dynamic code (`eval`, `exec`, `compile`, `__import__`).
- File operations enforce repository-bound path validation and reject traversal/symlink edits.
- Audit logs are append-only JSONL with SHA-256 hash per entry for tamper evidence.
- Bandit is part of the verification toolchain.

## Secure Configuration Guidance

- Use least-privilege tokens and rotate credentials every 90 days.
- Restrict write access to production repositories and CI secrets.
- Keep dependencies and container base images patched.
- Enable Azure Monitor alerts and review security events daily.
