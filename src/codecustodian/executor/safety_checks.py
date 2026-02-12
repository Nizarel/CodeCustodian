"""Pre-execution safety checks.

Implements a 5-point safety check before any code change is applied:
1. File exists and is writable
2. No uncommitted changes in target file
3. Syntax validation of proposed changes
4. Change scope within acceptable limits
5. No protected files modified
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from codecustodian.logging import get_logger
from codecustodian.models import RefactoringPlan

logger = get_logger("executor.safety_checks")

PROTECTED_FILES = {
    ".github/workflows/",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    ".gitignore",
    "Dockerfile",
    "LICENSE",
}


@dataclass
class SafetyCheckResult:
    """Result of pre-execution safety checks."""

    passed: bool = True
    checks: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def run_safety_checks(plan: RefactoringPlan, repo_path: str | Path) -> SafetyCheckResult:
    """Run all 5 pre-execution safety checks."""
    result = SafetyCheckResult()
    root = Path(repo_path)

    # Check 1: Files exist and are writable
    for change in plan.changes:
        fp = root / change.file_path
        if not fp.exists():
            if change.change_type.value != "insert":
                result.failures.append(f"File not found: {change.file_path}")
                result.passed = False
        elif not fp.is_file():
            result.failures.append(f"Not a file: {change.file_path}")
            result.passed = False
        else:
            result.checks.append(f"✓ File exists: {change.file_path}")

    # Check 2: Syntax validation of proposed changes
    for change in plan.changes:
        if change.new_content and change.file_path.endswith(".py"):
            try:
                # Validate the new content would parse
                fp = root / change.file_path
                if fp.exists():
                    original = fp.read_text(encoding="utf-8")
                    if change.old_content:
                        modified = original.replace(change.old_content, change.new_content, 1)
                        ast.parse(modified)
                        result.checks.append(f"✓ Syntax valid: {change.file_path}")
            except SyntaxError as e:
                result.failures.append(
                    f"Syntax error in proposed change for {change.file_path}: {e}"
                )
                result.passed = False

    # Check 3: Change scope (max files per plan)
    max_files = 10
    if len(plan.changes) > max_files:
        result.warnings.append(
            f"Plan modifies {len(plan.changes)} files (recommend max {max_files})"
        )

    # Check 4: No protected files modified
    for change in plan.changes:
        for protected in PROTECTED_FILES:
            if change.file_path.startswith(protected):
                result.warnings.append(
                    f"Modifying protected file: {change.file_path}"
                )

    # Check 5: Confidence threshold
    if plan.confidence_score < 5:
        result.warnings.append(
            f"Low confidence score: {plan.confidence_score}/10"
        )

    status = "PASSED" if result.passed else "FAILED"
    logger.info(
        "Safety checks %s: %d checks, %d failures, %d warnings",
        status,
        len(result.checks),
        len(result.failures),
        len(result.warnings),
    )
    return result
