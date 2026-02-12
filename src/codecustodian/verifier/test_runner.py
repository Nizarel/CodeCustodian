"""Test runner — execute pytest and collect results.

Discovers and runs tests relevant to changed files, collects
coverage data, and returns structured results.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from codecustodian.logging import get_logger
from codecustodian.models import VerificationResult

logger = get_logger("verifier.test_runner")


class TestRunner:
    """Execute tests and collect coverage metrics."""

    def __init__(
        self,
        framework: str = "pytest",
        timeout: int = 300,
        coverage_threshold: int = 80,
    ) -> None:
        self.framework = framework
        self.timeout = timeout
        self.coverage_threshold = coverage_threshold

    def run_tests(
        self, changed_files: list[Path], repo_path: str | Path
    ) -> VerificationResult:
        """Run tests covering the changed files."""
        test_files = self._discover_tests(changed_files, Path(repo_path))

        if not test_files:
            logger.info("No relevant tests found — running full suite")
            test_files = [Path(repo_path) / "tests"]

        args = [
            "pytest",
            "--verbose",
            "--tb=short",
            "--cov=src/codecustodian",
            "--cov-report=json:.coverage.json",
            "--junitxml=results.xml",
            *[str(f) for f in test_files],
        ]

        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(repo_path),
            )

            exit_code = result.returncode
            passed = exit_code == 0

            # Parse coverage
            coverage = self._parse_coverage(Path(repo_path) / ".coverage.json")

            return VerificationResult(
                passed=passed,
                tests_run=self._count_tests(result.stdout),
                tests_passed=self._count_tests(result.stdout, status="passed"),
                tests_failed=self._count_tests(result.stdout, status="failed"),
                coverage_overall=coverage,
            )

        except subprocess.TimeoutExpired:
            logger.error("Tests timed out after %ds", self.timeout)
            return VerificationResult(
                passed=False, failures=[f"Test timeout after {self.timeout}s"]
            )
        except FileNotFoundError:
            logger.error("pytest not found — install with: pip install pytest")
            return VerificationResult(
                passed=False, failures=["pytest not installed"]
            )

    def _discover_tests(
        self, changed_files: list[Path], repo_path: Path
    ) -> list[Path]:
        """Find tests covering changed files using naming conventions."""
        test_files: set[Path] = set()
        tests_dir = repo_path / "tests"

        for changed in changed_files:
            # Convention: test_<filename>.py
            test_name = f"test_{changed.stem}.py"
            for test_file in tests_dir.rglob(test_name):
                test_files.add(test_file)

            # Broader pattern match
            for test_file in tests_dir.rglob("test_*.py"):
                if changed.stem in test_file.stem:
                    test_files.add(test_file)

        return sorted(test_files)

    @staticmethod
    def _parse_coverage(coverage_file: Path) -> float:
        """Parse coverage percentage from JSON report."""
        if not coverage_file.exists():
            return 0.0
        try:
            with open(coverage_file) as f:
                data = json.load(f)
            return data.get("totals", {}).get("percent_covered", 0.0)
        except (json.JSONDecodeError, KeyError):
            return 0.0

    @staticmethod
    def _count_tests(output: str, status: str | None = None) -> int:
        """Count tests from pytest output (approximate)."""
        # Simple heuristic — will be replaced with proper XML parsing
        for line in output.splitlines():
            if "passed" in line or "failed" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if status and part == status and i > 0:
                        try:
                            return int(parts[i - 1])
                        except ValueError:
                            pass
                    elif status is None and part in ("passed", "failed"):
                        try:
                            return int(parts[i - 1])
                        except ValueError:
                            pass
        return 0
