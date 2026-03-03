"""Business impact scoring for technical debt findings (FR-PRIORITY-100).

Implements a 5-factor scoring model that quantifies the real business
cost of each finding, enabling prioritization by business value rather
than mere severity.

Factors
-------
1. **Usage frequency** — telemetry-based call count (CodeContext)
2. **Criticality** — critical-path detection (payments, auth, security)
3. **Change frequency** — git history churn rate
4. **Velocity impact** — Azure DevOps blocked work items
5. **Regulatory risk** — PII / GDPR / HIPAA annotations

Score formula::

    Score = (Usage x 100) + (Criticality x 50) + (ChangeFreq x 30)
          + (VelocityImpact x 40) + (RegulatoryRisk x 80)
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from codecustodian.logging import get_logger
from codecustodian.models import Finding

logger = get_logger("intelligence.business_impact")


# ── Score breakdown model ──────────────────────────────────────────────────


class ImpactBreakdown(BaseModel):
    """Detailed breakdown of the five scoring factors."""

    usage: float = 0.0
    criticality: float = 0.0
    change_frequency: float = 0.0
    velocity_impact: float = 0.0
    regulatory_risk: float = 0.0
    total: float = 0.0
    factors: list[str] = Field(default_factory=list)


# ── Weight configuration ───────────────────────────────────────────────────


class ScoringWeights(BaseModel):
    """Configurable weights for each scoring factor."""

    usage: float = 100.0
    criticality: float = 50.0
    change_frequency: float = 30.0
    velocity_impact: float = 40.0
    regulatory_risk: float = 80.0


# ── Scorer ─────────────────────────────────────────────────────────────────


class BusinessImpactScorer:
    """5-factor business impact scoring (FR-PRIORITY-100).

    Score = (Usage x W1) + (Criticality x W2) + (ChangeFreq x W3)
          + (VelocityImpact x W4) + (RegulatoryRisk x W5)

    Each factor is normalised to 0-10 before multiplication.
    """

    CRITICAL_PATTERNS: ClassVar[list[str]] = [
        "payment", "auth", "billing", "security", "crypto",
        "checkout", "token", "credential", "session",
    ]
    REGULATED_PATTERNS: ClassVar[list[str]] = [
        "pii", "credit_card", "ssn", "hipaa", "gdpr",
        "ferpa", "sox", "pci", "phi", "personal_data",
    ]

    def __init__(
        self,
        weights: ScoringWeights | None = None,
        *,
        devops_client: Any | None = None,
    ) -> None:
        self.weights = weights or ScoringWeights()
        self._devops_client = devops_client

    # ── Public API ─────────────────────────────────────────────────────

    async def score(
        self,
        finding: Finding,
        repo_path: str = ".",
    ) -> float:
        """Calculate composite business impact score for a finding.

        Returns:
            Float score (higher = more impactful).
        """
        breakdown = await self.score_detailed(finding, repo_path)
        return breakdown.total

    async def score_detailed(
        self,
        finding: Finding,
        repo_path: str = ".",
    ) -> ImpactBreakdown:
        """Return the full breakdown with per-factor scores."""
        usage = await self._get_usage_frequency(finding)
        criticality = self._get_criticality(finding)
        change_freq = await self._get_change_frequency(finding, repo_path)
        velocity = await self._get_velocity_impact(finding)
        regulatory = self._get_regulatory_risk(finding)

        total = (
            usage * self.weights.usage
            + criticality * self.weights.criticality
            + change_freq * self.weights.change_frequency
            + velocity * self.weights.velocity_impact
            + regulatory * self.weights.regulatory_risk
        )

        factors: list[str] = []
        if usage > 0:
            factors.append(f"usage={usage:.1f}")
        if criticality > 3:
            factors.append(f"critical_path={criticality:.1f}")
        if change_freq > 3:
            factors.append(f"high_churn={change_freq:.1f}")
        if velocity > 0:
            factors.append(f"velocity_impact={velocity:.1f}")
        if regulatory > 0:
            factors.append(f"regulatory={regulatory:.1f}")

        logger.debug(
            "Impact score for %s: %.1f [%s]",
            finding.id,
            total,
            ", ".join(factors) or "baseline",
        )

        return ImpactBreakdown(
            usage=usage,
            criticality=criticality,
            change_frequency=change_freq,
            velocity_impact=velocity,
            regulatory_risk=regulatory,
            total=round(total, 2),
            factors=factors,
        )

    async def score_batch(
        self,
        findings: list[Finding],
        repo_path: str = ".",
    ) -> list[tuple[Finding, ImpactBreakdown]]:
        """Score multiple findings and return sorted (highest first)."""
        results: list[tuple[Finding, ImpactBreakdown]] = []
        for finding in findings:
            breakdown = await self.score_detailed(finding, repo_path)
            finding.business_impact_score = breakdown.total
            results.append((finding, breakdown))
        results.sort(key=lambda x: x[1].total, reverse=True)
        return results

    # ── Factor 1: Usage frequency ──────────────────────────────────────

    async def _get_usage_frequency(self, finding: Finding) -> float:
        """Normalised usage frequency (0-10) from telemetry metadata.

        Falls back to ``CodeContext.usage_frequency`` if metadata is
        not available.
        """
        raw = finding.metadata.get("usage_frequency", 0)
        if raw <= 0:
            return 0.0
        # Logarithmic normalisation: 1→1, 10→3.3, 100→6.6, 1000→10
        import math
        return min(10.0, round(math.log10(max(raw, 1)) * 3.33, 1))

    # ── Factor 2: Criticality ──────────────────────────────────────────

    def _get_criticality(self, finding: Finding) -> float:
        """Identify critical-path code: payments, auth, data processing.

        Returns 0-10 based on file path and metadata flags.
        """
        file_lower = finding.file.lower()
        matches = sum(1 for p in self.CRITICAL_PATTERNS if p in file_lower)

        # Metadata may carry an explicit criticality_level
        meta_level = finding.metadata.get("criticality_level", "normal")
        if meta_level == "critical":
            return 10.0
        if meta_level == "high":
            return 7.0

        if matches >= 2:
            return 10.0
        if matches == 1:
            return 7.0
        return 3.0

    # ── Factor 3: Change frequency (git history) ───────────────────────

    async def _get_change_frequency(
        self,
        finding: Finding,
        repo_path: str,
    ) -> float:
        """Normalised change frequency (0-10) from git log.

        Uses ``asyncio.to_thread`` so the synchronous Git I/O
        doesn't block the event loop.
        """
        try:
            commits = await asyncio.to_thread(
                self._count_recent_commits, finding.file, repo_path
            )
        except Exception:
            return 0.0

        if commits <= 0:
            return 0.0
        # 1 commit → 1, 5 → 5, 10+ → 10
        return min(10.0, float(commits))

    @staticmethod
    def _count_recent_commits(
        file_path: str,
        repo_path: str,
        *,
        days: int = 90,
    ) -> int:
        """Count commits touching *file_path* in the last *days* days.

        Uses GitPython if available, otherwise falls back to
        ``git log --oneline`` via subprocess.
        """
        import subprocess

        abs_file = Path(repo_path) / file_path
        if not abs_file.exists():
            return 0

        try:
            result = subprocess.run(
                [
                    "git", "log", "--oneline",
                    f"--since={days} days ago",
                    "--", file_path,
                ],
                capture_output=True,
                text=True,
                cwd=repo_path,
                timeout=10,
            )
            if result.returncode == 0:
                return len(result.stdout.strip().splitlines())
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return 0

    # ── Factor 4: Velocity impact ──────────────────────────────────────

    async def _get_velocity_impact(self, finding: Finding) -> float:
        """Check Azure DevOps for work items blocked by this tech debt.

        Returns 0-10 based on number of blocked items.
        If no DevOps client is configured, returns 0.
        """
        if self._devops_client is None:
            # Check metadata for pre-computed blocked count
            blocked = finding.metadata.get("blocked_work_items", 0)
            if blocked <= 0:
                return 0.0
            return min(10.0, float(blocked) * 2)

        try:
            blocked = await self._devops_client.get_blocked_items(finding.file)
            return min(10.0, float(blocked) * 2)
        except Exception:
            return 0.0

    # ── Factor 5: Regulatory risk ──────────────────────────────────────

    def _get_regulatory_risk(self, finding: Finding) -> float:
        """Check for PII, financial data, healthcare records handling.

        Returns 0-10 based on file path patterns and metadata.
        """
        file_lower = finding.file.lower()
        desc_lower = finding.description.lower()
        combined = f"{file_lower} {desc_lower}"

        matches = sum(1 for p in self.REGULATED_PATTERNS if p in combined)

        # Metadata may carry explicit compliance tags
        compliance_tags = finding.metadata.get("compliance", [])
        if isinstance(compliance_tags, list):
            matches += len(compliance_tags)

        if matches >= 3:
            return 10.0
        if matches >= 2:
            return 8.0
        if matches == 1:
            return 5.0
        return 0.0
