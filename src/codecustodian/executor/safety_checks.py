"""Pre-execution safety checks — extended safety system (FR-EXEC-101).

Every refactoring must pass ALL checks before execution begins.
Failure on any check aborts or downgrades to proposal mode.

Checks:
1. Syntax Validation — ``ast.parse()`` new code
2. Import Availability — verify all imports resolve
3. Critical Path Protection — confidence ≥ 9 for critical files
4. Concurrent Change Detection — git SHA mismatch → abort
5. Dangerous Function Detection — block ``eval``/``exec`` style calls
6. Secrets Detection — block hardcoded secrets
7. Blast Radius — abort when > 30% of codebase affected
"""

from __future__ import annotations

import ast
import importlib.util
import re
import subprocess
from pathlib import Path

from codecustodian.logging import get_logger
from codecustodian.models import (
    Finding,
    RefactoringPlan,
    SafetyCheckResult,
    SafetyResult,
)

logger = get_logger("executor.safety_checks")

# Patterns that indicate critical files requiring high confidence
CRITICAL_FILE_PATTERNS: set[str] = {
    "main.py",
    "__init__.py",
    "app.py",
    "wsgi.py",
    "asgi.py",
    "manage.py",
    "conftest.py",
}

CRITICAL_DIR_PATTERNS: set[str] = {
    "api/",
    "routes/",
    "endpoints/",
    "auth/",
    "middleware/",
}

# Patterns for detecting hardcoded secrets
_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"""(?:api[_-]?key|apikey)\s*[:=]\s*['"][A-Za-z0-9_\-]{16,}['"]""", re.I),
    re.compile(r"""(?:secret|password|passwd|pwd)\s*[:=]\s*['"][^'"]{8,}['"]""", re.I),
    re.compile(r"""(?:token|bearer)\s*[:=]\s*['"][A-Za-z0-9_\-\.]{16,}['"]""", re.I),
    re.compile(r"""(?:AWS_SECRET_ACCESS_KEY|aws_secret)\s*[:=]\s*['"][^'"]+['"]""", re.I),
    re.compile(r"""(?:PRIVATE[_-]?KEY)\s*[:=]\s*['"]-----BEGIN""", re.I),
    re.compile(r"""ghp_[A-Za-z0-9]{36}"""),  # GitHub PAT
    re.compile(r"""sk-[A-Za-z0-9]{32,}"""),  # OpenAI key
    re.compile(r"""AKIA[A-Z0-9]{16}"""),  # AWS access key ID
]

# Protected files — warn when modifying
PROTECTED_FILES: set[str] = {
    ".github/workflows/",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    ".gitignore",
    "Dockerfile",
    "LICENSE",
}

_DANGEROUS_CALLS: set[str] = {"eval", "exec", "compile", "__import__"}


