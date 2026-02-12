"""Alternative solution generation.

Generates multiple refactoring approaches for complex findings,
allowing teams to choose the best option.
"""

from __future__ import annotations

from codecustodian.models import Finding, RefactoringPlan


def generate_alternatives(
    finding: Finding,
    primary_plan: RefactoringPlan,
) -> list[str]:
    """Generate alternative refactoring approaches.

    Returns a list of alternative description strings.
    """
    alternatives: list[str] = []

    if finding.type.value == "deprecated_api":
        alternatives.append(
            "Suppress the deprecation warning with a compatibility wrapper"
        )
        alternatives.append(
            "Pin the library version to avoid the breaking change"
        )

    elif finding.type.value == "code_smell":
        alternatives.append(
            "Extract helper functions to reduce complexity"
        )
        alternatives.append(
            "Refactor to use a strategy/command pattern"
        )

    elif finding.type.value == "todo_comment":
        alternatives.append(
            "Convert TODO to a GitHub Issue for tracking"
        )
        alternatives.append(
            "Remove the TODO and implement the suggested change"
        )

    return alternatives
