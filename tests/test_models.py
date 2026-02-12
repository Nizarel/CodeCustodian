"""Tests for core data models."""

from __future__ import annotations

import pytest

from codecustodian.models import (
    ChangeType,
    CodeContext,
    ExecutionResult,
    FileChange,
    Finding,
    FindingType,
    PipelineResult,
    PipelineStage,
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
        assert str(f.file_path) == "src/utils/helpers.py"

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
            lint_violations=[{"code": "E501", "msg": "line too long"}],
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
