"""Pipeline orchestrator — coordinates the full CodeCustodian workflow.

Implements the linear pipeline:
  Scan → De-dup → Prioritize → Plan → [Approve?] → Execute → Verify → PR / Proposal

Each stage is isolated: a failure on one finding does not block others.
Includes OpenTelemetry distributed tracing (FR-OBS-101), proposal mode
(BR-PR-003), configurable PR sizing (BR-PLN-002), and approval gates
(BR-GOV-002).
"""

from __future__ import annotations

import os
import time
from collections import defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.trace.status import Status, StatusCode

from codecustodian.exceptions import (
    ApprovalRequiredError,
    ExecutorError,
    PlannerError,
    VerifierError,
)
from codecustodian.logging import get_logger
from codecustodian.models import (
    ExecutionResult,
    Finding,
    PipelineResult,
    PipelineStage,
    ProposalResult,
    PullRequestInfo,
    RefactoringPlan,
    VerificationResult,
)

if TYPE_CHECKING:
    from codecustodian.config.schema import CodeCustodianConfig

logger = get_logger("pipeline")
tracer = trace.get_tracer("codecustodian.pipeline", "1.0.0")


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
        with tracer.start_as_current_span(
            "pipeline.run",
            attributes={
                "pipeline.run_id": self._result.run_id,
                "pipeline.repo_path": self.repo_path,
                "pipeline.dry_run": self.dry_run,
            },
        ) as root_span:
            start = time.monotonic()
            logger.info(
                "Pipeline starting for %s (run_id=%s)",
                self.repo_path,
                self._result.run_id,
            )

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

                # Stage 3: Prioritize (with business impact scoring)
                findings = self._prioritize(findings)

                # Stage 4: Group & size for PR batching (BR-PLN-002)
                batches = self._group_findings(findings)
                logger.info(
                    "Grouped %d findings into %d batches",
                    len(findings),
                    len(batches),
                )

                # Stages 5–8: Plan → Approve? → Execute → Verify → PR/Proposal
                for batch in batches:
                    for finding in batch:
                        await self._process_finding(finding)

            except Exception as exc:
                logger.exception("Pipeline failed")
                self._result.errors.append(str(exc))
                root_span.set_status(Status(StatusCode.ERROR, str(exc)))
                root_span.record_exception(exc)

            elapsed = time.monotonic() - start
            self._result.total_duration_seconds = elapsed
            self._result.completed_at = datetime.now(UTC)

            root_span.set_attribute("pipeline.duration_seconds", elapsed)
            root_span.set_attribute("pipeline.findings_count", len(self._result.findings))
            root_span.set_attribute("pipeline.prs_created", self._result.prs_created)

            logger.info("Pipeline finished in %.1fs", elapsed)
            return self._result

    # ── PR sizing / splitting (BR-PLN-002) ─────────────────────────────

    def _group_findings(self, findings: list[Finding]) -> list[list[Finding]]:
        """Group findings into batches respecting PR size limits.

        Groups by directory proximity, then splits batches that exceed
        ``max_files_per_pr`` or ``max_lines_per_pr``.
        """
        max_files = self.config.behavior.max_files_per_pr
        max_prs = self.config.behavior.max_prs_per_run

        if not self.config.behavior.auto_split_prs:
            return [findings[:max_prs]]

        # Group by parent directory
        dir_groups: dict[str, list[Finding]] = defaultdict(list)
        for f in findings:
            parent = str(os.path.dirname(f.file)) or "."
            dir_groups[parent].append(f)

        batches: list[list[Finding]] = []
        for _dir_path, group in dir_groups.items():
            current_batch: list[Finding] = []
            for finding in group:
                current_batch.append(finding)
                if len(current_batch) >= max_files:
                    batches.append(current_batch)
                    current_batch = []
            if current_batch:
                batches.append(current_batch)

        # Respect overall PR limit
        return batches[:max_prs]

    # ── Stage implementations ──────────────────────────────────────────

    async def _scan(self) -> list[Finding]:
        """Run all enabled scanners."""
        with tracer.start_as_current_span(
            "pipeline.scan",
            attributes={"pipeline.repo_path": self.repo_path},
        ):
            from codecustodian.scanner.registry import get_default_registry

            logger.info(
                "Scanning %s …",
                self.repo_path,
                extra={"stage": PipelineStage.SCAN.value},
            )

            registry = get_default_registry(self.config)
            all_findings: list[Finding] = []

            for scanner in registry.get_enabled():
                scanner_name = scanner.name
                with tracer.start_as_current_span(
                    f"pipeline.scan.{scanner_name}",
                    attributes={"scanner.name": scanner_name},
                ):
                    try:
                        results = scanner.scan(self.repo_path)
                        logger.info(
                            "Scanner %s found %d issues",
                            scanner_name,
                            len(results),
                        )
                        all_findings.extend(results)
                    except Exception as exc:
                        logger.exception("Scanner %s failed", scanner_name)
                        self._result.errors.append(
                            f"scanner.{scanner_name}: {exc}"
                        )

            return all_findings

    def _dedup(self, findings: list[Finding]) -> list[Finding]:
        """Remove duplicate findings using dedup_key."""
        with tracer.start_as_current_span(
            "pipeline.dedup",
            attributes={"pipeline.input_count": len(findings)},
        ):
            logger.info(
                "De-duplicating %d findings",
                len(findings),
                extra={"stage": PipelineStage.DEDUP.value},
            )
            seen: set[str] = set()
            unique: list[Finding] = []
            for f in findings:
                if f.dedup_key not in seen:
                    seen.add(f.dedup_key)
                    unique.append(f)
            logger.info(
                "De-duplication removed %d duplicates",
                len(findings) - len(unique),
            )
            return unique

    def _prioritize(self, findings: list[Finding]) -> list[Finding]:
        """Sort findings by combined priority + business impact score."""
        with tracer.start_as_current_span(
            "pipeline.prioritize",
            attributes={"pipeline.input_count": len(findings)},
        ):
            logger.info(
                "Prioritizing %d findings",
                len(findings),
                extra={"stage": PipelineStage.PRIORITIZE.value},
            )
            return sorted(
                findings,
                key=lambda f: f.priority_score + f.business_impact_score,
                reverse=True,
            )

    async def _process_finding(self, finding: Finding) -> None:
        """Run plan → [approve] → execute/proposal → verify → PR for a finding."""
        try:
            plan = await self._plan(finding)
            if plan is None:
                return

            # ── Proposal mode check (BR-PR-003) ───────────────────────
            if self._should_create_proposal(finding, plan):
                proposal = self._create_proposal(finding, plan)
                self._result.proposals.append(proposal)
                logger.info(
                    "Created proposal (not PR) for finding %s — confidence %d < threshold %d",
                    finding.id,
                    plan.confidence_score,
                    self.config.behavior.proposal_mode_threshold,
                )
                return

            self._result.plans.append(plan)

            # ── Dry-run gate ───────────────────────────────────────────
            if self.dry_run:
                logger.info("Dry-run: skipping execution for %s", finding.id)
                return

            # ── Approval gate (BR-GOV-002) ─────────────────────────────
            try:
                self._check_approval(plan)
            except ApprovalRequiredError as exc:
                logger.info(
                    "Plan %s requires approval — pausing: %s",
                    plan.id,
                    exc.message,
                )
                self._result.errors.append(f"{plan.id}: awaiting approval")
                return

            # ── Execute ────────────────────────────────────────────────
            execution = await self._execute(plan)
            self._result.executions.append(execution)

            if not execution.success:
                logger.warning("Execution failed for %s", finding.id)
                return

            # ── Verify ─────────────────────────────────────────────────
            verification = await self._verify(execution)
            self._result.verifications.append(verification)

            if verification.passed:
                pr = await self._create_pr(finding, plan, execution, verification)
                if pr:
                    self._result.pull_requests.append(pr)
            else:
                # Downgrade to proposal if verification fails (BR-QA-002)
                logger.warning(
                    "Verification failed for %s — downgrading to proposal and rolling back",
                    finding.id,
                )
                await self._rollback(execution)
                proposal = self._create_proposal(
                    finding,
                    plan,
                    extra_risks=["Automated verification failed after execution"],
                )
                self._result.proposals.append(proposal)

        except PlannerError as exc:
            logger.exception("Planner error for finding %s", finding.id)
            self._result.errors.append(f"{finding.id}: planner: {exc.message}")
        except ExecutorError as exc:
            logger.exception("Executor error for finding %s", finding.id)
            self._result.errors.append(f"{finding.id}: executor: {exc.message}")
        except VerifierError as exc:
            logger.exception("Verifier error for finding %s", finding.id)
            self._result.errors.append(f"{finding.id}: verifier: {exc.message}")
        except Exception as exc:
            logger.exception("Error processing finding %s", finding.id)
            self._result.errors.append(f"{finding.id}: {exc}")

    # ── Proposal mode helpers ──────────────────────────────────────────

    def _should_create_proposal(self, finding: Finding, plan: RefactoringPlan) -> bool:
        """Determine if this finding should get a proposal instead of a PR.

        Returns ``True`` when:
        - Plan confidence < ``proposal_mode_threshold``
        - Plan confidence < ``confidence_threshold`` (already existed)
        - Sensitive path detected via ``ApprovalConfig.sensitive_paths``
        """
        threshold = self.config.behavior.proposal_mode_threshold
        if plan.confidence_score < threshold:
            return True
        if plan.confidence_score < self.config.behavior.confidence_threshold:
            return True

        # Check sensitive paths
        from codecustodian.config.policies import PolicyManager

        pm = PolicyManager()
        sensitive = self.config.approval.sensitive_paths
        if pm.should_use_proposal_mode(finding.file, finding.type.value, sensitive_paths=sensitive):
            return True

        return False

    def _create_proposal(
        self,
        finding: Finding,
        plan: RefactoringPlan,
        *,
        extra_risks: list[str] | None = None,
    ) -> ProposalResult:
        """Build an advisory ``ProposalResult`` from a finding + plan."""
        risks = [f"Confidence score: {plan.confidence_score}/10"]
        if plan.risk_level.value != "low":
            risks.append(f"Risk level: {plan.risk_level.value}")
        if extra_risks:
            risks.extend(extra_risks)

        return ProposalResult(
            finding=finding,
            recommended_steps=[
                plan.summary,
                f"Review AI reasoning: {plan.ai_reasoning}" if plan.ai_reasoning else "Review changes manually",
                "Run tests after applying changes",
            ],
            estimated_effort=plan.reviewer_effort if hasattr(plan, "reviewer_effort") else "medium",
            risks=risks,
            is_proposal_only=True,
        )

    # ── Approval gate (BR-GOV-002) ─────────────────────────────────────

    def _check_approval(self, plan: RefactoringPlan) -> bool:
        """Check if plan requires approval before execution.

        Raises:
            ApprovalRequiredError: When the plan needs human approval.
        """
        with tracer.start_as_current_span(
            "pipeline.check_approval",
            attributes={"plan.id": plan.id},
        ):
            if self.config.approval.require_plan_approval:
                raise ApprovalRequiredError(
                    message=f"Plan {plan.id} requires approval before execution",
                    resource_id=plan.id,
                    approval_type="plan",
                )
            return True

    # ── Core stage methods ─────────────────────────────────────────────

    async def _plan(self, finding: Finding) -> RefactoringPlan | None:
        """Generate a refactoring plan using the AI planner."""
        with tracer.start_as_current_span(
            "pipeline.plan",
            attributes={
                "finding.id": finding.id,
                "finding.type": finding.type.value,
            },
        ):
            # TODO: Wire up CopilotPlanner (Phase 3)
            logger.info(
                "Planning for %s",
                finding.id,
                extra={"stage": PipelineStage.PLAN.value},
            )
            return None

    async def _execute(self, plan: RefactoringPlan) -> ExecutionResult:
        """Apply code changes from the plan."""
        with tracer.start_as_current_span(
            "pipeline.execute",
            attributes={
                "plan.id": plan.id,
                "plan.confidence": plan.confidence_score,
            },
        ):
            # TODO: Wire up SafeFileEditor + GitManager (Phase 4)
            logger.info(
                "Executing plan %s",
                plan.id,
                extra={"stage": PipelineStage.EXECUTE.value},
            )
            return ExecutionResult(plan_id=plan.id, success=False)

    async def _verify(self, execution: ExecutionResult) -> VerificationResult:
        """Verify applied changes with tests + linting."""
        with tracer.start_as_current_span(
            "pipeline.verify",
            attributes={"execution.plan_id": execution.plan_id},
        ):
            # TODO: Wire up Verifier (Phase 4)
            logger.info(
                "Verifying execution %s",
                execution.plan_id,
                extra={"stage": PipelineStage.VERIFY.value},
            )
            return VerificationResult(passed=False)

    async def _create_pr(
        self,
        finding: Finding,
        plan: RefactoringPlan,
        execution: ExecutionResult,
        verification: VerificationResult,
    ) -> PullRequestInfo | None:
        """Create a pull request for verified changes."""
        with tracer.start_as_current_span(
            "pipeline.create_pr",
            attributes={
                "finding.id": finding.id,
                "plan.id": plan.id,
            },
        ):
            # TODO: Wire up PRCreator (Phase 5)
            logger.info(
                "Creating PR for %s",
                finding.id,
                extra={"stage": PipelineStage.PR.value},
            )
            return None

    async def _rollback(self, execution: ExecutionResult) -> None:
        """Restore files from backup after verification failure."""
        with tracer.start_as_current_span(
            "pipeline.rollback",
            attributes={"execution.plan_id": execution.plan_id},
        ):
            # TODO: Wire up BackupManager.restore (Phase 4)
            logger.info("Rolling back execution %s", execution.plan_id)
