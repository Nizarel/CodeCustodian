"""Deprecated API scanner.

Detects usage of deprecated library functions and suggests modern
replacements.  Uses AST parsing, import alias resolution, version-aware
urgency scoring, and usage frequency counting (FR-SCAN-010 – 014, FR-SCAN-100).
"""

from __future__ import annotations

import ast
import json
from collections import Counter, defaultdict
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

from codecustodian.logging import get_logger
from codecustodian.models import Finding, FindingType, SeverityLevel
from codecustodian.scanner.base import BaseScanner

logger = get_logger("scanner.deprecated_api")

_DATA_DIR = Path(__file__).parent / "data"

# Package names on PyPI → importlib metadata distribution names
_DIST_NAMES: dict[str, str] = {
    "pd": "pandas",
    "pandas": "pandas",
    "np": "numpy",
    "numpy": "numpy",
    "flask": "flask",
    "django": "django",
    "requests": "requests",
}


class DeprecatedAPIScanner(BaseScanner):
    """Scan for deprecated API usage based on AST analysis.

    Enhancements over basic attribute matching:
    - **Import alias resolution** — ``import pandas as pd`` maps
      ``pd`` → ``pandas`` so ``pd.DataFrame.append`` is detected.
    - **Version-aware urgency** — compares installed version against
      ``removal_version`` to compute an urgency multiplier.
    - **Usage frequency counting** — aggregate counts per deprecated
      name across all files, stored in ``finding.metadata``.
    """

    name = "deprecated_apis"
    description = "Detects deprecated library function calls"

    def __init__(self, config: Any = None) -> None:
        super().__init__(config)
        self._rules = self._load_rules()

    # ── Public API ────────────────────────────────────────────────────

    def scan(self, repo_path: str | Path) -> list[Finding]:
        findings: list[Finding] = []
        py_files = self.find_python_files(repo_path)

        # Collect raw findings across all files
        for py_file in py_files:
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(source, filename=str(py_file))
                findings.extend(self._check_file(py_file, tree))
            except SyntaxError:
                logger.debug("Skipping %s — syntax error", py_file)

        # ── Usage frequency enrichment (FR-SCAN-013) ──────────────
        freq: Counter[str] = Counter()
        files_per_name: dict[str, set[str]] = defaultdict(set)
        for f in findings:
            dep_name = f.metadata.get("deprecated_name", "")
            freq[dep_name] += 1
            files_per_name[dep_name].add(f.file)

        for f in findings:
            dep_name = f.metadata.get("deprecated_name", "")
            f.metadata["usage_count"] = freq.get(dep_name, 1)
            f.metadata["affected_files"] = len(files_per_name.get(dep_name, set()))
            # Boost priority for high-frequency usage
            count = freq.get(dep_name, 1)
            if count >= 10:
                f.priority_score = min(200.0, f.priority_score * 1.3)
            elif count >= 5:
                f.priority_score = min(200.0, f.priority_score * 1.15)

        return sorted(findings, key=lambda f: f.priority_score, reverse=True)

    # ── Per-file analysis ─────────────────────────────────────────────

    def _check_file(self, file_path: Path, tree: ast.AST) -> list[Finding]:
        """Walk AST and match against deprecation rules.

        First builds an **import alias map** from ``import`` and
        ``from … import`` statements, then resolves attribute chains
        through those aliases.
        """
        alias_map = self._build_alias_map(tree)
        findings: list[Finding] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                full_name = self._resolve_attribute(node, alias_map)
                if full_name and full_name in self._rules:
                    rule = self._rules[full_name]
                    urgency = self._calculate_urgency(rule)
                    base_priority = rule.get("priority", 100.0) * urgency
                    findings.append(
                        Finding(
                            type=FindingType.DEPRECATED_API,
                            severity=SeverityLevel(rule.get("severity", "high")),
                            file=str(file_path),
                            line=node.lineno,
                            column=node.col_offset,
                            description=rule.get(
                                "message", f"{full_name} is deprecated"
                            ),
                            suggestion=rule.get("replacement", ""),
                            priority_score=min(200.0, base_priority),
                            scanner_name=self.name,
                            metadata={
                                "deprecated_name": full_name,
                                "deprecated_since": rule.get("deprecated_since", ""),
                                "removal_version": rule.get("removal_version", ""),
                                "migration_guide_url": rule.get(
                                    "migration_guide_url", ""
                                ),
                                "urgency": urgency,
                            },
                        )
                    )

        return findings

    # ── Import alias resolution (FR-SCAN-012 / 4.2.3) ────────────────

    @staticmethod
    def _build_alias_map(tree: ast.AST) -> dict[str, str]:
        """Extract import aliases from a module AST.

        Examples::

            import pandas as pd        → {"pd": "pandas"}
            import numpy               → {"numpy": "numpy"}
            from collections import OrderedDict as OD → {"OD": "collections.OrderedDict"}
            from os import path         → {"path": "os.path"}
        """
        alias_map: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    local = alias.asname or alias.name
                    alias_map[local] = alias.name
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    local = alias.asname or alias.name
                    alias_map[local] = f"{module}.{alias.name}" if module else alias.name
        return alias_map

    @staticmethod
    def _resolve_attribute(
        node: ast.Attribute,
        alias_map: dict[str, str] | None = None,
    ) -> str | None:
        """Resolve ``obj.attr`` to a fully-qualified dotted name.

        When *alias_map* is provided the leftmost ``ast.Name`` is
        looked up in the map first (e.g. ``pd`` → ``pandas``).
        """
        parts: list[str] = [node.attr]
        current = node.value
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            root = current.id
            if alias_map and root in alias_map:
                root = alias_map[root]
            parts.append(root)
            return ".".join(reversed(parts))
        return None

    # ── Version-aware urgency (FR-SCAN-014 / 4.2.4) ──────────────────

    @staticmethod
    def _calculate_urgency(rule: dict[str, Any]) -> float:
        """Return an urgency multiplier (1.0 – 2.0) based on version proximity.

        - Already past ``removal_version`` → 2.0
        - Within one minor version of removal → 1.5
        - Otherwise → 1.0
        """
        removal = rule.get("removal_version", "")
        if not removal:
            return 1.0

        dep_name = rule.get("name", "")
        # Derive the distribution name from the first dotted component
        top_level = dep_name.split(".")[0]
        dist_name = _DIST_NAMES.get(top_level)
        if not dist_name:
            return 1.0

        try:
            installed_str = importlib_metadata.version(dist_name)
        except importlib_metadata.PackageNotFoundError:
            return 1.0

        try:
            installed = _parse_version(installed_str)
            target = _parse_version(removal)
        except (ValueError, IndexError):
            return 1.0

        if installed >= target:
            return 2.0
        # Within one minor version
        if installed[0] == target[0] and target[1] - installed[1] <= 1:
            return 1.5
        return 1.0

    # ── Rule loading ──────────────────────────────────────────────────

    def _load_rules(self) -> dict[str, dict[str, Any]]:
        """Load deprecation rules from JSON data file."""
        rules_file = _DATA_DIR / "deprecations.json"
        if not rules_file.exists():
            logger.warning("Deprecation rules file not found: %s", rules_file)
            return {}
        with open(rules_file) as f:
            raw = json.load(f)
        # Index by full dotted name for O(1) lookup
        indexed: dict[str, dict[str, Any]] = {}
        for entry in raw.get("deprecations", []):
            indexed[entry["name"]] = entry
        return indexed


# ── Helpers ────────────────────────────────────────────────────────────────


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse a version string like ``'1.24.0'`` into a comparable tuple."""
    return tuple(int(x) for x in v.split(".")[:3])
