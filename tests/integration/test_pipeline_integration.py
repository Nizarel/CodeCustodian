"""Integration tests for pipeline workflow on fixture repository."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from codecustodian.config.schema import CodeCustodianConfig
from codecustodian.models import (
    ChangeType,
    ExecutionResult,
    FileChange,
    PullRequestInfo,
    RefactoringPlan,
    VerificationResult,
)
from codecustodian.pipeline import Pipeline

FIXTURE_REPO = Path("tests/fixtures/sample_repo")


def _prepare_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "sample_repo"
    shutil.copytree(FIXTURE_REPO, repo)
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "init"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return repo


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pipeline_run_with_fixture_repo_dry_run(tmp_path: Path, monkeypatch) -> None:
    repo = _prepare_repo(tmp_path)

    async def _fake_plan(self, finding):
        return RefactoringPlan(
            finding_id=finding.id,
            summary="Apply safe remediation",
            confidence_score=8,
            changes=[
                FileChange(
                    file_path=finding.file,
                    change_type=ChangeType.REPLACE,
                    old_content="TODO",
                    new_content="DONE",
                )
            ],
        )

    monkeypatch.setattr(Pipeline, "_plan", _fake_plan)

    config = CodeCustodianConfig.from_file(repo / ".codecustodian.yml")
    pipeline = Pipeline(config=config, repo_path=str(repo), dry_run=True)

    result = await pipeline.run()

    assert result.total_findings > 0
    assert len(result.plans) > 0
    assert result.prs_created == 0
    assert result.total_duration_seconds > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pipeline_full_path_with_mocked_execute_verify_pr(tmp_path: Path, monkeypatch) -> None:
    repo = _prepare_repo(tmp_path)

    async def _fake_plan(self, finding):
        return RefactoringPlan(
            finding_id=finding.id,
            summary="Apply safe remediation",
            confidence_score=9,
            changes=[
                FileChange(
                    file_path=finding.file,
                    change_type=ChangeType.REPLACE,
                    old_content="old",
                    new_content="new",
                )
            ],
        )

    async def _fake_execute(self, plan):
        return ExecutionResult(
            plan_id=plan.id,
            success=True,
            changes_applied=plan.changes,
            branch_name="tech-debt/test",
            commit_sha="abc123",
        )

    async def _fake_verify(self, execution):
        return VerificationResult(passed=True, tests_run=5, tests_passed=5)

    async def _fake_create_pr(self, finding, plan, execution, verification):
        return PullRequestInfo(number=1, url="https://example/pr/1", title="Test PR")

    monkeypatch.setattr(Pipeline, "_plan", _fake_plan)
    monkeypatch.setattr(Pipeline, "_execute", _fake_execute)
    monkeypatch.setattr(Pipeline, "_verify", _fake_verify)
    monkeypatch.setattr(Pipeline, "_create_pr", _fake_create_pr)

    config = CodeCustodianConfig.from_file(repo / ".codecustodian.yml")
    config.approval.require_plan_approval = False

    pipeline = Pipeline(config=config, repo_path=str(repo), dry_run=False)
    result = await pipeline.run()

    assert result.total_findings > 0
    assert len(result.executions) > 0
    assert len(result.verifications) > 0
    assert result.prs_created > 0
