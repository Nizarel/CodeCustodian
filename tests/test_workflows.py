"""Workflow structure regression tests."""

from __future__ import annotations

from pathlib import Path

import yaml


def _load_workflow(path: str) -> dict:
    content = Path(path).read_text(encoding="utf-8")
    parsed = yaml.safe_load(content)
    assert isinstance(parsed, dict)
    return parsed


def test_pr_review_bot_workflow_structure() -> None:
    workflow = _load_workflow(".github/workflows/pr-review-bot.yml")

    triggers = workflow.get("on") or workflow.get(True, {})
    assert "pull_request" in triggers
    assert "workflow_run" in triggers
    assert "workflow_dispatch" in triggers

    permissions = workflow.get("permissions", {})
    assert permissions.get("pull-requests") == "write"
    assert permissions.get("issues") == "write"

    jobs = workflow.get("jobs", {})
    assert "review" in jobs
    steps = jobs["review"].get("steps", [])
    step_names = {step.get("name") for step in steps if isinstance(step, dict)}

    assert "Build PR review summary" in step_names
    assert "Upsert PR review comment" in step_names
    assert "Sync PR labels from review summary" in step_names
    assert "Enforce blocking findings gate" in step_names


def test_ci_self_heal_workflow_uses_marker_comment() -> None:
    workflow = _load_workflow(".github/workflows/ci-self-heal.yml")
    jobs = workflow.get("jobs", {})
    assert "analyze-failure" in jobs

    steps = jobs["analyze-failure"].get("steps", [])
    comment_step = next(
        step
        for step in steps
        if isinstance(step, dict) and step.get("name") == "Comment healing plan on PR"
    )
    script = comment_step.get("with", {}).get("script", "")
    assert "codecustodian-healing-plan" in script
