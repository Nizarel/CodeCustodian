"""Type coverage scanner.

Analyzes Python files for missing type annotations on functions
and reports per-file and overall type coverage percentages
(FR-SCAN-050 – 052, FR-SCAN-104).

AI-inferred type suggestions are deferred to Phase 3 (Copilot SDK).
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from codecustodian.logging import get_logger
from codecustodian.models import Finding, FindingType, SeverityLevel
from codecustodian.scanner.base import BaseScanner

logger = get_logger("scanner.type_coverage")


class TypeCoverageScanner(BaseScanner):
    """Scan for missing type annotations with per-file coverage reporting.

    When ``strict_mode`` is enabled (via config), private/dunder
    methods are also checked.
    """

    name = "type_coverage"
    description = "Detects functions missing type annotations"

    def scan(self, repo_path: str | Path) -> list[Finding]:
        findings: list[Finding] = []
        target_coverage = 80
        strict_mode = False

        if self.config:
            cfg = self.config.scanners.type_coverage
            target_coverage = cfg.target_coverage
            strict_mode = cfg.strict_mode

        total_functions = 0
        typed_functions = 0
        per_file_stats: dict[str, dict[str, int]] = {}

        for py_file in self.find_python_files(repo_path):
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError:
                continue

            file_total = 0
            file_typed = 0

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Skip private methods unless strict_mode
                    if not strict_mode:
                        if node.name.startswith("_") and not node.name.startswith("__"):
                            continue

                    total_functions += 1
                    file_total += 1

                    has_return = node.returns is not None
                    has_param_types = all(
                        arg.annotation is not None
                        for arg in node.args.args
                        if arg.arg != "self" and arg.arg != "cls"
                    )

                    if has_return and has_param_types:
                        typed_functions += 1
                        file_typed += 1
                    else:
                        missing: list[str] = []
                        if not has_return:
                            missing.append("return type")
                        if not has_param_types:
                            missing.append("parameter types")

                        # TODO(Phase 3): AI-inferred type suggestions via Copilot SDK
                        ai_suggestion = self._suggest_types(node)

                        suggestion = "Add type annotations for better IDE support and safety"
                        if ai_suggestion:
                            suggestion = f"{suggestion}. Suggested: {ai_suggestion}"

                        findings.append(
                            Finding(
                                type=FindingType.TYPE_COVERAGE,
                                severity=SeverityLevel.LOW,
                                file=str(py_file),
                                line=node.lineno,
                                description=(
                                    f"Function '{node.name}' missing: {', '.join(missing)}"
                                ),
                                suggestion=suggestion,
                                priority_score=20.0,
                                scanner_name=self.name,
                                metadata={
                                    "function_name": node.name,
                                    "missing": missing,
                                },
                            )
                        )

            if file_total > 0:
                file_key = str(py_file)
                per_file_stats[file_key] = {
                    "total": file_total,
                    "typed": file_typed,
                }
                file_coverage = file_typed / file_total * 100
                # Generate a per-file summary finding when below target
                if file_coverage < target_coverage:
                    findings.append(
                        Finding(
                            type=FindingType.TYPE_COVERAGE,
                            severity=(
                                SeverityLevel.MEDIUM
                                if file_coverage < target_coverage / 2
                                else SeverityLevel.LOW
                            ),
                            file=file_key,
                            line=1,
                            description=(
                                f"File type coverage {file_coverage:.0f}% "
                                f"({file_typed}/{file_total} functions typed, "
                                f"target: {target_coverage}%)"
                            ),
                            suggestion=(
                                f"Add type annotations to {file_total - file_typed} "
                                f"more functions to reach {target_coverage}% coverage"
                            ),
                            priority_score=25.0 + max(
                                0, (target_coverage - file_coverage) * 0.3
                            ),
                            scanner_name=self.name,
                            metadata={
                                "metric": "file_type_coverage",
                                "file_coverage": round(file_coverage, 1),
                                "total": file_total,
                                "typed": file_typed,
                            },
                        )
                    )

        overall = (typed_functions / total_functions * 100) if total_functions > 0 else 100
        logger.info(
            "Type coverage: %.1f%% (%d/%d functions typed, target: %d%%)",
            overall,
            typed_functions,
            total_functions,
            target_coverage,
        )

        return sorted(findings, key=lambda f: f.priority_score, reverse=True)

    # ── AI type suggestion stub (Phase 3) ─────────────────────────────

    @staticmethod
    def _suggest_types(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
        """Return AI-inferred type suggestions for *node*.

        .. note::

            Placeholder — will integrate GitHub Copilot SDK in Phase 3
            to provide context-aware type suggestions ranked by
            business value (FR-SCAN-104).
        """
        # TODO(Phase 3): Integrate Copilot SDK for AI-inferred type suggestions
        return None