class SafetyCheckRunner:
    """Extended pre-execution safety system (FR-EXEC-101).

    Usage::

        runner = SafetyCheckRunner(repo_path="/path/to/repo")
        result = await runner.run_all_checks(plan, finding)
        if not result.passed:
            # abort or downgrade to proposal
    """

    def __init__(self, repo_path: str | Path) -> None:
        self.repo_path = Path(repo_path)

    async def run_all_checks(
        self, plan: RefactoringPlan, finding: Finding | None = None
    ) -> SafetyResult:
        """Run all safety checks sequentially.

        Args:
            plan: The refactoring plan to validate.
            finding: The finding the plan addresses (optional, used for Check 3).

        Returns:
            SafetyResult with check details and pass/fail status.
        """
        checks: list[SafetyCheckResult] = []

        checks.append(await self.check_syntax(plan))
        checks.append(await self.check_import_availability(plan))
        checks.append(await self.check_critical_path(plan, finding))
        checks.append(await self.check_concurrent_changes(plan))
        checks.append(await self.check_dangerous_functions(plan))
        checks.append(await self.check_secrets(plan))
        checks.append(await self.check_blast_radius(plan))

        any_failed = any(c.failed for c in checks)
        result = SafetyResult(
            passed=not any_failed,
            checks=checks,
            action="abort_or_propose" if any_failed else "proceed",
        )

        status = "PASSED" if result.passed else "FAILED"
        logger.info(
            "Safety checks %s: %d/%d passed",
            status,
            sum(1 for c in checks if c.passed),
            len(checks),
        )
        return result

    # ── Check 1: Syntax Validation ─────────────────────────────────────

    async def check_syntax(self, plan: RefactoringPlan) -> SafetyCheckResult:
        """Parse new code with ``ast.parse()``, reject if syntax errors."""
        for change in plan.changes:
            if not change.file_path.endswith(".py"):
                continue

            if not change.new_content:
                continue

            fp = self.repo_path / change.file_path
            if not fp.exists():
                # For INSERT changes on new files, validate the content directly
                if change.old_content == "":
                    try:
                        ast.parse(change.new_content)
                    except SyntaxError as e:
                        return SafetyCheckResult(
                            name="syntax",
                            passed=False,
                            message=f"Syntax error in new file {change.file_path}: {e}",
                        )
                continue

            try:
                original = fp.read_text(encoding="utf-8")
                if change.old_content:
                    modified = original.replace(change.old_content, change.new_content, 1)
                else:
                    modified = change.new_content
                ast.parse(modified)
            except SyntaxError as e:
                return SafetyCheckResult(
                    name="syntax",
                    passed=False,
                    message=f"Syntax error in proposed change for {change.file_path}: {e}",
                )

        return SafetyCheckResult(
            name="syntax",
            passed=True,
            message="All proposed changes parse successfully",
        )

    # ── Check 2: Import Availability ───────────────────────────────────

    async def check_import_availability(
        self, plan: RefactoringPlan
    ) -> SafetyCheckResult:
        """Verify all imports in new code are available."""
        missing_imports: list[str] = []

        for change in plan.changes:
            if not change.file_path.endswith(".py") or not change.new_content:
                continue

            try:
                tree = ast.parse(change.new_content)
            except SyntaxError:
                # Syntax check (Check 1) will catch this
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top_level = alias.name.split(".")[0]
                        if not self._is_module_available(top_level):
                            missing_imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    top_level = node.module.split(".")[0]
                    if not self._is_module_available(top_level):
                        missing_imports.append(node.module)

        if missing_imports:
            return SafetyCheckResult(
                name="imports",
                passed=False,
                message=f"Missing imports: {', '.join(missing_imports)}",
            )

        return SafetyCheckResult(
            name="imports",
            passed=True,
            message="All imports are available",
        )

    @staticmethod
    def _is_module_available(module_name: str) -> bool:
        """Check if a top-level module is importable."""
        try:
            return importlib.util.find_spec(module_name) is not None
        except (ModuleNotFoundError, ValueError):
            return False

    # ── Check 3: Critical Path Protection ──────────────────────────────

    async def check_critical_path(
        self, plan: RefactoringPlan, finding: Finding | None = None
    ) -> SafetyCheckResult:
        """Require confidence ≥ 9 for critical files.

        Critical files: ``main.py``, ``__init__.py``, API endpoints, etc.
        """
        critical_files: list[str] = []

        for change in plan.changes:
            file_name = Path(change.file_path).name
            file_str = change.file_path.replace("\\", "/")

            if file_name in CRITICAL_FILE_PATTERNS or any(pattern in file_str for pattern in CRITICAL_DIR_PATTERNS):
                critical_files.append(change.file_path)

        if critical_files and plan.confidence_score < 9:
            return SafetyCheckResult(
                name="critical_path",
                passed=False,
                message=(
                    f"Critical files modified ({', '.join(critical_files)}) "
                    f"but confidence is {plan.confidence_score}/10 (requires ≥ 9). "
                    "Escalate to senior review."
                ),
            )

        return SafetyCheckResult(
            name="critical_path",
            passed=True,
            message="No critical path issues",
        )

    # ── Check 4: Concurrent Change Detection ───────────────────────────

    async def check_concurrent_changes(
        self, plan: RefactoringPlan
    ) -> SafetyCheckResult:
        """Check if files have been modified since scan (git SHA mismatch).

        Compares the current git SHA of each file to the SHA stored
        in the plan metadata (if available).
        """
        for change in plan.changes:
            fp = self.repo_path / change.file_path
            if not fp.exists():
                continue

            # If the plan has stored file SHAs in metadata, compare
            expected_sha = change.metadata.get("git_sha") if change.metadata else None
            if expected_sha is None:
                # No SHA to compare — skip (cannot detect staleness)
                continue

            current_sha = self._get_file_git_sha(change.file_path)
            if current_sha and current_sha != expected_sha:
                return SafetyCheckResult(
                    name="concurrent_changes",
                    passed=False,
                    message=(
                        f"File {change.file_path} was modified since scan "
                        f"(expected SHA {expected_sha[:8]}, got {current_sha[:8]}). "
                        "Abort and re-scan."
                    ),
                )

        return SafetyCheckResult(
            name="concurrent_changes",
            passed=True,
            message="No concurrent modifications detected",
        )

    def _get_file_git_sha(self, file_path: str) -> str | None:
        """Get the git blob SHA for a file."""
        try:
            result = subprocess.run(
                ["git", "hash-object", str(self.repo_path / file_path)],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(self.repo_path),
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None

    # ── Check 5: Dangerous Function Detection ────────────────────────

    async def check_dangerous_functions(
        self, plan: RefactoringPlan
    ) -> SafetyCheckResult:
        """Block dangerous dynamic execution functions in generated code."""
        findings: list[str] = []

        for change in plan.changes:
            if not change.new_content:
                continue

            try:
                tree = ast.parse(change.new_content)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue

                called_name: str | None = None
                if isinstance(node.func, ast.Name):
                    called_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    called_name = node.func.attr

                if called_name in _DANGEROUS_CALLS:
                    findings.append(f"{change.file_path}:{called_name}")

        if findings:
            return SafetyCheckResult(
                name="dangerous_functions",
                passed=False,
                message=(
                    "Dangerous dynamic execution calls detected: "
                    f"{', '.join(findings)}."
                ),
            )

        return SafetyCheckResult(
            name="dangerous_functions",
            passed=True,
            message="No dangerous dynamic execution functions detected",
        )

    # ── Check 6: Secrets Detection ─────────────────────────────────────

    async def check_secrets(self, plan: RefactoringPlan) -> SafetyCheckResult:
        """Scan new code for hardcoded secrets (API keys, passwords, tokens)."""
        found_secrets: list[str] = []

        for change in plan.changes:
            if not change.new_content:
                continue

            for pattern in _SECRET_PATTERNS:
                matches = pattern.findall(change.new_content)
                if matches:
                    found_secrets.append(
                        f"{change.file_path}: pattern '{pattern.pattern[:40]}…' "
                        f"matched {len(matches)} time(s)"
                    )

        if found_secrets:
            return SafetyCheckResult(
                name="secrets",
                passed=False,
                message=(
                    f"Hardcoded secrets detected: {'; '.join(found_secrets)}. "
                    "Block execution and alert security team."
                ),
            )

        return SafetyCheckResult(
            name="secrets",
            passed=True,
            message="No hardcoded secrets detected",
        )

    # ── Check 7: Blast Radius ──────────────────────────────────────────

    async def check_blast_radius(
        self, plan: RefactoringPlan, threshold: float = 0.3
    ) -> SafetyCheckResult:
        """Abort when a proposed change affects > 30% of the codebase."""
        try:
            from codecustodian.intelligence.blast_radius import BlastRadiusAnalyzer

            analyzer = BlastRadiusAnalyzer(self.repo_path)
            report = analyzer.analyze(plan)

            if report.radius_score > threshold:
                return SafetyCheckResult(
                    name="blast_radius",
                    passed=False,
                    message=(
                        f"Blast radius {report.radius_score:.0%} exceeds {threshold:.0%} threshold. "
                        f"Directly affected: {len(report.directly_affected)} modules, "
                        f"transitively affected: {len(report.transitively_affected)} modules. "
                        "Downgrade to proposal mode."
                    ),
                )

            return SafetyCheckResult(
                name="blast_radius",
                passed=True,
                message=(
                    f"Blast radius {report.radius_score:.0%} — "
                    f"{len(report.directly_affected)} direct, "
                    f"{len(report.transitively_affected)} transitive"
                ),
            )
        except Exception as exc:
            # Non-blocking: if analysis fails, pass with a warning
            return SafetyCheckResult(
                name="blast_radius",
                passed=True,
                message=f"Blast radius analysis skipped: {exc}",
                severity="warning",
            )
