"""Tests for core data models."""

from __future__ import annotations

from pathlib import Path

import pytest

from codecustodian.models import (
    AlternativeSolution,
    ChangeType,
    CodeContext,
    ExecutionResult,
    FileChange,
    Finding,
    FindingType,
    PipelineResult,
    PipelineStage,
    ProposalResult,
    PullRequestInfo,
    RefactoringPlan,
    RiskLevel,
    SeverityLevel,
    VerificationResult,
)


class TestSeverityLevel:
    def test_values(self):
        assert SeverityLevel.CRITICAL == "critical"
        assert SeverityLevel.INFO == "info"

    def test_all_members(self):
        assert len(SeverityLevel) == 5


class TestFindingType:
    def test_values(self):
        assert FindingType.DEPRECATED_API == "deprecated_api"
        assert FindingType.SECURITY == "security"

    def test_all_members(self):
        assert len(FindingType) == 5


class TestFinding:
    def test_create_minimal(self):
        f = Finding(
            type=FindingType.CODE_SMELL,
            severity=SeverityLevel.MEDIUM,
            file="src/main.py",
            line=42,
            description="Function too long",
        )
        assert f.type == FindingType.CODE_SMELL
        assert f.severity == SeverityLevel.MEDIUM
        assert f.file == "src/main.py"
        assert f.line == 42
        assert len(f.id) == 12

    def test_auto_id(self):
        f1 = Finding(
            type=FindingType.CODE_SMELL,
            severity=SeverityLevel.LOW,
            file="a.py",
            line=1,
            description="test",
        )
        f2 = Finding(
            type=FindingType.CODE_SMELL,
            severity=SeverityLevel.LOW,
            file="a.py",
            line=1,
            description="test",
        )
        assert f1.id != f2.id

    def test_file_path_property(self):
        f = Finding(
            type=FindingType.SECURITY,
            severity=SeverityLevel.HIGH,
            file="src/utils/helpers.py",
            line=10,
            description="Hardcoded password",
        )
        assert f.file_path == Path("src/utils/helpers.py")

    def test_metadata(self):
        f = Finding(
            type=FindingType.DEPRECATED_API,
            severity=SeverityLevel.MEDIUM,
            file="a.py",
            line=1,
            description="test",
            metadata={"replacement": "new_api()"},
        )
        assert f.metadata["replacement"] == "new_api()"


class TestCodeContext:
    def test_create(self):
        ctx = CodeContext(
            file_path="src/main.py",
            source_code="def foo():\n    pass",
            start_line=1,
            end_line=2,
        )
        assert ctx.has_tests is False
        assert ctx.language == "python"


class TestFileChange:
    def test_replace(self):
        change = FileChange(
            file_path="src/main.py",
            change_type=ChangeType.REPLACE,
            old_content="old_api()",
            new_content="new_api()",
        )
        assert change.change_type == ChangeType.REPLACE


class TestRefactoringPlan:
    def test_create(self):
        plan = RefactoringPlan(
            finding_id="abc123",
            summary="Replace deprecated API",
            confidence_score=8,
        )
        assert plan.confidence_score == 8
        assert plan.risk_level == RiskLevel.LOW

    def test_confidence_bounds(self):
        with pytest.raises(Exception):
            RefactoringPlan(
                finding_id="x", summary="test", confidence_score=0
            )
        with pytest.raises(Exception):
            RefactoringPlan(
                finding_id="x", summary="test", confidence_score=11
            )


class TestExecutionResult:
    def test_success(self):
        result = ExecutionResult(plan_id="p1", success=True)
        assert result.success
        assert result.errors == []

    def test_failure(self):
        result = ExecutionResult(
            plan_id="p1",
            success=False,
            errors=["Syntax error"],
        )
        assert not result.success
        assert len(result.errors) == 1


class TestVerificationResult:
    def test_passed(self):
        vr = VerificationResult(
            passed=True,
            tests_run=10,
            tests_passed=10,
        )
        assert vr.passed
        assert vr.tests_failed == 0

    def test_with_lint_violations(self):
        vr = VerificationResult(
            passed=False,
            lint_passed=False,
            lint_violations=[{"file": "app.py", "code": "E501", "message": "line too long", "tool": "ruff"}],
        )
        assert not vr.lint_passed
        assert len(vr.lint_violations) == 1


