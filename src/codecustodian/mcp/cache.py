"""In-memory cache for inter-tool state within an MCP session.

Allows tools to pass findings and plans between calls — e.g.
``scan_repository`` stores findings, ``plan_refactoring`` retrieves them.

Thread-safe via ``asyncio.Lock``.  Entries expire after a configurable TTL
(default 30 minutes).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from codecustodian.logging import get_logger

logger = get_logger("mcp.cache")

_DEFAULT_TTL_SECONDS: int = 30 * 60  # 30 minutes


class _Entry:
    """A cache entry with a timestamp for TTL-based expiry."""

    __slots__ = ("created_at", "value")

    def __init__(self, value: Any) -> None:
        self.value = value
        self.created_at: float = time.monotonic()

    def expired(self, ttl: int) -> bool:
        return (time.monotonic() - self.created_at) >= ttl


class ScanCache:
    """In-memory cache for findings and plans keyed by ID.

    Usage::

        cache = ScanCache()
        cache.store_finding(finding)
        f = cache.get_finding("abc123")

        cache.store_plan(plan)
        p = cache.get_plan("def456")
    """

    def __init__(self, ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._findings: dict[str, _Entry] = {}
        self._plans: dict[str, _Entry] = {}
        self._lock = asyncio.Lock()

    # ── Findings ───────────────────────────────────────────────────────

    async def store_finding(self, finding: Any) -> None:
        """Store a finding keyed by its ``id``."""
        async with self._lock:
            self._findings[finding.id] = _Entry(finding)
            logger.debug("Cached finding %s", finding.id)

    async def store_findings(self, findings: list[Any]) -> None:
        """Bulk-store findings."""
        async with self._lock:
            for f in findings:
                self._findings[f.id] = _Entry(f)
            logger.debug("Cached %d findings", len(findings))

    async def get_finding(self, finding_id: str) -> Any | None:
        """Retrieve a finding by ID, or ``None`` if missing/expired."""
        async with self._lock:
            entry = self._findings.get(finding_id)
            if entry is None or entry.expired(self._ttl):
                return None
            return entry.value

    async def list_findings(self) -> list[Any]:
        """Return all non-expired findings."""
        async with self._lock:
            self._purge_expired(self._findings)
            return [e.value for e in self._findings.values()]

    # ── Plans ──────────────────────────────────────────────────────────

    async def store_plan(self, plan: Any) -> None:
        """Store a plan keyed by its ``id``."""
        async with self._lock:
            self._plans[plan.id] = _Entry(plan)
            logger.debug("Cached plan %s", plan.id)

    async def get_plan(self, plan_id: str) -> Any | None:
        """Retrieve a plan by ID, or ``None`` if missing/expired."""
        async with self._lock:
            entry = self._plans.get(plan_id)
            if entry is None or entry.expired(self._ttl):
                return None
            return entry.value

    async def list_plans(self) -> list[Any]:
        """Return all non-expired plans."""
        async with self._lock:
            self._purge_expired(self._plans)
            return [e.value for e in self._plans.values()]

    # ── Housekeeping ───────────────────────────────────────────────────

    def _purge_expired(self, store: dict[str, _Entry]) -> None:
        """Remove expired entries (call while holding ``_lock``)."""
        expired_keys = [k for k, v in store.items() if v.expired(self._ttl)]
        for k in expired_keys:
            del store[k]

    async def clear(self) -> None:
        """Remove all entries."""
        async with self._lock:
            self._findings.clear()
            self._plans.clear()
            logger.debug("Cache cleared")

    async def stats(self) -> dict[str, int]:
        """Return cache statistics."""
        async with self._lock:
            self._purge_expired(self._findings)
            self._purge_expired(self._plans)
            return {
                "findings": len(self._findings),
                "plans": len(self._plans),
            }


# Module-level singleton shared by all MCP tools within the same process.
scan_cache = ScanCache()
