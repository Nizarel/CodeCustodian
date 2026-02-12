"""GitHub Copilot SDK client wrapper.

Wraps ``github-copilot-sdk`` for multi-turn AI planning sessions
with tool calling, model routing, and structured output.
"""

from __future__ import annotations

from typing import Any

from codecustodian.logging import get_logger
from codecustodian.models import (
    CodeContext,
    Finding,
    RefactoringPlan,
    RiskLevel,
)

logger = get_logger("planner.copilot_client")


class CopilotPlannerClient:
    """Wrapper around the GitHub Copilot SDK for refactoring planning.

    This client will be fully wired once the Copilot SDK is installed
    and available. Currently provides the interface and routing logic.
    """

    def __init__(
        self,
        *,
        token: str | None = None,
        model_selection: str = "auto",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        timeout: int = 30,
    ) -> None:
        self.token = token
        self.model_selection = model_selection
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self._client: Any = None

    def _ensure_client(self) -> None:
        """Lazily initialize the Copilot SDK client."""
        if self._client is not None:
            return

        try:
            from github_copilot_sdk import CopilotClient

            self._client = CopilotClient(token=self.token)
            logger.info("Copilot SDK client initialized")
        except ImportError:
            logger.warning(
                "github-copilot-sdk not installed — using fallback planning"
            )

    async def plan(
        self,
        finding: Finding,
        context: CodeContext,
    ) -> RefactoringPlan:
        """Generate a refactoring plan for a finding.

        Uses multi-turn conversation with the Copilot SDK to:
        1. Analyze the finding and context
        2. Request additional information via tool calls
        3. Generate a structured refactoring plan
        4. Score confidence based on context quality
        """
        self._ensure_client()

        model = self._select_model(finding)
        logger.info(
            "Planning for finding %s using model=%s",
            finding.id,
            model,
        )

        if self._client is None:
            # Fallback: return a stub plan when SDK not available
            return RefactoringPlan(
                finding_id=finding.id,
                summary=f"Refactor: {finding.description}",
                description=finding.suggestion,
                confidence_score=3,
                risk_level=RiskLevel.MEDIUM,
                ai_reasoning="Copilot SDK not available — manual review required",
                model_used="none",
            )

        # TODO: Full Copilot SDK integration (Phase 3)
        # Will implement:
        # 1. Build system + user prompts
        # 2. Register tools (@define_tool)
        # 3. Multi-turn conversation loop
        # 4. Parse structured output
        # 5. Calculate confidence score
        return RefactoringPlan(
            finding_id=finding.id,
            summary=f"Refactor: {finding.description}",
            confidence_score=5,
            risk_level=RiskLevel.LOW,
            model_used=model,
        )

    def _select_model(self, finding: Finding) -> str:
        """Route to the appropriate model based on complexity."""
        if self.model_selection != "auto":
            model_map = {
                "fast": "gpt-4o-mini",
                "balanced": "gpt-4o",
                "reasoning": "o1-preview",
            }
            return model_map.get(self.model_selection, "gpt-4o")

        # Auto-route based on finding characteristics
        if finding.severity.value in ("critical", "high"):
            return "gpt-4o"
        return "gpt-4o-mini"
