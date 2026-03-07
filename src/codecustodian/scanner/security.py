"""Security pattern scanner.

Wraps Bandit for security analysis and adds custom regex-based
pattern detection for hardcoded secrets, weak crypto, injection
risks, deserialization, and path traversal (FR-SCAN-040 - 043,
FR-SCAN-101).

Each finding includes an **exploit scenario** and **compliance impact**
(PCI DSS, GDPR, SOC 2, OWASP).
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
from collections import deque
from pathlib import Path
from typing import Any

from codecustodian.logging import get_logger
from codecustodian.models import Finding, FindingType, SeverityLevel
from codecustodian.scanner.base import BaseScanner

logger = get_logger("scanner.security")

# ── Custom pattern definitions ────────────────────────────────────────────

_CUSTOM_PATTERNS: dict[str, list[dict[str, Any]]] = {
    "hardcoded_secrets": [
        {
            "regex": r"""(?i)(?:password|passwd|secret|api_key|apikey|token|auth_token|access_key|private_key)\s*=\s*["'][^"']{4,}["']""",
            "message": "Potential hardcoded secret or credential",
            "severity": SeverityLevel.CRITICAL,
            "cwe": "CWE-798",
            "priority": 190.0,
        },
        {
            "regex": r"""(?i)(?:AWS|AZURE|GCP|GITHUB|SLACK|STRIPE)[_A-Z]*(?:KEY|SECRET|TOKEN)\s*=\s*["'][^"']+["']""",
            "message": "Potential cloud provider credential in source code",
            "severity": SeverityLevel.CRITICAL,
            "cwe": "CWE-798",
            "priority": 195.0,
        },
    ],
    "weak_crypto": [
        {
            "regex": r"""hashlib\.(?:md5|sha1)\b""",
            "message": "Weak hash algorithm (MD5/SHA1) used — vulnerable to collision attacks",
            "severity": SeverityLevel.HIGH,
            "cwe": "CWE-328",
            "priority": 140.0,
        },
        {
            "regex": r"""from\s+Crypto\.Cipher\s+import\s+DES\b""",
            "message": "DES encryption is insecure — use AES instead",
            "severity": SeverityLevel.HIGH,
            "cwe": "CWE-327",
            "priority": 140.0,
        },
        {
            "regex": r"""\bnew\s+(?:MD5|SHA1)(?:Managed|CryptoServiceProvider)?\s*\(""",
            "message": "Weak hash algorithm (MD5/SHA1) used — vulnerable to collision attacks (C#)",
            "severity": SeverityLevel.HIGH,
            "cwe": "CWE-328",
            "priority": 140.0,
        },
        {
            "regex": r'''"crypto/md5"|"crypto/sha1"''',
            "message": "Weak hash algorithm (MD5/SHA1) used — vulnerable to collision attacks (Go)",
            "severity": SeverityLevel.HIGH,
            "cwe": "CWE-328",
            "priority": 140.0,
        },
        {
            "regex": r"""MessageDigest\.getInstance\s*\(\s*["'](?:MD5|SHA-1)["']""",
            "message": "Weak hash algorithm (MD5/SHA-1) used — vulnerable to collision attacks (Java)",
            "severity": SeverityLevel.HIGH,
            "cwe": "CWE-328",
            "priority": 140.0,
        },
    ],
    "sql_injection": [
        {
            "regex": r"""\.execute\s*\(\s*(?:f["']|["'].*%[sd]|.*\.format\s*\()""",
            "message": "Potential SQL injection — use parameterised queries",
            "severity": SeverityLevel.CRITICAL,
            "cwe": "CWE-89",
            "priority": 185.0,
        },
        {
            "regex": r"""\bSqlCommand\s*\([^)]*\+""",
            "message": "Potential SQL injection via string concatenation in SqlCommand (C#)",
            "severity": SeverityLevel.CRITICAL,
            "cwe": "CWE-89",
            "priority": 185.0,
        },
        {
            "regex": r"""\bdb\.(?:Query|Exec)\s*\([^)]*\+""",
            "message": "Potential SQL injection via string concatenation in db.Query/Exec (Go)",
            "severity": SeverityLevel.CRITICAL,
            "cwe": "CWE-89",
            "priority": 185.0,
        },
        {
            "regex": r"""(?:Statement|PreparedStatement).*execute(?:Query|Update)?\s*\([^)]*\+""",
            "message": "Potential SQL injection via string concatenation in Statement.execute (Java)",
            "severity": SeverityLevel.CRITICAL,
            "cwe": "CWE-89",
            "priority": 185.0,
        },
    ],
    "command_injection": [
        {
            "regex": r"""os\.system\s*\(""",
            "message": "os.system() is vulnerable to command injection — use subprocess.run()",
            "severity": SeverityLevel.HIGH,
            "cwe": "CWE-78",
            "priority": 150.0,
        },
        {
            "regex": r"""subprocess\.(?:call|run|Popen)\s*\([^)]*shell\s*=\s*True""",
            "message": "subprocess with shell=True is vulnerable to command injection",
            "severity": SeverityLevel.HIGH,
            "cwe": "CWE-78",
            "priority": 150.0,
        },
        {
            "regex": r"""\beval\s*\(""",
            "message": "eval() can execute arbitrary code — avoid with untrusted input",
            "severity": SeverityLevel.HIGH,
            "cwe": "CWE-95",
            "priority": 160.0,
        },
        {
            "regex": r"""\bexec\s*\(""",
            "message": "exec() can execute arbitrary code — avoid with untrusted input",
            "severity": SeverityLevel.HIGH,
            "cwe": "CWE-95",
            "priority": 155.0,
        },
        {
            "regex": r"""\bProcess\.Start\s*\(""",
            "message": "Process.Start() may be vulnerable to command injection (C#)",
            "severity": SeverityLevel.HIGH,
            "cwe": "CWE-78",
            "priority": 150.0,
        },
        {
            "regex": r"""\bexec\.Command\s*\(""",
            "message": "exec.Command() may be vulnerable to command injection (Go)",
            "severity": SeverityLevel.HIGH,
            "cwe": "CWE-78",
            "priority": 150.0,
        },
        {
            "regex": r"""\bRuntime\.getRuntime\s*\(\s*\)\.exec\s*\(""",
            "message": "Runtime.exec() may be vulnerable to command injection (Java)",
            "severity": SeverityLevel.HIGH,
            "cwe": "CWE-78",
            "priority": 150.0,
        },
    ],
    "deserialization": [
        {
            "regex": r"""pickle\.loads?\s*\(""",
            "message": "pickle deserialization of untrusted data can lead to RCE",
            "severity": SeverityLevel.CRITICAL,
            "cwe": "CWE-502",
            "priority": 180.0,
        },
        {
            "regex": r"""yaml\.load\s*\([^)]*(?!Loader\s*=\s*yaml\.SafeLoader)""",
            "message": "yaml.load() without SafeLoader can execute arbitrary code",
            "severity": SeverityLevel.HIGH,
            "cwe": "CWE-502",
            "priority": 160.0,
        },
    ],
    "path_traversal": [
        {
            "regex": r"""open\s*\(.*(?:request|input|argv|args|params)""",
            "message": "Potential path traversal — validate file paths from user input",
            "severity": SeverityLevel.MEDIUM,
            "cwe": "CWE-22",
            "priority": 100.0,
        },
    ],
}

