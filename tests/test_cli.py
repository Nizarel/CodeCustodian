"""CLI tests for Phase 10 command implementation."""

from __future__ import annotations

import json
from pathlib import Path

from codecustodian.cli.main import app
from codecustodian.models import Finding, FindingType, SeverityLevel


def _load_json_from_output(output: str):
    """Extract final JSON payload from mixed stdout that may include logs."""
    decoder = json.JSONDecoder()
    text = output.strip()
    for index, char in enumerate(text):
        if char not in "[{":
            continue
        try:
            payload, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if text[index + end :].strip() == "":
            return payload
    raise AssertionError(f"No JSON payload found in output: {output}")


def test_version_command(cli_runner) -> None:
    result = cli_runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "codecustodian 0.15.1" in result.stdout


def test_validate_command_success(cli_runner) -> None:
    result = cli_runner.invoke(app, ["validate", "--path", ".codecustodian.yml"])
    assert result.exit_code == 0
    assert "Configuration is valid" in result.stdout


def test_init_creates_config(cli_runner, tmp_path: Path) -> None:
    result = cli_runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / ".codecustodian.yml").exists()
    assert (tmp_path / ".github" / "workflows" / "codecustodian.yml").exists()


def test_init_fails_when_config_exists(cli_runner, tmp_path: Path) -> None:
    (tmp_path / ".codecustodian.yml").write_text('version: "1.0"\n')
    result = cli_runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 1
    assert "already exists" in result.stdout


