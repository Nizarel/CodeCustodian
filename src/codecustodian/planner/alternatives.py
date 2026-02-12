"""Alternative solution generation.

Generates multiple refactoring approaches for complex findings using
the Copilot SDK session.  Falls back to static alternatives when the
AI is unavailable.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from codecustodian.logging import get_logger
from codecustodian.models import AlternativeSolution, Finding, RefactoringPlan
from codecustodian.planner.prompts import build_alternatives_prompt

if TYPE_CHECKING:
    from codecustodian.planner.copilot_client import CopilotPlannerClient

logger = get_logger("planner.alternatives")


# ── Static fallback alternatives ───────────────────────────────────────────


def generate_static_alternatives(
    finding: Finding,
    primary_plan: RefactoringPlan,
) -> list[AlternativeSolution]:
    """Generate fallback alternative descriptions (no AI required).

    Returns structured ``AlternativeSolution`` objects with static
    suggestions based on finding type.
    """
    alternatives: list[AlternativeSolution] = []

    if finding.type.value == "deprecated_api":
        alternatives.append(
            AlternativeSolution(
                name="Compatibility wrapper",
                description="Suppress the deprecation warning with a compatibility wrapper",
                pros=["No code changes needed", "Quick to implement"],
                cons=["Warning persists", "May break in future versions"],
                confidence_score=4,
            )
        )
        alternatives.append(
            AlternativeSolution(
                name="Pin library version",
                description="Pin the library version to avoid the breaking change",
                pros=["Zero code changes", "Immediate fix"],
                cons=["Accumulates tech debt", "Security risk from old versions"],
                confidence_score=3,
            )
        )

    elif finding.type.value == "code_smell":
        alternatives.append(
            AlternativeSolution(
                name="Extract helper functions",
                description="Extract helper functions to reduce complexity",
                pros=["Improved readability", "Easier testing"],
                cons=["More files/functions to maintain"],
                confidence_score=6,
            )
        )
        alternatives.append(
            AlternativeSolution(
                name="Strategy pattern",
                description="Refactor to use a strategy/command pattern",
                pros=["Open-closed principle", "Easy to extend"],
                cons=["More boilerplate", "Potentially over-engineered"],
                confidence_score=5,
            )
        )

    elif finding.type.value == "security":
        alternatives.append(
            AlternativeSolution(
                name="Input validation",
                description="Add strict input validation and sanitization",
                pros=["Defense in depth", "Minimal code changes"],
                cons=["May not eliminate root cause"],
                confidence_score=5,
            )
        )

    elif finding.type.value == "todo_comment":
        alternatives.append(
            AlternativeSolution(
                name="Convert to issue",
                description="Convert TODO to a GitHub Issue for tracking",
                pros=["Better visibility", "Trackable"],
                cons=["TODO still in code unless removed"],
                confidence_score=7,
            )
        )
        alternatives.append(
            AlternativeSolution(
                name="Implement now",
                description="Remove the TODO and implement the suggested change",
                pros=["Clean code", "No deferred work"],
                cons=["Effort required", "Risk of side effects"],
                confidence_score=5,
            )
        )

    elif finding.type.value == "type_coverage":
        alternatives.append(
            AlternativeSolution(
                name="Gradual typing",
                description="Add type stubs (*.pyi) instead of inline annotations",
                pros=["No runtime changes", "Incremental adoption"],
                cons=["Stubs can drift from implementation"],
                confidence_score=5,
            )
        )

    return alternatives


# Keep backward-compatible alias
def generate_alternatives(
    finding: Finding,
    primary_plan: RefactoringPlan,
) -> list[str]:
    """Generate alternative description strings (legacy API).

    Returns plain strings for backward compatibility with existing tests.
    """
    alts = generate_static_alternatives(finding, primary_plan)
    return [a.description for a in alts]


# ── AI-powered alternative generator ──────────────────────────────────────


class AlternativeGenerator:
    """Generate 2-3 alternative refactoring approaches via the Copilot SDK.

    Uses the existing session from the planning turn to request
    alternatives in a follow-up turn (Turn 3).

    Falls back to static alternatives if AI generation fails.
    """

    def __init__(self, copilot_client: CopilotPlannerClient) -> None:
        self._client = copilot_client

    async def generate_alternatives(
        self,
        finding: Finding,
        session: Any,
        primary_plan: RefactoringPlan,
    ) -> list[AlternativeSolution]:
        """Request alternative approaches from the AI.

        Args:
            finding: The finding being planned for.
            session: Active ``CopilotSession`` (reuses Turn 2 context).
            primary_plan: The primary refactoring plan already generated.

        Returns:
            List of ``AlternativeSolution`` objects.
        """
        try:
            prompt = build_alternatives_prompt(primary_plan.summary)
            response = await self._client.send_and_wait(session, prompt)
            alternatives = self._parse_alternatives(response)
            if alternatives:
                logger.info(
                    "Generated %d AI alternatives for %s",
                    len(alternatives),
                    finding.id,
                )
                return alternatives
        except Exception:
            logger.warning(
                "AI alternative generation failed for %s — using fallback",
                finding.id,
                exc_info=True,
            )

        # Fallback to static alternatives
        return generate_static_alternatives(finding, primary_plan)

    def select_recommended(
        self, alternatives: list[AlternativeSolution]
    ) -> AlternativeSolution | None:
        """Mark the highest-confidence alternative as recommended.

        Breaks ties by fewest changes (simpler is better).
        Returns the recommended alternative, or None if list is empty.
        """
        if not alternatives:
            return None

        # Sort by confidence (desc), then by fewest changes (asc)
        ranked = sorted(
            alternatives,
            key=lambda a: (-a.confidence_score, len(a.changes)),
        )
        ranked[0].recommended = True
        return ranked[0]

    @staticmethod
    def _parse_alternatives(response: str) -> list[AlternativeSolution]:
        """Parse JSON array of alternatives from AI response.

        Handles both raw JSON and markdown-fenced code blocks.
        """
        text = response.strip()

        # Strip markdown fencing
        if text.startswith("```"):
            lines = text.splitlines()
            # Remove first and last ``` lines
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON array from response
            start = text.find("[")
            end = text.rfind("]")
            if start >= 0 and end > start:
                try:
                    data = json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    return []
            else:
                return []

        if not isinstance(data, list):
            data = [data]

        results: list[AlternativeSolution] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                alt = AlternativeSolution(
                    name=item.get("name", "Alternative"),
                    description=item.get("description", ""),
                    pros=item.get("pros", []),
                    cons=item.get("cons", []),
                    confidence_score=max(1, min(10, int(item.get("confidence_score", 5)))),
                    recommended=bool(item.get("recommended", False)),
                )
                results.append(alt)
            except (ValueError, TypeError):
                continue

        return results


def is_complex_finding(finding: Finding, *, threshold: int = 10) -> bool:
    """Determine if a finding warrants alternative generation.

    Complex findings: cyclomatic complexity > threshold, multi-file scope,
    or critical severity.
    """
    meta = finding.metadata
    cc = meta.get("cyclomatic_complexity", 0)
    if cc and int(cc) > threshold:
        return True
    if meta.get("multi_file", False):
        return True
    if finding.severity.value == "critical":
        return True
    return False
