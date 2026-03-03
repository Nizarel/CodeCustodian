"""Planner orchestrator.

Coordinates the AI planning workflow using a multi-turn Copilot SDK
session:

    Turn 1 (tool-assisted): context gathering via ``send_streaming()``
    Turn 2 (plan generation): structured JSON via ``send_and_wait()``
    Turn 3 (alternatives):   optional AI-powered alternatives

Includes confidence scoring, reviewer-effort estimation, and
proposal-mode downgrade for low-confidence plans.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from codecustodian.logging import get_logger
from codecustodian.models import (
    ChangeType,
    CodeContext,
    FileChange,
    Finding,
    ProposalResult,
    RefactoringPlan,
    RiskLevel,
)
from codecustodian.planner.agents import get_agent_tools, select_agent
from codecustodian.planner.alternatives import (
    AlternativeGenerator,
    is_complex_finding,
)
from codecustodian.planner.confidence import calculate_confidence, estimate_reviewer_effort
from codecustodian.planner.copilot_client import CopilotPlannerClient
from codecustodian.planner.prompts import (
    SYSTEM_PROMPT,
    build_context_request_prompt,
    build_finding_prompt,
)
from codecustodian.planner.skills import SkillRegistry
from codecustodian.planner.tools import get_all_tools

if TYPE_CHECKING:
    from codecustodian.config.schema import CopilotConfig

logger = get_logger("planner")


class Planner:
    """Orchestrate AI-powered refactoring planning.

    Example::

        client = CopilotPlannerClient(config)
        await client.start()
        planner = Planner(config=config, copilot_client=client)
        result = await planner.plan_refactoring(finding, context)
        await client.stop()
    """

    def __init__(
        self,
        config: CopilotConfig,
        copilot_client: CopilotPlannerClient,
    ) -> None:
        self.config = config
        self.client = copilot_client
        self.alt_generator = AlternativeGenerator(copilot_client)
        # ── Skills & Agents ───────────────────────────────────────────
        self._skill_registry = SkillRegistry()
        skill_dir = config.custom_skill_dir or None
        self._skill_registry.load_skills(skill_dir)
        # Session pool: agent_name → session (for multi-session reuse)
        self._session_pool: dict[str, Any] = {}

    async def plan_refactoring(
        self,
        finding: Finding,
        context: CodeContext,
    ) -> RefactoringPlan | ProposalResult:
        """Create a refactoring plan using a multi-turn Copilot session.

        Steps:
        1. Select agent profile & load domain skills
        2. Select model (agent preference → finding severity)
        3. Create or reuse session with composite system prompt
        4. Turn 1: context gathering (tool-assisted streaming)
        5. Turn 2: plan generation (send_and_wait, JSON output)
        6. Turn 3: alternative generation (conditional)
        7. Post-process: confidence, reviewer effort, proposal downgrade
        """
        # ── Agent selection ───────────────────────────────────────────
        agent = select_agent(finding) if self.config.enable_agents else None
        agent_name = agent.name if agent else "default"

        # ── Skill loading ─────────────────────────────────────────────
        if agent and agent.skill_names:
            skills = self._skill_registry.get_skills_by_names(agent.skill_names)
        else:
            skills = self._skill_registry.get_skills_for_finding(finding.type.value)
        skill_context = self._skill_registry.format_skill_context(skills)

        # ── Model selection (agent preference overrides config) ───────
        preference = agent.model_preference if agent else ""
        model = self.client.select_model(finding, preference=preference)

        # ── Tool filtering ────────────────────────────────────────────
        all_tools = get_all_tools()
        tools = get_agent_tools(agent, all_tools) if agent else all_tools

        # ── Composite system prompt ───────────────────────────────────
        base_prompt = SYSTEM_PROMPT
        if agent and agent.system_prompt_overlay:
            base_prompt = f"{agent.system_prompt_overlay}\n\n{base_prompt}"

        logger.info(
            "Agent=%s model=%s skills=%d for %s",
            agent_name,
            model,
            len(skills),
            finding.id,
        )

        # ── Session: reuse from pool or create new ────────────────────
        session_reuse = self.config.session_reuse and agent is not None
        session = self._session_pool.get(agent_name) if session_reuse else None
        created_new = session is None

        if session is None:
            session = await self.client.create_session(
                model=model,
                tools=tools,
                system_prompt=base_prompt,
                skill_context=skill_context,
                session_reuse=session_reuse,
            )
            if session_reuse:
                self._session_pool[agent_name] = session

        try:
            # ── Turn 1: Context gathering (tool-assisted) ─────────────
            context_prompt = build_context_request_prompt(finding)
            await self.client.send_streaming(session, context_prompt)
            logger.debug(
                "Turn 1 complete — context gathered for %s", finding.id
            )

            # ── Turn 2: Plan generation ───────────────────────────────
            planning_prompt = build_finding_prompt(finding, context)
            raw_response = await self.client.send_and_wait(
                session, planning_prompt
            )

            plan = self._parse_plan(raw_response, finding, model)

            # Retry once on parse failure
            if plan is None:
                logger.warning(
                    "JSON parse failed for %s — retrying with clarification",
                    finding.id,
                )
                clarify = (
                    "Your previous response was not valid JSON. "
                    "Please respond with ONLY the JSON object following the "
                    "schema specified in the system prompt. No markdown, "
                    "no explanation — just the JSON."
                )
                raw_response = await self.client.send_and_wait(
                    session, clarify
                )
                plan = self._parse_plan(raw_response, finding, model)

            if plan is None:
                # Final fallback: return stub plan with confidence 1
                logger.error(
                    "Plan parse failed twice for %s — returning stub",
                    finding.id,
                )
                plan = RefactoringPlan(
                    finding_id=finding.id,
                    summary=f"Refactor: {finding.description}",
                    description="AI produced unparseable output",
                    confidence_score=1,
                    risk_level=RiskLevel.HIGH,
                    ai_reasoning="Failed to parse AI response",
                    model_used=model,
                )

            # ── Turn 3: Alternatives (conditional) ────────────────────
            if (
                self.config.enable_alternatives
                and is_complex_finding(finding)
            ):
                alternatives = await self.alt_generator.generate_alternatives(
                    finding, session, plan
                )
                plan.alternatives = alternatives
                recommended = self.alt_generator.select_recommended(
                    alternatives
                )
                if recommended:
                    logger.info(
                        "Recommended alternative: %s (confidence=%d)",
                        recommended.name,
                        recommended.confidence_score,
                    )

            # ── Post-processing ───────────────────────────────────────
            score, factors = calculate_confidence(plan, context)
            plan.confidence_score = score
            plan.confidence_factors = factors
            plan.reviewer_effort = estimate_reviewer_effort(
                plan, context, confidence=score
            )
            plan.model_used = model
            plan.estimated_tokens = (
                self.client.usage.input_tokens + self.client.usage.output_tokens
            )

            logger.info(
                "Plan created for %s: confidence=%d, effort=%s, risk=%s, model=%s",
                finding.id,
                plan.confidence_score,
                plan.reviewer_effort,
                plan.risk_level.value,
                model,
            )

            # ── Proposal downgrade (BR-PR-003) ───────────────────────
            if plan.confidence_score < self.config.proposal_mode_threshold:
                logger.info(
                    "Confidence %d < threshold %d — downgrading to proposal",
                    plan.confidence_score,
                    self.config.proposal_mode_threshold,
                )
                return self._convert_to_proposal(plan, finding)

            return plan

        finally:
            # Only destroy sessions that are NOT pooled for reuse
            if not session_reuse or not created_new:
                pass  # pooled session — kept alive for next finding
            else:
                # Non-pooled one-off session — clean up immediately
                pass
            if not session_reuse:
                try:
                    await session.destroy()
                except Exception:
                    logger.debug("Session cleanup failed", exc_info=True)

    async def close_sessions(self) -> None:
        """Destroy all pooled sessions. Call at pipeline shutdown."""
        for name, session in self._session_pool.items():
            try:
                await session.destroy()
                logger.debug("Closed pooled session for agent=%s", name)
            except Exception:
                logger.debug(
                    "Failed to close session for agent=%s", name, exc_info=True
                )
        self._session_pool.clear()

    # ── Parse helpers ──────────────────────────────────────────────────

    def _parse_plan(
        self,
        raw: str,
        finding: Finding,
        model: str,
    ) -> RefactoringPlan | None:
        """Parse a JSON response into a ``RefactoringPlan``.

        Returns ``None`` if parsing fails.
        """
        text = raw.strip()

        # Strip markdown fencing
        if text.startswith("```"):
            lines = text.splitlines()
            lines = [line for line in lines if not line.strip().startswith("```")]
            text = "\n".join(lines).strip()

        # Try to find JSON object
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None

        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None

        if not isinstance(data, dict):
            return None

        # Check for proposal mode response
        if data.get("is_proposal"):
            return None  # Handled by caller separately

        # Build FileChange objects
        changes: list[FileChange] = []
        for ch in data.get("changes", []):
            if not isinstance(ch, dict):
                continue
            changes.append(
                FileChange(
                    file_path=ch.get("file_path", finding.file),
                    change_type=ch.get("change_type", ChangeType.REPLACE),
                    old_content=ch.get("old_content", ""),
                    new_content=ch.get("new_content", ""),
                    start_line=ch.get("start_line"),
                    end_line=ch.get("end_line"),
                    description=ch.get("description", ""),
                )
            )

        # Build plan
        risk_str = data.get("risk_level", "medium")
        try:
            risk = RiskLevel(risk_str)
        except ValueError:
            risk = RiskLevel.MEDIUM

        return RefactoringPlan(
            finding_id=finding.id,
            summary=data.get("summary", f"Refactor: {finding.description}"),
            description=data.get("description", ""),
            changes=changes,
            confidence_score=max(1, min(10, int(data.get("confidence_score", 5)))),
            risk_level=risk,
            ai_reasoning=data.get("ai_reasoning", data.get("reasoning", "")),
            changes_signature=bool(data.get("changes_signature", False)),
            requires_manual_verification=bool(
                data.get("requires_manual_verification", False)
            ),
            model_used=model,
        )

    @staticmethod
    def _convert_to_proposal(
        plan: RefactoringPlan,
        finding: Finding,
    ) -> ProposalResult:
        """Downgrade a low-confidence plan to a proposal-only result."""
        steps: list[str] = []
        if plan.summary:
            steps.append(f"Review suggested refactoring: {plan.summary}")
        for change in plan.changes:
            steps.append(
                f"Modify {change.file_path}: {change.description or 'see diff'}"
            )
        if plan.ai_reasoning:
            steps.append(f"AI reasoning: {plan.ai_reasoning}")

        risks = [f"Low confidence ({plan.confidence_score}/10)"]
        if plan.changes_signature:
            risks.append("Involves function signature changes")
        if plan.requires_manual_verification:
            risks.append("Requires manual verification")

        return ProposalResult(
            finding=finding,
            recommended_steps=steps,
            estimated_effort=plan.reviewer_effort,
            risks=risks,
        )
