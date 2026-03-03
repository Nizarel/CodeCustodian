---
name: security-remediation
description: >
  Deep expertise in security vulnerability remediation including
  OWASP Top 10, CWE mappings, and secure coding patterns for Python.
---

# Security Remediation Skill

## OWASP Top 10 Mapping

When analyzing security findings, map each to the relevant OWASP category:

| OWASP ID | Category | Typical Python Patterns |
|----------|----------|------------------------|
| A01 | Broken Access Control | Missing auth decorators, insecure direct object references |
| A02 | Cryptographic Failures | `hashlib.md5`, `DES`, hardcoded keys, weak random |
| A03 | Injection | f-string SQL, `os.system(user_input)`, `eval()`, `exec()` |
| A04 | Insecure Design | Missing rate limiting, no input validation |
| A05 | Security Misconfiguration | `DEBUG=True` in production, default secrets |
| A06 | Vulnerable Components | Outdated dependencies with known CVEs |
| A07 | Auth Failures | Plaintext passwords, weak session tokens |
| A08 | Data Integrity Failures | Insecure deserialization (`pickle.loads`), missing signatures |
| A09 | Logging Failures | Logging secrets, missing audit trails |
| A10 | SSRF | Unvalidated URL fetches, internal network access |

## Secure Replacement Patterns

### SQL Injection → Parameterized Queries
```python
# VULNERABLE
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")

# SAFE — parameterized query
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

### Command Injection → subprocess with list args
```python
# VULNERABLE
os.system(f"grep {pattern} {filename}")

# SAFE — subprocess with explicit args, no shell
import subprocess
subprocess.run(["grep", pattern, filename], check=True, capture_output=True)
```

### Weak Crypto → Modern Alternatives
```python
# VULNERABLE
import hashlib
hashlib.md5(password.encode()).hexdigest()

# SAFE — use bcrypt or argon2 for passwords
import bcrypt
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

# SAFE — use SHA-256+ for non-password hashing
hashlib.sha256(data.encode()).hexdigest()
```

### Hardcoded Secrets → Environment Variables
```python
# VULNERABLE
API_KEY = "sk-abc123secret"

# SAFE — environment variable
import os
API_KEY = os.environ["API_KEY"]

# SAFE — secrets manager
from azure.keyvault.secrets import SecretClient
```

### Insecure Deserialization → Safe Alternatives
```python
# VULNERABLE
import pickle
data = pickle.loads(untrusted_bytes)

# SAFE — use JSON for data interchange
import json
data = json.loads(untrusted_string)
```

### Path Traversal → Validated Paths
```python
# VULNERABLE
filepath = os.path.join(BASE_DIR, user_input)

# SAFE — resolve and validate
filepath = (Path(BASE_DIR) / user_input).resolve()
if not filepath.is_relative_to(Path(BASE_DIR).resolve()):
    raise ValueError("Path traversal detected")
```

## CWE Reference Quick Guide

- **CWE-78**: OS Command Injection → `subprocess.run([...])` with no shell
- **CWE-79**: XSS → Template auto-escaping, `markupsafe.escape()`
- **CWE-89**: SQL Injection → Parameterized queries, ORM
- **CWE-94**: Code Injection → Never `eval()`/`exec()` user input
- **CWE-200**: Information Exposure → Sanitize error messages
- **CWE-259**: Hardcoded Password → Environment/vault
- **CWE-327**: Broken Crypto → Modern algorithms (AES-256, SHA-256+)
- **CWE-502**: Insecure Deserialization → JSON instead of pickle
- **CWE-611**: XML External Entity → `defusedxml` library
- **CWE-918**: SSRF → URL allowlisting, no internal network access

## Remediation Principles

1. **Never trust user input** — Validate, sanitize, and escape at boundaries
2. **Least privilege** — Minimal permissions for operations
3. **Defense in depth** — Multiple layers of protection
4. **Fail secure** — On error, deny access rather than grant
5. **Keep it simple** — Prefer well-tested stdlib/library solutions over custom crypto
6. **Preserve functionality** — Security fix must not break existing behavior
