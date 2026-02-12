"""Tests for the Pipeline orchestrator."""

from __future__ import annotations

import pytest

from codecustodian.config.schema import CodeCustodianConfig
from codecustodian.exceptions import ApprovalRequiredError
from codecustodian.models import (
    Finding,
    FindingType,
    ProposalResult,
    RefactoringPlan,
    SeverityLevel,
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
