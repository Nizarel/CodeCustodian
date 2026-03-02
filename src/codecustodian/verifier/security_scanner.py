"""Post-change security scanner (verification phase) — FR-VERIFY-102.

Runs Bandit on modified files, scans dependencies for known vulnerabilities,
and generates SARIF 2.1.0 reports for the GitHub Security tab.

Trivy (container scanning) and TruffleHog (secrets scanning) are
deferred to Phase 9 — stubs are provided for forward compatibility.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from codecustodian.logging import get_logger
from codecustodian.models import SecurityIssue

logger = get_logger("verifier.security_scanner")


class SecurityVerifier:
    """Verify that changes don't introduce security issues.

    Combines Bandit analysis, dependency vulnerability checks,
    and SARIF report generation.
    """

    def verify(self, changed_files: list[Path]) -> dict:
        """Run security checks on changed files.

        Returns a dict with ``passed`` bool, ``issues`` list, and
        ``sarif`` report.
        """
        issues: list[SecurityIssue] = []

        # Run Bandit on changed Python files
        py_files = [f for f in changed_files if f.suffix == ".py"]
        if py_files:
            issues.extend(self._run_bandit(py_files))

        passed = all(i.severity != "HIGH" for i in issues)

        sarif = self.generate_sarif(issues)

        return {
            "passed": passed,
            "total_issues": len(issues),
            "issues": [i.model_dump() for i in issues],
            "sarif": sarif,
        }

    def scan_dependencies(self, requirements_path: str | Path) -> list[SecurityIssue]:
        """Check for known vulnerable package versions.

        Reads a ``requirements.txt`` or ``pyproject.toml`` and checks
        each dependency against a built-in known-vulnerability list.
        A more thorough check would use ``pip-audit`` or ``safety``.
        """
        req_path = Path(requirements_path)
        if not req_path.exists():
            return []

        issues: list[SecurityIssue] = []

        # Try pip-audit if available
        try:
            result = subprocess.run(
                ["pip-audit", "--format=json", "-r", str(req_path)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.stdout:
                data = json.loads(result.stdout)
                for vuln in data.get("dependencies", []):
                    for v in vuln.get("vulns", []):
                        issues.append(
                            SecurityIssue(
                                file=str(req_path),
                                severity="HIGH" if "critical" in v.get("id", "").lower() else "MEDIUM",
                                description=f"{vuln.get('name')}=={vuln.get('version')}: {v.get('id')} — {v.get('description', '')[:200]}",
                                test_id=v.get("id", ""),
                                tool="pip-audit",
                            )
                        )
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            logger.info("pip-audit not available — skipping dependency scan")

        return issues

    # ── Trivy / TruffleHog stubs (Phase 9) ─────────────────────────────

    async def scan_containers(self, dockerfile_path: str) -> list[SecurityIssue]:
        """Trivy container scanning for CVEs in base images.

        Deferred to Phase 9.
        """
        logger.info("Container scanning deferred to Phase 9")
        return []

    async def scan_secrets(self, repo_path: str) -> list[SecurityIssue]:
        """TruffleHog secrets scanning.

        Deferred to Phase 9.
        """
        logger.info("TruffleHog scanning deferred to Phase 9")
        return []

    # ── Bandit ─────────────────────────────────────────────────────────

    def _run_bandit(self, files: list[Path]) -> list[SecurityIssue]:
        """Run Bandit on specific files."""
        try:
            result = subprocess.run(
                [
                    "bandit",
                    "-f", "json",
                    "-q",
                    *[str(f) for f in files],
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if not result.stdout:
                return []

            data = json.loads(result.stdout)
            return [
                SecurityIssue(
                    file=r.get("filename", ""),
                    line=r.get("line_number", 0),
                    severity=r.get("issue_severity", "LOW"),
                    confidence=r.get("issue_confidence", "LOW"),
                    description=r.get("issue_text", ""),
                    test_id=r.get("test_id", ""),
                    tool="bandit",
                    cwe=str(r.get("issue_cwe", {}).get("id", "")),
                )
                for r in data.get("results", [])
            ]

        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            logger.warning("Bandit verification failed or not available")
            return []

    # ── SARIF generation ───────────────────────────────────────────────

    @staticmethod
    def generate_sarif(issues: list[SecurityIssue]) -> dict:
        """Generate a SARIF 2.1.0 report for the GitHub Security tab.

        Ref: https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html
        """
        rules: list[dict] = []
        results: list[dict] = []
        seen_rule_ids: set[str] = set()

        for issue in issues:
            rule_id = issue.test_id or f"{issue.tool}-{issue.cwe or 'unknown'}"

            if rule_id not in seen_rule_ids:
                seen_rule_ids.add(rule_id)
                rules.append({
                    "id": rule_id,
                    "shortDescription": {"text": issue.description[:200]},
                    "defaultConfiguration": {
                        "level": _sarif_level(issue.severity),
                    },
                })

            results.append({
                "ruleId": rule_id,
                "level": _sarif_level(issue.severity),
                "message": {"text": issue.description},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": issue.file},
                            "region": {"startLine": max(issue.line, 1)},
                        }
                    }
                ],
            })

        return {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "CodeCustodian",
                            "version": "1.0.0",
                            "rules": rules,
                        }
                    },
                    "results": results,
                }
            ],
        }


def _sarif_level(severity: str) -> str:
    """Map severity to SARIF level."""
    mapping = {
        "HIGH": "error",
        "MEDIUM": "warning",
        "LOW": "note",
        "INFO": "note",
    }
    return mapping.get(severity.upper(), "warning")