def test_scan_outputs_json(cli_runner) -> None:
    result = cli_runner.invoke(
        app,
        [
            "scan",
            "--repo-path",
            "tests/fixtures/sample_repo",
            "--output-format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = _load_json_from_output(result.stdout)
    assert isinstance(payload, list)
    assert any(item["type"] == "security" for item in payload)


def test_scan_outputs_sarif(cli_runner) -> None:
    result = cli_runner.invoke(
        app,
        [
            "scan",
            "--repo-path",
            "tests/fixtures/sample_repo",
            "--output-format",
            "sarif",
        ],
    )
    assert result.exit_code == 0
    payload = _load_json_from_output(result.stdout)
    assert payload["version"] == "2.1.0"
    assert payload["runs"]
    assert payload["runs"][0]["tool"]["driver"]["name"] == "CodeCustodian"
    assert payload["runs"][0]["results"]


def test_run_outputs_json(cli_runner, monkeypatch) -> None:
    class _DummyResult:
        def model_dump_json(self, **_kwargs):
            return json.dumps({"findings": [], "plans": []})

    class _DummyPipeline:
        def __init__(self, **_kwargs):
            pass

        async def run(self):
            return _DummyResult()

    monkeypatch.setattr("codecustodian.pipeline.Pipeline", _DummyPipeline)

    result = cli_runner.invoke(
        app,
        [
            "run",
            "--repo-path",
            ".",
            "--config",
            ".codecustodian.yml",
            "--dry-run",
            "--output-format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = _load_json_from_output(result.stdout)
    assert payload == {"findings": [], "plans": []}


def test_onboard_repo_outputs_json(cli_runner, tmp_path: Path) -> None:
    result = cli_runner.invoke(
        app,
        ["onboard", "--repo-path", str(tmp_path), "--template", "full_scan"],
    )
    assert result.exit_code == 0
    payload = _load_json_from_output(result.stdout)
    assert payload["status"] == "configured"


def test_report_outputs_json(cli_runner) -> None:
    result = cli_runner.invoke(app, ["report", "--format", "json"])
    assert result.exit_code == 0
    payload = _load_json_from_output(result.stdout)
    assert "net_roi_pct" in payload
    assert "total_operational_cost" in payload


def test_findings_filter_type_json(cli_runner) -> None:
    result = cli_runner.invoke(
        app,
        [
            "findings",
            "--repo-path",
            "tests/fixtures/sample_repo",
            "--type",
            "security",
            "--output-format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = _load_json_from_output(result.stdout)
    assert payload
    assert all(item["type"] == "security" for item in payload)


def test_findings_filter_type_sarif(cli_runner) -> None:
    result = cli_runner.invoke(
        app,
        [
            "findings",
            "--repo-path",
            "tests/fixtures/sample_repo",
            "--type",
            "security",
            "--output-format",
            "sarif",
        ],
    )
    assert result.exit_code == 0
    payload = _load_json_from_output(result.stdout)
    run = payload["runs"][0]
    assert run["tool"]["driver"]["rules"]
    assert run["results"]
    assert all(item["ruleId"] == "security" for item in run["results"])


def test_create_prs_outputs_summary(cli_runner, monkeypatch) -> None:
    class _DummyResult:
        findings = [1, 2]  # noqa: RUF012
        plans = [1]  # noqa: RUF012
        proposals = []  # noqa: RUF012
        errors = []  # noqa: RUF012
        prs_created = 1

    class _DummyPipeline:
        def __init__(self, **_kwargs):
            pass

        async def run(self):
            return _DummyResult()

    monkeypatch.setattr("codecustodian.pipeline.Pipeline", _DummyPipeline)

    result = cli_runner.invoke(
        app,
        ["create-prs", "--repo-path", ".", "--config", ".codecustodian.yml", "--top", "3"],
    )
    assert result.exit_code == 0
    payload = _load_json_from_output(result.stdout)
    assert payload["prs_created"] == 1
    assert payload["findings"] == 2


def test_heal_outputs_detected_signals_as_json(cli_runner, tmp_path: Path) -> None:
    log_file = tmp_path / "ci.log"
    log_file.write_text(
        "Ruff check failed with F401\n"
        "mypy src/codecustodian\n"
        "error: Incompatible return value type\n",
        encoding="utf-8",
    )

    result = cli_runner.invoke(
        app,
        ["heal", "--failure-log", str(log_file), "--output-format", "json"],
    )
    assert result.exit_code == 0
    payload = _load_json_from_output(result.stdout)
    assert payload["status"] == "signals-detected"
    keys = {item["key"] for item in payload["signals"]}
    assert "ruff" in keys
    assert "mypy" in keys
    assert payload["patch_candidates"]
    patch_ids = {item["id"] for item in payload["patch_candidates"]}
    assert "mypy-incompatible-return" in patch_ids


def test_heal_fails_for_missing_log_file(cli_runner) -> None:
    result = cli_runner.invoke(
        app,
        ["heal", "--failure-log", "missing-ci.log", "--output-format", "json"],
    )
    assert result.exit_code != 0
    assert "Failure log file not found" in result.output


def test_review_pr_outputs_json(cli_runner) -> None:
    result = cli_runner.invoke(
        app,
        [
            "review-pr",
            "--repo-path",
            "tests/fixtures/sample_repo",
            "--output-format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = _load_json_from_output(result.stdout)
    assert "status" in payload
    assert "risk_level" in payload
    assert "total_findings" in payload
    assert "suggested_labels" in payload


def test_review_pr_marks_security_as_blocking_with_label(cli_runner) -> None:
    result = cli_runner.invoke(
        app,
        [
            "review-pr",
            "--repo-path",
            "tests/fixtures/sample_repo",
            "--output-format",
            "json",
            "--block-on",
            "critical,high",
        ],
    )
    assert result.exit_code == 0
    payload = _load_json_from_output(result.stdout)
    assert payload["blocking_issues"] >= 1
    assert "needs-fix" in payload["suggested_labels"]
    assert "security-risk" in payload["suggested_labels"]


def test_review_pr_custom_block_on_critical_only(cli_runner) -> None:
    result = cli_runner.invoke(
        app,
        [
            "review-pr",
            "--repo-path",
            "tests/fixtures/sample_repo",
            "--output-format",
            "json",
            "--block-on",
            "critical",
        ],
    )
    assert result.exit_code == 0
    payload = _load_json_from_output(result.stdout)
    assert payload["blocking_issues"] == payload["by_severity"].get("critical", 0)


def test_review_pr_rejects_invalid_block_on_value(cli_runner) -> None:
    result = cli_runner.invoke(
        app,
        [
            "review-pr",
            "--repo-path",
            "tests/fixtures/sample_repo",
            "--output-format",
            "json",
            "--block-on",
            "urgent",
        ],
    )
    assert result.exit_code != 0
    assert "--block-on must only contain" in result.output


def test_review_pr_includes_healing_plan(cli_runner, tmp_path: Path) -> None:
    healing_plan = tmp_path / "healing-plan.json"
    healing_plan.write_text(
        json.dumps(
            {
                "status": "signals-detected",
                "signals": [{"key": "ruff", "title": "Ruff lint failure"}],
                "recommended_commands": ["ruff check src tests --fix"],
                "patch_candidates": [{"id": "ruff-f401-remove-unused-import"}],
            }
        ),
        encoding="utf-8",
    )

    result = cli_runner.invoke(
        app,
        [
            "review-pr",
            "--repo-path",
            "tests/fixtures/sample_repo",
            "--output-format",
            "json",
            "--healing-plan-file",
            str(healing_plan),
        ],
    )
    assert result.exit_code == 0
    payload = _load_json_from_output(result.stdout)
    assert "healing_plan" in payload
    assert payload["healing_plan"]["status"] == "signals-detected"


def test_review_pr_outputs_table(cli_runner) -> None:
    result = cli_runner.invoke(
        app,
        [
            "review-pr",
            "--repo-path",
            "tests/fixtures/sample_repo",
            "--output-format",
            "table",
        ],
    )
    assert result.exit_code == 0
    assert "PR Review Status" in result.stdout


def test_status_command_renders_with_mocked_services(cli_runner, monkeypatch) -> None:
    finding = Finding(
        type=FindingType.SECURITY,
        severity=SeverityLevel.HIGH,
        file="src/security.py",
        line=12,
        description="Potential vulnerability",
    )

    monkeypatch.setattr(
        "codecustodian.cli.main._scan_findings", lambda *_args, **_kwargs: [finding]
    )

    class _DummyBudgetSummary:
        total_spent = 12.5
        remaining = 487.5
        utilization_pct = 2.5

    class _DummyBudgetManager:
        def get_summary(self):
            return _DummyBudgetSummary()

    class _DummySLA:
        total_runs = 2
        success_rate = 100.0
        avg_duration_seconds = 1.5
        total_prs = 1

    class _DummySLAReporter:
        def generate_report(self, **_kwargs):
            return _DummySLA()

        def close(self):
            return None

    monkeypatch.setattr(
        "codecustodian.enterprise.budget_manager.BudgetManager", _DummyBudgetManager
    )
    monkeypatch.setattr("codecustodian.enterprise.sla_reporter.SLAReporter", _DummySLAReporter)

    result = cli_runner.invoke(
        app, ["status", "--repo-path", ".", "--config", ".codecustodian.yml"]
    )
    assert result.exit_code == 0
    assert "Operational Status" in result.stdout


def test_interactive_exits_immediately(cli_runner, monkeypatch) -> None:
    class _DummyPrompt:
        def execute(self):
            return "Exit"

    class _DummyInquirer:
        @staticmethod
        def select(**_kwargs):
            return _DummyPrompt()

    class _DummyModule:
        inquirer = _DummyInquirer

    import sys

    monkeypatch.setitem(sys.modules, "InquirerPy", _DummyModule)
    result = cli_runner.invoke(
        app, ["interactive", "--repo-path", ".", "--config", ".codecustodian.yml"]
    )
    assert result.exit_code == 0
