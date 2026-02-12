"""Confidence scoring for refactoring plans.

Calculates a 1-10 confidence score based on multiple factors
including test coverage, change scope, and complexity.
"""

from __future__ import annotations

from codecustodian.models import CodeContext, RefactoringPlan


def calculate_confidence(plan: RefactoringPlan, context: CodeContext) -> int:
    """Score confidence 1-10 based on multiple factors.

    High confidence (9-10):
    - Direct 1:1 API replacement
    - Comprehensive test coverage
    - No breaking changes to function signature

    Low confidence (1-4):
    - Complex multi-file refactoring
    - No test coverage
    - Significant logic changes
    """
    score = 10

    # Deduct for missing tests
    if not context.has_tests:
        score -= 3

    # Deduct for signature changes
    if plan.changes_signature:
        score -= 2

    # Deduct for multi-file changes
    files_changed = len(set(c.file_path for c in plan.changes))
    if files_changed > 3:
        score -= 2
    elif files_changed > 1:
        score -= 1

    # Deduct for manual verification needed
    if plan.requires_manual_verification:
        score -= 2

    # Deduct for many changes
    if len(plan.changes) > 5:
        score -= 1

    return max(1, min(10, score))
