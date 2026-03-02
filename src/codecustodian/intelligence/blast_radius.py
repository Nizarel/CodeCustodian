"""Blast radius analysis for refactoring plans (Section 4.7).

Builds a reverse-dependency graph from AST-parsed imports across the repo,
then traverses the graph to quantify the downstream impact of proposed changes.
Uses stdlib only (ast, pathlib) — no external graph library needed.
"""

from __future__ import annotations

import ast
from collections import deque
from pathlib import Path

from pydantic import BaseModel, Field

from codecustodian.logging import get_logger
from codecustodian.models import RefactoringPlan

logger = get_logger("intelligence.blast_radius")


class BlastRadiusReport(BaseModel):
    """Impact analysis result for a refactoring plan."""

    directly_affected: list[str] = Field(default_factory=list)
    transitively_affected: list[str] = Field(default_factory=list)
    affected_tests: list[str] = Field(default_factory=list)
    total_files_in_repo: int = 0
    radius_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Fraction of codebase affected"
    )
    risk_level: str = "low"


class BlastRadiusAnalyzer:
    """Analyze the downstream impact of proposed code changes.

    Builds an import-based dependency graph and uses BFS to determine
    which modules are transitively affected by a change set.
    """

    def __init__(self, repo_path: str | Path) -> None:
        self.repo_path = Path(repo_path)
        self._graph: dict[str, set[str]] = {}  # module → set of modules it imports
        self._reverse: dict[str, set[str]] = {}  # module → set of modules that import it
        self._all_modules: set[str] = set()
        self._built = False

    def build_graph(self) -> None:
        """Walk the repo and build the import dependency graph."""
        py_files = sorted(self.repo_path.rglob("*.py"))
        for py_file in py_files:
            rel = str(py_file.relative_to(self.repo_path)).replace("\\", "/")
            # Skip hidden dirs, __pycache__, .venv etc.
            if any(part.startswith(".") or part == "__pycache__" for part in py_file.parts):
                continue
            module = self._path_to_module(rel)
            self._all_modules.add(module)
            imports = self._extract_imports(py_file)
            self._graph[module] = imports
            for imp in imports:
                self._reverse.setdefault(imp, set()).add(module)

        self._built = True
        logger.info(
            "Import graph built: %d modules, %d edges",
            len(self._all_modules),
            sum(len(v) for v in self._graph.values()),
        )

    def analyze(self, plan: RefactoringPlan) -> BlastRadiusReport:
        """Compute blast radius for a refactoring plan."""
        if not self._built:
            self.build_graph()

        # Seed: modules directly changed by the plan
        changed_modules: set[str] = set()
        for change in plan.changes:
            rel = change.file_path.replace("\\", "/")
            module = self._path_to_module(rel)
            changed_modules.add(module)

        # BFS through reverse-dependency graph
        visited: set[str] = set()
        queue: deque[str] = deque(changed_modules)
        direct: set[str] = set()
        transitive: set[str] = set()

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            dependents = self._reverse.get(current, set())
            for dep in dependents:
                if dep in changed_modules:
                    continue
                if dep not in visited:
                    if current in changed_modules:
                        direct.add(dep)
                    else:
                        transitive.add(dep)
                    queue.append(dep)

        # Remove overlap (direct takes precedence)
        transitive -= direct

        # Identify affected tests
        all_affected = changed_modules | direct | transitive
        tests = sorted(m for m in all_affected if self._is_test_module(m))

        total = max(len(self._all_modules), 1)
        radius = len(all_affected) / total

        if radius > 0.3:
            risk = "critical"
        elif radius > 0.15:
            risk = "high"
        elif radius > 0.05:
            risk = "medium"
        else:
            risk = "low"

        return BlastRadiusReport(
            directly_affected=sorted(direct),
            transitively_affected=sorted(transitive),
            affected_tests=tests,
            total_files_in_repo=total,
            radius_score=round(radius, 4),
            risk_level=risk,
        )

    def _extract_imports(self, file_path: Path) -> set[str]:
        """Extract imported module names from a Python file."""
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError):
            return set()

        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imports.add(node.module.split(".")[0])
        return imports

    def _path_to_module(self, rel_path: str) -> str:
        """Convert a relative file path to a dotted module name."""
        if rel_path.endswith("/__init__.py"):
            return rel_path[:-12].replace("/", ".")
        if rel_path.endswith(".py"):
            return rel_path[:-3].replace("/", ".")
        return rel_path.replace("/", ".")

    @staticmethod
    def _is_test_module(module: str) -> bool:
        """Check if a module name looks like a test module."""
        parts = module.split(".")
        return any(p.startswith("test_") or p == "tests" or p == "conftest" for p in parts)
