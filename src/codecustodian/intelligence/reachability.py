"""Reachability analysis for security findings (v0.14.0).

Determines whether a finding's module is reachable from application
entry points (Flask routes, FastAPI endpoints, Lambda handlers, etc.)
by building an import-level dependency graph and running reverse BFS.

Findings reachable from public entry points are tagged ``"reachable"``
and should be prioritised higher than ``"internal_only"`` code.

Reuses AST-based import extraction patterns from
``codecustodian.intelligence.blast_radius``.
"""

from __future__ import annotations

import ast
from collections import deque
from pathlib import Path

from pydantic import BaseModel, Field

from codecustodian.logging import get_logger
from codecustodian.models import Finding, ReachabilityResult

logger = get_logger("intelligence.reachability")

# ── Decorator / pattern constants for entry-point detection ────────────────

_FLASK_DECORATORS = {"route", "get", "post", "put", "delete", "patch"}
_FASTAPI_DECORATORS = {"get", "post", "put", "delete", "patch", "options", "head", "api_route"}
_DJANGO_VIEW_BASES = {"View", "APIView", "GenericAPIView", "ModelViewSet", "ViewSet"}


class EntryPoint(BaseModel):
    """A detected application entry point."""

    module: str
    kind: str = Field(description="flask | fastapi | django | lambda | main")
    detail: str = ""


