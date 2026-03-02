"""TODO comment scanner.

Detects TODO, FIXME, HACK, and XXX comments with:
- Git blame integration for age calculation (FR-SCAN-022)
- Age-based severity mapping (FR-SCAN-023)
- Author attribution from git blame (FR-SCAN-103)
- Auto-issue creation flag for stale TODOs (FR-SCAN-103)
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from codecustodian.logging import get_logger
from codecustodian.models import Finding, FindingType, SeverityLevel
from codecustodian.scanner.base import BaseScanner

logger = get_logger("scanner.todo_comments")

# Default extensions to scan (user-configurable via `languages` config field).
_DEFAULT_EXTENSIONS = [".py", ".go", ".cs", ".js", ".ts", ".java"]

# Unified comment pattern —  matches:
#   Python/Shell:   #  TODO: ...
#   Go/C#/JS/TS:    // TODO: ...
#   Block comment:  /* TODO: ... */  (single-line only)
_TODO_PATTERN = re.compile(
    r"(?:#|//|/\*[*\s]*)\s*(TODO|FIXME|HACK|XXX|NOTE)\b[:\s]*(.*?)(?:\*/)?$",
    re.IGNORECASE,
)


class TodoCommentScanner(BaseScanner):
    """Scan for TODO/FIXME/HACK/XXX comments and assess age.

    When the repository is a valid Git repo, each matched line is
    enriched with **blame data** (author, age in days).  Age-based
    severity overrides tag-based severity when the comment is stale.
    """

    name = "todo_comments"
    description = "Detects aging TODO-style comments"

    def scan(self, repo_path: str | Path) -> list[Finding]:
        findings: list[Finding] = []
        max_age = 90
        patterns = ["TODO", "FIXME", "HACK", "XXX"]
        auto_issue = False
        extensions = _DEFAULT_EXTENSIONS

        if self.config:
            cfg = self.config.scanners.todo_comments
            max_age = cfg.max_age_days
            patterns = cfg.patterns
            auto_issue = cfg.auto_issue
            if cfg.languages:
                extensions = [ext if ext.startswith(".") else f".{ext}" for ext in cfg.languages]

        # Unified comment prefix pattern covering #, //, /* ... */
        pattern = re.compile(
            rf"(?:#|//|/\*[*\s]*)\s*({'|'.join(re.escape(p) for p in patterns)})\b[:\s]*(.*?)(?:\*/)?$",
            re.IGNORECASE,
        )

        # Try to initialise a GitPython Repo for blame lookups
        blame_repo = self._get_git_repo(repo_path)

        for src_file in self.find_files(repo_path, extensions):
            try:
                lines = src_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue

            # Pre-fetch blame data for this file (once per file)
            blame_map = self._build_blame_map(blame_repo, src_file, repo_path)

            for line_num, line in enumerate(lines, start=1):
                match = pattern.search(line)
                if match:
                    tag = match.group(1).upper()
                    message = match.group(2).strip()

                    # ── Blame enrichment ──────────────────────────
                    blame_info = blame_map.get(line_num, {})
                    age_days: int | None = blame_info.get("age_days")
                    author: str = blame_info.get("author", "")
                    author_email: str = blame_info.get("author_email", "")

                    # ── Severity (tag-based, then age override) ───
                    severity = self._tag_severity(tag)
                    if age_days is not None:
                        severity = self._age_severity(severity, age_days, max_age)

                    priority = self._compute_priority(severity, age_days, max_age)

                    meta: dict[str, Any] = {
                        "tag": tag,
                        "message": message,
                        "language": src_file.suffix.lstrip("."),
                    }
                    if author:
                        meta["author"] = author
                    if author_email:
                        meta["author_email"] = author_email
                    if age_days is not None:
                        meta["age_days"] = age_days

                    # Auto-issue flag (FR-SCAN-103)
                    if auto_issue and age_days is not None and age_days > max_age:
                        meta["auto_issue"] = True

                    findings.append(
                        Finding(
                            type=FindingType.TODO_COMMENT,
                            severity=severity,
                            file=str(src_file),
                            line=line_num,
                            description=f"{tag}: {message}" if message else tag,
                            suggestion=f"Resolve or convert to issue: {message}",
                            priority_score=priority,
                            scanner_name=self.name,
                            metadata=meta,
                        )
                    )

        return sorted(findings, key=lambda f: f.priority_score, reverse=True)

    # ── Git blame helpers ─────────────────────────────────────────────

    @staticmethod
    def _get_git_repo(repo_path: str | Path) -> Any | None:
        """Return a ``git.Repo`` for *repo_path*, or ``None`` on failure."""
        try:
            from git import InvalidGitRepositoryError, Repo

            return Repo(str(repo_path), search_parent_directories=True)
        except (ImportError, InvalidGitRepositoryError, Exception):
            logger.debug("Git blame unavailable for %s — falling back", repo_path)
            return None

    @staticmethod
    def _build_blame_map(
        repo: Any | None,
        file_path: Path,
        repo_path: str | Path,
    ) -> dict[int, dict[str, Any]]:
        """Build ``{line_num: {author, author_email, age_days}}`` via ``git blame``.

        Returns an empty dict when blame is unavailable.
        """
        if repo is None:
            return {}
        try:
            rel_path = str(file_path.relative_to(Path(repo_path).resolve()))
            # Use blame_incremental for memory efficiency
            entries = repo.blame_incremental("HEAD", rel_path)
            now = datetime.now(UTC)
            blame_map: dict[int, dict[str, Any]] = {}
            for entry in entries:
                authored = datetime.fromtimestamp(
                    entry.commit.authored_date, tz=UTC
                )
                age_days = (now - authored).days
                info = {
                    "author": str(entry.commit.author.name) if entry.commit.author else "",
                    "author_email": str(entry.commit.author.email) if entry.commit.author else "",
                    "age_days": age_days,
                }
                for lineno in entry.linenos:
                    blame_map[lineno] = info
            return blame_map
        except Exception:
            logger.debug("Git blame failed for %s", file_path)
            return {}

    # ── Severity mapping ──────────────────────────────────────────────

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
    def _age_severity(
        base: SeverityLevel, age_days: int, max_age: int
    ) -> SeverityLevel:
        """Override severity when a comment has aged beyond thresholds.

        - ``age > 2 x max_age`` -> CRITICAL
        - ``age > max_age`` → HIGH
        - ``age > max_age / 2`` → at least MEDIUM
        """
        if age_days > 2 * max_age:
            return SeverityLevel.CRITICAL
        if age_days > max_age:
            return SeverityLevel.HIGH
        if age_days > max_age // 2:
            # Ensure at least MEDIUM (don't downgrade HIGH tags)
            if base in (SeverityLevel.LOW, SeverityLevel.INFO):
                return SeverityLevel.MEDIUM
        return base

    @staticmethod
    def _compute_priority(
        severity: SeverityLevel,
        age_days: int | None,
        max_age: int,
    ) -> float:
        """Compute priority incorporating severity weight and age bonus."""
        weights = {
            SeverityLevel.CRITICAL: 10,
            SeverityLevel.HIGH: 7,
            SeverityLevel.MEDIUM: 4,
            SeverityLevel.LOW: 2,
            SeverityLevel.INFO: 1,
        }
        base = float(weights.get(severity, 4) * 10)
        if age_days is not None and max_age > 0:
            # Add up to +50 for comments far past max_age
            overage_ratio = age_days / max_age
            base += min(50.0, overage_ratio * 20.0)
        return min(200.0, base)
