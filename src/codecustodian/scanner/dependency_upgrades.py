"""Dependency upgrade intelligence scanner.

Scans dependency manifest files and flags outdated package pins/constraints
against a curated recommendation catalog.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

from codecustodian.logging import get_logger
from codecustodian.models import Finding, FindingType, SeverityLevel
from codecustodian.scanner.base import BaseScanner

logger = get_logger("scanner.dependency_upgrades")

_DATA_DIR = Path(__file__).parent / "data"

_DEP_PATTERN = re.compile(r"^\s*([A-Za-z0-9_.-]+)(?:\[[^\]]+\])?\s*([<>=!~].+)?\s*$")
_PIN_PATTERN = re.compile(r"==\s*([0-9][0-9A-Za-z_.-]*)")


def _normalize_name(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def _parse_version(version: str) -> tuple[int, ...]:
    # Keep numeric ordering deterministic without external dependencies.
    numeric_parts: list[int] = []
    for token in re.findall(r"\d+", version):
        numeric_parts.append(int(token))
    if not numeric_parts:
        return (0,)
    return tuple(numeric_parts)


def _is_older(current: str, recommended: str) -> bool:
    return _parse_version(current) < _parse_version(recommended)


class DependencyUpgradeScanner(BaseScanner):
    """Detects dependencies that should be upgraded based on known recommendations."""

    name = "dependency_upgrades"
    description = "Detects stale dependency constraints and suggests safe upgrades"
    enabled = True

    def __init__(self, config: Any = None) -> None:
        super().__init__(config)
        self._recommendations = self._load_recommendations()

    def scan(self, repo_path: str | Path) -> list[Finding]:
        findings: list[Finding] = []
        root = Path(repo_path)

        tracked_files = [
            "requirements.txt",
            "requirements-dev.txt",
            "requirements-test.txt",
            "pyproject.toml",
            "uv.lock",
            "poetry.lock",
        ]
        if self.config:
            tracked_files = self.config.scanners.dependency_upgrades.tracked_files

        targets = [root / rel_path for rel_path in tracked_files]

        for target in targets:
            if not target.exists():
                continue
            if target.name == "pyproject.toml":
                findings.extend(self._scan_pyproject(target))
            elif target.name in {"uv.lock", "poetry.lock"}:
                findings.extend(self._scan_lockfile(target))
            else:
                findings.extend(self._scan_requirements(target))

        for finding in findings:
            finding.priority_score = self.calculate_priority(finding)

        return sorted(findings, key=lambda item: item.priority_score, reverse=True)

    def _scan_requirements(self, file_path: Path) -> list[Finding]:
        findings: list[Finding] = []
        lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()

        for line_no, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            match = _DEP_PATTERN.match(stripped)
            if not match:
                continue

            package = _normalize_name(match.group(1))
            spec = (match.group(2) or "").strip()
            findings.extend(self._evaluate_spec(package, spec, str(file_path), line_no))

        return findings

    def _scan_pyproject(self, file_path: Path) -> list[Finding]:
        findings: list[Finding] = []
        try:
            data = tomllib.loads(file_path.read_text(encoding="utf-8", errors="ignore"))
        except tomllib.TOMLDecodeError:
            logger.warning("Skipping malformed pyproject.toml: %s", file_path)
            return findings

        deps = data.get("project", {}).get("dependencies", [])
        if not isinstance(deps, list):
            return findings

        for dep in deps:
            if not isinstance(dep, str):
                continue
            match = _DEP_PATTERN.match(dep.strip())
            if not match:
                continue
            package = _normalize_name(match.group(1))
            spec = (match.group(2) or "").strip()
            findings.extend(self._evaluate_spec(package, spec, str(file_path), 1))

        return findings

    def _scan_lockfile(self, file_path: Path) -> list[Finding]:
        """Scan lockfiles with TOML-like package entries (uv.lock, poetry.lock)."""
        findings: list[Finding] = []
        try:
            data = tomllib.loads(file_path.read_text(encoding="utf-8", errors="ignore"))
        except tomllib.TOMLDecodeError:
            logger.warning("Skipping malformed lockfile: %s", file_path)
            return findings

        package_rows = data.get("package", [])
        if not isinstance(package_rows, list):
            return findings

        for row in package_rows:
            if not isinstance(row, dict):
                continue

            raw_name = row.get("name")
            raw_version = row.get("version")
            if not isinstance(raw_name, str) or not isinstance(raw_version, str):
                continue

            package = _normalize_name(raw_name)
            spec = f"=={raw_version.strip()}"
            findings.extend(self._evaluate_spec(package, spec, str(file_path), 1))

        return findings

    def _evaluate_spec(
        self,
        package: str,
        spec: str,
        file_path: str,
        line_no: int,
    ) -> list[Finding]:
        recommendation = self._recommendations.get(package)
        if not recommendation:
            return []

        rec_version = recommendation["recommended_min"]
        base_severity = recommendation["severity"]
        reason = recommendation["reason"]

        findings: list[Finding] = []
        pin_match = _PIN_PATTERN.search(spec)
        if pin_match:
            pinned = pin_match.group(1)
            if _is_older(pinned, rec_version):
                findings.append(
                    self._finding(
                        package=package,
                        file_path=file_path,
                        line_no=line_no,
                        severity=base_severity,
                        description=(
                            f"{package} is pinned to {pinned}, below recommended {rec_version}"
                        ),
                        suggestion=f"Upgrade to {package}>={rec_version}",
                        spec=spec,
                        rec_version=rec_version,
                        reason=reason,
                        urgency=1.5,
                    )
                )
            return findings

        if not spec:
            findings.append(
                self._finding(
                    package=package,
                    file_path=file_path,
                    line_no=line_no,
                    severity="low",
                    description=f"{package} has no explicit version constraint",
                    suggestion=f"Add lower bound: {package}>={rec_version}",
                    spec=spec,
                    rec_version=rec_version,
                    reason=reason,
                    urgency=1.0,
                )
            )
            return findings

        # Detect upper bound below recommendation, e.g. <2.0 when recommended is 2.3.
        upper_match = re.search(r"<\s*([0-9][0-9A-Za-z_.-]*)", spec)
        if upper_match and _is_older(upper_match.group(1), rec_version):
            findings.append(
                self._finding(
                    package=package,
                    file_path=file_path,
                    line_no=line_no,
                    severity="medium",
                    description=(
                        f"{package} constraint '{spec}' blocks recommended version {rec_version}"
                    ),
                    suggestion=f"Adjust constraint to allow {package}>={rec_version}",
                    spec=spec,
                    rec_version=rec_version,
                    reason=reason,
                    urgency=1.2,
                )
            )

        return findings

    def _finding(
        self,
        *,
        package: str,
        file_path: str,
        line_no: int,
        severity: str,
        description: str,
        suggestion: str,
        spec: str,
        rec_version: str,
        reason: str,
        urgency: float,
    ) -> Finding:
        normalized_severity = severity.lower().strip()
        if normalized_severity not in {"critical", "high", "medium", "low", "info"}:
            normalized_severity = "medium"

        return Finding(
            type=FindingType.DEPENDENCY_UPGRADE,
            severity=SeverityLevel(normalized_severity),
            file=file_path,
            line=line_no,
            description=description,
            suggestion=suggestion,
            scanner_name=self.name,
            metadata={
                "package": package,
                "current_spec": spec,
                "recommended_min": rec_version,
                "reason": reason,
                "urgency": urgency,
                "impact": 1.3,
                "effort": "low",
            },
        )

    def _load_recommendations(self) -> dict[str, dict[str, str]]:
        path = _DATA_DIR / "dependency_recommendations.json"
        if not path.exists():
            logger.warning("Dependency recommendation file not found: %s", path)
            return {}

        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)

        recommendations: dict[str, dict[str, str]] = {}
        for item in raw.get("packages", []):
            name = _normalize_name(str(item.get("name", "")))
            if not name:
                continue
            recommendations[name] = {
                "recommended_min": str(item.get("recommended_min", "")).strip(),
                "severity": str(item.get("severity", "medium")).strip().lower(),
                "reason": str(item.get("reason", "Upgrade recommended")).strip(),
            }

        return recommendations
