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
from pathlib import Path
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
from codecustodian.intelligence.business_impact import BusinessImpactScorer
from codecustodian.enterprise.sla_reporter import SLAReporter
from codecustodian.integrations.work_iq import WorkIQContextProvider
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
        self._work_iq: WorkIQContextProvider | None = None
        if getattr(self.config.work_iq, "enabled", False):
            self._work_iq = WorkIQContextProvider()

        # Phase 8: Business Impact Scorer
        self._impact_scorer: BusinessImpactScorer | None = None
        if getattr(self.config, "business_impact", None) and self.config.business_impact.enabled:
            from codecustodian.intelligence.business_impact import ScoringWeights
            weights = ScoringWeights(
                usage=self.config.business_impact.usage_weight,
                criticality=self.config.business_impact.criticality_weight,
                change_frequency=self.config.business_impact.change_frequency_weight,
                velocity_impact=self.config.business_impact.velocity_impact_weight,
                regulatory_risk=self.config.business_impact.regulatory_risk_weight,
            )
            self._impact_scorer = BusinessImpactScorer(weights=weights)

        # Phase 8: SLA Reporter
        self._sla_reporter: SLAReporter | None = None
        if getattr(self.config, "sla", None) and self.config.sla.enabled:
            self._sla_reporter = SLAReporter(db_path=self.config.sla.db_path)

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
                findings = await self._score_business_impact(findings)
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

            # Phase 8: Record SLA metrics (BR-ENT-002)
            if self._sla_reporter is not None:
                try:
                    self._sla_reporter.record_from_pipeline_result(self._result)
                except Exception as sla_exc:
                    logger.warning("SLA recording failed: %s", sla_exc)

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

    async def _score_business_impact(self, findings: list[Finding]) -> list[Finding]:
        """Score business impact for all findings (FR-PRIORITY-100)."""
        if self._impact_scorer is None:
            return findings

        with tracer.start_as_current_span(
            "pipeline.business_impact",
            attributes={"pipeline.input_count": len(findings)},
        ):
            logger.info("Scoring business impact for %d findings", len(findings))
            for finding in findings:
                try:
                    score = await self._impact_scorer.score(finding, self.repo_path)
                    finding.business_impact_score = score
                except Exception as exc:
                    logger.warning(
                        "Business impact scoring failed for %s: %s",
                        finding.id,
                        exc,
                    )
            return findings

    async def _process_finding(self, finding: Finding) -> None:
        """Run plan → [approve] → execute/proposal → verify → PR for a finding."""
        try:
            if self._work_iq is not None:
                try:
                    org_context = await self._work_iq.get_organizational_context(
                        f"{finding.file} {finding.type.value}"
                    )
                    if (
                        org_context.related_documents
                        or org_context.recent_discussions
                        or org_context.upcoming_meetings
                        or org_context.related_teams
                    ):
                        finding.metadata["work_iq_context"] = org_context.model_dump()

                    should_create = await self._work_iq.should_create_pr_now(finding)
                    if not should_create:
                        logger.info(
                            "Deferring finding %s based on Work IQ sprint context",
                            finding.id,
                        )
                        return
                except Exception as exc:
                    logger.warning(
                        "Work IQ context lookup failed for %s: %s",
                        finding.id,
                        exc,
                    )

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
        """Apply code changes from the plan.

        Workflow:
        1. Run 5-point safety checks
        2. Create a feature branch
        3. Apply all changes atomically
        4. Commit
        """
        with tracer.start_as_current_span(
            "pipeline.execute",
            attributes={
                "plan.id": plan.id,
                "plan.confidence": plan.confidence_score,
            },
        ):
            import time as _time

            from codecustodian.executor.backup import BackupManager
            from codecustodian.executor.file_editor import SafeFileEditor
            from codecustodian.executor.git_manager import GitManager
            from codecustodian.executor.safety_checks import SafetyCheckRunner

            logger.info(
                "Executing plan %s",
                plan.id,
                extra={"stage": PipelineStage.EXECUTE.value},
            )
            start = _time.monotonic()

            try:
                # 1. Safety checks
                safety_runner = SafetyCheckRunner(self.repo_path)
                safety_result = await safety_runner.run_all_checks(plan)

                if not safety_result.passed:
                    return ExecutionResult(
                        plan_id=plan.id,
                        success=False,
                        errors=[f"Safety check failed: {safety_result.action}"]
                        + [c.message for c in safety_result.failures],
                        safety_result=safety_result,
                        duration_seconds=_time.monotonic() - start,
                    )

                # 2. Setup backup + editor
                backup_mgr = BackupManager(
                    backup_dir=f"{self.repo_path}/.codecustodian-backups",
                    retention_days=self.config.advanced.backup_retention_days,
                )
                editor = SafeFileEditor(
                    validate_syntax=self.config.advanced.validate_syntax,
                    backup_manager=backup_mgr,
                )

                # 3. Apply changes atomically
                backup_paths = editor.apply_changes(plan.changes)

                # 4. Git operations
                git_mgr = GitManager(self.repo_path)
                # Find the finding for branch naming
                finding = next(
                    (f for f in self._result.findings if f.id == plan.finding_id),
                    None,
                )
                branch_name = ""
                commit_sha = ""
                if finding:
                    branch_name = git_mgr.create_branch(finding)
                    commit_sha = git_mgr.commit(
                        finding,
                        plan,
                        author_name=self.config.advanced.git.author_name,
                        author_email=self.config.advanced.git.author_email,
                    )

                return ExecutionResult(
                    plan_id=plan.id,
                    success=True,
                    changes_applied=plan.changes,
                    backup_paths=[str(bp) for bp in backup_paths],
                    branch_name=branch_name,
                    commit_sha=commit_sha,
                    safety_result=safety_result,
                    transaction_log=backup_mgr.transaction_log,
                    duration_seconds=_time.monotonic() - start,
                )

            except Exception as exc:
                logger.exception("Execution failed for plan %s", plan.id)
                return ExecutionResult(
                    plan_id=plan.id,
                    success=False,
                    errors=[str(exc)],
                    duration_seconds=_time.monotonic() - start,
                )

    async def _verify(self, execution: ExecutionResult) -> VerificationResult:
        """Verify applied changes with tests + linting + security."""
        with tracer.start_as_current_span(
            "pipeline.verify",
            attributes={"execution.plan_id": execution.plan_id},
        ):
            import time as _time

            from codecustodian.verifier.linter import LinterRunner
            from codecustodian.verifier.security_scanner import SecurityVerifier
            from codecustodian.verifier.test_runner import TestRunner

            logger.info(
                "Verifying execution %s",
                execution.plan_id,
                extra={"stage": PipelineStage.VERIFY.value},
            )
            start = _time.monotonic()

            changed_paths = [
                Path(c.file_path) for c in execution.changes_applied
            ]

            # Tests
            test_runner = TestRunner(
                framework=self.config.advanced.testing.framework,
                timeout=self.config.advanced.testing.timeout,
                coverage_threshold=self.config.advanced.testing.coverage_threshold,
            )
            test_result = test_runner.run_tests(changed_paths, self.repo_path)

            # Linting
            linter = LinterRunner()
            lint_violations = linter.run_all(changed_paths)

            # Security
            sec_verifier = SecurityVerifier()
            sec_result = sec_verifier.verify(changed_paths)

            # Combine
            lint_passed = len(lint_violations) == 0
            sec_passed = sec_result.get("passed", True)

            all_passed = test_result.passed and lint_passed and sec_passed

            failures = list(test_result.failures)
            if not lint_passed:
                failures.append(
                    f"{len(lint_violations)} lint violation(s) found"
                )
            if not sec_passed:
                failures.append(
                    f"{sec_result.get('total_issues', 0)} security issue(s) found"
                )

            return VerificationResult(
                passed=all_passed,
                tests_run=test_result.tests_run,
                tests_passed=test_result.tests_passed,
                tests_failed=test_result.tests_failed,
                tests_skipped=test_result.tests_skipped,
                coverage_overall=test_result.coverage_overall,
                coverage_delta=test_result.coverage_delta,
                lint_passed=lint_passed,
                lint_violations=lint_violations,
                security_passed=sec_passed,
                security_issues=[
                    __import__("codecustodian.models", fromlist=["SecurityIssue"]).SecurityIssue(**i)
                    for i in sec_result.get("issues", [])
                ],
                failures=failures,
                duration_seconds=_time.monotonic() - start,
            )

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
            logger.info(
                "Creating PR for %s",
                finding.id,
                extra={"stage": PipelineStage.PR.value},
            )

            if not self.github_token:
                logger.warning(
                    "No GitHub token — skipping PR creation for %s",
                    finding.id,
                )
                return None

            try:
                from codecustodian.executor.git_manager import GitManager
                from codecustodian.integrations.github_integration.comments import (
                    CommentManager,
                )
                from codecustodian.integrations.github_integration.pr_creator import (
                    PullRequestCreator,
                )

                # Derive repo name
                git_mgr = GitManager(self.repo_path)
                repo_name = git_mgr.get_repo_name(
                    config_override=self.config.github.repo_name,
                )

                # Push the branch to remote
                git_mgr.push(execution.branch_name)

                # Create the PR
                creator = PullRequestCreator(self.github_token, repo_name)
                reviewers = list(self.config.github.reviewers)
                team_reviewers = list(self.config.github.team_reviewers)

                if self._work_iq is not None:
                    try:
                        expert = await self._work_iq.get_expert_for_finding(finding)
                        finding.metadata["work_iq_expert"] = expert.model_dump()
                        if expert.email and expert.available:
                            reviewers = [expert.email] + [
                                reviewer
                                for reviewer in reviewers
                                if reviewer != expert.email
                            ]
                    except Exception as exc:
                        logger.warning(
                            "Work IQ expert lookup failed for %s: %s",
                            finding.id,
                            exc,
                        )

                pr_info = creator.create_pr(
                    finding=finding,
                    plan=plan,
                    execution=execution,
                    verification=verification,
                    branch=execution.branch_name,
                    base=self.config.github.base_branch,
                    draft_threshold=self.config.github.draft_threshold,
                    reviewers=reviewers,
                    team_reviewers=team_reviewers,
                )

                # Post audit trail comment
                try:
                    cm = CommentManager(self.github_token, repo_name)
                    cm.post_audit_summary(
                        pr_number=pr_info.number,
                        finding=finding,
                        plan=plan,
                        execution=execution,
                        verification=verification,
                    )
                except Exception:
                    logger.warning(
                        "Failed to post audit summary on PR #%d",
                        pr_info.number,
                    )

                return pr_info

            except Exception as exc:
                logger.exception(
                    "PR creation failed for finding %s", finding.id,
                )
                self._result.errors.append(
                    f"{finding.id}: pr_creation: {exc}",
                )
                return None

    async def _rollback(self, execution: ExecutionResult) -> None:
        """Restore files from backup after verification failure."""
        with tracer.start_as_current_span(
            "pipeline.rollback",
            attributes={"execution.plan_id": execution.plan_id},
        ):
            from codecustodian.executor.backup import BackupManager
            from codecustodian.executor.git_manager import GitManager

            logger.info("Rolling back execution %s", execution.plan_id)

            # Restore files from backups
            if execution.backup_paths:
                backup_mgr = BackupManager(
                    backup_dir=f"{self.repo_path}/.codecustodian-backups"
                )
                restored = backup_mgr.restore_all(
                    execution.backup_paths, self.repo_path
                )
                logger.info("Restored %d files from backup", restored)

            # Clean up git branch
            if execution.branch_name:
                try:
                    git_mgr = GitManager(self.repo_path)
                    git_mgr.cleanup(execution.branch_name)
                except Exception as exc:
                    logger.warning(
                        "Git cleanup failed for %s: %s",
                        execution.branch_name,
                        exc,
                    )
