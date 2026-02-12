"""Planner orchestrator.

Coordinates the AI planning workflow: context gathering → prompt
building → Copilot SDK call → confidence scoring → plan validation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from codecustodian.logging import get_logger
from codecustodian.models import CodeContext, Finding, RefactoringPlan
from codecustodian.planner.confidence import calculate_confidence
from codecustodian.planner.copilot_client import CopilotPlannerClient

if TYPE_CHECKING:
    from codecustodian.config.schema import CopilotConfig

logger = get_logger("planner")


class Planner:
    """Orchestrate AI-powered refactoring planning."""

    def __init__(self, config: CopilotConfig | None = None, token: str | None = None) -> None:
        self.config = config
        self.client = CopilotPlannerClient(
            token=token,
            model_selection=config.model_selection if config else "auto",
            temperature=config.temperature if config else 0.1,
            max_tokens=config.max_tokens if config else 4096,
        )

    async def create_plan(
        self,
        finding: Finding,
        context: CodeContext,
    ) -> RefactoringPlan:
        """Create a refactoring plan for a finding.

        Steps:
        1. Call Copilot SDK with finding + context
        2. Calculate confidence score
        3. Generate alternatives
        4. Validate plan
        """
        plan = await self.client.plan(finding, context)

        # Recalculate confidence with full context
        plan.confidence_score = calculate_confidence(plan, context)

        logger.info(
            "Plan created for %s: confidence=%d, risk=%s",
            finding.id,
            plan.confidence_score,
            plan.risk_level.value,
        )

        return plan
