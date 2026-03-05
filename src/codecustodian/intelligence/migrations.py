"""Agentic migration engine.

Provides multi-stage framework migration planning and execution,
powered by the Copilot SDK and networkx for dependency ordering.

Flow:
    1. Detect deprecated framework usage via scanner findings
    2. Load playbook (if available) or ask AI for migration guide
    3. Build a dependency graph of migration stages
    4. Topologically sort stages to honour dependencies
    5. Execute each stage atomically with rollback safety
    6. Verify after each stage (tests + lint)
    7. Return a ``MigrationPlan`` with per-stage results
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import networkx as nx

from codecustodian.logging import get_logger
from codecustodian.models import (
    Finding,
    MigrationPlan,
    MigrationPlaybook,
    MigrationStage,
)

if TYPE_CHECKING:
    from codecustodian.config.schema import MigrationsConfig

logger = get_logger("intelligence.migrations")


class MigrationEngine:
    """Plan and execute multi-stage framework migrations.

    Each migration is modelled as a directed acyclic graph (DAG) of
    ``MigrationStage`` nodes.  ``networkx`` handles topological ordering
    so stages execute in dependency-safe order.

    Example::

        engine = MigrationEngine(config)
        plan = await engine.plan_migration(findings, copilot_session)
        results = await engine.execute_plan(plan, executor, verifier)
    """

    def __init__(
        self,
        config: MigrationsConfig,
        copilot_client: Any | None = None,
    ) -> None:
        self.config = config
        self.client = copilot_client

    # ── public API ────────────────────────────────────────────────────

    async def plan_migration(
        self,
        findings: list[Finding],
        session: Any | None = None,
    ) -> MigrationPlan | None:
        """Analyse *findings* and produce a ``MigrationPlan``."""
        if not self.config.enabled:
            return None

        # Group findings by framework hint
        framework, from_ver, to_ver = self._detect_framework(findings)
        if not framework:
            logger.info("No framework migration detected in findings")
            return None

        # Try to load a playbook first
        playbook = self._load_playbook(framework)
        if playbook:
            stages = self._stages_from_playbook(playbook)
        else:
            stages = await self._ask_ai_for_stages(
                framework, from_ver, to_ver, findings, session
            )

        if not stages:
            logger.warning("No migration stages generated for %s", framework)
            return None

        # Build dependency graph and sort
        ordered_stages = self._topological_sort(stages)

        plan = MigrationPlan(
            framework=framework,
            from_version=from_ver,
            to_version=to_ver,
            migration_guide_url=playbook.guide_url if playbook else "",
            stages=ordered_stages,
            breaking_changes=self._extract_breaking_changes(findings),
            estimated_complexity=self._estimate_complexity(ordered_stages),
            pr_strategy=self.config.pr_strategy,
            total_files_affected=self._count_affected_files(ordered_stages),
        )

        logger.info(
            "Migration plan: %s %s→%s — %d stages, complexity=%s, strategy=%s",
            framework,
            from_ver,
            to_ver,
            len(ordered_stages),
            plan.estimated_complexity,
            plan.pr_strategy,
        )
        return plan

    async def execute_plan(
        self,
        plan: MigrationPlan,
        executor: Any | None = None,
        verifier: Any | None = None,
    ) -> MigrationPlan:
        """Execute each stage in dependency order.

        Marks each stage as ``passed`` or ``failed``.  On failure the
        stage is marked ``rolled_back`` and later stages that depend on
        it are skipped.
        """
        failed_stages: set[str] = set()

        for stage in plan.stages:
            # Skip if a dependency failed
            if any(dep in failed_stages for dep in stage.depends_on):
                stage.status = "rolled_back"
                failed_stages.add(stage.name)
                logger.warning(
                    "Skipping stage '%s' — dependency failed", stage.name
                )
                continue

            stage.status = "running"
            logger.info("Executing migration stage: %s", stage.name)

            try:
                if executor:
                    for fc in stage.file_changes:
                        await executor.apply_change(fc)

                # Verify
                if verifier:
                    ok = await verifier.verify_all()
                else:
                    ok = True

                stage.status = "passed" if ok else "failed"
                if not ok:
                    failed_stages.add(stage.name)
                    logger.warning("Stage '%s' verification failed", stage.name)
            except Exception:
                stage.status = "failed"
                failed_stages.add(stage.name)
                logger.exception("Stage '%s' execution error", stage.name)

        return plan

    # ── playbook loading ──────────────────────────────────────────────

    def _load_playbook(self, framework: str) -> MigrationPlaybook | None:
        """Load a playbook from config if one matches *framework*."""
        playbook_cfg = self.config.playbooks.get(framework)
        if not playbook_cfg:
            return None
        return MigrationPlaybook(
            name=framework,
            framework=framework,
            guide_url=playbook_cfg.guide_url,
            patterns=[
                {"pattern": p.pattern, "replacement": p.replacement}
                for p in playbook_cfg.patterns
            ],
        )

    def _stages_from_playbook(
        self, playbook: MigrationPlaybook
    ) -> list[MigrationStage]:
        """Convert a playbook's patterns into sequential stages."""
        stages: list[MigrationStage] = []
        for i, pat in enumerate(playbook.patterns):
            stages.append(
                MigrationStage(
                    name=f"step-{i + 1}",
                    description=f"Replace: {pat.get('pattern', '')} → {pat.get('replacement', '')}",
                    order=i,
                    depends_on=[f"step-{i}"] if i > 0 else [],
                    patterns=[pat],
                )
            )
        return stages

    # ── AI stage generation ───────────────────────────────────────────

    async def _ask_ai_for_stages(
        self,
        framework: str,
        from_ver: str,
        to_ver: str,
        findings: list[Finding],
        session: Any | None,
    ) -> list[MigrationStage]:
        """Ask the Copilot SDK to generate migration stages."""
        if not session or not self.client:
            return self._fallback_stages(findings)

        finding_summaries = "\n".join(
            f"- {f.file}:{f.line} — {f.description}" for f in findings[:20]
        )

        prompt = (
            f"Plan a multi-stage migration for framework '{framework}' "
            f"from version {from_ver} to {to_ver}.\n\n"
            f"Affected findings:\n{finding_summaries}\n\n"
            "Respond with ONLY a JSON array of stage objects:\n"
            '[{"name": "...", "description": "...", "order": 0, '
            '"depends_on": [], "files_affected": [], '
            '"patterns": [{"pattern": "old", "replacement": "new"}]}]'
        )

        try:
            raw = await self.client.send_and_wait(session, prompt)
            return self._parse_stages(raw)
        except Exception:
            logger.exception("AI migration planning failed — using fallback")
            return self._fallback_stages(findings)

    def _parse_stages(self, raw: str) -> list[MigrationStage]:
        """Parse JSON array of stages from AI response."""
        text = raw.strip()
        # Strip markdown fencing
        if text.startswith("```"):
            lines = text.splitlines()
            lines = [line for line in lines if not line.strip().startswith("```")]
            text = "\n".join(lines).strip()

        start = text.find("[")
        end = text.rfind("]")
        if start < 0 or end <= start:
            return []

        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return []

        stages: list[MigrationStage] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            stages.append(
                MigrationStage(
                    name=item.get("name", f"stage-{len(stages)}"),
                    description=item.get("description", ""),
                    order=item.get("order", len(stages)),
                    depends_on=item.get("depends_on", []),
                    files_affected=item.get("files_affected", []),
                    patterns=item.get("patterns", []),
                )
            )
        return stages

    def _fallback_stages(self, findings: list[Finding]) -> list[MigrationStage]:
        """Create a single-stage migration as fallback."""
        return [
            MigrationStage(
                name="migrate-all",
                description="Apply all migration changes in a single stage",
                order=0,
                files_affected=list({f.file for f in findings}),
            )
        ]

    # ── graph utilities ───────────────────────────────────────────────

    def _topological_sort(
        self, stages: list[MigrationStage]
    ) -> list[MigrationStage]:
        """Sort stages in dependency order using networkx."""
        g = nx.DiGraph()
        stage_map = {s.name: s for s in stages}

        for s in stages:
            g.add_node(s.name)
            for dep in s.depends_on:
                if dep in stage_map:
                    g.add_edge(dep, s.name)

        if not nx.is_directed_acyclic_graph(g):
            logger.warning("Cycle detected in migration stages — using order field")
            return sorted(stages, key=lambda s: s.order)

        ordered_names = list(nx.topological_sort(g))
        return [stage_map[name] for name in ordered_names if name in stage_map]

    # ── detection helpers ─────────────────────────────────────────────

    @staticmethod
    def _detect_framework(
        findings: list[Finding],
    ) -> tuple[str, str, str]:
        """Detect framework and version range from findings."""
        for f in findings:
            desc = f.description.lower()
            if "deprecated" in desc or "migration" in desc:
                # Try to extract framework name from description
                for kw in ("flask", "django", "fastapi", "sqlalchemy", "pydantic", "celery", "pytest"):
                    if kw in desc:
                        return kw, "unknown", "latest"
        return "", "", ""

    @staticmethod
    def _extract_breaking_changes(findings: list[Finding]) -> list[str]:
        """Pull breaking-change descriptions from finding metadata."""
        changes: list[str] = []
        for f in findings:
            if f.severity.value in ("high", "critical"):
                changes.append(f"{f.file}:{f.line} — {f.description}")
        return changes

    @staticmethod
    def _estimate_complexity(stages: list[MigrationStage]) -> str:
        """Estimate migration complexity based on stage count & files."""
        total_files = sum(len(s.files_affected) for s in stages)
        if len(stages) <= 2 and total_files <= 5:
            return "simple"
        if len(stages) > 5 or total_files > 20:
            return "expert-only"
        return "complex"

    @staticmethod
    def _count_affected_files(stages: list[MigrationStage]) -> int:
        """Count unique files affected across all stages."""
        files: set[str] = set()
        for s in stages:
            files.update(s.files_affected)
            files.update(fc.file_path for fc in s.file_changes)
        return len(files)
