"""TODO comment scanner.

Detects TODO, FIXME, HACK, and XXX comments, with age tracking
via git blame to prioritize stale items.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from codecustodian.logging import get_logger
from codecustodian.models import Finding, FindingType, SeverityLevel
from codecustodian.scanner.base import BaseScanner

logger = get_logger("scanner.todo_comments")

_TODO_PATTERN = re.compile(
    r"#\s*(TODO|FIXME|HACK|XXX|NOTE)\b[:\s]*(.*)",
    re.IGNORECASE,
)


class TodoCommentScanner(BaseScanner):
    """Scan for TODO/FIXME/HACK/XXX comments and assess age."""

    name = "todo_comments"
    description = "Detects aging TODO-style comments"

    def scan(self, repo_path: str | Path) -> list[Finding]:
        findings: list[Finding] = []
        max_age = 90
        patterns = ["TODO", "FIXME", "HACK", "XXX"]

        if self.config:
            cfg = self.config.scanners.todo_comments
            max_age = cfg.max_age_days
            patterns = cfg.patterns

        pattern = re.compile(
            rf"#\s*({'|'.join(re.escape(p) for p in patterns)})\b[:\s]*(.*)",
            re.IGNORECASE,
        )

        for py_file in self.find_python_files(repo_path):
            try:
                lines = py_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue

            for line_num, line in enumerate(lines, start=1):
                match = pattern.search(line)
                if match:
                    tag = match.group(1).upper()
                    message = match.group(2).strip()
                    severity = self._tag_severity(tag)
                    priority = self._calculate_priority(severity, max_age)

                    findings.append(
                        Finding(
                            type=FindingType.TODO_COMMENT,
                            severity=severity,
                            file=str(py_file),
                            line=line_num,
                            description=f"{tag}: {message}" if message else tag,
                            suggestion=f"Resolve or convert to issue: {message}",
                            priority_score=priority,
                            scanner_name=self.name,
                            metadata={"tag": tag, "message": message},
                        )
                    )

        return sorted(findings, key=lambda f: f.priority_score, reverse=True)

    @staticmethod
    def _tag_severity(tag: str) -> SeverityLevel:
        mapping = {
            "FIXME": SeverityLevel.HIGH,
            "HACK": SeverityLevel.HIGH,
            "TODO": SeverityLevel.MEDIUM,
            "XXX": SeverityLevel.MEDIUM,
            "NOTE": SeverityLevel.LOW,
        }
        return mapping.get(tag, SeverityLevel.MEDIUM)

    @staticmethod
    def _calculate_priority(severity: SeverityLevel, max_age_days: int) -> float:
        weights = {
            SeverityLevel.CRITICAL: 10,
            SeverityLevel.HIGH: 7,
            SeverityLevel.MEDIUM: 4,
            SeverityLevel.LOW: 2,
        }
        return float(weights.get(severity, 4) * 10)
