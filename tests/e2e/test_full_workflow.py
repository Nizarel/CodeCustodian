"""End-to-end CLI workflow tests on fixture repository."""

from __future__ import annotations

import json

import pytest

from codecustodian.cli.main import app


FIXTURE_REPO = "tests/fixtures/sample_repo"


def _load_json_from_output(output: str):
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


@pytest.mark.e2e
def test_scan_command_detects_fixture_findings(cli_runner) -> None:
    result = cli_runner.invoke(
        app,
        [
            "scan",
            "--repo-path",
            FIXTURE_REPO,
            "--output-format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = _load_json_from_output(result.stdout)
    assert isinstance(payload, list)
    assert len(payload) >= 3
    finding_types = {item["type"] for item in payload}
    assert "security" in finding_types
    assert "todo_comment" in finding_types


@pytest.mark.e2e
def test_run_dry_run_outputs_pipeline_result_json(cli_runner) -> None:
    result = cli_runner.invoke(
        app,
        [
            "run",
            "--repo-path",
            FIXTURE_REPO,
            "--config",
            f"{FIXTURE_REPO}/.codecustodian.yml",
            "--dry-run",
            "--output-format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = _load_json_from_output(result.stdout)
    assert "findings" in payload
    assert "plans" in payload
    assert isinstance(payload["findings"], list)
