"""Tests for planner modules — Phase 3.

Covers:
- CopilotPlannerClient (mocked SDK)
- Tools (@define_tool-decorated)
- Prompt engineering
- Alternative generation (AI + static fallback)
- Confidence scoring + reviewer effort estimation
- Planner orchestrator (multi-turn, proposal mode, parse retry)
"""

from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from codecustodian.config.schema import AzureOpenAIProviderConfig, CopilotConfig
from codecustodian.exceptions import BudgetExceededError, PlannerError
from codecustodian.models import (
    AlternativeSolution,
    CodeContext,
    FileChange,
    Finding,
    FindingType,
    ProposalResult,
    RefactoringPlan,
    SeverityLevel,
)
from codecustodian.planner.alternatives import (
    AlternativeGenerator,
    generate_alternatives,
    generate_static_alternatives,
    is_complex_finding,
)
from codecustodian.planner.confidence import calculate_confidence, estimate_reviewer_effort
from codecustodian.planner.copilot_client import (
    CopilotPlannerClient,
    UsageAccumulator,
)
from codecustodian.planner.prompts import (
    SYSTEM_PROMPT,
    build_alternatives_prompt,
    build_context_request_prompt,
    build_finding_prompt,
    build_user_prompt,
    truncate_context,
)
from codecustodian.planner.tools import (
    CheckTypeHintsParams,
    FindTestCoverageParams,
    GetCallSitesParams,
    GetFunctionParams,
    GetGitHistoryParams,
    GetImportsParams,
    SearchReferencesParams,
    _get_impl,
    check_type_hints,
    find_test_coverage,
    get_all_tools,
    get_call_sites,
    get_function_definition,
    get_git_history,
    get_imports,
    search_references,
)

# ═══════════════════════════════════════════════════════════════════════════
# Test helpers
# ═══════════════════════════════════════════════════════════════════════════


def _make_config(**overrides: Any) -> CopilotConfig:
    defaults: dict[str, Any] = {
        "model_selection": "auto",
        "max_tokens": 4096,
        "timeout": 30,
        "max_cost_per_run": 5.00,
        "streaming": True,
        "enable_alternatives": True,
        "proposal_mode_threshold": 5,
    }
    defaults.update(overrides)
    return CopilotConfig(**defaults)


def _make_finding(**overrides: Any) -> Finding:
    defaults: dict[str, Any] = {
        "type": FindingType.CODE_SMELL,
        "severity": SeverityLevel.MEDIUM,
        "file": "src/main.py",
        "line": 42,
        "description": "Function too complex",
        "suggestion": "Extract helper functions",
    }
    defaults.update(overrides)
    return Finding(**defaults)


def _make_context(**overrides: Any) -> CodeContext:
    defaults: dict[str, Any] = {
        "file_path": "src/main.py",
        "source_code": "def foo(): pass",
        "start_line": 1,
        "end_line": 1,
        "has_tests": True,
    }
    defaults.update(overrides)
    return CodeContext(**defaults)


def _make_plan(**overrides: Any) -> RefactoringPlan:
    defaults: dict[str, Any] = {
        "finding_id": "f1",
        "summary": "test refactoring",
        "confidence_score": 5,
    }
    defaults.update(overrides)
    return RefactoringPlan(**defaults)


def _mock_copilot_client() -> MagicMock:
    """Create a mock CopilotClient from the SDK."""
    client = MagicMock()
    client.start = AsyncMock()
    client.stop = AsyncMock()
    client.list_models = AsyncMock(
        return_value=[
            SimpleNamespace(id="gpt-5-mini"),
            SimpleNamespace(id="gpt-5.2-codex"),
            SimpleNamespace(id="gpt-5.1-codex"),
        ]
    )
    session = MagicMock()
    session.send_and_wait = AsyncMock(return_value="response")
    session.send = AsyncMock()
    session.on = MagicMock()
    session.destroy = AsyncMock()
    client.create_session = AsyncMock(return_value=session)
    return client


# ═══════════════════════════════════════════════════════════════════════════
# TestConfidenceScoring — extended with new factors
# ═══════════════════════════════════════════════════════════════════════════


