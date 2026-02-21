"""Tests for the Pipeline orchestrator."""

from __future__ import annotations

import pytest

from codecustodian.config.schema import CodeCustodianConfig
from codecustodian.exceptions import ApprovalRequiredError
from codecustodian.models import (
    ExecutionResult,
    FileChange,
    Finding,
    FindingType,
    ProposalResult,
    PullRequestInfo,
    RefactoringPlan,
    SeverityLevel,
    VerificationResult,
)
from codecustodian.pipeline import Pipeline


def _make_finding(**kwargs) -> Finding:
    defaults = dict(
        type=FindingType.CODE_SMELL,
        severity=SeverityLevel.MEDIUM,
        file="src/main.py",
        line=10,
        description="test finding",
    )
    defaults.update(kwargs)
    return Finding(**defaults)


class TestPipelineInit:
    def test_create_with_defaults(self):
        config = CodeCustodianConfig()
        pipeline = Pipeline(config=config, repo_path="/tmp/repo")
        assert pipeline.repo_path == "/tmp/repo"
        assert pipeline.dry_run is False

    def test_create_dry_run(self):
        config = CodeCustodianConfig()
        pipeline = Pipeline(config=config, repo_path="/tmp/repo", dry_run=True)
        assert pipeline.dry_run is True


class TestPipelineRun:
    @pytest.mark.asyncio
    async def test_run_empty_repo(self):
        """Pipeline runs to completion even with no findings."""
        config = CodeCustodianConfig()
        pipeline = Pipeline(config=config, repo_path="/tmp/empty")
        result = await pipeline.run()
        assert result.total_findings == 0
        assert result.prs_created == 0
        assert result.total_duration_seconds > 0
        assert result.completed_at is not None


class TestPipelineDedup:
    def test_dedup_removes_duplicates(self):
        config = CodeCustodianConfig()
        pipeline = Pipeline(config=config, repo_path="/tmp/repo")

        f1 = _make_finding(description="dup")
        f2 = _make_finding(description="dup")  # same dedup_key
        f3 = _make_finding(description="unique")

        result = pipeline._dedup([f1, f2, f3])
        assert len(result) == 2

    def test_dedup_preserves_unique(self):
        config = CodeCustodianConfig()
        pipeline = Pipeline(config=config, repo_path="/tmp/repo")

        findings = [_make_finding(description=f"issue {i}") for i in range(5)]
        result = pipeline._dedup(findings)
        assert len(result) == 5


class TestPipelinePrioritize:
    def test_prioritize_by_score(self):
        config = CodeCustodianConfig()
        pipeline = Pipeline(config=config, repo_path="/tmp/repo")

        low = _make_finding(priority_score=1.0, business_impact_score=0.0)
        high = _make_finding(priority_score=5.0, business_impact_score=3.0)
        mid = _make_finding(priority_score=3.0, business_impact_score=1.0)

        result = pipeline._prioritize([low, high, mid])
        assert result[0].priority_score == 5.0  # highest combined score first


class TestPipelineGroupFindings:
    def test_group_by_directory(self):
        config = CodeCustodianConfig()
        pipeline = Pipeline(config=config, repo_path="/tmp/repo")

        findings = [
            _make_finding(file="src/a.py"),
            _make_finding(file="src/b.py"),
            _make_finding(file="tests/test_a.py"),
        ]
        batches = pipeline._group_findings(findings)
        assert len(batches) >= 1
        # All findings are accounted for
        total = sum(len(b) for b in batches)
        assert total == 3

    def test_respects_max_files_per_pr(self):
        config = CodeCustodianConfig()
        config.behavior.max_files_per_pr = 2
        pipeline = Pipeline(config=config, repo_path="/tmp/repo")

        findings = [_make_finding(file=f"src/f{i}.py") for i in range(5)]
        batches = pipeline._group_findings(findings)
        for batch in batches:
            assert len(batch) <= 2


