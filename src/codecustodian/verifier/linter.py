"""Linter runner — execute ruff, mypy, bandit on changed files (FR-VERIFY-101).

Compares against a baseline to report only NEW violations.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from codecustodian.logging import get_logger
from codecustodian.models import LintViolation

logger = get_logger("verifier.linter")


class LinterRunner:
    """Run linters and collect violations with baseline comparison.

    Usage::

        runner = LinterRunner()
        violations = runner.run_all(changed_files)
        new_only = runner.filter_new_violations(violations, baseline)
    """

    def run_all(self, changed_files: list[Path]) -> list[LintViolation]:
        """Run ruff, mypy, and bandit on changed files."""
        violations: list[LintViolation] = []
        violations.extend(self._run_ruff(changed_files))
        violations.extend(self._run_mypy(changed_files))
        violations.extend(self._run_bandit(changed_files))
        return violations

    def get_baseline(self, files: list[Path]) -> list[LintViolation]:
        """Capture lint baseline before changes for comparison.

        This should be called before applying changes to know
        which violations are pre-existing.
        """
        return self.run_all(files)

    @staticmethod
    def filter_new_violations(
        current: list[LintViolation],
        baseline: list[LintViolation],
    ) -> list[LintViolation]:
        """Return only violations that were NOT in the baseline.

        Matching is done by (file, line, code, tool) tuple.
        """
        baseline_keys = {
            (v.file, v.line, v.code, v.tool) for v in baseline
        }
        return [
            v for v in current
            if (v.file, v.line, v.code, v.tool) not in baseline_keys
        ]

    def _run_ruff(self, files: list[Path]) -> list[LintViolation]:
        """Run ruff linter with JSON output."""
        if not files:
            return []

        try:
            result = subprocess.run(
                ["ruff", "check", "--output-format=json", *[str(f) for f in files]],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if not result.stdout:
                return []

            violations: list[LintViolation] = []
            for v in json.loads(result.stdout):
                violations.append(
                    LintViolation(
                        file=v.get("filename", ""),
                        line=v.get("location", {}).get("row", 0),
                        code=v.get("code", ""),
                        message=v.get("message", ""),
                        tool="ruff",
                        severity="error" if v.get("code", "").startswith("E") else "warning",
                    )
                )
            return violations

        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            logger.warning("Ruff check failed or not available")
            return []

    def _run_mypy(self, files: list[Path]) -> list[LintViolation]:
        """Run mypy type checker."""
        if not files:
            return []

        try:
            result = subprocess.run(
                ["mypy", "--no-error-summary", *[str(f) for f in files]],
                capture_output=True,
                text=True,
                timeout=120,
            )

            violations: list[LintViolation] = []
            for line in result.stdout.splitlines():
                if ": error:" in line or ": warning:" in line:
                    parts = line.split(":", 3)
                    if len(parts) >= 4:
                        violations.append(
                            LintViolation(
                                file=parts[0],
                                line=int(parts[1]) if parts[1].strip().isdigit() else 0,
                                code="mypy",
                                message=parts[3].strip(),
                                tool="mypy",
                                severity="error" if "error" in parts[2] else "warning",
                            )
                        )
            return violations

        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("Mypy check failed or not available")
            return []

    def _run_bandit(self, files: list[Path]) -> list[LintViolation]:
        """Run bandit security linter with JSON output (FR-VERIFY-101)."""
        py_files = [f for f in files if f.suffix == ".py"]
        if not py_files:
            return []

        try:
            result = subprocess.run(
                [
                    "bandit",
                    "-f", "json",
                    "-q",
                    *[str(f) for f in py_files],
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if not result.stdout:
                return []

            violations: list[LintViolation] = []
            data = json.loads(result.stdout)
            for r in data.get("results", []):
                severity = r.get("issue_severity", "LOW").lower()
                violations.append(
                    LintViolation(
                        file=r.get("filename", ""),
                        line=r.get("line_number", 0),
                        code=r.get("test_id", ""),
                        message=r.get("issue_text", ""),
                        tool="bandit",
                        severity="error" if severity == "high" else "warning",
                    )
                )
            return violations

        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            logger.warning("Bandit check failed or not available")
            return []
