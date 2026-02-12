"""Budget governance for AI-driven refactoring (FR-COST-100, FR-COST-101).

Tracks per-run and monthly AI-operation costs, enforces hard spending
limits, fires threshold alerts, and persists cost history via JSONL for
trend analysis.

Usage::

    budget = BudgetManager(config.budget)
    budget.record_cost("plan", 0.03, run_id="abc123")
    budget.check_budget(estimated_cost=0.05)   # raises BudgetExceededError
    summary = budget.get_summary()
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from codecustodian.exceptions import BudgetExceededError
from codecustodian.logging import get_logger

logger = get_logger("enterprise.budget")


# ── Models ─────────────────────────────────────────────────────────────────


class CostEntry(BaseModel):
    """A single cost record."""

    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    run_id: str = ""
    operation: str = ""          # plan | execute | verify | scan
    cost_usd: float = 0.0
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    details: dict[str, Any] = Field(default_factory=dict)


class BudgetAlert(BaseModel):
    """Alert emitted when a threshold is crossed."""

    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    threshold_pct: int
    current_cost: float
    budget_limit: float
    message: str


class BudgetSummary(BaseModel):
    """Snapshot of the current budget state."""

    monthly_budget: float
    total_spent: float
    remaining: float
    usage_pct: float
    entries_count: int
    alerts_fired: list[int] = Field(default_factory=list)
    period: str = ""


# ── Manager ────────────────────────────────────────────────────────────────


class BudgetManager:
    """Track and enforce AI operation costs (FR-COST-100, FR-COST-101).

    Persists cost entries in a JSONL file partitioned by month.  Checks
    hard limits before each AI call and emits alerts at configurable
    thresholds.

    Args:
        monthly_budget: Maximum monthly spend in USD.
        alert_thresholds: List of usage-% thresholds to alert on.
        hard_limit: If ``True``, raises ``BudgetExceededError`` at 100%.
        data_dir: Directory for JSONL cost logs.
    """

    def __init__(
        self,
        monthly_budget: float = 500.0,
        alert_thresholds: list[int] | None = None,
        hard_limit: bool = True,
        data_dir: str | Path = ".codecustodian-costs",
    ) -> None:
        self.monthly_budget = monthly_budget
        self.alert_thresholds = sorted(alert_thresholds or [50, 80, 90, 100])
        self.hard_limit = hard_limit

        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._period = datetime.now(timezone.utc).strftime("%Y-%m")
        self._log_file = self.data_dir / f"costs-{self._period}.jsonl"
        self._alerts_fired: set[int] = set()

        # Load existing entries to set baseline
        self._total_spent = self._load_total()

    @classmethod
    def from_config(cls, config: Any) -> BudgetManager:
        """Create a ``BudgetManager`` from a ``BudgetConfig`` model."""
        return cls(
            monthly_budget=config.monthly_budget,
            alert_thresholds=list(config.alert_thresholds),
            hard_limit=config.hard_limit,
        )

    # ── Cost recording ─────────────────────────────────────────────────

    def record_cost(
        self,
        operation: str,
        cost_usd: float,
        *,
        run_id: str = "",
        model: str = "",
        tokens_in: int = 0,
        tokens_out: int = 0,
        **details: Any,
    ) -> CostEntry:
        """Record a cost entry and check thresholds (FR-COST-100).

        Returns the recorded ``CostEntry``.
        """
        entry = CostEntry(
            run_id=run_id,
            operation=operation,
            cost_usd=cost_usd,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            details=details,
        )
        with open(self._log_file, "a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")

        self._total_spent += cost_usd
        logger.info(
            "Cost recorded: $%.4f (%s) — total $%.2f / $%.2f",
            cost_usd,
            operation,
            self._total_spent,
            self.monthly_budget,
        )

        self._check_thresholds()
        return entry

    # ── Budget enforcement ─────────────────────────────────────────────

    def check_budget(self, estimated_cost: float = 0.0) -> bool:
        """Check if spending ``estimated_cost`` would exceed the budget.

        Args:
            estimated_cost: The projected cost of the next operation.

        Returns:
            ``True`` if within budget.

        Raises:
            BudgetExceededError: When hard limit is on and budget exceeded.
        """
        projected = self._total_spent + estimated_cost
        if self.hard_limit and projected > self.monthly_budget:
            raise BudgetExceededError(
                message=(
                    f"Budget exceeded: ${projected:.2f} > "
                    f"${self.monthly_budget:.2f} limit"
                ),
                current_cost=self._total_spent,
                budget_limit=self.monthly_budget,
            )
        return True

    # ── Summary ────────────────────────────────────────────────────────

    def get_summary(self) -> BudgetSummary:
        """Return a snapshot of the current budget state (FR-COST-101)."""
        remaining = max(0.0, self.monthly_budget - self._total_spent)
        usage_pct = (
            (self._total_spent / self.monthly_budget * 100)
            if self.monthly_budget > 0
            else 0.0
        )
        return BudgetSummary(
            monthly_budget=self.monthly_budget,
            total_spent=self._total_spent,
            remaining=remaining,
            usage_pct=round(usage_pct, 2),
            entries_count=self._count_entries(),
            alerts_fired=sorted(self._alerts_fired),
            period=self._period,
        )

    # ── Alerts ─────────────────────────────────────────────────────────

    def get_alerts(self) -> list[BudgetAlert]:
        """Return all alerts that would fire at the current spending level."""
        alerts: list[BudgetAlert] = []
        usage_pct = (
            (self._total_spent / self.monthly_budget * 100)
            if self.monthly_budget > 0
            else 0.0
        )
        for threshold in self.alert_thresholds:
            if usage_pct >= threshold:
                alerts.append(
                    BudgetAlert(
                        threshold_pct=threshold,
                        current_cost=self._total_spent,
                        budget_limit=self.monthly_budget,
                        message=(
                            f"Budget usage at {usage_pct:.1f}% "
                            f"(${self._total_spent:.2f}/${self.monthly_budget:.2f})"
                        ),
                    )
                )
        return alerts

    # ── Internal ───────────────────────────────────────────────────────

    def _check_thresholds(self) -> None:
        """Fire alerts for newly-crossed thresholds."""
        if self.monthly_budget <= 0:
            return
        usage_pct = self._total_spent / self.monthly_budget * 100
        for threshold in self.alert_thresholds:
            if usage_pct >= threshold and threshold not in self._alerts_fired:
                self._alerts_fired.add(threshold)
                logger.warning(
                    "BUDGET ALERT: %d%% threshold crossed — $%.2f / $%.2f",
                    threshold,
                    self._total_spent,
                    self.monthly_budget,
                )

    def _load_total(self) -> float:
        """Load total spent from existing JSONL entries."""
        if not self._log_file.exists():
            return 0.0
        total = 0.0
        for line in self._log_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                total += entry.get("cost_usd", 0.0)
            except json.JSONDecodeError:
                continue
        return total

    def _count_entries(self) -> int:
        """Count entries in the current period's log file."""
        if not self._log_file.exists():
            return 0
        return sum(
            1
            for line in self._log_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
