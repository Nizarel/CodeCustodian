"""Deprecated API scanner.

Detects usage of deprecated library functions and suggests modern replacements.
Uses AST parsing + a JSON deprecation database.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from codecustodian.logging import get_logger
from codecustodian.models import Finding, FindingType, SeverityLevel
from codecustodian.scanner.base import BaseScanner

logger = get_logger("scanner.deprecated_api")

_DATA_DIR = Path(__file__).parent / "data"


class DeprecatedAPIScanner(BaseScanner):
    """Scan for deprecated API usage based on AST analysis."""

    name = "deprecated_apis"
    description = "Detects deprecated library function calls"

    def __init__(self, config: Any = None) -> None:
        super().__init__(config)
        self._rules = self._load_rules()

    def scan(self, repo_path: str | Path) -> list[Finding]:
        findings: list[Finding] = []
        py_files = self.find_python_files(repo_path)

        for py_file in py_files:
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(source, filename=str(py_file))
                findings.extend(self._check_file(py_file, tree))
            except SyntaxError:
                logger.debug("Skipping %s — syntax error", py_file)

        return sorted(findings, key=lambda f: f.priority_score, reverse=True)

    def _check_file(self, file_path: Path, tree: ast.AST) -> list[Finding]:
        """Walk AST and match against deprecation rules."""
        findings: list[Finding] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                full_name = self._resolve_attribute(node)
                if full_name and full_name in self._rules:
                    rule = self._rules[full_name]
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
                            priority_score=rule.get("priority", 100.0),
                            scanner_name=self.name,
                            metadata={
                                "deprecated_name": full_name,
                                "deprecated_since": rule.get("deprecated_since", ""),
                                "removal_version": rule.get("removal_version", ""),
                            },
                        )
                    )

        return findings

    def _resolve_attribute(self, node: ast.Attribute) -> str | None:
        """Try to resolve ``obj.attr`` to a dotted name string."""
        parts: list[str] = [node.attr]
        current = node.value
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
            return ".".join(reversed(parts))
        return None

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
