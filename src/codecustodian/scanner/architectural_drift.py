"""Architectural drift detection scanner (Section 4.9).

Detects structural violations: circular dependencies, layer boundary
violations, forbidden imports, and module size violations.

Architecture rules are defined in ``.codecustodian.yml`` under the
``architecture:`` config section.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

from codecustodian.logging import get_logger
from codecustodian.models import Finding, FindingType, SeverityLevel
from codecustodian.scanner.base import BaseScanner

if TYPE_CHECKING:
    from codecustodian.config.schema import CodeCustodianConfig

logger = get_logger("scanner.architectural_drift")


class ArchitecturalDriftScanner(BaseScanner):
    """Detect architectural violations based on import graph analysis.

    Checks for:
    1. Circular dependencies between modules
    2. Layer boundary violations (e.g., controller → database)
    3. Forbidden import patterns from config
    4. Module size violations
    """

    name = "architectural_drift"
    description = "Detect architectural drift: circular deps, layer violations, forbidden imports"
    enabled = True

    def __init__(self, config: CodeCustodianConfig | None = None) -> None:
        super().__init__(config)
        self._arch_config = self._load_arch_config()

    def _load_arch_config(self) -> dict:
        """Load architecture rules from config or use sensible defaults."""
        if self.config and hasattr(self.config, "architecture"):
            return self.config.architecture  # type: ignore[return-value]

        # Default rules when no explicit architecture config exists
        return {
            "layers": {
                "cli": "presentation",
                "mcp": "presentation",
                "scanner": "domain",
                "planner": "domain",
                "executor": "domain",
                "verifier": "domain",
                "intelligence": "domain",
                "enterprise": "service",
                "integrations": "infrastructure",
                "config": "infrastructure",
            },
            "forbidden_imports": [
                {"from_layer": "infrastructure", "to_layer": "presentation"},
                {"from_layer": "domain", "to_layer": "presentation"},
            ],
            "max_module_lines": 600,
        }

    def scan(self, repo_path: str | Path) -> list[Finding]:
        """Scan for architectural drift violations."""
        root = Path(repo_path)
        findings: list[Finding] = []

        py_files = self.find_python_files(root)
        if not py_files:
            return findings

        # Build import map
        import_map: dict[str, list[str]] = {}
        file_sizes: dict[str, int] = {}
        for py_file in py_files:
            rel = str(py_file.relative_to(root)).replace("\\", "/")
            imports = self._get_imports(py_file)
            import_map[rel] = imports
            try:
                file_sizes[rel] = len(py_file.read_text(encoding="utf-8", errors="replace").splitlines())
            except OSError:
                file_sizes[rel] = 0

        # Check 1: Circular dependencies
        findings.extend(self._check_circular_deps(import_map, root))

        # Check 2: Layer boundary violations
        findings.extend(self._check_layer_violations(import_map))

        # Check 3: Module size violations
        findings.extend(self._check_module_sizes(file_sizes))

        # Set priority scores
        for f in findings:
            f.priority_score = self.calculate_priority(f)
            f.scanner_name = self.name

        return sorted(findings, key=lambda f: f.priority_score, reverse=True)

    def _get_imports(self, file_path: Path) -> list[str]:
        """Extract import module names from a file."""
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            return []

        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imports.append(node.module)
        return imports

    def _check_circular_deps(
        self, import_map: dict[str, list[str]], root: Path
    ) -> list[Finding]:
        """Detect circular import chains."""
        findings: list[Finding] = []
        # Build a simplified module graph from file-level imports
        module_graph: dict[str, set[str]] = {}
        file_to_module: dict[str, str] = {}

        for rel_path in import_map:
            module = self._rel_to_top_package(rel_path)
            file_to_module[rel_path] = module
            if module not in module_graph:
                module_graph[module] = set()

        for rel_path, imports in import_map.items():
            src_module = file_to_module[rel_path]
            for imp in imports:
                top = imp.split(".")[0]
                if top in module_graph and top != src_module:
                    module_graph[src_module].add(top)

        # Detect cycles using DFS
        visited: set[str] = set()
        rec_stack: set[str] = set()
        reported_cycles: set[frozenset[str]] = set()

        def _dfs(node: str, path: list[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in module_graph.get(node, set()):
                if neighbor not in visited:
                    _dfs(neighbor, [*path, neighbor])
                elif neighbor in rec_stack:
                    cycle_start = path.index(neighbor) if neighbor in path else -1
                    if cycle_start >= 0:
                        cycle = frozenset(path[cycle_start:])
                        if cycle not in reported_cycles and len(cycle) >= 2:
                            reported_cycles.add(cycle)
                            cycle_list = [*path[cycle_start:], neighbor]
                            findings.append(Finding(
                                type=FindingType.CODE_SMELL,
                                severity=SeverityLevel.HIGH,
                                file=f"{node}/__init__.py",
                                line=1,
                                description=(
                                    f"Circular dependency detected: "
                                    f"{' → '.join(cycle_list)}"
                                ),
                                suggestion="Break the cycle by introducing an interface or moving shared code to a common module.",
                                metadata={"drift_type": "circular_dependency", "cycle": cycle_list},
                            ))
            rec_stack.discard(node)

        for module in module_graph:
            if module not in visited:
                _dfs(module, [module])

        return findings

    def _check_layer_violations(self, import_map: dict[str, list[str]]) -> list[Finding]:
        """Check for forbidden cross-layer imports."""
        findings: list[Finding] = []
        layers = self._arch_config.get("layers", {})
        forbidden = self._arch_config.get("forbidden_imports", [])

        if not layers or not forbidden:
            return findings

        for rel_path, imports in import_map.items():
            src_pkg = self._rel_to_top_package(rel_path)
            src_layer = layers.get(src_pkg)
            if not src_layer:
                continue

            for imp in imports:
                parts = imp.split(".")
                # Find the deepest matching package in layers
                target_layer = None
                for part in parts:
                    if part in layers:
                        target_layer = layers[part]
                        break

                if not target_layer:
                    continue

                for rule in forbidden:
                    if rule["from_layer"] == src_layer and rule["to_layer"] == target_layer:
                        findings.append(Finding(
                            type=FindingType.CODE_SMELL,
                            severity=SeverityLevel.MEDIUM,
                            file=rel_path,
                            line=1,
                            description=(
                                f"Layer violation: {src_pkg} ({src_layer}) imports "
                                f"{imp} ({target_layer}). "
                                f"Rule: {src_layer} → {target_layer} is forbidden."
                            ),
                            suggestion=f"Route through the service layer instead of importing directly from {target_layer}.",
                            metadata={"drift_type": "layer_violation", "from_layer": src_layer, "to_layer": target_layer},
                        ))
        return findings

    def _check_module_sizes(self, file_sizes: dict[str, int]) -> list[Finding]:
        """Flag modules exceeding the configured line limit."""
        findings: list[Finding] = []
        max_lines = self._arch_config.get("max_module_lines", 600)

        for rel_path, lines in file_sizes.items():
            if lines > max_lines:
                findings.append(Finding(
                    type=FindingType.CODE_SMELL,
                    severity=SeverityLevel.LOW,
                    file=rel_path,
                    line=1,
                    description=(
                        f"Module {rel_path} has {lines} lines, exceeding "
                        f"the {max_lines}-line limit."
                    ),
                    suggestion="Consider splitting into smaller, focused modules.",
                    metadata={"drift_type": "module_size", "lines": lines, "limit": max_lines},
                ))
        return findings

    @staticmethod
    def _rel_to_top_package(rel_path: str) -> str:
        """Extract the top-level package name from a relative path."""
        parts = rel_path.replace("\\", "/").split("/")
        # Skip src/codecustodian prefix if present
        if len(parts) > 2 and parts[0] == "src":
            return parts[2] if len(parts) > 2 else parts[1]
        return parts[0]
