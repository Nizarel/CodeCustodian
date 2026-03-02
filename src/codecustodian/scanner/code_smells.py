"""Code smell scanner.

Detects complexity and maintainability issues using **radon** (Python API)
and AST analysis (FR-SCAN-030 - 033, FR-SCAN-102):

- Cyclomatic complexity via ``radon.complexity.cc_visit``
- Cognitive complexity (Sonar-style)
- Maintainability index via ``radon.metrics.mi_visit``
- Long functions, too many parameters, deep nesting
- Dead code detection (single-file, private symbols)
- File-length check
"""

from __future__ import annotations

import ast
from pathlib import Path

from radon.complexity import cc_rank, cc_visit
from radon.metrics import mi_rank, mi_visit

from codecustodian.logging import get_logger
from codecustodian.models import Finding, FindingType, SeverityLevel
from codecustodian.scanner.base import BaseScanner

logger = get_logger("scanner.code_smells")

# Cognitive complexity default threshold
_DEFAULT_COGNITIVE_THRESHOLD = 15


class CodeSmellScanner(BaseScanner):
    """Detect code smells based on complexity metrics.

    Integrates the **radon** Python API for cyclomatic complexity and
    maintainability index, plus a Sonar-style cognitive complexity
    calculator and single-file dead code detection.
    """

    name = "code_smells"
    description = "Detects complexity and maintainability issues"

    def scan(self, repo_path: str | Path) -> list[Finding]:
        findings: list[Finding] = []
        thresholds = self._get_thresholds()

        for py_file in self.find_python_files(repo_path):
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError:
                logger.debug("Skipping %s — syntax error", py_file)
                continue

            findings.extend(self._analyze_functions(py_file, tree, thresholds))
            findings.extend(self._check_cyclomatic_complexity(py_file, source, thresholds))
            findings.extend(self._check_maintainability_index(py_file, source))
            findings.extend(self._check_cognitive_complexity(py_file, tree, thresholds))
            findings.extend(self._check_dead_code(py_file, tree))
            findings.extend(self._check_file_length(py_file, source, thresholds))

        return sorted(findings, key=lambda f: f.priority_score, reverse=True)

    # ── Thresholds ────────────────────────────────────────────────────

    def _get_thresholds(self) -> dict[str, int]:
        if self.config:
            cfg = self.config.scanners.code_smells
            return {
                "cyclomatic_complexity": cfg.cyclomatic_complexity,
                "function_length": cfg.function_length,
                "nesting_depth": cfg.nesting_depth,
                "max_parameters": cfg.max_parameters,
                "file_length": cfg.file_length,
                "cognitive_complexity": getattr(
                    cfg, "cognitive_complexity", _DEFAULT_COGNITIVE_THRESHOLD
                ),
            }
        return {
            "cyclomatic_complexity": 10,
            "function_length": 50,
            "nesting_depth": 4,
            "max_parameters": 5,
            "file_length": 500,
            "cognitive_complexity": _DEFAULT_COGNITIVE_THRESHOLD,
        }

    # ── Existing AST checks ──────────────────────────────────────────

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

    # ── Radon cyclomatic complexity (FR-SCAN-031 / 4.4.1) ────────────

    def _check_cyclomatic_complexity(
        self,
        file_path: Path,
        source: str,
        thresholds: dict[str, int],
    ) -> list[Finding]:
        """Use ``radon.complexity.cc_visit`` to detect high-CC functions."""
        findings: list[Finding] = []
        threshold = thresholds["cyclomatic_complexity"]

        try:
            blocks = cc_visit(source)
        except Exception:
            logger.debug("radon cc_visit failed for %s", file_path)
            return findings

        for block in blocks:
            if block.complexity > threshold:
                rank = cc_rank(block.complexity)
                findings.append(
                    Finding(
                        type=FindingType.CODE_SMELL,
                        severity=(
                            SeverityLevel.CRITICAL if rank in ("E", "F")
                            else SeverityLevel.HIGH if rank in ("C", "D")
                            else SeverityLevel.MEDIUM
                        ),
                        file=str(file_path),
                        line=block.lineno,
                        end_line=block.endline,
                        description=(
                            f"Function '{block.name}' has cyclomatic complexity "
                            f"{block.complexity} (rank {rank}, threshold: {threshold})"
                        ),
                        suggestion=(
                            "Reduce branching by extracting helper functions, "
                            "using early returns, or applying the strategy pattern"
                        ),
                        priority_score=min(
                            200.0, 80.0 + (block.complexity - threshold) * 5
                        ),
                        scanner_name=self.name,
                        metadata={
                            "metric": "cyclomatic_complexity",
                            "value": block.complexity,
                            "rank": rank,
                        },
                    )
                )

        return findings

    # ── Radon maintainability index (FR-SCAN-102 / 4.4.4) ────────────

    def _check_maintainability_index(
        self,
        file_path: Path,
        source: str,
    ) -> list[Finding]:
        """Report files with a maintainability index below 20 (rank B or C)."""
        findings: list[Finding] = []

        try:
            mi_score = mi_visit(source, multi=True)
        except Exception:
            logger.debug("radon mi_visit failed for %s", file_path)
            return findings

        rank = mi_rank(mi_score)
        if rank in ("B", "C"):
            findings.append(
                Finding(
                    type=FindingType.CODE_SMELL,
                    severity=(
                        SeverityLevel.HIGH if rank == "C" else SeverityLevel.MEDIUM
                    ),
                    file=str(file_path),
                    line=1,
                    description=(
                        f"File has low maintainability index: {mi_score:.1f} "
                        f"(rank {rank}, A > 19 is good)"
                    ),
                    suggestion=(
                        "Reduce overall complexity, shorten functions, "
                        "and improve documentation to raise MI"
                    ),
                    priority_score=min(200.0, 60.0 + (20 - mi_score) * 3),
                    scanner_name=self.name,
                    metadata={
                        "metric": "maintainability_index",
                        "mi_score": round(mi_score, 2),
                        "mi_rank": rank,
                    },
                )
            )

        return findings

    # ── Cognitive complexity (Sonar-style — FR-SCAN-102 / 4.4.2) ─────

    def _check_cognitive_complexity(
        self,
        file_path: Path,
        tree: ast.AST,
        thresholds: dict[str, int],
    ) -> list[Finding]:
        """Compute Sonar-style cognitive complexity per function."""
        findings: list[Finding] = []
        threshold = thresholds.get("cognitive_complexity", _DEFAULT_COGNITIVE_THRESHOLD)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                score = _cognitive_complexity(node)
                if score > threshold:
                    findings.append(
                        Finding(
                            type=FindingType.CODE_SMELL,
                            severity=(
                                SeverityLevel.HIGH if score > threshold * 2
                                else SeverityLevel.MEDIUM
                            ),
                            file=str(file_path),
                            line=node.lineno,
                            description=(
                                f"Function '{node.name}' has cognitive complexity "
                                f"{score} (threshold: {threshold})"
                            ),
                            suggestion=(
                                "Simplify control flow: reduce nesting, "
                                "flatten boolean expressions, extract helpers"
                            ),
                            priority_score=min(
                                200.0, 75.0 + (score - threshold) * 4
                            ),
                            scanner_name=self.name,
                            metadata={
                                "metric": "cognitive_complexity",
                                "value": score,
                            },
                        )
                    )

        return findings

    # ── Dead code detection (single-file — 4.4.3) ────────────────────

    def _check_dead_code(
        self, file_path: Path, tree: ast.AST
    ) -> list[Finding]:
        """Detect private functions/classes defined but never referenced.

        Only flags symbols starting with ``_`` (private) to reduce
        false positives from cross-module usage.
        """
        findings: list[Finding] = []

        # Pass 1: collect defined private names
        defined: dict[str, int] = {}  # name → lineno
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name.startswith("_") and not node.name.startswith("__"):
                    defined[node.name] = node.lineno

        if not defined:
            return findings

        # Pass 2: collect all referenced names
        referenced: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                referenced.add(node.id)
            elif isinstance(node, ast.Attribute):
                referenced.add(node.attr)

        # Report unreferenced private symbols
        for name, lineno in defined.items():
            if name not in referenced:
                findings.append(
                    Finding(
                        type=FindingType.CODE_SMELL,
                        severity=SeverityLevel.LOW,
                        file=str(file_path),
                        line=lineno,
                        description=f"Private symbol '{name}' appears unused in this file",
                        suggestion="Remove dead code or add a usage reference",
                        priority_score=30.0,
                        scanner_name=self.name,
                        metadata={"metric": "dead_code", "symbol": name},
                    )
                )

        return findings

    # ── File-length check ─────────────────────────────────────────────

    def _check_file_length(
        self,
        file_path: Path,
        source: str,
        thresholds: dict[str, int],
    ) -> list[Finding]:
        """Flag files exceeding the configured line-count limit."""
        findings: list[Finding] = []
        max_lines = thresholds.get("file_length", 500)
        line_count = source.count("\n") + 1

        if line_count > max_lines:
            findings.append(
                Finding(
                    type=FindingType.CODE_SMELL,
                    severity=SeverityLevel.MEDIUM,
                    file=str(file_path),
                    line=1,
                    description=(
                        f"File is {line_count} lines long "
                        f"(threshold: {max_lines})"
                    ),
                    suggestion="Consider splitting into smaller modules",
                    priority_score=min(
                        200.0, 50.0 + (line_count - max_lines) * 0.1
                    ),
                    scanner_name=self.name,
                    metadata={"metric": "file_length", "value": line_count},
                )
            )

        return findings

    # ── Nesting depth ─────────────────────────────────────────────────

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


# ── Cognitive complexity calculator ───────────────────────────────────────


def _cognitive_complexity(node: ast.AST, nesting: int = 0) -> int:
    """Compute Sonar-style cognitive complexity for an AST node.

    Rules:
    - +1 for each ``if / elif / else / for / while / except / with``
    - +1 nesting increment for each level of nesting
    - +1 for boolean sequence operators (``and`` / ``or``)
    - +1 for ``break`` / ``continue``
    """
    total = 0
    increment_nodes = (ast.If, ast.For, ast.While, ast.With, ast.ExceptHandler)

    for child in ast.iter_child_nodes(node):
        if isinstance(child, increment_nodes):
            # +1 inherent + nesting increment
            total += 1 + nesting
            total += _cognitive_complexity(child, nesting + 1)
        elif isinstance(child, ast.BoolOp):
            # +1 per boolean operator (and / or chain)
            total += len(child.values) - 1
            total += _cognitive_complexity(child, nesting)
        elif isinstance(child, (ast.Break, ast.Continue)):
            total += 1
        else:
            total += _cognitive_complexity(child, nesting)

    return total