class TestPipelineResult:
    def test_empty(self):
        result = PipelineResult()
        assert result.total_findings == 0
        assert result.success_rate == 0.0
        assert result.prs_created == 0
        assert result.findings_fixed == 0

    def test_with_data(self):
        result = PipelineResult(
            findings=[
                Finding(
                    type=FindingType.CODE_SMELL,
                    severity=SeverityLevel.LOW,
                    file="a.py",
                    line=1,
                    description="test",
                )
            ],
            executions=[
                ExecutionResult(plan_id="p1", success=True),
                ExecutionResult(plan_id="p2", success=False),
            ],
            pull_requests=[
                PullRequestInfo(number=1, url="https://github.com/test/pr/1", title="Fix"),
            ],
            total_duration_seconds=12.5,
        )
        assert result.total_findings == 1
        assert result.findings_fixed == 1
        assert result.success_rate == 50.0
        assert result.prs_created == 1
        assert result.duration_seconds == 12.5


class TestEnumCompleteness:
    def test_pipeline_stages(self):
        stages = [s.value for s in PipelineStage]
        assert "scan" in stages
        assert "verify" in stages
        assert "feedback" in stages

    def test_change_types(self):
        assert len(ChangeType) == 4

    def test_risk_levels(self):
        assert len(RiskLevel) == 3


# ── Phase 1 additions ─────────────────────────────────────────────────


class TestFindingDedupKey:
    def test_dedup_key_deterministic(self):
        """Same type+file+line+description → same dedup_key."""
        f1 = Finding(
            type=FindingType.CODE_SMELL,
            severity=SeverityLevel.LOW,
            file="a.py",
            line=1,
            description="test",
        )
        f2 = Finding(
            type=FindingType.CODE_SMELL,
            severity=SeverityLevel.LOW,
            file="a.py",
            line=1,
            description="test",
        )
        assert f1.dedup_key == f2.dedup_key

    def test_dedup_key_differs_for_different_descriptions(self):
        f1 = Finding(
            type=FindingType.CODE_SMELL,
            severity=SeverityLevel.LOW,
            file="a.py",
            line=1,
            description="issue A",
        )
        f2 = Finding(
            type=FindingType.CODE_SMELL,
            severity=SeverityLevel.LOW,
            file="a.py",
            line=1,
            description="issue B",
        )
        assert f1.dedup_key != f2.dedup_key

    def test_dedup_key_in_model_dump(self):
        f = Finding(
            type=FindingType.SECURITY,
            severity=SeverityLevel.HIGH,
            file="x.py",
            line=5,
            description="hardcoded key",
        )
        dump = f.model_dump()
        assert "dedup_key" in dump
        assert len(dump["dedup_key"]) == 16


class TestFindingNewFields:
    def test_business_impact_score_default(self):
        f = Finding(
            type=FindingType.CODE_SMELL,
            severity=SeverityLevel.LOW,
            file="a.py",
            line=1,
            description="test",
        )
        assert f.business_impact_score == 0.0

    def test_reviewer_effort_estimate_valid(self):
        for level in ("low", "medium", "high"):
            f = Finding(
                type=FindingType.CODE_SMELL,
                severity=SeverityLevel.LOW,
                file="a.py",
                line=1,
                description="test",
                reviewer_effort_estimate=level,
            )
            assert f.reviewer_effort_estimate == level

    def test_reviewer_effort_estimate_invalid(self):
        with pytest.raises(Exception, match="reviewer_effort_estimate"):
            Finding(
                type=FindingType.CODE_SMELL,
                severity=SeverityLevel.LOW,
                file="a.py",
                line=1,
                description="test",
                reviewer_effort_estimate="extreme",
            )


