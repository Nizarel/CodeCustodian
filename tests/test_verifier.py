"""Tests for verifier modules: test runner, linter, and security scanner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codecustodian.models import SecurityIssue
from codecustodian.verifier import linter as linter_mod
from codecustodian.verifier import security_scanner as security_mod
from codecustodian.verifier import test_runner as test_runner_mod


class _Completed:
    def __init__(self, returncode: int = 0, stdout: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout


class TestTestRunnerPaths:
    def test_run_tests_success_with_delta(self, tmp_path: Path, monkeypatch) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        tests_dir = repo / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_demo.py").write_text("def test_demo():\n    assert True\n")

        runner = test_runner_mod.TestRunner(timeout=10)

        def _fake_run(args, capture_output, text, timeout, cwd):
            junit_arg = [item for item in args if str(item).startswith("--junitxml=")][0]
            cov_arg = [item for item in args if str(item).startswith("--cov-report=json:")][0]
            junit_path = Path(junit_arg.split("=", 1)[1])
            cov_path = Path(cov_arg.split("json:", 1)[1])

            junit_path.write_text(
                """<?xml version=\"1.0\" encoding=\"utf-8\"?>
<testsuite tests=\"1\" errors=\"0\" failures=\"0\" skipped=\"0\"> 
  <testcase classname=\"tests.test_demo\" name=\"test_demo\" time=\"0.1\"/>
</testsuite>
"""
            )
            cov_path.write_text(json.dumps({"totals": {"percent_covered": 84.0}}))
            return _Completed(returncode=0, stdout="ok")

        monkeypatch.setattr("codecustodian.verifier.test_runner.subprocess.run", _fake_run)

        result = runner.run_tests([Path("src/demo.py")], repo, baseline_coverage=80.0)

        assert result.passed is True
        assert result.tests_run == 1
        assert result.tests_passed == 1
        assert result.coverage_overall == 84.0
        assert result.coverage_delta == 4.0

    def test_run_tests_timeout(self, tmp_path: Path, monkeypatch) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()

        runner = test_runner_mod.TestRunner(timeout=1)

        def _convert_timeout(*_args, **_kwargs):
            import subprocess

            raise subprocess.TimeoutExpired(cmd="pytest", timeout=1)

        monkeypatch.setattr("codecustodian.verifier.test_runner.subprocess.run", _convert_timeout)

        result = runner.run_tests([Path("src/demo.py")], repo)
        assert result.passed is False
        assert "timeout" in result.failures[0].lower()

    def test_get_baseline_failures(self, tmp_path: Path, monkeypatch) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()

        runner = test_runner_mod.TestRunner(timeout=10)

        def _fake_run(args, capture_output, text, timeout, cwd):
            junit_arg = [item for item in args if str(item).startswith("--junitxml=")][0]
            junit_path = Path(junit_arg.split("=", 1)[1])
            junit_path.write_text(
                """<?xml version=\"1.0\" encoding=\"utf-8\"?>
<testsuite tests=\"2\" errors=\"0\" failures=\"1\" skipped=\"0\"> 
  <testcase classname=\"tests.test_a\" name=\"test_pass\" time=\"0.1\"/>
  <testcase classname=\"tests.test_a\" name=\"test_fail\" time=\"0.1\"> 
    <failure message=\"assert\">trace</failure>
  </testcase>
</testsuite>
"""
            )
            return _Completed(returncode=1, stdout="failed")

        monkeypatch.setattr("codecustodian.verifier.test_runner.subprocess.run", _fake_run)

        failures = runner.get_baseline_failures(repo)
        assert "tests.test_a::test_fail" in failures

    def test_run_tests_fails_on_coverage_drop(self, tmp_path: Path, monkeypatch) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        tests_dir = repo / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_demo.py").write_text("def test_demo():\n    assert True\n")

        runner = test_runner_mod.TestRunner(timeout=10)

        def _fake_run(args, capture_output, text, timeout, cwd):
            junit_arg = [item for item in args if str(item).startswith("--junitxml=")][0]
            cov_arg = [item for item in args if str(item).startswith("--cov-report=json:")][0]
            junit_path = Path(junit_arg.split("=", 1)[1])
            cov_path = Path(cov_arg.split("json:", 1)[1])
            junit_path.write_text(
                """<?xml version=\"1.0\" encoding=\"utf-8\"?>