class TestPipelineProposalMode:
    def test_should_create_proposal_low_confidence(self):
        config = CodeCustodianConfig()
        config.behavior.proposal_mode_threshold = 5
        pipeline = Pipeline(config=config, repo_path="/tmp/repo")

        finding = _make_finding()
        plan = RefactoringPlan(finding_id="f1", summary="test", confidence_score=3)
        assert pipeline._should_create_proposal(finding, plan) is True

    def test_should_not_create_proposal_high_confidence(self):
        config = CodeCustodianConfig()
        pipeline = Pipeline(config=config, repo_path="/tmp/repo")

        finding = _make_finding()
        plan = RefactoringPlan(finding_id="f1", summary="test", confidence_score=9)
        assert pipeline._should_create_proposal(finding, plan) is False

    def test_create_proposal_returns_proposal_result(self):
        config = CodeCustodianConfig()
        pipeline = Pipeline(config=config, repo_path="/tmp/repo")

        finding = _make_finding()
        plan = RefactoringPlan(finding_id="f1", summary="Fix it", confidence_score=4)

        proposal = pipeline._create_proposal(finding, plan)
        assert isinstance(proposal, ProposalResult)
        assert proposal.is_proposal_only is True
        assert len(proposal.risks) >= 1


class TestPipelineApprovalGate:
    def test_check_approval_no_requirement(self):
        config = CodeCustodianConfig()
        config.approval.require_plan_approval = False
        pipeline = Pipeline(config=config, repo_path="/tmp/repo")

        plan = RefactoringPlan(finding_id="f1", summary="test", confidence_score=8)
        assert pipeline._check_approval(plan) is True

    def test_check_approval_raises_when_required(self):
        config = CodeCustodianConfig()
        config.approval.require_plan_approval = True
        pipeline = Pipeline(config=config, repo_path="/tmp/repo")

        plan = RefactoringPlan(finding_id="f1", summary="test", confidence_score=8)
        with pytest.raises(ApprovalRequiredError):
            pipeline._check_approval(plan)


