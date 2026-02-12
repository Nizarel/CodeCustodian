"""Security pattern scanner.

Wraps Bandit for security analysis with JSON output parsing.
Detects hardcoded secrets, weak crypto, injection risks.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from codecustodian.logging import get_logger
from codecustodian.models import Finding, FindingType, SeverityLevel
from codecustodian.scanner.base import BaseScanner

logger = get_logger("scanner.security")


class SecurityScanner(BaseScanner):
    """Scan for security issues using Bandit."""

    name = "security_patterns"
    description = "Detects security vulnerabilities via Bandit"

    def scan(self, repo_path: str | Path) -> list[Finding]:
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

        return sorted(findings, key=lambda f: f.priority_score, reverse=True)

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
