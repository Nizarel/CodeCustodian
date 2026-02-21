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
    assert "codecustodian 0.10.0" in result.stdout


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
    (tmp_path / ".codecustodian.yml").write_text("version: \"1.0\"\n")
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


def test_create_prs_outputs_summary(cli_runner, monkeypatch) -> None:
    class _DummyResult:
        findings = [1, 2]
        plans = [1]
        proposals = []
        errors = []
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


def test_status_command_renders_with_mocked_services(cli_runner, monkeypatch) -> None:
    finding = Finding(
        type=FindingType.SECURITY,
        severity=SeverityLevel.HIGH,
        file="src/security.py",
        line=12,
        description="Potential vulnerability",
    )

    monkeypatch.setattr("codecustodian.cli.main._scan_findings", lambda *_args, **_kwargs: [finding])

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

    monkeypatch.setattr("codecustodian.enterprise.budget_manager.BudgetManager", _DummyBudgetManager)
    monkeypatch.setattr("codecustodian.enterprise.sla_reporter.SLAReporter", _DummySLAReporter)

    result = cli_runner.invoke(app, ["status", "--repo-path", ".", "--config", ".codecustodian.yml"])
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
    result = cli_runner.invoke(app, ["interactive", "--repo-path", ".", "--config", ".codecustodian.yml"])
    assert result.exit_code == 0