class ReachabilityAnalyzer:
    """Trace reachability from entry points to finding modules.

    Builds a forward import graph (module → modules it imports) and
    a reverse graph (module → modules that import it), detects entry
    points via AST inspection, then uses BFS on the forward graph to
    find paths from entry points to target modules.
    """

    def __init__(self, repo_path: str | Path) -> None:
        self.repo_path = Path(repo_path)
        self._forward: dict[str, set[str]] = {}  # module → what it imports
        self._reverse: dict[str, set[str]] = {}  # module → who imports it
        self._all_modules: set[str] = set()
        self._entry_points: list[EntryPoint] = []
        self._built = False

    # ── Graph construction ─────────────────────────────────────────────

    def build_graph(self) -> None:
        """Walk the repo, build the import graph, and detect entry points."""
        py_files = sorted(self.repo_path.rglob("*.py"))
        for py_file in py_files:
            if any(part.startswith(".") or part == "__pycache__" for part in py_file.parts):
                continue

            rel = str(py_file.relative_to(self.repo_path)).replace("\\", "/")
            module = self._path_to_module(rel)
            self._all_modules.add(module)

            imports = self._extract_imports(py_file)
            self._forward[module] = imports
            for imp in imports:
                self._reverse.setdefault(imp, set()).add(module)

            # Detect entry points in this file
            entry = self._detect_entry_point(py_file, module)
            if entry:
                self._entry_points.append(entry)

        self._built = True
        logger.info(
            "Reachability graph: %d modules, %d entry points",
            len(self._all_modules),
            len(self._entry_points),
        )

    # ── Entry-point detection ──────────────────────────────────────────

    def detect_entry_points(self) -> list[EntryPoint]:
        """Return detected entry points (builds graph if needed)."""
        if not self._built:
            self.build_graph()
        return list(self._entry_points)

    def _detect_entry_point(self, file_path: Path, module: str) -> EntryPoint | None:
        """Inspect a file's AST for entry-point patterns."""
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError):
            return None

        for node in ast.walk(tree):
            # Flask / FastAPI route decorators
            if isinstance(node, ast.FunctionDef) and node.decorator_list:
                for dec in node.decorator_list:
                    kind = self._check_route_decorator(dec)
                    if kind:
                        return EntryPoint(
                            module=module,
                            kind=kind,
                            detail=f"{node.name}()",
                        )

            # Django class-based views
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    base_name = ""
                    if isinstance(base, ast.Name):
                        base_name = base.id
                    elif isinstance(base, ast.Attribute):
                        base_name = base.attr
                    if base_name in _DJANGO_VIEW_BASES:
                        return EntryPoint(
                            module=module,
                            kind="django",
                            detail=f"class {node.name}",
                        )

            # Lambda handler: def handler(event, context)
            if isinstance(node, ast.FunctionDef) and node.name == "handler":
                args = [a.arg for a in node.args.args]
                if "event" in args and "context" in args:
                    return EntryPoint(
                        module=module,
                        kind="lambda",
                        detail="handler(event, context)",
                    )

        # if __name__ == "__main__" block
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.If)
                and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name)
                and node.test.left.id == "__name__"
            ):
                return EntryPoint(
                    module=module,
                    kind="main",
                    detail='if __name__ == "__main__"',
                )

        return None

    @staticmethod
    def _check_route_decorator(dec: ast.expr) -> str | None:
        """Check if a decorator is a Flask/FastAPI route. Returns framework name or None."""
        # @app.route("/...") or @router.get("/...")
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
            attr = dec.func.attr
            if attr in _FLASK_DECORATORS:
                # Heuristic: check the variable name for framework hint
                if isinstance(dec.func.value, ast.Name):
                    var = dec.func.value.id
                    if var in ("app", "blueprint", "bp"):
                        return "flask"
                    if var in ("router", "app"):
                        return "fastapi"
                return "flask"  # default to flask for .route()
        # @app.route without call (rare)
        if isinstance(dec, ast.Attribute) and dec.attr in _FLASK_DECORATORS:
            return "flask"
        return None

    # ── Reachability tracing ───────────────────────────────────────────

    def trace_reachability(self, target_module: str) -> list[list[str]]:
        """Find all paths from entry points to *target_module*.

        Uses BFS on the forward import graph starting from each entry
        point module.  Returns a list of module chains (paths).
        """
        if not self._built:
            self.build_graph()

        chains: list[list[str]] = []
        for ep in self._entry_points:
            path = self._bfs_path(ep.module, target_module)
            if path:
                chains.append(path)
        return chains

    def _bfs_path(self, start: str, target: str) -> list[str] | None:
        """BFS from *start* to *target* over the forward import graph."""
        if start == target:
            return [start]

        visited: set[str] = set()
        queue: deque[list[str]] = deque([[start]])

        while queue:
            path = queue.popleft()
            current = path[-1]

            if current in visited:
                continue
            visited.add(current)

            for neighbour in self._forward.get(current, set()):
                if neighbour == target:
                    return [*path, neighbour]
                if neighbour not in visited and neighbour in self._all_modules:
                    queue.append([*path, neighbour])

        return None

    # ── Finding analysis ───────────────────────────────────────────────

    def analyze_finding(self, finding: Finding) -> ReachabilityResult:
        """Determine reachability for a single finding."""
        if not self._built:
            self.build_graph()

        rel = finding.file.replace("\\", "/")
        target = self._path_to_module(rel)
        chains = self.trace_reachability(target)
        is_reachable = len(chains) > 0

        framework = "unknown"
        if chains:
            # Use the framework of the first entry point that reaches the target
            for ep in self._entry_points:
                if any(chain[0] == ep.module for chain in chains):
                    framework = ep.kind
                    break

        return ReachabilityResult(
            finding_id=finding.id,
            entry_points=[chain[0] for chain in chains],
            call_chains=chains,
            is_reachable=is_reachable,
            reachability_tag="reachable" if is_reachable else "internal_only",
            framework=framework,
        )

    def analyze_findings(self, findings: list[Finding]) -> list[ReachabilityResult]:
        """Batch-analyze reachability for multiple findings."""
        if not self._built:
            self.build_graph()
        return [self.analyze_finding(f) for f in findings]

    # ── AST helpers (mirrors BlastRadiusAnalyzer) ──────────────────────

    @staticmethod
    def _extract_imports(file_path: Path) -> set[str]:
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

    @staticmethod
    def _path_to_module(rel_path: str) -> str:
        """Convert a relative file path to a dotted module name."""
        if rel_path.endswith("/__init__.py"):
            return rel_path[:-12].replace("/", ".")
        if rel_path.endswith(".py"):
            return rel_path[:-3].replace("/", ".")
        return rel_path.replace("/", ".")