class TestConfidenceScoring:
    def test_high_confidence(self):
        plan = _make_plan(
            changes_signature=False,
            confidence_score=9,
            requires_manual_verification=False,
        )
        ctx = _make_context(has_tests=True, coverage_percentage=100.0)
        score, factors = calculate_confidence(plan, ctx)
        assert score >= 8
        assert len(factors) == 0

    def test_low_without_tests(self):
        plan = _make_plan()
        ctx = _make_context(has_tests=False)
        score, factors = calculate_confidence(plan, ctx)
        assert score <= 7
        assert "no_tests: -3" in factors

    def test_lower_with_signature_change(self):
        plan = _make_plan(changes_signature=True)
        ctx = _make_context(has_tests=True)
        score, factors = calculate_confidence(plan, ctx)
        assert score <= 8
        assert "signature_change: -2" in factors

    def test_minimum_is_1(self):
        plan = _make_plan(
            changes_signature=True,
            requires_manual_verification=True,
            changes=[FileChange(file_path=f"f{i}.py", change_type="replace") for i in range(10)],
        )
        ctx = _make_context(has_tests=False)
        score, _factors = calculate_confidence(plan, ctx)
        assert score >= 1

    def test_call_sites_deduction(self):
        plan = _make_plan()
        ctx = _make_context(call_sites=[f"site{i}" for i in range(15)])
        _score, factors = calculate_confidence(plan, ctx)
        assert any("call_sites" in f for f in factors)

    def test_many_call_sites_deduction(self):
        plan = _make_plan()
        ctx = _make_context(call_sites=[f"site{i}" for i in range(25)])
        _, factors = calculate_confidence(plan, ctx)
        assert any("-2" in f and "call_sites" in f for f in factors)

    def test_low_coverage_deduction(self):
        plan = _make_plan()
        ctx = _make_context(coverage_percentage=30.0)
        _, factors = calculate_confidence(plan, ctx)
        assert any("low_coverage" in f for f in factors)

    def test_hot_path_deduction(self):
        plan = _make_plan()
        ctx = _make_context(usage_frequency=200)
        _, factors = calculate_confidence(plan, ctx)
        assert any("hot_path" in f for f in factors)

    def test_critical_path_deduction(self):
        plan = _make_plan()
        ctx = _make_context(criticality_level="critical")
        _, factors = calculate_confidence(plan, ctx)
        assert "critical_path: -1" in factors


class TestReviewerEffort:
    def test_low_effort(self):
        plan = _make_plan(confidence_score=9, changes_signature=False)
        ctx = _make_context()
        effort = estimate_reviewer_effort(plan, ctx, confidence=9)
        assert effort == "low"

    def test_high_effort(self):
        plan = _make_plan(confidence_score=3)
        ctx = _make_context()
        effort = estimate_reviewer_effort(plan, ctx, confidence=3)
        assert effort == "high"

    def test_medium_effort(self):
        plan = _make_plan(
            confidence_score=6,
            changes=[FileChange(file_path=f"f{i}.py", change_type="replace") for i in range(3)],
        )
        ctx = _make_context()
        effort = estimate_reviewer_effort(plan, ctx, confidence=6)
        assert effort == "medium"


# ═══════════════════════════════════════════════════════════════════════════
# TestAlternatives — static + AI-powered
# ═══════════════════════════════════════════════════════════════════════════


class TestAlternatives:
    def test_deprecated_api_static(self):
        finding = _make_finding(type=FindingType.DEPRECATED_API)
        plan = _make_plan()
        alts = generate_alternatives(finding, plan)
        assert len(alts) >= 1
        assert isinstance(alts[0], str)

    def test_code_smell_static(self):
        finding = _make_finding(type=FindingType.CODE_SMELL)
        plan = _make_plan()
        alts = generate_alternatives(finding, plan)
        assert len(alts) >= 1

    def test_security_static(self):
        finding = _make_finding(type=FindingType.SECURITY)
        plan = _make_plan()
        alts = generate_static_alternatives(finding, plan)
        assert len(alts) >= 1
        assert isinstance(alts[0], AlternativeSolution)

    def test_todo_static(self):
        finding = _make_finding(type=FindingType.TODO_COMMENT)
        plan = _make_plan()
        alts = generate_static_alternatives(finding, plan)
        assert len(alts) >= 1

    def test_type_coverage_static(self):
        finding = _make_finding(type=FindingType.TYPE_COVERAGE)
        plan = _make_plan()
        alts = generate_static_alternatives(finding, plan)
        assert len(alts) >= 1

    def test_is_complex_finding_cyclomatic(self):
        f = _make_finding(metadata={"cyclomatic_complexity": 15})
        assert is_complex_finding(f) is True

    def test_is_complex_finding_critical(self):
        f = _make_finding(severity=SeverityLevel.CRITICAL)
        assert is_complex_finding(f) is True

    def test_is_complex_finding_simple(self):
        f = _make_finding(severity=SeverityLevel.LOW, metadata={})
        assert is_complex_finding(f) is False


