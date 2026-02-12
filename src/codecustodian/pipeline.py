"""Pipeline orchestrator — coordinates the full CodeCustodian workflow.

Implements the linear pipeline:
  Scan → De-dup → Prioritize → Plan → Execute → Verify → PR → Feedback

Each stage is isolated: a failure on one finding does not block others.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import TYPE_CHECKING

from codecustodian.logging import get_logger
from codecustodian.models import (
    ExecutionResult,
    Finding,
    PipelineResult,
    PipelineStage,
    PullRequestInfo,
    RefactoringPlan,
    VerificationResult,
)

if TYPE_CHECKING:
    from codecustodian.config.schema import CodeCustodianConfig

logger = get_logger("pipeline")


class Pipeline:
    """Orchestrates the CodeCustodian pipeline for a single repository.

    Usage::

        pipeline = Pipeline(config=config, repo_path="/path/to/repo")
        result = await pipeline.run()
    """

    def __init__(
        self,
        config: CodeCustodianConfig,
        repo_path: str,
        *,
        github_token: str | None = None,
        copilot_token: str | None = None,
        dry_run: bool = False,
    ) -> None:
        self.config = config
        self.repo_path = repo_path
        self.github_token = github_token
        self.copilot_token = copilot_token
        self.dry_run = dry_run
        self._result = PipelineResult()

    async def run(self) -> PipelineResult:
        """Execute the full pipeline and return aggregated results."""
        start = time.monotonic()
        logger.info("Pipeline starting for %s", self.repo_path)

        try:
            # Stage 1: Scan
            findings = await self._scan()
            self._result.findings = findings
            logger.info(
                "Scan complete: %d findings",
                len(findings),
                extra={"stage": PipelineStage.SCAN.value},
            )

            # Stage 2: De-duplicate
            findings = self._dedup(findings)

            # Stage 3: Prioritize & limit
            findings = self._prioritize(findings)
            max_prs = self.config.behavior.max_prs_per_run
            findings = findings[:max_prs]

            # Stages 4–7: Plan → Execute → Verify → PR  (per finding)
            for finding in findings:
                await self._process_finding(finding)

        except Exception as exc:
            logger.exception("Pipeline failed")
            self._result.errors.append(str(exc))

        elapsed = time.monotonic() - start
        self._result.total_duration_seconds = elapsed
        self._result.completed_at = datetime.utcnow()
        logger.info("Pipeline finished in %.1fs", elapsed)
        return self._result

    # ── Stage implementations ──────────────────────────────────────────

    async def _scan(self) -> list[Finding]:
        """Run all enabled scanners."""
        # TODO: Wire up ScannerRegistry once implemented (Phase 2)
        logger.info("Scanning %s …", self.repo_path, extra={"stage": PipelineStage.SCAN.value})
        return []

    def _dedup(self, findings: list[Finding]) -> list[Finding]:
        """Remove duplicate findings across runs."""
        # TODO: Wire up DeduplicationEngine once implemented (Phase 2)
        logger.info("De-duplicating %d findings", len(findings), extra={"stage": PipelineStage.DEDUP.value})
        return findings

    def _prioritize(self, findings: list[Finding]) -> list[Finding]:
        """Sort findings by priority_score descending."""
        logger.info("Prioritizing %d findings", len(findings), extra={"stage": PipelineStage.PRIORITIZE.value})
        return sorted(findings, key=lambda f: f.priority_score, reverse=True)

    async def _process_finding(self, finding: Finding) -> None:
        """Run plan → execute → verify → PR for a single finding."""
        try:
            plan = await self._plan(finding)
            if plan is None:
                return

            if plan.confidence_score < self.config.behavior.confidence_threshold:
                logger.info(
                    "Skipping finding %s — confidence %d < threshold %d",
                    finding.id,
                    plan.confidence_score,
                    self.config.behavior.confidence_threshold,
                )
                return

            self._result.plans.append(plan)

            if self.dry_run:
                logger.info("Dry-run: skipping execution for %s", finding.id)
                return

            execution = await self._execute(plan)
            self._result.executions.append(execution)

            if not execution.success:
                logger.warning("Execution failed for %s", finding.id)
                return

            verification = await self._verify(execution)
            self._result.verifications.append(verification)

            if verification.passed:
                pr = await self._create_pr(finding, plan, execution, verification)
                if pr:
                    self._result.pull_requests.append(pr)
            else:
                logger.warning("Verification failed for %s — rolling back", finding.id)
                await self._rollback(execution)

        except Exception as exc:
            logger.exception("Error processing finding %s", finding.id)
            self._result.errors.append(f"{finding.id}: {exc}")

    async def _plan(self, finding: Finding) -> RefactoringPlan | None:
        """Generate a refactoring plan using the AI planner."""
        # TODO: Wire up CopilotPlanner (Phase 3)
        logger.info("Planning for %s", finding.id, extra={"stage": PipelineStage.PLAN.value})
        return None

    async def _execute(self, plan: RefactoringPlan) -> ExecutionResult:
        """Apply code changes from the plan."""
        # TODO: Wire up SafeFileEditor + GitManager (Phase 4)
        logger.info("Executing plan %s", plan.id, extra={"stage": PipelineStage.EXECUTE.value})
        return ExecutionResult(plan_id=plan.id, success=False)

    async def _verify(self, execution: ExecutionResult) -> VerificationResult:
        """Verify applied changes with tests + linting."""
        # TODO: Wire up Verifier (Phase 4)
        logger.info("Verifying execution %s", execution.plan_id, extra={"stage": PipelineStage.VERIFY.value})
        return VerificationResult(passed=False)

    async def _create_pr(
        self,
        finding: Finding,
        plan: RefactoringPlan,
        execution: ExecutionResult,
        verification: VerificationResult,
    ) -> PullRequestInfo | None:
        """Create a pull request for verified changes."""
        # TODO: Wire up PRCreator (Phase 5)
        logger.info("Creating PR for %s", finding.id, extra={"stage": PipelineStage.PR.value})
        return None

    async def _rollback(self, execution: ExecutionResult) -> None:
        """Restore files from backup after verification failure."""
        # TODO: Wire up BackupManager.restore (Phase 4)
        logger.info("Rolling back execution %s", execution.plan_id)
