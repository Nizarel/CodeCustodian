"""CodeCustodian — Autonomous AI agent for technical debt management.

Powered by GitHub Copilot SDK and FastMCP.
"""

__version__ = "0.15.1"
__author__ = "Nizarel"
__app_name__ = "codecustodian"

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

__all__ = [
    "ApprovalRequiredError",
    "AzureIntegrationError",
    "BudgetExceededError",
    "CodeCustodianError",
    "ExecutorError",
    "GitHubAPIError",
    "PlannerError",
    "ScannerError",
    "VerifierError",
    "__version__",
]
