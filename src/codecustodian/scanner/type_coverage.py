"""Type coverage scanner.

Analyzes Python files for missing type annotations on functions
and reports overall type coverage percentage.
"""

from __future__ import annotations

import ast
from pathlib import Path

from codecustodian.logging import get_logger
from codecustodian.models import Finding, FindingType, SeverityLevel
from codecustodian.scanner.base import BaseScanner

logger = get_logger("scanner.type_coverage")


class TypeCoverageScanner(BaseScanner):
    """Scan for missing type annotations."""

    name = "type_coverage"
    description = "Detects functions missing type annotations"

    def scan(self, repo_path: str | Path) -> list[Finding]:
        findings: list[Finding] = []
        target_coverage = 80

        if self.config:
            target_coverage = self.config.scanners.type_coverage.target_coverage

        total_functions = 0
        typed_functions = 0

        for py_file in self.find_python_files(repo_path):
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Skip private/dunder methods for less noise
                    if node.name.startswith("_") and not node.name.startswith("__"):
                        continue

                    total_functions += 1
                    has_return = node.returns is not None
                    has_param_types = all(
                        arg.annotation is not None
                        for arg in node.args.args
                        if arg.arg != "self" and arg.arg != "cls"
                    )

                    if has_return and has_param_types:
                        typed_functions += 1
                    else:
                        missing = []
                        if not has_return:
                            missing.append("return type")
                        if not has_param_types:
                            missing.append("parameter types")

                        findings.append(
                            Finding(
                                type=FindingType.TYPE_COVERAGE,
                                severity=SeverityLevel.LOW,
                                file=str(py_file),
                                line=node.lineno,
                                description=(
                                    f"Function '{node.name}' missing: {', '.join(missing)}"
                                ),
                                suggestion="Add type annotations for better IDE support and safety",
                                priority_score=20.0,
                                scanner_name=self.name,
                                metadata={
                                    "function_name": node.name,
                                    "missing": missing,
                                },
                            )
                        )

        coverage = (typed_functions / total_functions * 100) if total_functions > 0 else 100
        logger.info(
            "Type coverage: %.1f%% (%d/%d functions typed, target: %d%%)",
            coverage,
            typed_functions,
            total_functions,
            target_coverage,
        )

        return sorted(findings, key=lambda f: f.priority_score, reverse=True)
