"""Tests for planner modules."""

from __future__ import annotations

import pytest

from codecustodian.models import (
    CodeContext,
    FileChange,
    Finding,
    FindingType,
    RefactoringPlan,
    RiskLevel,
    SeverityLevel,
)
from codecustodian.planner.alternatives import generate_alternatives
from codecustodian.planner.confidence import calculate_confidence
from codecustodian.planner.prompts import SYSTEM_PROMPT, build_user_prompt


class TestConfidenceScoring:
    def _make_context(self, has_tests: bool = True) -> CodeContext:
        return CodeContext(
            file_path="src/main.py",
            source_code="def foo(): pass",
            start_line=1,
            end_line=1,
            has_tests=has_tests,
        )

    def _make_plan(self, **kwargs) -> RefactoringPlan:
        defaults = {
            "finding_id": "f1",
            "summary": "test",
            "confidence_score": 5,
        }
        defaults.update(kwargs)
        return RefactoringPlan(**defaults)

    def test_high_confidence(self):
        plan = self._make_plan(changes_signature=False)
        ctx = self._make_context(has_tests=True)
        score = calculate_confidence(plan, ctx)
        assert score >= 8

    def test_low_without_tests(self):
        plan = self._make_plan()
        ctx = self._make_context(has_tests=False)
        score = calculate_confidence(plan, ctx)
        assert score <= 7

    def test_lower_with_signature_change(self):
        plan = self._make_plan(changes_signature=True)
        ctx = self._make_context(has_tests=True)
        score = calculate_confidence(plan, ctx)
        assert score <= 8

    def test_minimum_is_1(self):
        plan = self._make_plan(
            changes_signature=True,
            requires_manual_verification=True,
            changes=[
                FileChange(file_path=f"f{i}.py", change_type="replace")
                for i in range(10)
            ],
        )
        ctx = self._make_context(has_tests=False)
        score = calculate_confidence(plan, ctx)
        assert score >= 1


class TestAlternatives:
    def test_deprecated_api(self):
        finding = Finding(
            type=FindingType.DEPRECATED_API,
            severity=SeverityLevel.MEDIUM,
            file="a.py",
            line=1,
            description="test",
        )
        plan = RefactoringPlan(finding_id="f1", summary="test")
        alts = generate_alternatives(finding, plan)
        assert len(alts) >= 1

    def test_code_smell(self):
        finding = Finding(
            type=FindingType.CODE_SMELL,
            severity=SeverityLevel.LOW,
            file="a.py",
            line=1,
            description="test",
        )
        plan = RefactoringPlan(finding_id="f1", summary="test")
        alts = generate_alternatives(finding, plan)
        assert len(alts) >= 1


class TestPrompts:
    def test_system_prompt_not_empty(self):
        assert len(SYSTEM_PROMPT) > 100
        assert "CodeCustodian" in SYSTEM_PROMPT

    def test_build_user_prompt(self):
        finding = Finding(
            type=FindingType.CODE_SMELL,
            severity=SeverityLevel.MEDIUM,
            file="src/main.py",
            line=42,
            description="Function too complex",
            suggestion="Extract helper functions",
        )
        ctx = CodeContext(
            file_path="src/main.py",
            source_code="def foo(): pass",
            start_line=42,
            end_line=42,
            has_tests=True,
            related_tests=["tests/test_main.py"],
        )
        prompt = build_user_prompt(finding, ctx)
        assert "src/main.py" in prompt
        assert "42" in prompt
        assert "tests/test_main.py" in prompt


class TestCopilotClient:
    @pytest.mark.asyncio
    async def test_fallback_plan(self):
        from codecustodian.planner.copilot_client import CopilotPlannerClient

        client = CopilotPlannerClient()
        finding = Finding(
            type=FindingType.CODE_SMELL,
            severity=SeverityLevel.LOW,
            file="a.py",
            line=1,
            description="test",
        )
        ctx = CodeContext(
            file_path="a.py",
            source_code="x = 1",
            start_line=1,
            end_line=1,
        )
        plan = await client.plan(finding, ctx)
        assert plan.finding_id == finding.id
        assert plan.confidence_score >= 1
