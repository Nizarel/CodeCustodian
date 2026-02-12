"""Code smell scanner.

Detects complexity issues using radon and AST analysis:
- Cyclomatic complexity
- Long functions
- Deep nesting
- Too many parameters
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from codecustodian.logging import get_logger
from codecustodian.models import Finding, FindingType, SeverityLevel
from codecustodian.scanner.base import BaseScanner

logger = get_logger("scanner.code_smells")


class CodeSmellScanner(BaseScanner):
    """Detect code smells based on complexity metrics."""

    name = "code_smells"
    description = "Detects complexity and maintainability issues"

    def scan(self, repo_path: str | Path) -> list[Finding]:
        findings: list[Finding] = []
        thresholds = self._get_thresholds()

        for py_file in self.find_python_files(repo_path):
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(source, filename=str(py_file))
                findings.extend(self._analyze_functions(py_file, tree, thresholds))
            except SyntaxError:
                logger.debug("Skipping %s — syntax error", py_file)

        return sorted(findings, key=lambda f: f.priority_score, reverse=True)

    def _get_thresholds(self) -> dict[str, int]:
        if self.config:
            cfg = self.config.scanners.code_smells
            return {
                "cyclomatic_complexity": cfg.cyclomatic_complexity,
                "function_length": cfg.function_length,
                "nesting_depth": cfg.nesting_depth,
                "max_parameters": cfg.max_parameters,
            }
        return {
            "cyclomatic_complexity": 10,
            "function_length": 50,
            "nesting_depth": 4,
            "max_parameters": 5,
        }

    def _analyze_functions(
        self, file_path: Path, tree: ast.AST, thresholds: dict[str, int]
    ) -> list[Finding]:
        findings: list[Finding] = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check function length
                if hasattr(node, "end_lineno") and node.end_lineno:
                    length = node.end_lineno - node.lineno + 1
                    if length > thresholds["function_length"]:
                        findings.append(
                            Finding(
                                type=FindingType.CODE_SMELL,
                                severity=SeverityLevel.MEDIUM,
                                file=str(file_path),
                                line=node.lineno,
                                end_line=node.end_lineno,
                                description=(
                                    f"Function '{node.name}' is {length} lines long "
                                    f"(threshold: {thresholds['function_length']})"
                                ),
                                suggestion="Consider breaking this function into smaller pieces",
                                priority_score=70.0 + min(length - thresholds["function_length"], 50),
                                scanner_name=self.name,
                                metadata={"metric": "function_length", "value": length},
                            )
                        )

                # Check parameter count
                params = len(node.args.args)
                if params > thresholds["max_parameters"]:
                    findings.append(
                        Finding(
                            type=FindingType.CODE_SMELL,
                            severity=SeverityLevel.MEDIUM,
                            file=str(file_path),
                            line=node.lineno,
                            description=(
                                f"Function '{node.name}' has {params} parameters "
                                f"(threshold: {thresholds['max_parameters']})"
                            ),
                            suggestion="Consider using a data class or configuration object",
                            priority_score=60.0 + (params - thresholds["max_parameters"]) * 5,
                            scanner_name=self.name,
                            metadata={"metric": "parameters", "value": params},
                        )
                    )

                # Check nesting depth
                max_depth = self._max_nesting_depth(node)
                if max_depth > thresholds["nesting_depth"]:
                    findings.append(
                        Finding(
                            type=FindingType.CODE_SMELL,
                            severity=SeverityLevel.HIGH if max_depth > 6 else SeverityLevel.MEDIUM,
                            file=str(file_path),
                            line=node.lineno,
                            description=(
                                f"Function '{node.name}' has nesting depth {max_depth} "
                                f"(threshold: {thresholds['nesting_depth']})"
                            ),
                            suggestion="Use early returns or extract helper functions to reduce nesting",
                            priority_score=80.0 + (max_depth - thresholds["nesting_depth"]) * 10,
                            scanner_name=self.name,
                            metadata={"metric": "nesting_depth", "value": max_depth},
                        )
                    )

        return findings

    def _max_nesting_depth(self, node: ast.AST, current: int = 0) -> int:
        """Calculate maximum nesting depth of control-flow statements."""
        max_depth = current
        nesting_nodes = (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.ExceptHandler)

        for child in ast.iter_child_nodes(node):
            if isinstance(child, nesting_nodes):
                depth = self._max_nesting_depth(child, current + 1)
                max_depth = max(max_depth, depth)
            else:
                depth = self._max_nesting_depth(child, current)
                max_depth = max(max_depth, depth)

        return max_depth