class TestAlternativeGenerator:
    @pytest.mark.asyncio
    async def test_generate_parses_json(self):
        config = _make_config()
        client = CopilotPlannerClient(config)
        generator = AlternativeGenerator(client)

        # Mock send_and_wait to return JSON alternatives
        ai_response = json.dumps(
            [
                {
                    "name": "Extract Method",
                    "description": "Pull logic into a helper",
                    "pros": ["Cleaner"],
                    "cons": ["More functions"],
                    "confidence_score": 7,
                },
                {
                    "name": "Inline",
                    "description": "Simplify inline",
                    "pros": ["Less indirection"],
                    "cons": ["Longer function"],
                    "confidence_score": 5,
                },
            ]
        )
        client.send_and_wait = AsyncMock(return_value=ai_response)

        finding = _make_finding()
        plan = _make_plan()
        session = MagicMock()

        alts = await generator.generate_alternatives(finding, session, plan)
        assert len(alts) == 2
        assert alts[0].name == "Extract Method"
        assert alts[1].confidence_score == 5

    def test_select_recommended(self):
        config = _make_config()
        client = CopilotPlannerClient(config)
        generator = AlternativeGenerator(client)

        alts = [
            AlternativeSolution(name="A", description="a", confidence_score=5),
            AlternativeSolution(name="B", description="b", confidence_score=8),
            AlternativeSolution(
                name="C",
                description="c",
                confidence_score=8,
                changes=[FileChange(file_path="x.py", change_type="replace")],
            ),
        ]
        rec = generator.select_recommended(alts)
        assert rec is not None
        assert rec.recommended is True
        # B has confidence=8 and 0 changes, C has confidence=8 and 1 change
        assert rec.name == "B"

    @pytest.mark.asyncio
    async def test_fallback_on_failure(self):
        config = _make_config()
        client = CopilotPlannerClient(config)
        generator = AlternativeGenerator(client)

        # Mock send_and_wait to raise
        client.send_and_wait = AsyncMock(side_effect=Exception("API error"))

        finding = _make_finding(type=FindingType.DEPRECATED_API)
        plan = _make_plan()
        session = MagicMock()

        alts = await generator.generate_alternatives(finding, session, plan)
        # Should fall back to static alternatives
        assert len(alts) >= 1
        assert isinstance(alts[0], AlternativeSolution)


# ═══════════════════════════════════════════════════════════════════════════
# TestPrompts
# ═══════════════════════════════════════════════════════════════════════════


class TestPrompts:
    def test_system_prompt_not_empty(self):
        assert len(SYSTEM_PROMPT) > 100
        assert "CodeCustodian" in SYSTEM_PROMPT
        assert "confidence_score" in SYSTEM_PROMPT
        assert "changes_signature" in SYSTEM_PROMPT

    def test_build_user_prompt(self):
        finding = _make_finding()
        ctx = _make_context(
            related_tests=["tests/test_main.py"],
        )
        prompt = build_user_prompt(finding, ctx)
        assert "src/main.py" in prompt
        assert "42" in prompt
        assert "tests/test_main.py" in prompt

    def test_build_finding_prompt_deprecated(self):
        finding = _make_finding(
            type=FindingType.DEPRECATED_API,
            metadata={
                "replacement": "pd.concat()",
                "migration_guide_url": "https://pandas.pydata.org/migrate",
                "removed_in": "2.0",
                "urgency": "high",
            },
        )
        ctx = _make_context()
        prompt = build_finding_prompt(finding, ctx)
        assert "pd.concat()" in prompt
        assert "pandas.pydata.org" in prompt
        assert "Urgency: high" in prompt

    def test_build_finding_prompt_security(self):
        finding = _make_finding(
            type=FindingType.SECURITY,
            metadata={
                "cwe": "CWE-78",
                "exploit_scenario": "Command injection via user input",
                "compliance_impact": ["PCI DSS", "SOC 2"],
            },
        )
        ctx = _make_context()
        prompt = build_finding_prompt(finding, ctx)
        assert "CWE-78" in prompt
        assert "Command injection" in prompt
        assert "PCI DSS" in prompt

    def test_build_finding_prompt_code_smell(self):
        finding = _make_finding(
            type=FindingType.CODE_SMELL,
            metadata={"cyclomatic_complexity": 15, "cognitive_complexity": 20},
        )
        ctx = _make_context()
        prompt = build_finding_prompt(finding, ctx)
        assert "Cyclomatic complexity: 15" in prompt
        assert "Cognitive complexity: 20" in prompt

    def test_build_context_request_prompt(self):
        finding = _make_finding()
        prompt = build_context_request_prompt(finding)
        assert "get the full function definition" in prompt.lower()
        assert finding.file in prompt

    def test_build_alternatives_prompt(self):
        prompt = build_alternatives_prompt("Replace deprecated call")
        assert "alternative" in prompt.lower()
        assert "Replace deprecated call" in prompt

    def test_truncate_context_short(self):
        short = "def foo(): pass"
        assert truncate_context(short) == short

    def test_truncate_context_long(self):
        long_code = "x = 1\n" * 5000
        result = truncate_context(long_code, max_tokens=500)
        assert "truncated" in result
        assert len(result) < len(long_code)


