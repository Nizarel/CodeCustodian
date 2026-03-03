"""Tests for Skills, Agents, and Multi-Session features (v0.13.0).

Covers:
- SkillRegistry: loading, parsing, querying, formatting
- AgentProfile: selection, tool filtering, registry
- Planner integration: agent routing, skill injection, session pooling
- CopilotPlannerClient: preference override, skill_context, session_reuse
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from codecustodian.config.schema import CopilotConfig
from codecustodian.models import (
    CodeContext,
    Finding,
    FindingType,
    SeverityLevel,
)
from codecustodian.planner.agents import (
    AGENT_REGISTRY,
    FINDING_TYPE_AGENT_MAP,
    AgentProfile,
    get_agent_tools,
    list_agents,
    select_agent,
)
from codecustodian.planner.skills import (
    FINDING_TYPE_SKILL_MAP,
    SkillDefinition,
    SkillRegistry,
    _parse_skill_md,
)


# ═══════════════════════════════════════════════════════════════════════════
# Test helpers
# ═══════════════════════════════════════════════════════════════════════════


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


def _make_skill_dir(base: Path, skills: dict[str, str]) -> Path:
    """Create a skill directory with SKILL.md files.

    Args:
        base: Parent directory.
        skills: Mapping of skill_name → SKILL.md content.

    Returns:
        Path to the created skill directory.
    """
    skill_dir = base / ".copilot_skills"
    skill_dir.mkdir(exist_ok=True)
    for name, content in skills.items():
        d = skill_dir / name
        d.mkdir(exist_ok=True)
        (d / "SKILL.md").write_text(content, encoding="utf-8")
    return skill_dir


# ═══════════════════════════════════════════════════════════════════════════
# Skill parsing tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSkillParsing:
    """Test YAML front-matter + markdown body parsing."""

    def test_parse_valid_frontmatter(self) -> None:
        text = textwrap.dedent("""\
        ---
        name: security-remediation
        description: OWASP patterns
        ---

        # Security Remediation
        Some content here.
        """)
        fm, body = _parse_skill_md(text)
        assert fm["name"] == "security-remediation"
        assert fm["description"] == "OWASP patterns"
        assert "# Security Remediation" in body
        assert "Some content here." in body

    def test_parse_no_frontmatter(self) -> None:
        text = "# Just markdown\nNo front matter."
        fm, body = _parse_skill_md(text)
        assert fm == {}
        assert "# Just markdown" in body

    def test_parse_empty_frontmatter(self) -> None:
        text = "---\n---\n\nBody only."
        fm, body = _parse_skill_md(text)
        assert fm == {}
        assert "Body only." in body

    def test_parse_invalid_yaml(self) -> None:
        text = "---\n: : invalid: yaml: [[\n---\n\nBody."
        fm, body = _parse_skill_md(text)
        # Should gracefully degrade
        assert isinstance(fm, dict)
        assert "Body." in body


# ═══════════════════════════════════════════════════════════════════════════
# Skill registry tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSkillRegistry:
    """Test skill loading, querying, and formatting."""

    def test_load_skills_from_directory(self) -> None:
        with TemporaryDirectory() as tmp:
            skill_dir = _make_skill_dir(Path(tmp), {
                "test-skill": textwrap.dedent("""\
                ---
                name: test-skill
                description: A test skill
                ---

                # Test Skill
                Test content.
                """),
            })
            registry = SkillRegistry()
            registry.load_skills(skill_dir)
            assert "test-skill" in registry.list_skills()
            skill = registry.get_skill("test-skill")
            assert skill is not None
            assert skill.description == "A test skill"
            assert "# Test Skill" in skill.content

    def test_load_skills_missing_directory(self) -> None:
        registry = SkillRegistry()
        registry.load_skills(Path("/nonexistent/path"))
        assert registry.list_skills() == []

    def test_load_skills_default_path(self) -> None:
        registry = SkillRegistry()
        # Should not crash when default .copilot_skills/ doesn't exist
        registry.load_skills()
        # May or may not find skills depending on cwd

    def test_load_skills_string_path(self) -> None:
        with TemporaryDirectory() as tmp:
            skill_dir = _make_skill_dir(Path(tmp), {
                "my-skill": "---\nname: my-skill\ndescription: test\n---\nBody.",
            })
            registry = SkillRegistry()
            registry.load_skills(str(skill_dir))
            assert "my-skill" in registry.list_skills()

    def test_get_skills_for_finding_security(self) -> None:
        with TemporaryDirectory() as tmp:
            skill_dir = _make_skill_dir(Path(tmp), {
                "security-remediation": "---\nname: security-remediation\ndescription: sec\n---\nSec body.",
                "code-quality": "---\nname: code-quality\ndescription: qual\n---\nQuality body.",
            })
            registry = SkillRegistry()
            registry.load_skills(skill_dir)
            skills = registry.get_skills_for_finding(FindingType.SECURITY)
            assert len(skills) == 2
            names = [s.name for s in skills]
            assert "security-remediation" in names
            assert "code-quality" in names

    def test_get_skills_for_finding_unknown_type(self) -> None:
        with TemporaryDirectory() as tmp:
            skill_dir = _make_skill_dir(Path(tmp), {
                "general-refactoring": "---\nname: general-refactoring\ndescription: gen\n---\nGeneral.",
            })
            registry = SkillRegistry()
            registry.load_skills(skill_dir)
            skills = registry.get_skills_for_finding("unknown_type")
            names = [s.name for s in skills]
            assert "general-refactoring" in names

    def test_get_skills_by_names(self) -> None:
        with TemporaryDirectory() as tmp:
            skill_dir = _make_skill_dir(Path(tmp), {
                "a": "---\nname: a\n---\nA body.",
                "b": "---\nname: b\n---\nB body.",
                "c": "---\nname: c\n---\nC body.",
            })
            registry = SkillRegistry()
            registry.load_skills(skill_dir)
            skills = registry.get_skills_by_names(["b", "a", "nonexistent"])
            assert len(skills) == 2
            assert skills[0].name == "b"
            assert skills[1].name == "a"

    def test_format_skill_context_empty(self) -> None:
        result = SkillRegistry.format_skill_context([])
        assert result == ""

    def test_format_skill_context_with_skills(self) -> None:
        skills = [
            SkillDefinition(name="alpha", description="Alpha desc", content="Alpha content."),
            SkillDefinition(name="beta", description="", content="Beta content."),
        ]
        result = SkillRegistry.format_skill_context(skills)
        assert "[Domain Skills]" in result
        assert "[End Domain Skills]" in result
        assert "## Skill: alpha" in result
        assert "Alpha desc" in result
        assert "Alpha content." in result
        assert "## Skill: beta" in result
        assert "Beta content." in result

    def test_finding_type_skill_map_covers_all_types(self) -> None:
        for ft in FindingType:
            assert ft.value in FINDING_TYPE_SKILL_MAP, (
                f"FindingType.{ft.name} not in FINDING_TYPE_SKILL_MAP"
            )

    def test_name_defaults_to_directory_name(self) -> None:
        with TemporaryDirectory() as tmp:
            skill_dir = _make_skill_dir(Path(tmp), {
                "my-dir": "---\ndescription: no name field\n---\nBody.",
            })
            registry = SkillRegistry()
            registry.load_skills(skill_dir)
            assert "my-dir" in registry.list_skills()


# ═══════════════════════════════════════════════════════════════════════════
# Agent profile tests
# ═══════════════════════════════════════════════════════════════════════════


class TestAgentProfiles:
    """Test agent registry, selection, and tool filtering."""

    def test_all_finding_types_have_agents(self) -> None:
        for ft in FindingType:
            assert ft.value in FINDING_TYPE_AGENT_MAP, (
                f"FindingType.{ft.name} not in FINDING_TYPE_AGENT_MAP"
            )

    def test_all_mapped_agents_exist_in_registry(self) -> None:
        for agent_name in FINDING_TYPE_AGENT_MAP.values():
            assert agent_name in AGENT_REGISTRY

    def test_select_agent_security(self) -> None:
        finding = _make_finding(type=FindingType.SECURITY)
        agent = select_agent(finding)
        assert agent.name == "security-auditor"
        assert agent.model_preference == "reasoning"

    def test_select_agent_deprecated_api(self) -> None:
        finding = _make_finding(type=FindingType.DEPRECATED_API)
        agent = select_agent(finding)
        assert agent.name == "modernization-expert"

    def test_select_agent_code_smell(self) -> None:
        finding = _make_finding(type=FindingType.CODE_SMELL)
        agent = select_agent(finding)
        assert agent.name == "quality-architect"

    def test_select_agent_type_coverage(self) -> None:
        finding = _make_finding(type=FindingType.TYPE_COVERAGE)
        agent = select_agent(finding)
        assert agent.name == "type-advisor"
        assert agent.model_preference == "fast"

    def test_select_agent_todo_comment(self) -> None:
        finding = _make_finding(type=FindingType.TODO_COMMENT)
        agent = select_agent(finding)
        assert agent.name == "task-resolver"

    def test_select_agent_dependency(self) -> None:
        finding = _make_finding(type=FindingType.DEPENDENCY_UPGRADE)
        agent = select_agent(finding)
        assert agent.name == "dependency-expert"

    def test_select_agent_has_skill_names(self) -> None:
        for profile in AGENT_REGISTRY.values():
            assert len(profile.skill_names) >= 1, (
                f"Agent {profile.name} has no skill_names"
            )

    def test_get_agent_tools_no_filter(self) -> None:
        profile = AgentProfile(name="test", tool_filter=None)
        tools = [MagicMock(__name__="tool_a"), MagicMock(__name__="tool_b")]
        result = get_agent_tools(profile, tools)
        assert len(result) == 2

    def test_get_agent_tools_with_filter(self) -> None:
        profile = AgentProfile(name="test", tool_filter=["tool_a"])
        tool_a = MagicMock(__name__="tool_a")
        tool_b = MagicMock(__name__="tool_b")
        result = get_agent_tools(profile, [tool_a, tool_b])
        assert len(result) == 1
        assert result[0].__name__ == "tool_a"

    def test_list_agents(self) -> None:
        agents = list_agents()
        assert "security-auditor" in agents
        assert "general-refactorer" in agents
        assert len(agents) == 7

    def test_agent_profile_model(self) -> None:
        profile = AgentProfile(
            name="test-agent",
            description="Test",
            system_prompt_overlay="Be helpful.",
            model_preference="balanced",
            skill_names=["general-refactoring"],
            tool_filter=["get_function_definition"],
        )
        assert profile.name == "test-agent"
        assert profile.model_preference == "balanced"


# ═══════════════════════════════════════════════════════════════════════════
# CopilotPlannerClient integration tests
# ═══════════════════════════════════════════════════════════════════════════


class TestCopilotClientExtensions:
    """Test new parameters: preference, skill_context, session_reuse."""

    def test_select_model_with_preference_override(self) -> None:
        config = _make_config(model_selection="auto")
        from codecustodian.planner.copilot_client import CopilotPlannerClient

        client = CopilotPlannerClient(config)
        finding = _make_finding(severity=SeverityLevel.LOW)

        # Without preference → auto routing (low severity → fast model)
        model_auto = client.select_model(finding)

        # With preference → overrides config
        model_reasoning = client.select_model(finding, preference="reasoning")
        assert model_reasoning in {
            "gpt-5.2-codex", "gpt-5.1-codex-max",
            "gpt-5.2", "gpt-5.1-codex",
        }

    def test_select_model_preference_auto_uses_config(self) -> None:
        config = _make_config(model_selection="fast")
        from codecustodian.planner.copilot_client import CopilotPlannerClient

        client = CopilotPlannerClient(config)
        finding = _make_finding()

        # preference="auto" should fall through to config.model_selection
        model = client.select_model(finding, preference="auto")
        assert model in {"gpt-5-mini", "gpt-4.1", "gpt-5.1-codex-mini"}

    @pytest.mark.asyncio
    async def test_create_session_with_skill_context(self) -> None:
        config = _make_config(github_token="test-token")
        from codecustodian.planner.copilot_client import CopilotPlannerClient

        client = CopilotPlannerClient(config)

        mock_sdk = MagicMock()
        mock_sdk.create_session = AsyncMock(return_value=AsyncMock())
        client._client = mock_sdk

        await client.create_session(
            model="gpt-5.1",
            system_prompt="Base prompt",
            skill_context="[Domain Skills]\n## Skill: security\nOWASP info\n[End Domain Skills]",
        )

        call_args = mock_sdk.create_session.call_args[0][0]
        content = call_args["system_message"]["content"]
        assert "[Domain Skills]" in content
        assert "Base prompt" in content
        assert content.startswith("[Domain Skills]")

    @pytest.mark.asyncio
    async def test_create_session_with_session_reuse(self) -> None:
        config = _make_config(github_token="test-token")
        from codecustodian.planner.copilot_client import CopilotPlannerClient

        client = CopilotPlannerClient(config)

        mock_sdk = MagicMock()
        mock_sdk.create_session = AsyncMock(return_value=AsyncMock())
        client._client = mock_sdk

        await client.create_session(
            model="gpt-5.1",
            system_prompt="Test",
            session_reuse=True,
        )

        call_args = mock_sdk.create_session.call_args[0][0]
        inf = call_args["infinite_sessions"]
        assert inf["enabled"] is True
        assert inf["background_compaction_threshold"] == 0.80
        assert inf["buffer_exhaustion_threshold"] == 0.95

    @pytest.mark.asyncio
    async def test_create_session_without_session_reuse(self) -> None:
        config = _make_config(github_token="test-token")
        from codecustodian.planner.copilot_client import CopilotPlannerClient

        client = CopilotPlannerClient(config)

        mock_sdk = MagicMock()
        mock_sdk.create_session = AsyncMock(return_value=AsyncMock())
        client._client = mock_sdk

        await client.create_session(
            model="gpt-5.1",
            system_prompt="Test",
            session_reuse=False,
        )

        call_args = mock_sdk.create_session.call_args[0][0]
        inf = call_args["infinite_sessions"]
        assert inf["enabled"] is False
        assert "background_compaction_threshold" not in inf

    @pytest.mark.asyncio
    async def test_create_session_no_skill_context(self) -> None:
        config = _make_config(github_token="test-token")
        from codecustodian.planner.copilot_client import CopilotPlannerClient

        client = CopilotPlannerClient(config)

        mock_sdk = MagicMock()
        mock_sdk.create_session = AsyncMock(return_value=AsyncMock())
        client._client = mock_sdk

        await client.create_session(
            model="gpt-5.1",
            system_prompt="Base only",
        )

        call_args = mock_sdk.create_session.call_args[0][0]
        content = call_args["system_message"]["content"]
        assert content == "Base only"


# ═══════════════════════════════════════════════════════════════════════════
# Config schema tests
# ═══════════════════════════════════════════════════════════════════════════


class TestConfigExtensions:
    """Test new CopilotConfig fields."""

    def test_defaults(self) -> None:
        config = CopilotConfig()
        assert config.enable_agents is True
        assert config.custom_skill_dir == ""
        assert config.session_reuse is True

    def test_disable_agents(self) -> None:
        config = CopilotConfig(enable_agents=False)
        assert config.enable_agents is False

    def test_custom_skill_dir(self) -> None:
        config = CopilotConfig(custom_skill_dir="/my/skills")
        assert config.custom_skill_dir == "/my/skills"


# ═══════════════════════════════════════════════════════════════════════════
# Planner integration tests
# ═══════════════════════════════════════════════════════════════════════════


class TestPlannerIntegration:
    """Test that Planner properly integrates agents, skills, and session pooling."""

    @pytest.mark.asyncio
    async def test_planner_uses_agent_for_security_finding(self) -> None:
        """Planner should route security findings to security-auditor agent."""
        config = _make_config(enable_agents=True)
        from codecustodian.planner.copilot_client import CopilotPlannerClient
        from codecustodian.planner.planner import Planner

        client = MagicMock(spec=CopilotPlannerClient)
        client.config = config
        client.select_model = MagicMock(return_value="gpt-5.2-codex")
        client.usage = SimpleNamespace(input_tokens=100, output_tokens=200)

        mock_session = AsyncMock()
        client.create_session = AsyncMock(return_value=mock_session)
        client.send_streaming = AsyncMock()
        client.send_and_wait = AsyncMock(return_value='{"summary":"Fix SQL injection","description":"Parameterize","changes":[],"confidence_score":8,"risk_level":"high","ai_reasoning":"SQL injection"}')

        planner = Planner(config=config, copilot_client=client)
        finding = _make_finding(type=FindingType.SECURITY, severity=SeverityLevel.CRITICAL)
        context = CodeContext(
            file_path="src/db.py",
            source_code="cursor.execute(f'SELECT * FROM {table}')",
            start_line=1,
            end_line=1,
        )

        result = await planner.plan_refactoring(finding, context)

        # Verify agent preference was used in model selection
        client.select_model.assert_called_once()
        call_kwargs = client.select_model.call_args
        assert call_kwargs.kwargs.get("preference") == "reasoning"

        # Verify skill context was passed to create_session
        client.create_session.assert_called_once()
        session_kwargs = client.create_session.call_args.kwargs
        assert "skill_context" in session_kwargs

        # Verify system prompt includes agent overlay
        assert "system_prompt" in session_kwargs
        assert "security-specialist" in session_kwargs["system_prompt"].lower()

    @pytest.mark.asyncio
    async def test_planner_agents_disabled_uses_defaults(self) -> None:
        """When enable_agents=False, planner should use default behavior."""
        config = _make_config(enable_agents=False)
        from codecustodian.planner.copilot_client import CopilotPlannerClient
        from codecustodian.planner.planner import Planner

        client = MagicMock(spec=CopilotPlannerClient)
        client.config = config
        client.select_model = MagicMock(return_value="gpt-5.1")
        client.usage = SimpleNamespace(input_tokens=100, output_tokens=200)

        mock_session = AsyncMock()
        client.create_session = AsyncMock(return_value=mock_session)
        client.send_streaming = AsyncMock()
        client.send_and_wait = AsyncMock(return_value='{"summary":"Refactor","description":"Fix","changes":[],"confidence_score":7,"risk_level":"low","ai_reasoning":"Simple"}')

        planner = Planner(config=config, copilot_client=client)
        finding = _make_finding()
        context = CodeContext(
            file_path="src/main.py",
            source_code="def foo(): pass",
            start_line=1,
            end_line=1,
        )

        await planner.plan_refactoring(finding, context)

        # No preference override when agents disabled
        call_kwargs = client.select_model.call_args
        assert call_kwargs.kwargs.get("preference") == ""

    @pytest.mark.asyncio
    async def test_planner_session_pool_reuse(self) -> None:
        """Session pool should reuse sessions for same agent type."""
        config = _make_config(enable_agents=True, session_reuse=True)
        from codecustodian.planner.copilot_client import CopilotPlannerClient
        from codecustodian.planner.planner import Planner

        client = MagicMock(spec=CopilotPlannerClient)
        client.config = config
        client.select_model = MagicMock(return_value="gpt-5.1")
        client.usage = SimpleNamespace(input_tokens=100, output_tokens=200)

        mock_session = AsyncMock()
        client.create_session = AsyncMock(return_value=mock_session)
        client.send_streaming = AsyncMock()
        client.send_and_wait = AsyncMock(return_value='{"summary":"Fix","description":"Fix","changes":[],"confidence_score":7,"risk_level":"low","ai_reasoning":"OK"}')

        planner = Planner(config=config, copilot_client=client)

        # Two findings of the same type → same agent
        finding1 = _make_finding(type=FindingType.CODE_SMELL, line=10)
        finding2 = _make_finding(type=FindingType.CODE_SMELL, line=20)
        context = CodeContext(
            file_path="src/main.py",
            source_code="def foo(): pass",
            start_line=1,
            end_line=1,
        )

        await planner.plan_refactoring(finding1, context)
        await planner.plan_refactoring(finding2, context)

        # create_session should be called only once (reuse on second call)
        assert client.create_session.call_count == 1

    @pytest.mark.asyncio
    async def test_planner_close_sessions(self) -> None:
        """close_sessions should destroy all pooled sessions."""
        config = _make_config(enable_agents=True, session_reuse=True)
        from codecustodian.planner.copilot_client import CopilotPlannerClient
        from codecustodian.planner.planner import Planner

        client = MagicMock(spec=CopilotPlannerClient)
        client.config = config
        client.select_model = MagicMock(return_value="gpt-5.1")
        client.usage = SimpleNamespace(input_tokens=100, output_tokens=200)

        mock_session = AsyncMock()
        client.create_session = AsyncMock(return_value=mock_session)
        client.send_streaming = AsyncMock()
        client.send_and_wait = AsyncMock(return_value='{"summary":"Fix","description":"Fix","changes":[],"confidence_score":7,"risk_level":"low","ai_reasoning":"OK"}')

        planner = Planner(config=config, copilot_client=client)
        finding = _make_finding(type=FindingType.SECURITY)
        context = CodeContext(
            file_path="src/main.py",
            source_code="def foo(): pass",
            start_line=1,
            end_line=1,
        )

        await planner.plan_refactoring(finding, context)
        assert len(planner._session_pool) == 1

        await planner.close_sessions()
        assert len(planner._session_pool) == 0
        mock_session.destroy.assert_called_once()

    @pytest.mark.asyncio
    async def test_planner_no_session_reuse_destroys_immediately(self) -> None:
        """When session_reuse=False, sessions are destroyed after each finding."""
        config = _make_config(enable_agents=True, session_reuse=False)
        from codecustodian.planner.copilot_client import CopilotPlannerClient
        from codecustodian.planner.planner import Planner

        client = MagicMock(spec=CopilotPlannerClient)
        client.config = config
        client.select_model = MagicMock(return_value="gpt-5.1")
        client.usage = SimpleNamespace(input_tokens=100, output_tokens=200)

        mock_session = AsyncMock()
        client.create_session = AsyncMock(return_value=mock_session)
        client.send_streaming = AsyncMock()
        client.send_and_wait = AsyncMock(return_value='{"summary":"Fix","description":"Fix","changes":[],"confidence_score":7,"risk_level":"low","ai_reasoning":"OK"}')

        planner = Planner(config=config, copilot_client=client)
        finding = _make_finding()
        context = CodeContext(
            file_path="src/main.py",
            source_code="def foo(): pass",
            start_line=1,
            end_line=1,
        )

        await planner.plan_refactoring(finding, context)
        mock_session.destroy.assert_called_once()
        assert len(planner._session_pool) == 0
