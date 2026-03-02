"""Test runner — execute pytest via subprocess and collect results.

Uses subprocess.run for process isolation, JUnit XML for reliable
result parsing, and coverage delta for regression detection.
Discriminates pre-existing failures from new ones (FR-VERIFY-100).
"""

from __future__ import annotations

import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from codecustodian.logging import get_logger
from codecustodian.models import VerificationResult

logger = get_logger("verifier.test_runner")


class TestRunner:
    """Execute tests via subprocess and collect coverage metrics.

    Args:
        framework: Test framework (only ``pytest`` supported currently).
        timeout: Maximum seconds for test execution.
        coverage_threshold: Minimum coverage percentage.
        workers: Number of parallel workers (requires pytest-xdist).
    """

    def __init__(
        self,
        framework: str = "pytest",
        timeout: int = 300,
        coverage_threshold: int = 80,
        workers: int = 4,
    ) -> None:
        self.framework = framework
        self.timeout = timeout
        self.coverage_threshold = coverage_threshold
        self.workers = workers

    def run_tests(
        self,
        changed_files: list[Path],
        repo_path: str | Path,
        *,
        baseline_coverage: float | None = None,
    ) -> VerificationResult:
        """Run tests covering the changed files.

        Args:
            changed_files: Files that were modified.
            repo_path: Root path of the repository.
            baseline_coverage: Coverage percentage before changes
                (for delta calculation).

        Returns:
            VerificationResult with test counts, coverage, and failures.
        """
        repo = Path(repo_path)
        test_files = self._discover_tests(changed_files, repo)
        junit_xml = repo / ".codecustodian-junit.xml"
        coverage_json = repo / ".codecustodian-coverage.json"

        if not test_files:
            logger.info("No relevant tests found — running full suite")
            test_files = [repo / "tests"]

        args = [
            "pytest",
            "--verbose",
            "--tb=short",
            "--cov=src",
            f"--cov-report=json:{coverage_json}",
            f"--junitxml={junit_xml}",
            *[str(f) for f in test_files],
        ]

        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(repo),
            )

            # Parse JUnit XML for reliable results
            tests_run, tests_passed, tests_failed, tests_skipped, failure_details = (
                self._parse_junit_xml(junit_xml)
            )

            # Parse coverage
            coverage = self._parse_coverage(coverage_json)

            # Coverage delta
            coverage_delta = 0.0
            if baseline_coverage is not None:
                coverage_delta = coverage - baseline_coverage

            # Determine pass/fail
            passed = result.returncode == 0

            # Build failure list
            failures: list[str] = []
            if tests_failed > 0:
                failures.extend(failure_details)

            if baseline_coverage is not None and coverage_delta < 0:
                failures.append(
                    f"Coverage decreased by {abs(coverage_delta):.1f}% "
                    f"({baseline_coverage:.1f}% → {coverage:.1f}%)"
                )
                passed = False

            return VerificationResult(
                passed=passed,
                tests_run=tests_run,
                tests_passed=tests_passed,
                tests_failed=tests_failed,
                tests_skipped=tests_skipped,
                coverage_overall=coverage,
                coverage_delta=coverage_delta,
                failures=failures,
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
        finally:
            # Cleanup temp files
            junit_xml.unlink(missing_ok=True)
            coverage_json.unlink(missing_ok=True)

    def get_baseline_failures(self, repo_path: str | Path) -> set[str]:
        """Run full test suite to capture pre-existing failures (FR-VERIFY-100).

        Returns a set of test node IDs that fail before any changes.
        """
        repo = Path(repo_path)
        junit_xml = repo / ".codecustodian-baseline-junit.xml"

        try:
            subprocess.run(
                [
                    "pytest",
                    "--tb=no",
                    "-q",
                    f"--junitxml={junit_xml}",
                ],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(repo),
            )

            if not junit_xml.exists():
                return set()

            tree = ET.parse(junit_xml)
            root = tree.getroot()
            failures: set[str] = set()

            for testcase in root.iter("testcase"):
                if testcase.find("failure") is not None or testcase.find("error") is not None:
                    classname = testcase.get("classname", "")
                    name = testcase.get("name", "")
                    failures.add(f"{classname}::{name}")

            return failures
        except (subprocess.TimeoutExpired, FileNotFoundError, ET.ParseError):
            return set()
        finally:
            junit_xml.unlink(missing_ok=True)

    def _discover_tests(
        self, changed_files: list[Path], repo_path: Path
    ) -> list[Path]:
        """Find tests covering changed files using naming conventions."""
        test_files: set[Path] = set()
        tests_dir = repo_path / "tests"

        if not tests_dir.exists():
            return []

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
    def _parse_junit_xml(
        junit_path: Path,
    ) -> tuple[int, int, int, int, list[str]]:
        """Parse JUnit XML report for reliable test results.

        Returns:
            Tuple of (tests_run, passed, failed, skipped, failure_messages).
        """
        if not junit_path.exists():
            return 0, 0, 0, 0, []

        try:
            tree = ET.parse(junit_path)
            root = tree.getroot()

            tests_run = 0
            passed = 0
            failed = 0
            skipped = 0
            failure_messages: list[str] = []

            for testcase in root.iter("testcase"):
                tests_run += 1
                failure_el = testcase.find("failure")
                error_el = testcase.find("error")
                skip_el = testcase.find("skipped")

                if failure_el is not None:
                    failed += 1
                    name = testcase.get("name", "unknown")
                    msg = failure_el.get("message", "")[:200]
                    failure_messages.append(f"{name}: {msg}")
                elif error_el is not None:
                    failed += 1
                    name = testcase.get("name", "unknown")
                    msg = error_el.get("message", "")[:200]
                    failure_messages.append(f"{name}: {msg}")
                elif skip_el is not None:
                    skipped += 1
                else:
                    passed += 1

            return tests_run, passed, failed, skipped, failure_messages

        except ET.ParseError:
            logger.warning("Failed to parse JUnit XML at %s", junit_path)
            return 0, 0, 0, 0, []

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