# ── Exploit scenario descriptions (FR-SCAN-101 / 4.5.4) ──────────────────

_EXPLOIT_SCENARIOS: dict[str, str] = {
    "hardcoded_secrets": (
        "An attacker with repository access (or via a leaked repo) can extract "
        "credentials and gain unauthorised access to external services, databases, "
        "or cloud resources."
    ),
    "weak_crypto": (
        "Weak hash algorithms (MD5, SHA-1) are vulnerable to collision attacks. "
        "An attacker could forge data that produces the same hash, bypassing "
        "integrity checks or password verification."
    ),
    "sql_injection": (
        "An attacker can craft malicious input to modify SQL queries, allowing "
        "data exfiltration, authentication bypass, or complete database compromise."
    ),
    "command_injection": (
        "An attacker can inject shell commands through unsanitised input, gaining "
        "arbitrary code execution on the server with the application's privileges."
    ),
    "deserialization": (
        "Deserializing untrusted data (e.g. pickle, YAML) can lead to Remote Code "
        "Execution (RCE) — an attacker crafts a payload that runs arbitrary code "
        "when deserialized."
    ),
    "path_traversal": (
        "An attacker can use '../' sequences in file paths to read or write "
        "arbitrary files on the server, potentially exposing sensitive data or "
        "overwriting configuration."
    ),
}

# ── Compliance impact mapping (FR-SCAN-101 / 4.5.5) ──────────────────────

_COMPLIANCE_MAPPING: dict[str, list[str]] = {
    "hardcoded_secrets": [
        "PCI DSS 6.5.3 — Insecure cryptographic storage",
        "SOC 2 CC6.1 — Logical access controls",
        "OWASP A07:2021 — Identification and Authentication Failures",
    ],
    "weak_crypto": [
        "PCI DSS 6.5.3 — Insecure cryptographic storage",
        "GDPR Art. 32 — Appropriate security measures",
        "OWASP A02:2021 — Cryptographic Failures",
    ],
    "sql_injection": [
        "PCI DSS 6.5.1 — Injection flaws",
        "OWASP A03:2021 — Injection",
        "GDPR Art. 32 — Appropriate security measures",
    ],
    "command_injection": [
        "PCI DSS 6.5.1 — Injection flaws",
        "OWASP A03:2021 — Injection",
    ],
    "deserialization": [
        "OWASP A08:2021 — Software and Data Integrity Failures",
        "PCI DSS 6.5.1 — Injection flaws",
    ],
    "path_traversal": [
        "OWASP A01:2021 — Broken Access Control",
        "PCI DSS 6.5.8 — Improper access control",
    ],
}


