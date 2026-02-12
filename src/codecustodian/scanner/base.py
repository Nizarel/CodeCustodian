"""Base scanner interface and shared types.

All scanner implementations must subclass ``BaseScanner`` and implement
the ``scan()`` method.

Includes a unified priority algorithm (FR-SCAN-002) and ``.gitignore``-
aware file discovery (BR-CFG-002).
"""

from __future__ import annotations

import fnmatch
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from codecustodian.logging import get_logger
from codecustodian.models import Finding, SeverityLevel

if TYPE_CHECKING:
    from codecustodian.config.schema import CodeCustodianConfig

logger = get_logger("scanner.base")

# ── Severity weights for priority formula (FR-SCAN-002) ───────────────────

_SEVERITY_WEIGHTS: dict[SeverityLevel, float] = {
    SeverityLevel.CRITICAL: 10.0,
    SeverityLevel.HIGH: 7.0,
    SeverityLevel.MEDIUM: 4.0,
    SeverityLevel.LOW: 2.0,
    SeverityLevel.INFO: 1.0,
}

_EFFORT_DIVISORS: dict[str, float] = {
    "low": 1.0,
    "medium": 2.0,
    "high": 4.0,
}


def _load_gitignore_patterns(repo_root: Path) -> list[str]:
    """Parse a ``.gitignore`` file into fnmatch-compatible patterns.

    Supports comment lines, negation (skipped), directory-only markers,
    and bare glob patterns.  Returns an empty list when the file is
    absent or unreadable.
    """
    gitignore = repo_root / ".gitignore"
    if not gitignore.is_file():
        return []
    try:
        raw = gitignore.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    patterns: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        # Strip trailing directory marker — fnmatch works on paths
        entry = line.rstrip("/")
        # If the pattern has no path separator, match anywhere in tree
        if "/" not in entry:
            patterns.append(f"**/{entry}")
            patterns.append(f"**/{entry}/**")
        else:
            patterns.append(entry)
            patterns.append(f"{entry}/**")
    return patterns


def is_excluded(file_path: str | Path, patterns: list[str]) -> bool:
    """Check whether *file_path* matches any exclusion pattern.

    Parameters
    ----------
    file_path:
        Relative path (e.g. ``src/foo.py``) or absolute path.
    patterns:
        ``fnmatch``-style glob patterns.

    Returns
    -------
    bool
        ``True`` when the path should be skipped.
    """
    # Normalise to forward slashes so patterns work on Windows too
    rel = str(file_path).replace("\\", "/")
    # Prefix with "/" so ``**/dir`` patterns match root-level entries
    prefixed = "/" + rel
    return any(
        fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(prefixed, pat)
        for pat in patterns
    )


class BaseScanner(ABC):
    """Abstract base class for all CodeCustodian scanners.

    Subclasses must implement:
    - ``name``: unique scanner identifier
    - ``description``: human-readable description
    - ``scan()``: return a list of ``Finding`` objects

    Class attributes:
    - ``enabled``: whether this scanner is active by default
    """

    name: str = "base"
    description: str = ""
    enabled: bool = True

    def __init__(self, config: CodeCustodianConfig | None = None) -> None:
        self.config = config

    # ── Abstract interface ────────────────────────────────────────────

    @abstractmethod
    def scan(self, repo_path: str | Path) -> list[Finding]:
        """Scan a repository and return findings.

        Parameters
        ----------
        repo_path:
            Root path of the repository to scan.

        Returns
        -------
        list[Finding]
            Detected issues sorted by priority_score descending.
        """
        ...

    # ── Priority algorithm (FR-SCAN-002) ──────────────────────────────

    @staticmethod
    def calculate_priority(finding: Finding) -> float:
        """Compute a unified priority score for *finding*.

        Formula::

            priority = (severity_weight × urgency × impact) / effort

        The result is clamped to **0 – 200**.

        ``urgency``, ``impact`` and ``effort`` are read from
        ``finding.metadata`` when present; they default to **1.0**.
        """
        weight = _SEVERITY_WEIGHTS.get(finding.severity, 4.0)
        urgency = float(finding.metadata.get("urgency", 1.0))
        impact = float(finding.metadata.get("impact", 1.0))
        effort_key = str(finding.metadata.get("effort", finding.reviewer_effort_estimate))
        effort_div = _EFFORT_DIVISORS.get(effort_key, 2.0)

        raw = (weight * urgency * impact) / effort_div
        # Scale to 0-200 range (base weight 10 * urgency 2.0 * impact 2.0
        # gives 40 max before effort divisor — multiply by 5 for range)
        scaled = raw * 5.0
        return max(0.0, min(200.0, round(scaled, 1)))

    # ── File discovery ────────────────────────────────────────────────

    def find_python_files(
        self,
        repo_path: str | Path,
        exclude_patterns: list[str] | None = None,
    ) -> list[Path]:
        """Discover Python files, respecting ``.gitignore`` and exclusion patterns.

        Parameters
        ----------
        repo_path:
            Root directory to search.
        exclude_patterns:
            Glob patterns to exclude (e.g. ``["vendor/**", ".venv/**"]``).
            Merged with ``.gitignore`` entries and config ``exclude_paths``.

        Returns
        -------
        list[Path]
            Sorted list of ``.py`` file paths.
        """
        root = Path(repo_path)
        config_excludes = (
            self.config.advanced.exclude_paths if self.config else []
        )
        user_excludes = exclude_patterns or []
        gitignore_excludes = _load_gitignore_patterns(root)

        all_excludes = list(set(config_excludes + user_excludes + gitignore_excludes))

        py_files: list[Path] = []
        for py_file in root.rglob("*.py"):
            rel = str(py_file.relative_to(root)).replace("\\", "/")
            if is_excluded(rel, all_excludes):
                continue
            py_files.append(py_file)

        return sorted(py_files)

    # ── Helpers ───────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} enabled={self.enabled}>"
