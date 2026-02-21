"""CodeCustodian — Autonomous AI agent for technical debt management.

Powered by GitHub Copilot SDK and FastMCP.
"""

__version__ = "0.10.0"
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
    "__version__",
    "CodeCustodianError",
    "ScannerError",
    "PlannerError",
    "ExecutorError",
    "VerifierError",
    "GitHubAPIError",
    "AzureIntegrationError",
    "BudgetExceededError",
    "ApprovalRequiredError",
]