class SecurityScanner(BaseScanner):
    """Scan for security issues using Bandit + custom regex patterns.

    Custom patterns run independently of Bandit so findings are reported
    even when Bandit is not installed.  Each finding includes an exploit
    scenario description and compliance impact references.
    """

    name = "security_patterns"
    description = "Detects security vulnerabilities via Bandit and custom patterns"

    def scan(self, repo_path: str | Path) -> list[Finding]:
        findings: list[Finding] = []

        # Bandit integration (existing — 4.5.1)
        findings.extend(self._run_bandit(repo_path))

        # Custom pattern detection (4.5.2)
        enabled_categories = self._get_enabled_categories()
        findings.extend(self._scan_custom_patterns(repo_path, enabled_categories))

        # Reachability enrichment for Python findings (entrypoint -> vulnerable function)
        self._enrich_reachability(repo_path, findings)

        return sorted(findings, key=lambda f: f.priority_score, reverse=True)

    # ── Reachability enrichment ──────────────────────────────────────

    def _enrich_reachability(self, repo_path: str | Path, findings: list[Finding]) -> None:
        """Annotate findings with simple reachability metadata.

        The analysis builds a lightweight call graph across Python files and marks
        whether the function containing a finding is reachable from inferred
        application entrypoints.
        """
        py_files = self.find_python_files(repo_path)
        if not py_files:
            return

        functions: dict[str, dict[str, Any]] = {}
        for py_file in py_files:
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue

                name = node.name
                start = node.lineno
                end = getattr(node, "end_lineno", None) or node.lineno
                calls: set[str] = set()
                for child in ast.walk(node):
                    if not isinstance(child, ast.Call):
                        continue
                    if isinstance(child.func, ast.Name):
                        calls.add(child.func.id)
                    elif isinstance(child.func, ast.Attribute):
                        calls.add(child.func.attr)

                is_entry = self._is_entrypoint_function(node)
                functions[name] = {
                    "file": str(py_file),
                    "start": start,
                    "end": end,
                    "calls": calls,
                    "is_entry": is_entry,
                }

        if not functions:
            return

        entrypoints = {name for name, data in functions.items() if data["is_entry"]}
        reachable: set[str] = set(entrypoints)
        queue: deque[str] = deque(entrypoints)
        parent: dict[str, str] = {}

        while queue:
            current = queue.popleft()
            for callee in functions.get(current, {}).get("calls", set()):
                if callee in functions and callee not in reachable:
                    reachable.add(callee)
                    parent[callee] = current
                    queue.append(callee)

        for finding in findings:
            if not str(finding.file).endswith(".py"):
                continue

            fn_name = self._find_enclosing_function(functions, finding.file, finding.line)
            if not fn_name:
                continue

            is_reachable = fn_name in reachable
            finding.metadata["reachable"] = is_reachable
            finding.metadata["enclosing_function"] = fn_name
            if is_reachable:
                finding.metadata["call_chain"] = self._build_call_chain(parent, fn_name)
                finding.priority_score = min(200.0, finding.priority_score * 1.1)

    @staticmethod
    def _is_entrypoint_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """Heuristic entrypoint detection for web handlers and common app roots."""
        name = node.name.lower()
        if name in {"main", "handler", "handle_request", "run"}:
            return True

        for deco in node.decorator_list:
            if isinstance(deco, ast.Name) and deco.id.lower() in {
                "route",
                "get",
                "post",
                "put",
                "patch",
                "delete",
            }:
                return True
            if isinstance(deco, ast.Attribute) and deco.attr.lower() in {
                "route",
                "get",
                "post",
                "put",
                "patch",
                "delete",
            }:
                return True

        return False

    @staticmethod
    def _find_enclosing_function(
        functions: dict[str, dict[str, Any]],
        file_path: str,
        line: int,
    ) -> str | None:
        for name, data in functions.items():
            if data["file"] != str(file_path):
                continue
            if data["start"] <= line <= data["end"]:
                return name
        return None

    @staticmethod
    def _build_call_chain(parent: dict[str, str], leaf: str) -> list[str]:
        chain = [leaf]
        cur = leaf
        while cur in parent:
            cur = parent[cur]
            chain.append(cur)
        chain.reverse()
        return chain

    # ── Config wiring ─────────────────────────────────────────────────

    def _get_enabled_categories(self) -> set[str]:
        """Read SecurityScannerConfig to determine which pattern categories to run."""
        categories = set(_CUSTOM_PATTERNS.keys())
        if not self.config:
            return categories

        cfg = self.config.scanners.security_patterns
        if not cfg.detect_hardcoded_secrets:
            categories.discard("hardcoded_secrets")
        if not cfg.detect_weak_crypto:
            categories.discard("weak_crypto")
        if not cfg.detect_sql_injection:
            categories.discard("sql_injection")
        if not cfg.detect_command_injection:
            categories.discard("command_injection")
        return categories

    # ── Bandit subprocess ─────────────────────────────────────────────

    def _run_bandit(self, repo_path: str | Path) -> list[Finding]:
        """Run Bandit as subprocess with JSON output parsing."""
        findings: list[Finding] = []

        try:
            result = subprocess.run(
                [
                    "bandit",
                    "-r",
                    str(repo_path),
                    "-f",
                    "json",
                    "--severity-level",
                    "low",
                    "-q",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.stdout:
                data = json.loads(result.stdout)
                for issue in data.get("results", []):
                    severity = self._map_severity(issue.get("issue_severity", "LOW"))
                    findings.append(
                        Finding(
                            type=FindingType.SECURITY,
                            severity=severity,
                            file=issue.get("filename", ""),
                            line=issue.get("line_number", 0),
                            description=issue.get("issue_text", ""),
                            suggestion=f"CWE: {issue.get('issue_cwe', {}).get('id', 'N/A')}",
                            priority_score=self._severity_to_priority(severity),
                            scanner_name=self.name,
                            metadata={
                                "source": "bandit",
                                "test_id": issue.get("test_id", ""),
                                "test_name": issue.get("test_name", ""),
                                "confidence": issue.get("issue_confidence", ""),
                            },
                        )
                    )
        except FileNotFoundError:
            logger.warning("Bandit not found — install with: pip install bandit")
        except subprocess.TimeoutExpired:
            logger.warning("Bandit timed out after 120s")
        except json.JSONDecodeError:
            logger.warning("Failed to parse Bandit output")

        return findings

    # ── Custom pattern scanning (FR-SCAN-042 / 4.5.2) ────────────────

    def _scan_custom_patterns(
        self,
        repo_path: str | Path,
        enabled_categories: set[str],
    ) -> list[Finding]:
        """Scan source files with regex-based security patterns."""
        findings: list[Finding] = []

        cfg_langs = (
            self.config.scanners.security_patterns.languages
            if self.config
            else ["py", "go", "cs", "js", "ts", "java"]
        )
        extensions = [ext if ext.startswith(".") else f".{ext}" for ext in cfg_langs]

        for src_file in self.find_files(repo_path, extensions):
            try:
                source = src_file.read_text(encoding="utf-8", errors="ignore")
                lines = source.splitlines()
            except OSError:
                continue

            for category, patterns in _CUSTOM_PATTERNS.items():
                if category not in enabled_categories:
                    continue
                for pat_def in patterns:
                    regex = re.compile(pat_def["regex"])
                    for line_num, line in enumerate(lines, start=1):
                        if regex.search(line):
                            findings.append(
                                Finding(
                                    type=FindingType.SECURITY,
                                    severity=pat_def["severity"],
                                    file=str(src_file),
                                    line=line_num,
                                    description=pat_def["message"],
                                    suggestion=f"CWE: {pat_def['cwe']}",
                                    priority_score=pat_def["priority"],
                                    scanner_name=self.name,
                                    metadata={
                                        "source": "custom_pattern",
                                        "category": category,
                                        "cwe": pat_def["cwe"],
                                        "language": src_file.suffix.lstrip("."),
                                        "exploit_scenario": _EXPLOIT_SCENARIOS.get(category, ""),
                                        "compliance": _COMPLIANCE_MAPPING.get(category, []),
                                    },
                                )
                            )

        return findings

    # ── Severity helpers ──────────────────────────────────────────────

    @staticmethod
    def _map_severity(bandit_severity: str) -> SeverityLevel:
        mapping = {
            "HIGH": SeverityLevel.CRITICAL,
            "MEDIUM": SeverityLevel.HIGH,
            "LOW": SeverityLevel.MEDIUM,
        }
        return mapping.get(bandit_severity.upper(), SeverityLevel.MEDIUM)

    @staticmethod
    def _severity_to_priority(severity: SeverityLevel) -> float:
        mapping = {
            SeverityLevel.CRITICAL: 180.0,
            SeverityLevel.HIGH: 140.0,
            SeverityLevel.MEDIUM: 80.0,
            SeverityLevel.LOW: 40.0,
        }
        return mapping.get(severity, 80.0)
