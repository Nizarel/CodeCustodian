"""AI planner module using GitHub Copilot SDK.

Re-exports the public API so consumers can do::

    from codecustodian.planner import Planner, CopilotPlannerClient
"""

from codecustodian.planner.agents import (
    AgentProfile,
    get_agent_tools,
    list_agents,
    select_agent,
)
from codecustodian.planner.alternatives import (
    AlternativeGenerator,
    generate_alternatives,
    generate_static_alternatives,
    is_complex_finding,
)
from codecustodian.planner.confidence import (
    calculate_confidence,
    estimate_reviewer_effort,
)
from codecustodian.planner.copilot_client import (
    CopilotPlannerClient,
    ToolAuditEntry,
    UsageAccumulator,
)
from codecustodian.planner.planner import Planner
from codecustodian.planner.prompts import (
    SYSTEM_PROMPT,
    build_alternatives_prompt,
    build_context_request_prompt,
    build_finding_prompt,
    build_user_prompt,
    truncate_context,
)
from codecustodian.planner.skills import SkillDefinition, SkillRegistry
from codecustodian.planner.tools import get_all_tools

__all__ = [
    "SYSTEM_PROMPT",
    "AgentProfile",
    "AlternativeGenerator",
    "CopilotPlannerClient",
    "Planner",
    "SkillDefinition",
    "SkillRegistry",
    "ToolAuditEntry",
    "UsageAccumulator",
    "build_alternatives_prompt",
    "build_context_request_prompt",
    "build_finding_prompt",
    "build_user_prompt",
    "calculate_confidence",
    "estimate_reviewer_effort",
    "generate_alternatives",
    "generate_static_alternatives",
    "get_agent_tools",
    "get_all_tools",
    "is_complex_finding",
    "list_agents",
    "select_agent",
    "truncate_context",
]
