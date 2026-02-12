"""Tests for the custom exception hierarchy."""

from __future__ import annotations

import pytest

from codecustodian.exceptions import (
    ApprovalRequiredError,
    AzureIntegrationError,
    BudgetExceededError,
    CodeCustodianError,
    ExecutorError,
    GitHubAPIError,
    PlannerError,
    ScannerError,
    VerifierError,
)


class TestExceptionHierarchy:
    def test_base_exception_message(self):
        exc = CodeCustodianError("something broke")
        assert str(exc) == "something broke"
        assert exc.message == "something broke"
        assert exc.details == {}

    def test_base_exception_details(self):
        exc = CodeCustodianError("fail", details={"key": "value"})
        assert exc.details["key"] == "value"

    def test_all_subclasses_inherit_base(self):
        for cls in (
            ScannerError,
            PlannerError,
            ExecutorError,
            VerifierError,
            GitHubAPIError,
            AzureIntegrationError,
            BudgetExceededError,
            ApprovalRequiredError,
        ):
            exc = cls("test")
            assert isinstance(exc, CodeCustodianError)
            assert isinstance(exc, Exception)

    def test_can_catch_with_base_class(self):
        with pytest.raises(CodeCustodianError):
            raise ScannerError("scanner broke")


class TestGitHubAPIError:
    def test_status_code(self):
        exc = GitHubAPIError("rate limited", status_code=429)
        assert exc.status_code == 429
        assert exc.response_body == ""

    def test_response_body(self):
        exc = GitHubAPIError(
            "not found",
            status_code=404,
            response_body='{"message": "Not Found"}',
        )
        assert "Not Found" in exc.response_body


class TestBudgetExceededError:
    def test_cost_fields(self):
        exc = BudgetExceededError(
            "over budget",
            current_cost=475.50,
            budget_limit=500.0,
        )
        assert exc.current_cost == 475.50
        assert exc.budget_limit == 500.0


class TestApprovalRequiredError:
    def test_resource_and_type(self):
        exc = ApprovalRequiredError(
            "needs approval",
            resource_id="plan-abc",
            approval_type="plan",
        )
        assert exc.resource_id == "plan-abc"
        assert exc.approval_type == "plan"
