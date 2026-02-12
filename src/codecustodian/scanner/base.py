"""Base scanner interface and shared types.

All scanner implementations must subclass ``BaseScanner`` and implement
the ``scan()`` method.
"""

from __future__ import annotations

import fnmatch
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from codecustodian.logging import get_logger
from codecustodian.models import Finding

if TYPE_CHECKING:
    from codecustodian.config.schema import CodeCustodianConfig

logger = get_logger("scanner.base")


class BaseScanner(ABC):
    """Abstract base class for all CodeCustodian scanners.

    Subclasses must implement:
    - ``name``: unique scanner identifier
    - ``description``: human-readable description
    - ``scan()``: return a list of ``Finding`` objects
    """

    name: str = "base"
    description: str = ""

    def __init__(self, config: CodeCustodianConfig | None = None) -> None:
        self.config = config

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

    def find_python_files(
        self,
        repo_path: str | Path,
        exclude_patterns: list[str] | None = None,
    ) -> list[Path]:
        """Discover Python files, respecting exclusion patterns.

        Parameters
        ----------
        repo_path:
            Root directory to search.
        exclude_patterns:
            Glob patterns to exclude (e.g. ``["vendor/**", ".venv/**"]``).

        Returns
        -------
        list[Path]
            Sorted list of ``.py`` file paths.
        """
        root = Path(repo_path)
        excludes = exclude_patterns or (
            self.config.advanced.exclude_paths if self.config else []
        )

        py_files: list[Path] = []
        for py_file in root.rglob("*.py"):
            rel = str(py_file.relative_to(root))
            if any(fnmatch.fnmatch(rel, pat) for pat in excludes):
                continue
            py_files.append(py_file)

        return sorted(py_files)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
