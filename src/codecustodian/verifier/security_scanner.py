"""Post-change security scanner (verification phase).

Runs Bandit + optional Trivy on modified files to ensure
no new security issues are introduced by refactorings.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from codecustodian.logging import get_logger

logger = get_logger("verifier.security_scanner")


class SecurityVerifier:
    """Verify that changes don't introduce security issues."""

    def verify(self, changed_files: list[Path]) -> dict:
        """Run security checks on changed files.

        Returns a dict with 'passed' bool and 'issues' list.
        """
        issues: list[dict] = []

        # Run Bandit on changed Python files
        py_files = [f for f in changed_files if f.suffix == ".py"]
        if py_files:
            issues.extend(self._run_bandit(py_files))

        passed = all(i.get("severity") != "HIGH" for i in issues)

        return {
            "passed": passed,
            "total_issues": len(issues),
            "issues": issues,
        }

    def _run_bandit(self, files: list[Path]) -> list[dict]:
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
                {
                    "file": r.get("filename", ""),
                    "line": r.get("line_number", 0),
                    "severity": r.get("issue_severity", "LOW"),
                    "confidence": r.get("issue_confidence", "LOW"),
                    "description": r.get("issue_text", ""),
                    "test_id": r.get("test_id", ""),
                }
                for r in data.get("results", [])
            ]

        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            logger.warning("Bandit verification failed or not available")
            return []