# ═══════════════════════════════════════════════════════════════════════════
# TestTools — @define_tool functions with fixture files
# ═══════════════════════════════════════════════════════════════════════════


class TestTools:
    @pytest.mark.asyncio
    async def test_get_function_definition(self, tmp_path: Path):
        src = tmp_path / "sample.py"
        src.write_text(
            textwrap.dedent("""\
            def hello(name: str) -> str:
                \"\"\"Greet someone.\"\"\"
                return f"Hello, {name}!"

            def goodbye():
                return "bye"
            """),
            encoding="utf-8",
        )
        result = await _get_impl(get_function_definition)(
            GetFunctionParams(file_path=str(src), function_name="hello")
        )
        assert "hello" in result
        assert "Greet someone" in result

    @pytest.mark.asyncio
    async def test_get_function_definition_not_found(self, tmp_path: Path):
        src = tmp_path / "sample.py"
        src.write_text("x = 1\n", encoding="utf-8")
        result = await _get_impl(get_function_definition)(
            GetFunctionParams(file_path=str(src), function_name="missing")
        )
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_get_function_definition_file_missing(self):
        result = await _get_impl(get_function_definition)(
            GetFunctionParams(file_path="/nonexistent/file.py", function_name="foo")
        )
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_get_imports(self, tmp_path: Path):
        src = tmp_path / "imports.py"
        src.write_text(
            "import os\nfrom pathlib import Path\nimport json\n",
            encoding="utf-8",
        )
        result = await _get_impl(get_imports)(GetImportsParams(file_path=str(src)))
        assert "os" in result
        assert "pathlib.Path" in result
        assert "json" in result

    @pytest.mark.asyncio
    async def test_get_imports_none(self, tmp_path: Path):
        src = tmp_path / "empty.py"
        src.write_text("x = 1\n", encoding="utf-8")
        result = await _get_impl(get_imports)(GetImportsParams(file_path=str(src)))
        assert "no imports" in result.lower()

    @pytest.mark.asyncio
    async def test_search_references(self, tmp_path: Path):
        (tmp_path / "a.py").write_text("from b import helper\nhelper()\n")
        (tmp_path / "b.py").write_text("def helper(): pass\n")
        result = await _get_impl(search_references)(
            SearchReferencesParams(symbol_name="helper", directory=str(tmp_path))
        )
        assert "helper" in result
        assert "a.py" in result

    @pytest.mark.asyncio
    async def test_search_references_none(self, tmp_path: Path):
        (tmp_path / "a.py").write_text("x = 1\n")
        result = await _get_impl(search_references)(
            SearchReferencesParams(symbol_name="nonexistent", directory=str(tmp_path))
        )
        assert "no references" in result.lower()

    @pytest.mark.asyncio
    async def test_find_test_coverage(self, tmp_path: Path):
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_utils.py").write_text(
            textwrap.dedent("""\
            def test_helper():
                from app import helper
                assert helper() == 42
            """),
            encoding="utf-8",
        )
        result = await _get_impl(find_test_coverage)(
            FindTestCoverageParams(function_name="helper", test_directory=str(tests_dir))
        )
        assert "test_helper" in result

    @pytest.mark.asyncio
    async def test_find_test_coverage_none(self, tmp_path: Path):
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_other.py").write_text("def test_something(): pass\n")
        result = await _get_impl(find_test_coverage)(
            FindTestCoverageParams(function_name="missing_func", test_directory=str(tests_dir))
        )
        assert "no tests" in result.lower()

    @pytest.mark.asyncio
    async def test_get_call_sites(self, tmp_path: Path):
        (tmp_path / "main.py").write_text(
            textwrap.dedent("""\
            from utils import process
            result = process(data)
            """),
            encoding="utf-8",
        )
        (tmp_path / "utils.py").write_text("def process(x): return x\n")
        result = await _get_impl(get_call_sites)(
            GetCallSitesParams(function_name="process", directory=str(tmp_path))
        )
        assert "main.py" in result
        assert "call site" in result.lower()

    @pytest.mark.asyncio
    async def test_get_call_sites_attribute(self, tmp_path: Path):
        (tmp_path / "app.py").write_text("obj.run()\n", encoding="utf-8")
        result = await _get_impl(get_call_sites)(
            GetCallSitesParams(function_name="run", directory=str(tmp_path))
        )
        assert "app.py" in result

    @pytest.mark.asyncio
    async def test_check_type_hints(self, tmp_path: Path):
        src = tmp_path / "typed.py"
        src.write_text(
            textwrap.dedent("""\
            def greet(name: str, age: int) -> str:
                return f"{name} is {age}"
            """),
            encoding="utf-8",
        )
        result = await _get_impl(check_type_hints)(
            CheckTypeHintsParams(file_path=str(src), function_name="greet")
        )
        assert "str" in result
        assert "int" in result
        assert "Return type" in result

    @pytest.mark.asyncio
    async def test_check_type_hints_untyped(self, tmp_path: Path):
        src = tmp_path / "untyped.py"
        src.write_text("def foo(x, y): return x + y\n", encoding="utf-8")
        result = await _get_impl(check_type_hints)(
            CheckTypeHintsParams(file_path=str(src), function_name="foo")
        )
        assert "missing" in result.lower()

    @pytest.mark.asyncio
    async def test_get_git_history_no_repo(self, tmp_path: Path):
        src = tmp_path / "file.py"
        src.write_text("x = 1\n", encoding="utf-8")
        result = await _get_impl(get_git_history)(GetGitHistoryParams(file_path=str(src)))
        assert "no git repository" in result.lower() or "not found" in result.lower()

    def test_get_all_tools_count(self):
        tools = get_all_tools()
        assert len(tools) == 9