class TestPipelineProcessFinding:
    @pytest.mark.asyncio
    async def test_plan_graceful_when_sdk_unavailable(self, monkeypatch):
        """When Copilot SDK is unavailable, _plan returns None (no crash)."""
        config = CodeCustodianConfig()
        pipeline = Pipeline(config=config, repo_path="/tmp/repo")
        finding = _make_finding(description="sdk unavailable")

        # Simulate the SDK being uninstallable by making the constructor raise
        class FakeClient:
            def __init__(self, *a, **kw):
                raise ImportError("no sdk")

        monkeypatch.setattr(
            "codecustodian.planner.copilot_client.CopilotPlannerClient",
            FakeClient,
        )

        result = await pipeline._plan(finding)
        assert result is None

    def test_build_code_context(self, tmp_path):
        """_build_code_context reads source code around the finding line."""
        src = tmp_path / "src" / "main.py"
        src.parent.mkdir(parents=True)
        src.write_text("import os\n\ndef foo():\n    pass\n\ndef bar():\n    return 1\n")

        config = CodeCustodianConfig()
        pipeline = Pipeline(config=config, repo_path=str(tmp_path))
        finding = _make_finding(file="src/main.py", line=4)

        ctx = pipeline._build_code_context(finding)
        assert "def foo" in ctx.source_code
        assert ctx.file_path == "src/main.py"
        assert len(ctx.imports) >= 1  # "import os"

    @pytest.mark.asyncio
    async def test_process_finding_dry_run_records_plan(self, monkeypatch):
        config = CodeCustodianConfig()
        pipeline = Pipeline(config=config, repo_path="/tmp/repo", dry_run=True)
        finding = _make_finding(description="dry-run finding")

        async def _fake_plan(_self, _finding):
            return RefactoringPlan(
                finding_id=_finding.id,
                summary="test plan",
                confidence_score=8,
                changes=[
                    FileChange(
                        file_path=_finding.file,
                        change_type="replace",
                        old_content="x",
                        new_content="y",
                    )
                ],
            )

        monkeypatch.setattr(Pipeline, "_plan", _fake_plan)

        await pipeline._process_finding(finding)

        assert len(pipeline._result.plans) == 1
        assert len(pipeline._result.executions) == 0

    @pytest.mark.asyncio
    async def test_process_finding_low_confidence_creates_proposal(self, monkeypatch):
        config = CodeCustodianConfig()
        config.behavior.proposal_mode_threshold = 5
        pipeline = Pipeline(config=config, repo_path="/tmp/repo", dry_run=False)
        finding = _make_finding(description="proposal finding")

        async def _fake_plan(_self, _finding):
            return RefactoringPlan(
                finding_id=_finding.id,
                summary="low confidence plan",
                confidence_score=3,
            )

        monkeypatch.setattr(Pipeline, "_plan", _fake_plan)

        await pipeline._process_finding(finding)

        assert len(pipeline._result.proposals) == 1
        assert pipeline._result.proposals[0].is_proposal_only is True

    @pytest.mark.asyncio
    async def test_process_finding_approval_required_adds_error(self, monkeypatch):
        config = CodeCustodianConfig()
        config.approval.require_plan_approval = True
        pipeline = Pipeline(config=config, repo_path="/tmp/repo", dry_run=False)
        finding = _make_finding(description="approval finding")

        async def _fake_plan(_self, _finding):
            return RefactoringPlan(
                finding_id=_finding.id,
                summary="approval plan",
                confidence_score=9,
            )

        monkeypatch.setattr(Pipeline, "_plan", _fake_plan)

        await pipeline._process_finding(finding)

        assert pipeline._result.errors
        assert "awaiting approval" in pipeline._result.errors[0]

    @pytest.mark.asyncio
    async def test_process_finding_execute_verify_pr_success(self, monkeypatch):
        config = CodeCustodianConfig()
        config.approval.require_plan_approval = False
        pipeline = Pipeline(config=config, repo_path="/tmp/repo", dry_run=False)
        finding = _make_finding(description="success finding")

        async def _fake_plan(_self, _finding):
            return RefactoringPlan(
                finding_id=_finding.id,
                summary="success plan",
                confidence_score=9,
                changes=[
                    FileChange(
                        file_path=_finding.file,
                        change_type="replace",
                        old_content="a",
                        new_content="b",
                    )
                ],
            )

        async def _fake_execute(_self, plan):
            return ExecutionResult(
                plan_id=plan.id,
                success=True,
                changes_applied=plan.changes,
                branch_name="branch/test",
                commit_sha="123",
            )

        async def _fake_verify(_self, _execution):
            return VerificationResult(passed=True, tests_run=1, tests_passed=1)

        async def _fake_create_pr(_self, _finding, _plan, _execution, _verification):
            return PullRequestInfo(number=1, url="https://example/pr/1", title="Test PR")

        monkeypatch.setattr(Pipeline, "_plan", _fake_plan)
        monkeypatch.setattr(Pipeline, "_execute", _fake_execute)
        monkeypatch.setattr(Pipeline, "_verify", _fake_verify)
        monkeypatch.setattr(Pipeline, "_create_pr", _fake_create_pr)

        await pipeline._process_finding(finding)

        assert len(pipeline._result.executions) == 1
        assert len(pipeline._result.verifications) == 1
        assert pipeline._result.prs_created == 1

    @pytest.mark.asyncio
    async def test_process_finding_verify_fail_rolls_back_to_proposal(self, monkeypatch):
        config = CodeCustodianConfig()
        config.approval.require_plan_approval = False
        pipeline = Pipeline(config=config, repo_path="/tmp/repo", dry_run=False)
        finding = _make_finding(description="verify fail finding")
        rollback_called = {"called": False}

        async def _fake_plan(_self, _finding):
            return RefactoringPlan(
                finding_id=_finding.id,
                summary="verify-fail plan",
                confidence_score=9,
                changes=[
                    FileChange(
                        file_path=_finding.file,
                        change_type="replace",
                        old_content="a",
                        new_content="b",
                    )
                ],
            )

        async def _fake_execute(_self, plan):
            return ExecutionResult(
                plan_id=plan.id,
                success=True,
                changes_applied=plan.changes,
                branch_name="branch/test",
                commit_sha="123",
                backup_paths=["/tmp/backup"],
            )

        async def _fake_verify(_self, _execution):
            return VerificationResult(passed=False, tests_run=1, tests_failed=1)

        async def _fake_rollback(_self, _execution):
            rollback_called["called"] = True

        monkeypatch.setattr(Pipeline, "_plan", _fake_plan)
        monkeypatch.setattr(Pipeline, "_execute", _fake_execute)
        monkeypatch.setattr(Pipeline, "_verify", _fake_verify)
        monkeypatch.setattr(Pipeline, "_rollback", _fake_rollback)

        await pipeline._process_finding(finding)

        assert rollback_called["called"] is True
        assert len(pipeline._result.proposals) == 1
        assert pipeline._result.prs_created == 0
