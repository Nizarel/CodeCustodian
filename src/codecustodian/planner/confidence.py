"""Confidence scoring for refactoring plans.

Calculates a 1-10 confidence score based on multiple factors
including test coverage, change scope, complexity, call sites,
and criticality.  Returns named factor strings for traceability.

Also provides reviewer effort estimation (low / medium / high).
"""

from __future__ import annotations

from codecustodian.models import CodeContext, RefactoringPlan


def calculate_confidence(
    plan: RefactoringPlan,
    context: CodeContext,
    *,
    scanner_adjustment: int = 0,
) -> tuple[int, list[str]]:
    """Score confidence 1-10 and return named deduction factors.

    High confidence (9-10):
    - Direct 1:1 API replacement
    - Comprehensive test coverage
    - No breaking changes to function signature

    Low confidence (1-4):
    - Complex multi-file refactoring
    - No test coverage
    - Significant logic changes

    Args:
        plan: The refactoring plan to score.
        context: Code context for the finding.
        scanner_adjustment: Adjustment from ``FeedbackCollector`` based
            on historical scanner success rate (FR-LEARN-100).
            Positive = increase threshold (reduce score), negative = boost.

    Returns:
        Tuple of ``(score, factors_list)`` where each factor string
        describes a deduction, e.g. ``"no_tests: -3"``.
    """
    score = 10
    factors: list[str] = []

    # ── Existing deductions ────────────────────────────────────────────

    # Deduct for missing tests
    if not context.has_tests:
        score -= 3
        factors.append("no_tests: -3")

    # Deduct for signature changes
    if plan.changes_signature:
        score -= 2
        factors.append("signature_change: -2")

    # Deduct for multi-file changes
    files_changed = len({c.file_path for c in plan.changes})
    if files_changed > 3:
        score -= 2
        factors.append(f"multi_file_{files_changed}: -2")
    elif files_changed > 1:
        score -= 1
        factors.append(f"multi_file_{files_changed}: -1")

    # Deduct for manual verification needed
    if plan.requires_manual_verification:
        score -= 2
        factors.append("manual_verification: -2")

    # Deduct for many changes
    if len(plan.changes) > 5:
        score -= 1
        factors.append(f"many_changes_{len(plan.changes)}: -1")

    # ── New deductions ─────────────────────────────────────────────────

    # Deduct for many call sites (high blast radius)
    call_site_count = len(context.call_sites)
    if call_site_count > 20:
        score -= 2
        factors.append(f"call_sites_{call_site_count}: -2")
    elif call_site_count > 10:
        score -= 1
        factors.append(f"call_sites_{call_site_count}: -1")

    # Deduct for low coverage percentage
    if context.coverage_percentage < 50:
        score -= 1
        factors.append(f"low_coverage_{context.coverage_percentage:.0f}%: -1")

    # Deduct for high usage frequency (hot path)
    if context.usage_frequency > 100:
        score -= 1
        factors.append(f"hot_path_{context.usage_frequency}: -1")

    # Deduct for critical-path code
    if context.criticality_level == "critical":
        score -= 1
        factors.append("critical_path: -1")

    # ── Learning-based adjustment (FR-LEARN-100) ───────────────────
    if scanner_adjustment > 0:
        score -= scanner_adjustment
        factors.append(f"scanner_history_adjustment: -{scanner_adjustment}")
    elif scanner_adjustment < 0:
        score -= scanner_adjustment  # Negative adjustment = boost
        factors.append(f"scanner_history_boost: +{abs(scanner_adjustment)}")

    final_score = max(1, min(10, score))
    return final_score, factors


def estimate_reviewer_effort(
    plan: RefactoringPlan,
    context: CodeContext,
    *,
    confidence: int | None = None,
) -> str:
    """Estimate reviewer effort: ``"low"`` / ``"medium"`` / ``"high"``.

    Args:
        plan: The refactoring plan.
        context: Code context for the finding.
        confidence: Pre-computed confidence score.  If ``None``,
            uses ``plan.confidence_score``.

    Returns:
        One of ``"low"``, ``"medium"``, ``"high"``.
    """
    conf = confidence if confidence is not None else plan.confidence_score
    files_changed = len({c.file_path for c in plan.changes})
    call_site_count = len(context.call_sites)

    # High effort: complex logic + many call sites + low confidence
    if conf < 5 or (call_site_count > 20 and files_changed > 3):
        return "high"

    # Low effort: single-file + high confidence + no signature changes
    if (
        files_changed <= 1
        and conf >= 8
        and not plan.changes_signature
    ):
        return "low"

    # Medium: everything else
    return "medium"