# ═══════════════════════════════════════════════════════════════════════════
# TestCopilotPlannerClient — mocked SDK
# ═══════════════════════════════════════════════════════════════════════════


class TestCopilotPlannerClient:
    @pytest.mark.asyncio
    async def test_start_stop(self):
        config = _make_config()
        client = CopilotPlannerClient(config)
        mock_sdk = _mock_copilot_client()

        # Directly assign the mock SDK client (bypassing the lazy import)
        client._client = mock_sdk
        await mock_sdk.start()
        assert client._client is not None
        mock_sdk.start.assert_awaited_once()

        await client.stop()
        mock_sdk.stop.assert_awaited_once()
        assert client._client is None

    @pytest.mark.asyncio
    async def test_stop_handles_exception_group(self):
        config = _make_config()
        client = CopilotPlannerClient(config)
        mock_sdk = _mock_copilot_client()
        mock_sdk.stop = AsyncMock(
            side_effect=ExceptionGroup("stop errors", [RuntimeError("destroy failed")])
        )
        client._client = mock_sdk

        await client.stop()

        mock_sdk.stop.assert_awaited_once()
        assert client._client is None

    @pytest.mark.asyncio
    async def test_list_available_models(self):
        config = _make_config()
        client = CopilotPlannerClient(config)
        mock_sdk = _mock_copilot_client()
        client._client = mock_sdk

        models = await client.list_available_models()
        assert len(models) == 3
        mock_sdk.list_models.assert_awaited_once()

        # Second call should use cache
        models2 = await client.list_available_models()
        assert models2 is models
        assert mock_sdk.list_models.await_count == 1

    def test_select_model_auto_critical(self):
        config = _make_config()
        client = CopilotPlannerClient(config)
        finding = _make_finding(severity=SeverityLevel.CRITICAL)
        model = client.select_model(finding)
        assert model == "gpt-5.2-codex"

    def test_select_model_auto_low(self):
        config = _make_config()
        client = CopilotPlannerClient(config)
        finding = _make_finding(severity=SeverityLevel.LOW)
        model = client.select_model(finding)
        assert model == "gpt-5-mini"

    def test_select_model_fast(self):
        config = _make_config(model_selection="fast")
        client = CopilotPlannerClient(config)
        model = client.select_model(_make_finding())
        assert model == "gpt-5-mini"

    def test_select_model_balanced(self):
        config = _make_config(model_selection="balanced")
        client = CopilotPlannerClient(config)
        model = client.select_model(_make_finding())
        assert model == "gpt-5.1-codex"

    def test_select_model_reasoning(self):
        config = _make_config(model_selection="reasoning")
        client = CopilotPlannerClient(config)
        model = client.select_model(_make_finding())
        assert model == "gpt-5.2-codex"

    def test_select_model_validates_available(self):
        config = _make_config()
        client = CopilotPlannerClient(config)
        # Simulate available models list
        client._available_models = [
            SimpleNamespace(id="gpt-5.2-codex"),
            SimpleNamespace(id="gpt-5-mini"),
        ]
        finding = _make_finding(severity=SeverityLevel.LOW)
        model = client.select_model(finding)
        assert model == "gpt-5-mini"

    @pytest.mark.asyncio
    async def test_create_session_with_tools(self):
        config = _make_config()
        client = CopilotPlannerClient(config)
        mock_sdk = _mock_copilot_client()
        client._client = mock_sdk

        await client.create_session(
            model="gpt-5.1-codex",
            tools=["tool1", "tool2"],
            system_prompt="Test prompt",
        )
        mock_sdk.create_session.assert_awaited_once()
        call_args = mock_sdk.create_session.call_args[0][0]
        assert call_args["model"] == "gpt-5.1-codex"
        assert call_args["tools"] == ["tool1", "tool2"]
        assert callable(call_args["on_permission_request"])
        assert call_args["system_message"]["mode"] == "append"
        assert call_args["infinite_sessions"]["enabled"] is False

    @pytest.mark.asyncio
    async def test_azure_provider_config(self):
        config = _make_config(
            azure_openai_provider=AzureOpenAIProviderConfig(
                base_url="https://myresource.openai.azure.com",
                api_key="test-key",
            )
        )
        client = CopilotPlannerClient(config)
        mock_sdk = _mock_copilot_client()
        client._client = mock_sdk

        await client.create_session(model="gpt-5.1-codex", system_prompt="test")
        call_args = mock_sdk.create_session.call_args[0][0]
        assert call_args["provider"]["type"] == "azure"
        assert "myresource" in call_args["provider"]["base_url"]
        assert call_args["provider"]["api_key"] == "test-key"

    @pytest.mark.asyncio
    async def test_reasoning_effort_set(self):
        config = _make_config(reasoning_effort="high")
        client = CopilotPlannerClient(config)
        mock_sdk = _mock_copilot_client()
        client._client = mock_sdk

        await client.create_session(model="gpt-5.2-codex", system_prompt="test")
        call_args = mock_sdk.create_session.call_args[0][0]
        assert call_args["reasoning_effort"] == "high"

    @pytest.mark.asyncio
    async def test_send_and_wait(self):
        config = _make_config()
        client = CopilotPlannerClient(config)
        mock_session = MagicMock()
        mock_session.send_and_wait = AsyncMock(return_value="plan output")

        result = await client.send_and_wait(mock_session, "create a plan")
        assert result == "plan output"

    @pytest.mark.asyncio
    async def test_cost_tracking_raises_budget(self):
        config = _make_config(max_cost_per_run=0.01)
        client = CopilotPlannerClient(config)

        # Simulate cost accumulation
        client.usage.record(1000, 500, 0.02)

        with pytest.raises(BudgetExceededError) as exc_info:
            client._check_budget()

        assert exc_info.value.current_cost == 0.02

    def test_ensure_client_raises_when_not_started(self):
        config = _make_config()
        client = CopilotPlannerClient(config)
        with pytest.raises(PlannerError, match="not started"):
            client._ensure_client()

    def test_resolve_token_from_config(self):
        config = _make_config(github_token="cfg-token")
        client = CopilotPlannerClient(config)
        assert client._resolve_token() == "cfg-token"

    def test_resolve_token_from_env(self):
        config = _make_config(github_token="")
        client = CopilotPlannerClient(config)
        with patch.dict(os.environ, {"GITHUB_TOKEN": "env-token"}):
            assert client._resolve_token() == "env-token"

    def test_resolve_token_fallback(self):
        config = _make_config(github_token="")
        client = CopilotPlannerClient(config)
        with patch.dict(os.environ, {}, clear=True):
            # Remove GITHUB_TOKEN if present
            os.environ.pop("GITHUB_TOKEN", None)
            assert client._resolve_token() == ""

    @pytest.mark.asyncio
    async def test_hook_pre_tool_use(self):
        config = _make_config()
        client = CopilotPlannerClient(config)
        result = await client._on_pre_tool_use(
            {"toolName": "get_imports", "toolArgs": {"file_path": "test.py"}},
            {"session_id": "s1"},
        )
        assert result == {"permissionDecision": "allow"}
        assert len(client.tool_audit_log) == 1
        assert client.tool_audit_log[0].tool_name == "get_imports"

    @pytest.mark.asyncio
    async def test_hook_error_recoverable(self):
        config = _make_config()
        client = CopilotPlannerClient(config)
        result = await client._on_error_occurred(
            {"errorContext": "tool_call", "error": "timeout", "recoverable": True},
            {"session_id": "s1"},
        )
        assert result["errorHandling"] == "retry"
        assert result["retryCount"] == 2

    @pytest.mark.asyncio
    async def test_hook_error_fatal(self):
        config = _make_config()
        client = CopilotPlannerClient(config)
        result = await client._on_error_occurred(
            {"errorContext": "session", "error": "crash", "recoverable": False},
            {"session_id": "s1"},
        )
        assert result["errorHandling"] == "abort"

    def test_usage_accumulator(self):
        acc = UsageAccumulator()
        acc.record(100, 50, 0.01)
        acc.record(200, 100, 0.02)
        assert acc.input_tokens == 300
        assert acc.output_tokens == 150
        assert abs(acc.total_cost - 0.03) < 1e-9
        assert acc.requests == 2


