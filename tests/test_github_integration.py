"""Tests for GitHub integration — Phase 5.

Covers:
- PullRequestCreator: body template, labels, draft mode, reviewers, error wrapping
- PRInteractionHandler: command dispatcher, all handlers, feedback recording
- IssueManager: create_issue, create_proposal_issue, duplicate detection
- CommentManager: review comments, PR comments, audit trail
- GitManager.get_repo_name: HTTPS/SSH URL parsing, config override
- Pipeline._create_pr: full wiring with mocked GitHub classes
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from codecustodian.exceptions import ExecutorError, GitHubAPIError
from codecustodian.models import (
    AlternativeSolution,
    ChangeType,
    ExecutionResult,
    FileChange,
    Finding,
    FindingType,
    LintViolation,
    ProposalResult,
    PullRequestInfo,
    RefactoringPlan,
    RiskLevel,
    SafetyCheckResult,
    SafetyResult,
    SecurityIssue,
    SeverityLevel,
    TransactionLogEntry,
    VerificationResult,
)

# ── Fixtures ───────────────────────────────────────────────────────────────

def _make_finding(**overrides) -> Finding:
    defaults = {
        "id": "f-001",
        "file": "src/app.py",
        "line": 42,
        "description": "Using deprecated API os.popen()",
        "suggestion": "Use subprocess.run() instead",
        "type": FindingType.DEPRECATED_API,
        "severity": SeverityLevel.HIGH,
    }
    defaults.update(overrides)
    return Finding(**defaults)


def _make_plan(**overrides) -> RefactoringPlan:
    defaults = {
        "id": "p-001",
        "finding_id": "f-001",
        "summary": "Replace os.popen with subprocess.run",
        "description": "Migrate from deprecated os.popen() to subprocess.run()",
        "changes": [
            FileChange(
                file_path="src/app.py",
                change_type=ChangeType.REPLACE,
                description="Replace os.popen with subprocess.run",
            ),
        ],
        "confidence_score": 8,
        "risk_level": RiskLevel.LOW,
        "ai_reasoning": "os.popen is deprecated since Python 3.0",
        "confidence_factors": ["Well-documented migration", "No side effects"],
        "reviewer_effort": "low",
        "alternatives": [
            AlternativeSolution(
                name="asyncio.subprocess",
                description="Use asyncio for async execution",
                pros=["Non-blocking"],
                cons=["Requires async context"],
                confidence_score=6,
            ),
        ],
    }
    defaults.update(overrides)
    return RefactoringPlan(**defaults)


def _make_execution(**overrides) -> ExecutionResult:
    defaults = {
        "plan_id": "p-001",
        "success": True,
        "branch_name": "tech-debt/deprecated-api-app-20250101-0000",
        "commit_sha": "abc123def456789012345678",
        "duration_seconds": 2.5,
        "safety_result": SafetyResult(
            passed=True,
            checks=[
                SafetyCheckResult(name="syntax", passed=True, message="OK"),
                SafetyCheckResult(name="imports", passed=True, message="OK"),
            ],
        ),
        "transaction_log": [
            TransactionLogEntry(
                action="backup",
                file_path="src/app.py",
                backup_path="/tmp/backup/app.py",
                success=True,
            ),
            TransactionLogEntry(
                action="apply",
                file_path="src/app.py",
                success=True,
            ),
        ],
    }
    defaults.update(overrides)
    return ExecutionResult(**defaults)


def _make_verification(**overrides) -> VerificationResult:
    defaults = {
        "passed": True,
        "tests_run": 42,
        "tests_passed": 40,
        "tests_failed": 1,
        "tests_skipped": 1,
        "coverage_overall": 85.3,
        "coverage_delta": 0.5,
        "lint_passed": True,
        "security_passed": True,
    }
    defaults.update(overrides)
    return VerificationResult(**defaults)


def _mock_github_repo():
    """Create a mock GitHub repository with common methods."""
    repo = MagicMock()
    repo.full_name = "owner/test-repo"

    # Mock PR
    mock_pr = MagicMock()
    mock_pr.number = 42
    mock_pr.html_url = "https://github.com/owner/test-repo/pull/42"
    mock_pr.body = ""
    repo.create_pull.return_value = mock_pr

    # Mock issue
    mock_issue = MagicMock()
    mock_issue.number = 10
    repo.create_issue.return_value = mock_issue

    # Mock commit
    mock_commit = MagicMock()
    repo.get_commit.return_value = mock_commit

    # Mock label creation (422 = already exists)
    repo.create_label.return_value = MagicMock()

    return repo


# ── PullRequestCreator Tests ──────────────────────────────────────────────


class TestPullRequestCreator:
    def _make_creator(self, mock_repo=None):
        with patch("github.Github") as MockGH:  # noqa: N806
            gh = MagicMock()
            repo = mock_repo or _mock_github_repo()
            gh.get_repo.return_value = repo
            MockGH.return_value = gh

            from codecustodian.integrations.github_integration.pr_creator import (
                PullRequestCreator,
            )

            creator = PullRequestCreator("fake-token", "owner/repo")
            creator.repo = repo
            return creator, repo

    def test_create_pr_returns_pull_request_info(self):
        creator, _repo = self._make_creator()
        finding = _make_finding()
        plan = _make_plan()
        execution = _make_execution()
        verification = _make_verification()

        result = creator.create_pr(
            finding, plan, execution, verification,
            branch="tech-debt/fix-123",
            base="main",
        )

        assert isinstance(result, PullRequestInfo)
        assert result.number == 42
        assert result.url == "https://github.com/owner/test-repo/pull/42"
        assert result.title.startswith("refactor:")
        assert result.branch == "tech-debt/fix-123"
        assert result.base_branch == "main"

    def test_create_pr_high_confidence_not_draft(self):
        creator, repo = self._make_creator()
        plan = _make_plan(confidence_score=9)

        result = creator.create_pr(
            _make_finding(), plan, _make_execution(), _make_verification(),
            branch="b", draft_threshold=7,
        )

        assert result.draft is False
        # Verify create_pull was called with draft=False
        call_kwargs = repo.create_pull.call_args[1]
        assert call_kwargs["draft"] is False

    def test_create_pr_low_confidence_is_draft(self):
        creator, repo = self._make_creator()
        plan = _make_plan(confidence_score=5)

        result = creator.create_pr(
            _make_finding(), plan, _make_execution(), _make_verification(),
            branch="b", draft_threshold=7,
        )

        assert result.draft is True
        call_kwargs = repo.create_pull.call_args[1]
        assert call_kwargs["draft"] is True
        assert "draft" in result.labels

    def test_create_pr_requests_reviewers(self):
        creator, repo = self._make_creator()
        mock_pr = repo.create_pull.return_value

        creator.create_pr(
            _make_finding(), _make_plan(), _make_execution(), _make_verification(),
            branch="b",
            reviewers=["alice", "bob"],
            team_reviewers=["core-team"],
        )

        mock_pr.create_review_request.assert_called_once_with(
            reviewers=["alice", "bob"],
            team_reviewers=["core-team"],
        )

    def test_create_pr_wraps_github_error(self):
        creator, repo = self._make_creator()
        err = Exception("rate limited")
        err.status = 403
        err.data = "rate limit exceeded"
        repo.create_pull.side_effect = err

        with pytest.raises(GitHubAPIError) as exc_info:
            creator.create_pr(
                _make_finding(), _make_plan(),
                _make_execution(), _make_verification(),
                branch="b",
            )

        assert exc_info.value.status_code == 403
        assert "f-001" in str(exc_info.value)

    def test_body_contains_all_sections(self):
        creator, _ = self._make_creator()
        finding = _make_finding()
        plan = _make_plan()
        execution = _make_execution()
        verification = _make_verification()

        body = creator._build_body(finding, plan, execution, verification)

        assert "## 🤖 Automated Tech Debt Refactoring" in body
        assert finding.description in body
        assert "Confidence" in body
        assert "AI Reasoning" in body
        assert "Confidence Factors" in body
        assert "Verification Results" in body
        assert "Alternatives Considered" in body
        assert "Risks" in body
        assert "CodeCustodian" in body

    def test_body_renders_alternatives_properly(self):
        creator, _ = self._make_creator()
        plan = _make_plan(
            alternatives=[
                AlternativeSolution(
                    name="Option A",
                    description="First approach",
                    pros=["Fast"],
                    cons=["Complex"],
                    confidence_score=7,
                    recommended=True,
                ),
            ],
        )

        body = creator._build_body(
            _make_finding(), plan, _make_execution(), _make_verification(),
        )

        assert "Option A" in body
        assert "⭐ **recommended**" in body
        assert "Fast" in body
        assert "Complex" in body

    def test_body_with_lint_violations(self):
        creator, _ = self._make_creator()
        verification = _make_verification(
            lint_passed=False,
            lint_violations=[
                LintViolation(file="app.py", line=10, code="E501", message="too long"),
            ],
        )

        body = creator._build_body(
            _make_finding(), _make_plan(), _make_execution(), verification,
        )

        assert "❌" in body
        assert "1 violation(s)" in body

    def test_body_with_security_issues(self):
        creator, _ = self._make_creator()
        verification = _make_verification(
            security_passed=False,
            security_issues=[
                SecurityIssue(file="app.py", description="hardcoded password"),
            ],
        )

        body = creator._build_body(
            _make_finding(), _make_plan(), _make_execution(), verification,
        )

        assert "❌" in body
        assert "1 issue(s)" in body

    def test_body_shows_risks_for_high_risk(self):
        creator, _ = self._make_creator()
        plan = _make_plan(
            risk_level=RiskLevel.HIGH,
            changes_signature=True,
            confidence_score=4,
        )

        body = creator._build_body(
            _make_finding(), plan, _make_execution(), _make_verification(),
        )

        assert "Risk level: **high**" in body
        assert "Public API signature changed" in body
        assert "Manual verification recommended" in body

    def test_select_labels_base_labels(self):
        from codecustodian.integrations.github_integration.pr_creator import (
            PullRequestCreator,
        )

        labels = PullRequestCreator._select_labels(
            _make_finding(), _make_plan(),
        )

        assert "tech-debt" in labels
        assert "automated" in labels
        assert "codecustodian" in labels

    def test_select_labels_priority_from_severity(self):
        from codecustodian.integrations.github_integration.pr_creator import (
            PullRequestCreator,
        )

        # HIGH severity → P2
        labels = PullRequestCreator._select_labels(
            _make_finding(severity=SeverityLevel.HIGH),
            _make_plan(),
        )
        assert "P2-high" in labels

        # CRITICAL → P1
        labels = PullRequestCreator._select_labels(
            _make_finding(severity=SeverityLevel.CRITICAL),
            _make_plan(),
        )
        assert "P1-critical" in labels

    def test_select_labels_category(self):
        from codecustodian.integrations.github_integration.pr_creator import (
            PullRequestCreator,
        )

        labels = PullRequestCreator._select_labels(
            _make_finding(type=FindingType.SECURITY),
            _make_plan(),
        )
        assert "security" in labels

        labels = PullRequestCreator._select_labels(
            _make_finding(type=FindingType.CODE_SMELL),
            _make_plan(),
        )
        assert "code-smell" in labels

    def test_select_labels_confidence_bucket(self):
        from codecustodian.integrations.github_integration.pr_creator import (
            PullRequestCreator,
        )

        # High confidence
        labels = PullRequestCreator._select_labels(
            _make_finding(), _make_plan(confidence_score=9),
        )
        assert "high-confidence" in labels
        assert "low-confidence" not in labels

        # Low confidence
        labels = PullRequestCreator._select_labels(
            _make_finding(), _make_plan(confidence_score=3),
        )
        assert "low-confidence" in labels
        assert "high-confidence" not in labels

    def test_select_labels_risk_and_effort(self):
        from codecustodian.integrations.github_integration.pr_creator import (
            PullRequestCreator,
        )

        labels = PullRequestCreator._select_labels(
            _make_finding(),
            _make_plan(risk_level=RiskLevel.HIGH, reviewer_effort="high"),
        )
        assert "risk:high" in labels
        assert "effort:high" in labels

    def test_ensure_labels_exist_ignores_422(self):
        creator, repo = self._make_creator()

        # Simulate 422 for existing label
        err_422 = Exception("already exists")
        err_422.status = 422
        repo.create_label.side_effect = err_422

        # Should not raise
        creator._ensure_labels_exist(["tech-debt", "automated"])

    def test_ensure_labels_exist_creates_labels(self):
        creator, repo = self._make_creator()
        repo.create_label.return_value = MagicMock()

        creator._ensure_labels_exist(["tech-debt", "P1-critical"])

        assert repo.create_label.call_count == 2


# ── PRInteractionHandler Tests ────────────────────────────────────────────


class TestPRInteractionHandler:
    def _make_handler(self, mock_repo=None, feedback_dir=None):
        with patch("github.Github") as MockGH:  # noqa: N806
            gh = MagicMock()
            repo = mock_repo or _mock_github_repo()
            gh.get_repo.return_value = repo
            MockGH.return_value = gh

            from codecustodian.integrations.github_integration.pr_interaction import (
                PRInteractionHandler,
            )

            tmpdir = feedback_dir or tempfile.mkdtemp()
            handler = PRInteractionHandler(
                "fake-token", "owner/repo", feedback_dir=tmpdir,
            )
            handler.repo = repo
            return handler, repo

    def _mock_pr_with_body(self, repo, pr_body=""):
        mock_pr = MagicMock()
        mock_pr.number = 42
        mock_pr.body = pr_body
        repo.get_pull.return_value = mock_pr
        return mock_pr

    def test_approve_command(self):
        handler, repo = self._make_handler()
        self._mock_pr_with_body(repo)

        result = handler.handle_comment(42, "@codecustodian approve")
        assert result is not None
        assert "✅" in result

    def test_approve_slash_command(self):
        handler, repo = self._make_handler()
        self._mock_pr_with_body(repo)

        result = handler.handle_comment(42, "/approve")
        assert result is not None
        assert "✅" in result

    def test_lgtm_bare_keyword(self):
        handler, repo = self._make_handler()
        self._mock_pr_with_body(repo)

        result = handler.handle_comment(42, "lgtm")
        assert result is not None
        assert "✅" in result

    def test_looks_good_bare_keyword(self):
        handler, repo = self._make_handler()
        self._mock_pr_with_body(repo)

        result = handler.handle_comment(42, "looks good")
        assert result is not None
        assert "✅" in result

    def test_reject_closes_pr(self):
        handler, repo = self._make_handler()
        mock_pr = self._mock_pr_with_body(repo)

        result = handler.handle_comment(42, "@codecustodian reject")
        assert "❌" in result
        mock_pr.edit.assert_called_once_with(state="closed")

    def test_explain_extracts_reasoning(self):
        handler, repo = self._make_handler()
        pr_body = (
            "<details>\n"
            "<summary>🧠 AI Reasoning</summary>\n"
            "\n"
            "os.popen is deprecated since Python 3.0.\n"
            "\n"
            "</details>"
        )
        self._mock_pr_with_body(repo, pr_body)

        result = handler.handle_comment(42, "/explain")
        assert "os.popen is deprecated" in result

    def test_retry_returns_message(self):
        handler, repo = self._make_handler()
        self._mock_pr_with_body(repo)

        result = handler.handle_comment(42, "@codecustodian retry")
        assert "🔄" in result
        assert "retry" in result.lower()

    def test_why_extracts_finding(self):
        handler, repo = self._make_handler()
        pr_body = (
            "> **Finding:** Using deprecated API os.popen()\n"
            "> **Severity:** high | **Type:** deprecated_api\n"
        )
        self._mock_pr_with_body(repo, pr_body)

        result = handler.handle_comment(42, "@codecustodian why")
        assert "Using deprecated API" in result

    def test_alternatives_extracts_section(self):
        handler, repo = self._make_handler()
        pr_body = (
            "<details>\n"
            "<summary>🔄 Alternatives Considered</summary>\n"
            "\n"
            "#### asyncio.subprocess\nUse asyncio for async execution\n"
            "\n"
            "</details>"
        )
        self._mock_pr_with_body(repo, pr_body)

        result = handler.handle_comment(42, "@codecustodian alternatives")
        assert "asyncio.subprocess" in result

    def test_modify_records_feedback(self):
        handler, repo = self._make_handler()
        self._mock_pr_with_body(repo)

        result = handler.handle_comment(
            42, "@codecustodian modify Use pathlib instead"
        )
        assert "📝" in result
        assert "Use pathlib instead" in result

    def test_feedback_shows_stats(self):
        handler, repo = self._make_handler()
        self._mock_pr_with_body(repo)

        result = handler.handle_comment(42, "@codecustodian feedback Great work!")
        assert "📊" in result
        assert "accuracy" in result.lower()

    def test_smaller_request(self):
        handler, repo = self._make_handler()
        self._mock_pr_with_body(repo)

        result = handler.handle_comment(42, "@codecustodian smaller")
        assert "✂️" in result

    def test_propose_closes_pr(self):
        handler, repo = self._make_handler()
        mock_pr = self._mock_pr_with_body(repo)

        result = handler.handle_comment(42, "@codecustodian propose")
        assert "📋" in result
        mock_pr.edit.assert_called_once_with(state="closed")

    def test_unknown_comment_returns_none(self):
        handler, repo = self._make_handler()
        self._mock_pr_with_body(repo)

        result = handler.handle_comment(42, "Just a regular comment")
        assert result is None

    def test_unknown_command_returns_none(self):
        handler, repo = self._make_handler()
        self._mock_pr_with_body(repo)

        result = handler.handle_comment(42, "@codecustodian unknown_cmd")
        assert result is None

    def test_feedback_recorded_to_store(self):
        tmpdir = tempfile.mkdtemp()
        handler, repo = self._make_handler(feedback_dir=tmpdir)
        pr_body = "Confidence | **8/10**"
        self._mock_pr_with_body(repo, pr_body)

        handler.handle_comment(42, "@codecustodian approve")

        feedback_file = Path(tmpdir) / "feedback.jsonl"
        assert feedback_file.exists()
        content = feedback_file.read_text()
        assert "approved" in content
        assert "pr-42" in content or "42" in content


# ── IssueManager Tests ────────────────────────────────────────────────────


class TestIssueManager:
    def _make_manager(self, mock_repo=None):
        with patch("github.Github") as MockGH:  # noqa: N806
            gh = MagicMock()
            repo = mock_repo or _mock_github_repo()
            gh.get_repo.return_value = repo
            MockGH.return_value = gh

            from codecustodian.integrations.github_integration.issues import (
                IssueManager,
            )

            mgr = IssueManager("fake-token", "owner/repo")
            mgr.repo = repo
            return mgr, repo

    def test_create_issue_returns_number(self):
        mgr, repo = self._make_manager()
        mock_issue = MagicMock()
        mock_issue.number = 15
        repo.create_issue.return_value = mock_issue

        num = mgr.create_issue(_make_finding(), reason="low confidence")

        assert num == 15
        repo.create_issue.assert_called_once()
        call_kwargs = repo.create_issue.call_args[1]
        assert "[Tech Debt]" in call_kwargs["title"]
        assert "low confidence" in call_kwargs["body"]

    def test_create_issue_wraps_error(self):
        mgr, repo = self._make_manager()
        err = Exception("forbidden")
        err.status = 403
        err.data = "rate limit"
        repo.create_issue.side_effect = err

        with pytest.raises(GitHubAPIError) as exc_info:
            mgr.create_issue(_make_finding())

        assert exc_info.value.status_code == 403

    def test_create_proposal_issue(self):
        mgr, repo = self._make_manager()
        mock_issue = MagicMock()
        mock_issue.number = 20
        repo.create_issue.return_value = mock_issue
        repo.get_issues.return_value = []  # No duplicates

        proposal = ProposalResult(
            finding=_make_finding(),
            recommended_steps=["Step 1", "Step 2"],
            estimated_effort="low",
            risks=["Low confidence"],
        )

        num = mgr.create_proposal_issue(proposal)

        assert num == 20
        call_kwargs = repo.create_issue.call_args[1]
        assert "[Proposal]" in call_kwargs["title"]
        assert "Step 1" in call_kwargs["body"]
        assert "proposal" in call_kwargs["labels"]

    def test_create_proposal_issue_detects_duplicate(self):
        mgr, repo = self._make_manager()

        # Create an existing open issue that matches
        existing_issue = MagicMock()
        existing_issue.number = 99
        existing_issue.title = f"[Proposal] {_make_finding().description[:40]}"
        repo.get_issues.return_value = [existing_issue]

        proposal = ProposalResult(
            finding=_make_finding(),
            recommended_steps=["Step 1"],
        )

        num = mgr.create_proposal_issue(proposal)

        assert num == 99
        repo.create_issue.assert_not_called()

    def test_create_proposal_issue_wraps_error(self):
        mgr, repo = self._make_manager()
        repo.get_issues.return_value = []  # No duplicates
        err = Exception("server error")
        err.status = 500
        err.data = ""
        repo.create_issue.side_effect = err

        with pytest.raises(GitHubAPIError):
            mgr.create_proposal_issue(
                ProposalResult(finding=_make_finding()),
            )

    def test_check_duplicate_returns_none_when_no_match(self):
        mgr, repo = self._make_manager()
        other_issue = MagicMock()
        other_issue.number = 5
        other_issue.title = "[Bug] Something unrelated"
        repo.get_issues.return_value = [other_issue]

        result = mgr._check_duplicate(_make_finding())
        assert result is None


# ── CommentManager Tests ──────────────────────────────────────────────────


class TestCommentManager:
    def _make_manager(self, mock_repo=None):
        with patch("github.Github") as MockGH:  # noqa: N806
            gh = MagicMock()
            repo = mock_repo or _mock_github_repo()
            gh.get_repo.return_value = repo
            MockGH.return_value = gh

            from codecustodian.integrations.github_integration.comments import (
                CommentManager,
            )

            mgr = CommentManager("fake-token", "owner/repo")
            mgr.repo = repo
            return mgr, repo

    def test_post_pr_comment(self):
        mgr, repo = self._make_manager()
        mock_pr = MagicMock()
        mock_comment = MagicMock()
        mock_comment.id = 100
        mock_pr.create_issue_comment.return_value = mock_comment
        repo.get_pull.return_value = mock_pr

        cid = mgr.post_pr_comment(42, "Hello!")
        assert cid == 100

    def test_post_review_comment(self):
        mgr, repo = self._make_manager()
        mock_pr = MagicMock()
        mock_comment = MagicMock()
        mock_comment.id = 200
        mock_pr.create_review_comment.return_value = mock_comment
        repo.get_pull.return_value = mock_pr
        repo.get_commit.return_value = MagicMock()

        cid = mgr.post_review_comment(
            42, "Issue here", "src/app.py", 10, "abc123",
        )
        assert cid == 200

    def test_post_audit_summary(self):
        mgr, repo = self._make_manager()
        mock_pr = MagicMock()
        mock_comment = MagicMock()
        mock_comment.id = 300
        mock_pr.create_issue_comment.return_value = mock_comment
        repo.get_pull.return_value = mock_pr

        finding = _make_finding()
        plan = _make_plan()
        execution = _make_execution()
        verification = _make_verification()

        cid = mgr.post_audit_summary(42, finding, plan, execution, verification)

        assert cid == 300
        call_args = mock_pr.create_issue_comment.call_args[0][0]
        assert "Audit Trail" in call_args
        assert "Safety Checks" in call_args
        assert "Transaction Log" in call_args

    def test_post_audit_summary_with_lint_violations(self):
        mgr, repo = self._make_manager()
        mock_pr = MagicMock()
        mock_comment = MagicMock()
        mock_comment.id = 301
        mock_pr.create_issue_comment.return_value = mock_comment
        repo.get_pull.return_value = mock_pr

        verification = _make_verification(
            lint_passed=False,
            lint_violations=[
                LintViolation(
                    file="app.py", line=10, code="E501",
                    message="line too long",
                ),
            ],
        )

        mgr.post_audit_summary(
            42, _make_finding(), _make_plan(),
            _make_execution(), verification,
        )

        call_args = mock_pr.create_issue_comment.call_args[0][0]
        assert "E501" in call_args
        assert "line too long" in call_args

    def test_post_audit_summary_with_security_issues(self):
        mgr, repo = self._make_manager()
        mock_pr = MagicMock()
        mock_comment = MagicMock()
        mock_comment.id = 302
        mock_pr.create_issue_comment.return_value = mock_comment
        repo.get_pull.return_value = mock_pr

        verification = _make_verification(
            security_passed=False,
            security_issues=[
                SecurityIssue(
                    file="app.py", line=5, severity="HIGH",
                    description="hardcoded secret",
                ),
            ],
        )

        mgr.post_audit_summary(
            42, _make_finding(), _make_plan(),
            _make_execution(), verification,
        )

        call_args = mock_pr.create_issue_comment.call_args[0][0]
        assert "hardcoded secret" in call_args


# ── GitManager.get_repo_name Tests ────────────────────────────────────────


class TestGitManagerRepoName:
    def _make_git_manager(self, remote_url=None):
        with patch("codecustodian.executor.git_manager.Repo") as MockRepo:  # noqa: N806
            mock_repo = MagicMock()
            mock_repo.active_branch = MagicMock()
            mock_repo.active_branch.__str__ = MagicMock(return_value="main")
            MockRepo.return_value = mock_repo

            if remote_url is not None:
                mock_remote = MagicMock()
                mock_remote.urls = iter([remote_url])
                mock_repo.remote.return_value = mock_remote
            else:
                mock_repo.remote.side_effect = ValueError("No remote")

            from codecustodian.executor.git_manager import GitManager

            gm = GitManager("/fake/repo")
            return gm

    def test_config_override_takes_precedence(self):
        gm = self._make_git_manager(remote_url="https://github.com/a/b.git")
        assert gm.get_repo_name(config_override="custom/repo") == "custom/repo"

    def test_https_url_parsing(self):
        gm = self._make_git_manager(
            remote_url="https://github.com/owner/my-repo.git",
        )
        assert gm.get_repo_name() == "owner/my-repo"

    def test_https_url_without_git_suffix(self):
        gm = self._make_git_manager(
            remote_url="https://github.com/owner/my-repo",
        )
        assert gm.get_repo_name() == "owner/my-repo"

    def test_ssh_url_parsing(self):
        gm = self._make_git_manager(
            remote_url="git@github.com:owner/my-repo.git",
        )
        assert gm.get_repo_name() == "owner/my-repo"

    def test_ssh_url_without_git_suffix(self):
        gm = self._make_git_manager(
            remote_url="git@github.com:owner/my-repo",
        )
        assert gm.get_repo_name() == "owner/my-repo"

    def test_no_remote_raises_error(self):
        gm = self._make_git_manager(remote_url=None)
        with pytest.raises(ExecutorError, match="Cannot determine GitHub repo name"):
            gm.get_repo_name()

    def test_unrecognized_url_raises_error(self):
        gm = self._make_git_manager(
            remote_url="https://gitlab.com/owner/repo.git",
        )
        with pytest.raises(ExecutorError, match="Cannot determine GitHub repo name"):
            gm.get_repo_name()


# ── GitHubConfig Tests ────────────────────────────────────────────────────


class TestGitHubConfig:
    def test_repo_name_default_empty(self):
        from codecustodian.config.schema import GitHubConfig

        cfg = GitHubConfig()
        assert cfg.repo_name == ""

    def test_repo_name_override(self):
        from codecustodian.config.schema import GitHubConfig

        cfg = GitHubConfig(repo_name="owner/my-repo")
        assert cfg.repo_name == "owner/my-repo"

    def test_draft_threshold_default(self):
        from codecustodian.config.schema import GitHubConfig

        cfg = GitHubConfig()
        assert cfg.draft_threshold == 7

    def test_draft_threshold_custom(self):
        from codecustodian.config.schema import GitHubConfig

        cfg = GitHubConfig(draft_threshold=5)
        assert cfg.draft_threshold == 5


# ── Pipeline._create_pr Wiring Test ───────────────────────────────────────


class TestPipelineCreatePR:
    @pytest.mark.asyncio
    async def test_create_pr_no_token_returns_none(self):
        """Pipeline._create_pr returns None when no github_token."""
        from codecustodian.config.schema import CodeCustodianConfig

        config = CodeCustodianConfig()
        pipeline = _make_pipeline(config, github_token=None)

        result = await pipeline._create_pr(
            _make_finding(), _make_plan(),
            _make_execution(), _make_verification(),
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_create_pr_full_wiring(self):
        """Pipeline._create_pr wires up GitManager, PRCreator, CommentManager."""
        from codecustodian.config.schema import CodeCustodianConfig

        config = CodeCustodianConfig(
            github={"repo_name": "owner/repo", "base_branch": "main"},
        )
        pipeline = _make_pipeline(config, github_token="fake-token")

        with (
            patch(
                "codecustodian.executor.git_manager.Repo",
            ),
            patch(
                "codecustodian.executor.git_manager.GitManager.get_repo_name",
                return_value="owner/repo",
            ),
            patch(
                "codecustodian.executor.git_manager.GitManager.push",
            ),
            patch("github.Github") as MockGH,  # noqa: N806
        ):
            # Setup PR creator mock
            mock_pr = MagicMock()
            mock_pr.number = 42
            mock_pr.html_url = "https://github.com/owner/repo/pull/42"
            mock_repo = MagicMock()
            mock_repo.create_pull.return_value = mock_pr
            mock_repo.create_label.return_value = MagicMock()
            # Comment manager's get_pull
            mock_cm_pr = MagicMock()
            mock_cm_comment = MagicMock()
            mock_cm_comment.id = 999
            mock_cm_pr.create_issue_comment.return_value = mock_cm_comment
            mock_repo.get_pull.return_value = mock_cm_pr
            MockGH.return_value.get_repo.return_value = mock_repo

            result = await pipeline._create_pr(
                _make_finding(), _make_plan(),
                _make_execution(), _make_verification(),
            )

            assert result is not None
            assert result.number == 42

    @pytest.mark.asyncio
    async def test_create_pr_handles_error_gracefully(self):
        """Pipeline._create_pr catches errors and returns None."""
        from codecustodian.config.schema import CodeCustodianConfig

        config = CodeCustodianConfig()
        pipeline = _make_pipeline(config, github_token="fake-token")

        with patch(
            "codecustodian.executor.git_manager.Repo",
            side_effect=Exception("git error"),
        ):
            result = await pipeline._create_pr(
                _make_finding(), _make_plan(),
                _make_execution(), _make_verification(),
            )

            assert result is None
            assert any("pr_creation" in e for e in pipeline._result.errors)


# ── __init__.py Export Tests ───────────────────────────────────────────────


class TestGitHubIntegrationExports:
    def test_all_classes_exported(self):
        from codecustodian.integrations.github_integration import (
            CommentManager,
            IssueManager,
            PRInteractionHandler,
            PullRequestCreator,
        )

        assert CommentManager is not None
        assert IssueManager is not None
        assert PRInteractionHandler is not None
        assert PullRequestCreator is not None


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_pipeline(config, github_token=None):
    """Create a Pipeline instance with minimal setup."""
    from codecustodian.pipeline import Pipeline

    return Pipeline(
        config=config,
        repo_path="/fake/repo",
        github_token=github_token,
    )
