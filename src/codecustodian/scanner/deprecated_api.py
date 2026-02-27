"""Deprecated API scanner.

Detects usage of deprecated library functions and suggests modern
replacements.  Uses AST parsing, import alias resolution, version-aware
urgency scoring, and usage frequency counting (FR-SCAN-010 – 014, FR-SCAN-100).
"""

from __future__ import annotations

import ast
import json
import re
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
        self._js_ts_rules = self._load_js_ts_rules()

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

        # Multi-language extension: JavaScript / TypeScript deprecation checks
        for src_file in self.find_files(repo_path, [".js", ".jsx", ".ts", ".tsx"]):
            try:
                source = src_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            findings.extend(self._check_js_ts_file(src_file, source))

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
                    severity_raw = str(rule.get("severity", "high")).lower()
                    if severity_raw not in {"critical", "high", "medium", "low", "info"}:
                        severity_raw = "high"
                    findings.append(
                        Finding(
                            type=FindingType.DEPRECATED_API,
                            severity=SeverityLevel(severity_raw),
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

    def _check_js_ts_file(self, file_path: Path, source: str) -> list[Finding]:
        """Detect deprecated JS/TS APIs via tree-sitter (when installed) or regex fallback."""
        findings: list[Finding] = []

        calls, parser_source = self._extract_js_ts_calls(source, file_path.suffix.lower())

        for rule in self._js_ts_rules.values():
            dep_name = rule["name"]
            if dep_name not in calls:
                continue

            match_line = self._first_matching_line(source, dep_name)
            severity_raw = str(rule.get("severity", "high")).lower()
            if severity_raw not in {"critical", "high", "medium", "low", "info"}:
                severity_raw = "high"

            findings.append(
                Finding(
                    type=FindingType.DEPRECATED_API,
                    severity=SeverityLevel(severity_raw),
                    file=str(file_path),
                    line=match_line,
                    description=rule.get("message", f"{dep_name} is deprecated"),
                    suggestion=rule.get("replacement", ""),
                    priority_score=min(200.0, float(rule.get("priority", 120.0))),
                    scanner_name=self.name,
                    metadata={
                        "deprecated_name": dep_name,
                        "deprecated_since": rule.get("deprecated_since", ""),
                        "language": file_path.suffix.lstrip(".").lower(),
                        "parser": parser_source,
                    },
                )
            )

        return findings

    def _extract_js_ts_calls(self, source: str, suffix: str) -> tuple[set[str], str]:
        """Extract call names from JS/TS source.

        Returns:
            (calls, parser_source) where parser_source is `tree-sitter` or `regex`.
        """
        calls = set()

        # Try tree-sitter first.
        try:
            from tree_sitter import Language, Parser  # type: ignore[import-untyped]

            if suffix in {".ts", ".tsx"}:
                import tree_sitter_typescript as tsts  # type: ignore[import-untyped]

                lang = Language(tsts.language_typescript())
            else:
                import tree_sitter_javascript as tsjs  # type: ignore[import-untyped]

                lang = Language(tsjs.language())

            parser = Parser(lang)
            tree = parser.parse(bytes(source, "utf8"))
            blob = source.encode("utf8")

            stack = [tree.root_node]
            while stack:
                node = stack.pop()
                if node.type == "call_expression":
                    fn = node.child_by_field_name("function")
                    if fn is not None:
                        text = blob[fn.start_byte:fn.end_byte].decode("utf8", errors="ignore")
                        calls.add(text.replace("?.", ".").strip())
                elif node.type == "new_expression":
                    ctor = node.child_by_field_name("constructor")
                    if ctor is not None:
                        text = blob[ctor.start_byte:ctor.end_byte].decode("utf8", errors="ignore")
                        calls.add(f"new {text.strip()}")

                stack.extend(list(node.children))

            if calls:
                return calls, "tree-sitter"
        except Exception:
            pass

        # Regex fallback keeps feature available when tree-sitter is not installed.
        for name in re.findall(r"\b([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*\(", source):
            calls.add(name.replace("?.", "."))
        for ctor in re.findall(r"\bnew\s+([A-Za-z_$][\w$]*)\s*\(", source):
            calls.add(f"new {ctor}")

        return calls, "regex"

    @staticmethod
    def _first_matching_line(source: str, dep_name: str) -> int:
        """Best-effort line locator for a deprecated API match."""
        needle = dep_name
        if dep_name.startswith("new "):
            needle = dep_name
        for idx, line in enumerate(source.splitlines(), start=1):
            if needle in line:
                return idx
        return 1

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
            indexed: dict[str, dict[str, Any]] = {}
        else:
            with open(rules_file) as f:
                raw = json.load(f)
            # Index by full dotted name for O(1) lookup
            indexed = {}
            for entry in raw.get("deprecations", []):
                indexed[entry["name"]] = entry

        # Merge user-defined rules from config (`custom_patterns`) as DSL-like entries.
        custom_rules = []
        if self.config:
            custom_rules = self.config.scanners.deprecated_apis.custom_patterns

        for rule in custom_rules:
            name = str(rule.get("name", "")).strip()
            if not name:
                continue
            indexed[name] = {
                "name": name,
                "message": str(rule.get("message", f"{name} is deprecated")).strip(),
                "replacement": str(rule.get("replacement", "")).strip(),
                "severity": str(rule.get("severity", "high")).strip().lower(),
                "deprecated_since": str(rule.get("deprecated_since", "")).strip(),
                "removal_version": str(rule.get("removal_version", "")).strip(),
                "priority": float(rule.get("priority", 110.0)),
                "migration_guide_url": str(rule.get("migration_guide_url", "")).strip(),
                "custom_rule": True,
            }

        return indexed

    def _load_js_ts_rules(self) -> dict[str, dict[str, Any]]:
        """Load JavaScript/TypeScript deprecation rules from JSON data file."""
        rules_file = _DATA_DIR / "deprecations_js_ts.json"
        if not rules_file.exists():
            return {}

        with open(rules_file) as f:
            raw = json.load(f)

        indexed: dict[str, dict[str, Any]] = {}
        for entry in raw.get("deprecations", []):
            name = str(entry.get("name", "")).strip()
            if not name:
                continue
            indexed[name] = entry

        return indexed


# ── Helpers ────────────────────────────────────────────────────────────────


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse a version string like ``'1.24.0'`` into a comparable tuple."""
    return tuple(int(x) for x in v.split(".")[:3])
