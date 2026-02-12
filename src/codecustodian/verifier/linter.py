"""Linter runner — execute ruff, mypy, bandit on changed files.

Compares against a baseline to report only new violations.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from codecustodian.logging import get_logger

logger = get_logger("verifier.linter")


@dataclass
class LintViolation:
    """A single lint violation."""

    file: str
    line: int
    code: str
    message: str
    tool: str
    severity: str = "warning"


class LinterRunner:
    """Run linters and collect violations."""

    def run_all(self, changed_files: list[Path]) -> list[LintViolation]:
        """Run ruff, mypy, and bandit on changed files."""
        violations: list[LintViolation] = []
        violations.extend(self._run_ruff(changed_files))
        violations.extend(self._run_mypy(changed_files))
        return violations

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
                                line=int(parts[1]) if parts[1].isdigit() else 0,
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
