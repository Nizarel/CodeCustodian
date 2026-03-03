"""Custom agent profiles for the AI planner.

Each agent profile is a specialised session configuration template
that combines a system-prompt overlay, model preference, skill set,
and optional tool filter.  The planner routes findings to the most
appropriate agent based on ``FindingType``.

Agent profiles are an **application-layer** concept — the Copilot SDK
creates sessions; agents are our routing and configuration layer on top.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from codecustodian.logging import get_logger
from codecustodian.models import Finding, FindingType

logger = get_logger("planner.agents")


# ── Agent profile model ───────────────────────────────────────────────────


class AgentProfile(BaseModel):
    """A specialised agent persona for the AI planner.

    Attributes:
        name: Unique agent identifier (e.g. ``"security-auditor"``).
        description: Human-readable purpose description.
        system_prompt_overlay: Extra instructions prepended to the base
            system prompt for this agent's domain.
        model_preference: Model routing hint — overrides
            ``CopilotConfig.model_selection`` for this finding.
            Values: ``"auto"`` | ``"fast"`` | ``"balanced"`` | ``"reasoning"``.
        skill_names: Names of skill directories to load for this agent.
        tool_filter: When set, only pass these tool names to the session.
            ``None`` means include all tools.
    """

    name: str
    description: str = ""
    system_prompt_overlay: str = ""
    model_preference: str = Field(
        default="auto",
        description="Model routing hint: auto | fast | balanced | reasoning",
    )
    skill_names: list[str] = Field(default_factory=list)
    tool_filter: list[str] | None = None


# ── Predefined agents ─────────────────────────────────────────────────────

AGENT_REGISTRY: dict[str, AgentProfile] = {
    "security-auditor": AgentProfile(
        name="security-auditor",
        description="Security-focused code reviewer specialising in vulnerability remediation",
        system_prompt_overlay=(
            "You are a security-specialist agent. Focus on:\n"
            "- OWASP Top 10 vulnerability categories\n"
            "- CWE mapping for each finding\n"
            "- Eliminating vulnerabilities without breaking functionality\n"
            "- Preferring stdlib/well-known libraries over custom crypto\n"
            "- Defence in depth — multiple layers of protection\n"
            "- Fail-secure patterns (deny on error)\n"
        ),
        model_preference="reasoning",
        skill_names=["security-remediation", "code-quality"],
    ),
    "modernization-expert": AgentProfile(
        name="modernization-expert",
        description="API migration specialist for deprecated library and stdlib upgrades",
        system_prompt_overlay=(
            "You are a modernization-expert agent. Focus on:\n"
            "- Drop-in API replacements that preserve exact behaviour\n"
            "- Checking the minimum Python/library version target\n"
            "- Backward compatibility wrappers when public signatures change\n"
            "- Migrating all call sites — not just the flagged one\n"
            "- Updating import paths when APIs move between modules\n"
            "- Consulting official migration guides for each library\n"
        ),
        model_preference="balanced",
        skill_names=["api-migration", "general-refactoring"],
    ),
    "quality-architect": AgentProfile(
        name="quality-architect",
        description="Code quality expert for complexity reduction and design improvement",
        system_prompt_overlay=(
            "You are a quality-architect agent. Focus on:\n"
            "- Extract Method for functions exceeding 50 lines\n"
            "- Replace Conditional with Polymorphism for type-switch chains\n"
            "- Introduce Parameter Object for functions with >5 params\n"
            "- Guard clauses to reduce nesting depth\n"
            "- SOLID principles — especially Single Responsibility\n"
            "- Preserving all existing tests and public interfaces\n"
        ),
        model_preference="balanced",
        skill_names=["code-quality", "general-refactoring"],
    ),
    "type-advisor": AgentProfile(
        name="type-advisor",
        description="Python type annotation specialist for mypy/pyright compatibility",
        system_prompt_overlay=(
            "You are a type-advisor agent. Focus on:\n"
            "- Modern Python 3.11+ typing syntax (PEP 604 unions, built-in generics)\n"
            "- Precise return type annotations (avoid bare Any)\n"
            "- Protocol for structural subtyping over ABC where appropriate\n"
            "- TypeVar / ParamSpec for generic functions\n"
            "- mypy strict mode compatibility\n"
            "- Using @override decorator for method overrides (3.12+)\n"
        ),
        model_preference="fast",
        skill_names=["python-typing"],
    ),
    "task-resolver": AgentProfile(
        name="task-resolver",
        description="TODO/FIXME resolution specialist",
        system_prompt_overlay=(
            "You are a task-resolver agent. Focus on:\n"
            "- Implementing the functionality described in the TODO comment\n"
            "- Respecting the original author's intent from context\n"
            "- Adding proper error handling, logging, or validation as described\n"
            "- Removing the TODO/FIXME/HACK/XXX comment after resolution\n"
            "- Creating a test for the newly implemented functionality\n"
            "- Keeping the implementation minimal — only what the TODO describes\n"
        ),
        model_preference="fast",
        skill_names=["todo-resolution"],
    ),
    "dependency-expert": AgentProfile(
        name="dependency-expert",
        description="Dependency upgrade and compatibility specialist",
        system_prompt_overlay=(
            "You are a dependency-expert agent. Focus on:\n"
            "- Checking release notes for breaking changes between versions\n"
            "- Verifying the target version supports our Python version\n"
            "- Identifying renamed parameters, moved imports, and changed defaults\n"
            "- Updating version pins in pyproject.toml / requirements files\n"
            "- Running tests to validate compatibility\n"
            "- Flagging transitive dependency conflicts\n"
        ),
        model_preference="balanced",
        skill_names=["dependency-management"],
    ),
    "general-refactorer": AgentProfile(
        name="general-refactorer",
        description="General-purpose refactoring agent (fallback)",
        system_prompt_overlay="",
        model_preference="auto",
        skill_names=["general-refactoring"],
    ),
}


# ── Finding type → agent mapping ──────────────────────────────────────────

FINDING_TYPE_AGENT_MAP: dict[str, str] = {
    FindingType.SECURITY.value: "security-auditor",
    FindingType.DEPRECATED_API.value: "modernization-expert",
    FindingType.CODE_SMELL.value: "quality-architect",
    FindingType.TYPE_COVERAGE.value: "type-advisor",
    FindingType.TODO_COMMENT.value: "task-resolver",
    FindingType.DEPENDENCY_UPGRADE.value: "dependency-expert",
}


# ── Public helpers ─────────────────────────────────────────────────────────


def select_agent(finding: Finding) -> AgentProfile:
    """Select the most appropriate agent profile for a finding.

    Falls back to ``"general-refactorer"`` for unmapped finding types.
    """
    type_value = finding.type.value if hasattr(finding.type, "value") else str(finding.type)
    agent_name = FINDING_TYPE_AGENT_MAP.get(type_value, "general-refactorer")
    profile = AGENT_REGISTRY[agent_name]
    logger.debug("Selected agent '%s' for finding type '%s'", profile.name, type_value)
    return profile


def get_agent_tools(
    profile: AgentProfile,
    all_tools: list[Any],
) -> list[Any]:
    """Filter the tool set based on the agent's ``tool_filter``.

    Returns all tools when ``tool_filter`` is ``None``.
    """
    if profile.tool_filter is None:
        return all_tools

    allowed = set(profile.tool_filter)
    return [
        t for t in all_tools
        if getattr(t, "__name__", getattr(t, "name", "")) in allowed
    ]


def list_agents() -> list[str]:
    """Return sorted list of registered agent names."""
    return sorted(AGENT_REGISTRY)