<testsuite tests=\"1\" errors=\"0\" failures=\"0\" skipped=\"0\"> 
  <testcase classname=\"tests.test_demo\" name=\"test_demo\" time=\"0.1\"/>
</testsuite>
"""
            )
            cov_path.write_text(json.dumps({"totals": {"percent_covered": 70.0}}))
            return _Completed(returncode=0, stdout="ok")

        monkeypatch.setattr("codecustodian.verifier.test_runner.subprocess.run", _fake_run)

        result = runner.run_tests([Path("src/demo.py")], repo, baseline_coverage=80.0)
        assert result.passed is False
        assert any("Coverage decreased" in item for item in result.failures)

    def test_run_tests_handles_pytest_missing(self, tmp_path: Path, monkeypatch) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        runner = test_runner_mod.TestRunner(timeout=10)

        def _raise_missing(*_args, **_kwargs):
            raise FileNotFoundError()

        monkeypatch.setattr("codecustodian.verifier.test_runner.subprocess.run", _raise_missing)
        result = runner.run_tests([Path("src/demo.py")], repo)
        assert result.passed is False
        assert "pytest not installed" in result.failures[0]

    def test_discover_tests_when_tests_dir_missing(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        runner = test_runner_mod.TestRunner()
        found = runner._discover_tests([Path("src/demo.py")], repo)
        assert found == []

    def test_parse_junit_xml_parse_error(self, tmp_path: Path) -> None:
        bad_xml = tmp_path / "bad.xml"
        bad_xml.write_text("<testsuite><testcase></testsuite>")
        parsed = test_runner_mod.TestRunner._parse_junit_xml(bad_xml)
        assert parsed == (0, 0, 0, 0, [])

    def test_parse_coverage_invalid_json(self, tmp_path: Path) -> None:
        bad_json = tmp_path / "coverage.json"
        bad_json.write_text("{not valid")
        result = test_runner_mod.TestRunner._parse_coverage(bad_json)
        assert result == 0.0


class TestLinterRunnerPaths:
    def test_run_ruff_parses_json(self, monkeypatch) -> None:
        runner = linter_mod.LinterRunner()

        payload = [
            {
                "filename": "src/app.py",
                "location": {"row": 12},
                "code": "E501",
                "message": "Line too long",
            }
        ]

        monkeypatch.setattr(
            "codecustodian.verifier.linter.subprocess.run",
            lambda *_args, **_kwargs: _Completed(stdout=json.dumps(payload)),
        )

        violations = runner._run_ruff([Path("src/app.py")])
        assert len(violations) == 1
        assert violations[0].tool == "ruff"

    def test_run_mypy_parses_stdout(self, monkeypatch) -> None:
        runner = linter_mod.LinterRunner()

        stdout = "src/app.py:5: error: Incompatible types\n"
        monkeypatch.setattr(
            "codecustodian.verifier.linter.subprocess.run",
            lambda *_args, **_kwargs: _Completed(stdout=stdout),
        )

        violations = runner._run_mypy([Path("src/app.py")])
        assert len(violations) == 1
        assert violations[0].tool == "mypy"
        assert violations[0].line == 5

    def test_run_bandit_parses_results(self, monkeypatch) -> None:
        runner = linter_mod.LinterRunner()
        payload = {
            "results": [
                {
                    "filename": "src/security.py",
                    "line_number": 7,
                    "test_id": "B307",
                    "issue_text": "Use of eval",
                    "issue_severity": "HIGH",
                }
            ]
        }
        monkeypatch.setattr(
            "codecustodian.verifier.linter.subprocess.run",
            lambda *_args, **_kwargs: _Completed(stdout=json.dumps(payload)),
        )

        violations = runner._run_bandit([Path("src/security.py")])
        assert len(violations) == 1
        assert violations[0].tool == "bandit"
        assert violations[0].severity == "error"

    def test_run_ruff_handles_failures(self, monkeypatch) -> None:
        runner = linter_mod.LinterRunner()

        def _raise(*_args, **_kwargs):
            raise FileNotFoundError()

        monkeypatch.setattr("codecustodian.verifier.linter.subprocess.run", _raise)
        violations = runner._run_ruff([Path("src/app.py")])
        assert violations == []

    def test_get_baseline_delegates_to_run_all(self, monkeypatch) -> None:
        runner = linter_mod.LinterRunner()

        monkeypatch.setattr(linter_mod.LinterRunner, "run_all", lambda self, files: ["ok"])
        baseline = runner.get_baseline([Path("src/app.py")])
        assert baseline == ["ok"]

    def test_bandit_skips_non_python_files(self) -> None:
        runner = linter_mod.LinterRunner()
        violations = runner._run_bandit([Path("README.md")])
        assert violations == []

    def test_bandit_handles_invalid_json(self, monkeypatch) -> None:
        runner = linter_mod.LinterRunner()

        monkeypatch.setattr(
            "codecustodian.verifier.linter.subprocess.run",
            lambda *_args, **_kwargs: _Completed(stdout="{bad json"),
        )
        violations = runner._run_bandit([Path("src/security.py")])
        assert violations == []


class TestSecurityVerifierPaths:
    def test_verify_fails_on_high_severity(self, monkeypatch) -> None:
        verifier = security_mod.SecurityVerifier()

        monkeypatch.setattr(
            security_mod.SecurityVerifier,
            "_run_bandit",
            lambda self, files: [
                SecurityIssue(
                    file=str(files[0]),
                    line=1,
                    severity="HIGH",
                    description="Issue",
                    test_id="B307",
                    tool="bandit",
                )
            ],
        )

        result = verifier.verify([Path("src/security.py")])
        assert result["passed"] is False
        assert result["total_issues"] == 1

    def test_scan_dependencies_with_pip_audit_output(self, tmp_path: Path, monkeypatch) -> None:
        requirements = tmp_path / "requirements.txt"
        requirements.write_text("requests==2.19.0\n")

        payload = {
            "dependencies": [
                {
                    "name": "requests",
                    "version": "2.19.0",
                    "vulns": [
                        {
                            "id": "CVE-TEST-1",
                            "description": "known vulnerability",
                        }
                    ],
                }
            ]
        }

        monkeypatch.setattr(
            "codecustodian.verifier.security_scanner.subprocess.run",
            lambda *args, **kwargs: _Completed(stdout=json.dumps(payload)),
        )

        verifier = security_mod.SecurityVerifier()
        issues = verifier.scan_dependencies(requirements)
        assert len(issues) == 1
        assert issues[0].tool == "pip-audit"

    def test_scan_dependencies_handles_missing_tool(self, tmp_path: Path, monkeypatch) -> None:
        requirements = tmp_path / "requirements.txt"
        requirements.write_text("requests==2.19.0\n")

        def _raise(*_args, **_kwargs):
            raise FileNotFoundError()

        monkeypatch.setattr("codecustodian.verifier.security_scanner.subprocess.run", _raise)

        verifier = security_mod.SecurityVerifier()
        issues = verifier.scan_dependencies(requirements)
        assert issues == []

    def test_run_bandit_direct_parse(self, monkeypatch) -> None:
        payload = {
            "results": [
                {
                    "filename": "src/security.py",
                    "line_number": 5,
                    "issue_severity": "HIGH",
                    "issue_confidence": "HIGH",
                    "issue_text": "Use of eval",
                    "test_id": "B307",
                    "issue_cwe": {"id": 95},
                }
            ]
        }
        monkeypatch.setattr(
            "codecustodian.verifier.security_scanner.subprocess.run",
            lambda *_args, **_kwargs: _Completed(stdout=json.dumps(payload)),
        )
        verifier = security_mod.SecurityVerifier()
        issues = verifier._run_bandit([Path("src/security.py")])
        assert len(issues) == 1
        assert issues[0].tool == "bandit"

    def test_run_bandit_direct_failure(self, monkeypatch) -> None:
        def _raise(*_args, **_kwargs):
            raise FileNotFoundError()

        monkeypatch.setattr("codecustodian.verifier.security_scanner.subprocess.run", _raise)
        verifier = security_mod.SecurityVerifier()
        issues = verifier._run_bandit([Path("src/security.py")])
        assert issues == []

    @pytest.mark.asyncio
    async def test_async_stub_scans_return_empty(self) -> None:
        verifier = security_mod.SecurityVerifier()
        container_issues = await verifier.scan_containers("Dockerfile")
        secret_issues = await verifier.scan_secrets(".")
        assert container_issues == []
        assert secret_issues == []