class TestCodeContextNewFields:
    def test_criticality_level_valid(self):
        for level in ("normal", "high", "critical"):
            ctx = CodeContext(
                file_path="a.py",
                source_code="x",
                start_line=1,
                end_line=1,
                criticality_level=level,
            )
            assert ctx.criticality_level == level

    def test_criticality_level_invalid(self):
        with pytest.raises(Exception, match="criticality_level"):
            CodeContext(
                file_path="a.py",
                source_code="x",
                start_line=1,
                end_line=1,
                criticality_level="legendary",
            )

    def test_coverage_percentage_bounds(self):
        ctx = CodeContext(
            file_path="a.py",
            source_code="x",
            start_line=1,
            end_line=1,
            coverage_percentage=85.5,
        )
        assert ctx.coverage_percentage == 85.5


class TestAlternativeSolution:
    def test_create_minimal(self):
        alt = AlternativeSolution(name="Option A", description="Try X")
        assert alt.name == "Option A"
        assert alt.confidence_score == 5
        assert alt.recommended is False

    def test_full_alternative(self):
        alt = AlternativeSolution(
            name="Strategy Pattern",
            description="Refactor using strategy pattern",
            pros=["Extensible", "Testable"],
            cons=["More complexity"],
            confidence_score=8,
            recommended=True,
        )
        assert len(alt.pros) == 2
        assert alt.recommended is True


class TestRefactoringPlanPhase1:
    def test_model_validator_auto_flags_low_confidence(self):
        """Plans with confidence < 7 auto-set requires_manual_verification."""
        plan = RefactoringPlan(finding_id="f1", summary="test", confidence_score=5)
        assert plan.requires_manual_verification is True

    def test_model_validator_skips_high_confidence(self):
        plan = RefactoringPlan(finding_id="f1", summary="test", confidence_score=8)
        assert plan.requires_manual_verification is False

    def test_confidence_factors(self):
        plan = RefactoringPlan(
            finding_id="f1",
            summary="test",
            confidence_score=8,
            confidence_factors=["has_tests", "simple_change"],
        )
        assert len(plan.confidence_factors) == 2

    def test_reviewer_effort_valid(self):
        plan = RefactoringPlan(
            finding_id="f1",
            summary="test",
            confidence_score=8,
            reviewer_effort="low",
        )
        assert plan.reviewer_effort == "low"

    def test_reviewer_effort_invalid(self):
        with pytest.raises(Exception, match="reviewer_effort"):
            RefactoringPlan(
                finding_id="f1",
                summary="test",
                confidence_score=8,
                reviewer_effort="extreme",
            )

    def test_alternatives_accepts_objects(self):
        alt = AlternativeSolution(name="A", description="Do A")
        plan = RefactoringPlan(
            finding_id="f1",
            summary="test",
            confidence_score=8,
            alternatives=[alt],
        )
        assert len(plan.alternatives) == 1
        assert plan.alternatives[0].name == "A"


class TestProposalResult:
    def test_create_minimal(self):
        f = Finding(
            type=FindingType.CODE_SMELL,
            severity=SeverityLevel.LOW,
            file="a.py",
            line=1,
            description="test",
        )
        proposal = ProposalResult(finding=f)
        assert proposal.is_proposal_only is True
        assert proposal.estimated_effort == "medium"

    def test_with_steps_and_risks(self):
        f = Finding(
            type=FindingType.SECURITY,
            severity=SeverityLevel.HIGH,
            file="auth.py",
            line=10,
            description="hardcoded secret",
        )
        proposal = ProposalResult(
            finding=f,
            recommended_steps=["Rotate secret", "Use env vars"],
            risks=["Service outage if rotated incorrectly"],
            estimated_effort="high",
        )
        assert len(proposal.recommended_steps) == 2
        assert len(proposal.risks) == 1


class TestPipelineResultProposals:
    def test_proposals_field(self):
        f = Finding(
            type=FindingType.CODE_SMELL,
            severity=SeverityLevel.LOW,
            file="a.py",
            line=1,
            description="test",
        )
        result = PipelineResult(
            proposals=[ProposalResult(finding=f)],
        )
        assert len(result.proposals) == 1
        assert result.proposals[0].is_proposal_only is True