# ═══════════════════════════════════════════════════════════════════════════
# TestPlannerOrchestrator — multi-turn flow
# ═══════════════════════════════════════════════════════════════════════════


class TestPlannerOrchestrator:
    def _setup_planner(
        self,
        *,
        plan_json: dict[str, Any] | None = None,
        config_overrides: dict[str, Any] | None = None,
    ) -> tuple:
        """Create Planner with mocked client."""
        config = _make_config(**(config_overrides or {}))
        client = CopilotPlannerClient(config)
        mock_sdk = _mock_copilot_client()
        client._client = mock_sdk

        # Mock session
        session = MagicMock()
        session.destroy = AsyncMock()

        # Default plan JSON
        if plan_json is None:
            plan_json = {
                "summary": "Replace deprecated call",
                "description": "Migrate from old API to new API",
                "changes": [
                    {
                        "file_path": "src/main.py",
                        "change_type": "replace",
                        "old_content": "old()",
                        "new_content": "new()",
                        "description": "Replace deprecated function",
                    }
                ],
                "confidence_score": 8,
                "risk_level": "low",
                "ai_reasoning": "Direct replacement available",
                "changes_signature": False,
                "requires_manual_verification": False,
            }

        # send_streaming returns empty (Turn 1 just triggers tools)
        client.send_streaming = AsyncMock(return_value="")
        # send_and_wait returns the plan JSON (Turn 2)
        client.send_and_wait = AsyncMock(return_value=json.dumps(plan_json))
        # create_session returns mock session
        client.create_session = AsyncMock(return_value=session)

        from codecustodian.planner.planner import Planner

        planner = Planner(config=config, copilot_client=client)
        return planner, client, session

    @pytest.mark.asyncio
    async def test_plan_refactoring_full_flow(self):
        planner, _client, session = self._setup_planner(
            config_overrides={"session_reuse": False},
        )
        finding = _make_finding()
        ctx = _make_context()

        result = await planner.plan_refactoring(finding, ctx)

        assert isinstance(result, RefactoringPlan)
        assert result.summary == "Replace deprecated call"
        assert len(result.changes) == 1
        assert result.confidence_score >= 1
        assert result.reviewer_effort in ("low", "medium", "high")

        # Verify session was destroyed
        session.destroy.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_proposal_mode_downgrade(self):
        plan_json = {
            "summary": "Complex refactoring",
            "changes": [
                {
                    "file_path": f"f{i}.py",
                    "change_type": "replace",
                    "old_content": "a",
                    "new_content": "b",
                }
                for i in range(6)
            ],
            "confidence_score": 3,
            "risk_level": "high",
            "ai_reasoning": "Very uncertain",
            "changes_signature": True,
            "requires_manual_verification": True,
        }
        planner, _client, _session = self._setup_planner(
            plan_json=plan_json,
            config_overrides={"proposal_mode_threshold": 5},
        )
        finding = _make_finding()
        ctx = _make_context(has_tests=False)

        result = await planner.plan_refactoring(finding, ctx)

        assert isinstance(result, ProposalResult)
        assert result.is_proposal_only is True
        assert len(result.recommended_steps) >= 1
        assert any("confidence" in r.lower() for r in result.risks)

    @pytest.mark.asyncio
    async def test_json_parse_retry(self):
        """Test that malformed JSON triggers a retry."""
        config = _make_config()
        client = CopilotPlannerClient(config)
        mock_sdk = _mock_copilot_client()
        client._client = mock_sdk

        session = MagicMock()
        session.destroy = AsyncMock()
        client.create_session = AsyncMock(return_value=session)
        client.send_streaming = AsyncMock(return_value="")

        good_json = json.dumps(
            {
                "summary": "Fix after retry",
                "changes": [],
                "confidence_score": 7,
                "risk_level": "low",
                "ai_reasoning": "Retry succeeded",
            }
        )

        # First call returns garbage, second returns valid JSON
        client.send_and_wait = AsyncMock(side_effect=["not valid json {{{", good_json])

        from codecustodian.planner.planner import Planner

        planner = Planner(config=config, copilot_client=client)
        finding = _make_finding()
        ctx = _make_context()

        result = await planner.plan_refactoring(finding, ctx)
        assert isinstance(result, RefactoringPlan)
        assert result.summary == "Fix after retry"
        # send_and_wait called twice (original + retry)
        assert client.send_and_wait.await_count == 2

    @pytest.mark.asyncio
    async def test_session_cleanup_on_error(self):
        """Verify session.destroy() is called even on error."""
        config = _make_config(session_reuse=False)
        client = CopilotPlannerClient(config)
        mock_sdk = _mock_copilot_client()
        client._client = mock_sdk

        session = MagicMock()
        session.destroy = AsyncMock()
        client.create_session = AsyncMock(return_value=session)
        client.send_streaming = AsyncMock(side_effect=Exception("boom"))

        from codecustodian.planner.planner import Planner

        planner = Planner(config=config, copilot_client=client)
        finding = _make_finding()
        ctx = _make_context()

        with pytest.raises(Exception, match="boom"):
            await planner.plan_refactoring(finding, ctx)

        session.destroy.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_alternatives_generated_for_complex(self):
        """Test that alternatives are generated for complex findings."""
        alt_json = json.dumps(
            [
                {
                    "name": "Alt1",
                    "description": "Alt approach",
                    "pros": ["pro"],
                    "cons": ["con"],
                    "confidence_score": 6,
                },
            ]
        )
        plan_json = {
            "summary": "Complex refactoring",
            "changes": [],
            "confidence_score": 7,
            "risk_level": "medium",
            "ai_reasoning": "Complex",
        }

        planner, client, _session = self._setup_planner(
            plan_json=plan_json,
            config_overrides={"enable_alternatives": True},
        )

        # Override send_and_wait to return plan first, then alternatives
        call_count = {"n": 0}
        original_return = json.dumps(plan_json)

        async def side_effect(sess, prompt, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return original_return
            return alt_json

        client.send_and_wait = AsyncMock(side_effect=side_effect)

        finding = _make_finding(
            severity=SeverityLevel.CRITICAL,  # Makes it complex
        )
        ctx = _make_context()

        result = await planner.plan_refactoring(finding, ctx)
        assert isinstance(result, RefactoringPlan)
        assert len(result.alternatives) >= 1

    @pytest.mark.asyncio
    async def test_double_parse_failure_returns_stub(self):
        """Test that double parse failure returns stub plan.

        The stub gets confidence=1, but post-processing recalculates via
        ``calculate_confidence``.  We engineer a context that produces a
        score below ``proposal_mode_threshold`` so the result is properly
        downgraded to a ``ProposalResult``.
        """
        config = _make_config(proposal_mode_threshold=5)
        client = CopilotPlannerClient(config)
        mock_sdk = _mock_copilot_client()
        client._client = mock_sdk

        session = MagicMock()
        session.destroy = AsyncMock()
        client.create_session = AsyncMock(return_value=session)
        client.send_streaming = AsyncMock(return_value="")
        # Both attempts return unparseable text
        client.send_and_wait = AsyncMock(return_value="I can't help with that")

        from codecustodian.planner.planner import Planner

        planner = Planner(config=config, copilot_client=client)
        finding = _make_finding()
        # Create context with severe deductions: no tests (-3), low coverage (-1),
        # many call sites (-2), hot path (-1), critical path (-1) = 10-8 = 2
        ctx = _make_context(
            has_tests=False,
            coverage_percentage=10.0,
            call_sites=[f"site{i}" for i in range(25)],
            usage_frequency=200,
            criticality_level="critical",
        )

        result = await planner.plan_refactoring(finding, ctx)
        # Score should be well below threshold of 5
        assert isinstance(result, ProposalResult)


# ═══════════════════════════════════════════════════════════════════════════
# TestCopilotConfig — schema validation
# ═══════════════════════════════════════════════════════════════════════════


class TestCopilotConfigValidation:
    def test_valid_model_selection(self):
        for ms in ("auto", "fast", "balanced", "reasoning"):
            config = CopilotConfig(model_selection=ms)
            assert config.model_selection == ms

    def test_invalid_model_selection(self):
        with pytest.raises(ValueError, match="model_selection"):
            CopilotConfig(model_selection="turbo")

    def test_valid_reasoning_effort(self):
        for re in ("", "low", "medium", "high", "xhigh"):
            config = CopilotConfig(reasoning_effort=re)
            assert config.reasoning_effort == re

    def test_invalid_reasoning_effort(self):
        with pytest.raises(ValueError, match="reasoning_effort"):
            CopilotConfig(reasoning_effort="ultra")

    def test_azure_provider(self):
        config = CopilotConfig(
            azure_openai_provider=AzureOpenAIProviderConfig(
                base_url="https://test.openai.azure.com",
                api_key="key123",
            )
        )
        assert config.azure_openai_provider is not None
        assert config.azure_openai_provider.api_version == "2024-10-21"
