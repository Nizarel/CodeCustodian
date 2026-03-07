# CodeCustodian — Custom Instructions for GitHub Copilot

## Project Overview

CodeCustodian is an autonomous AI agent for technical debt management. It scans
Python codebases for deprecated APIs, TODO comments, code smells, security issues,
type coverage gaps, architectural drift, and dependency staleness, then uses the
GitHub Copilot SDK to plan safe refactorings, applies them atomically, verifies
with tests + linting, and creates pull requests — keeping humans in control.

**Version:** 0.15.2 · **Tests:** 949 · **Coverage:** 82%+

## Project Structure

```
src/codecustodian/
├── cli/            # Typer CLI — 15 commands (scan, run, report, heal, …)
├── config/         # Pydantic v2 config loader (.codecustodian.yml)
├── scanner/        # 7 built-in scanners implementing BaseScanner ABC
├── planner/        # GitHub Copilot SDK integration (12 agent profiles)
├── executor/       # Atomic file edits with backup/rollback
├── verifier/       # pytest + ruff + bandit verification
├── mcp/            # FastMCP v2 server (17 tools, 7 prompts, 8 resources)
├── enterprise/     # Budget, SLA, ROI, RBAC, approval workflows
├── intelligence/   # Debt forecasting, reachability, PyPI intelligence
├── feedback/       # Learning from PR outcomes
├── integrations/   # GitHub (PyGithub), Azure DevOps, Teams ChatOps
├── onboarding/     # Repository onboarding wizard
├── models.py       # Shared Pydantic models (Finding, Plan, RefactorResult, …)
├── pipeline.py     # Orchestrator: scan → dedup → prioritize → plan → execute → verify → PR
├── logging.py      # Structured JSON logging with secret masking
└── exceptions.py   # Custom exception hierarchy
tests/
├── unit/           # Fast isolated tests
├── integration/    # Cross-module tests
├── e2e/            # End-to-end (local + Azure deployment)
├── fixtures/       # Shared test data
└── conftest.py     # Shared fixtures and markers
infra/              # Azure Bicep IaC (Container Apps, Key Vault, Monitor)
.github/workflows/  # 6 CI/CD workflows
```

## Architecture

- **Pipeline:** Scan → De-dup → Prioritize → Plan → Execute → Verify → PR
- **AI Engine:** GitHub Copilot SDK with 12 agent profiles and 8 domain skills
- **MCP Server:** FastMCP v2 — `type: http` at Azure Container Apps, `type: stdio` locally
- **Integrations:** GitHub (PyGithub), Azure DevOps, Azure Monitor, Teams ChatOps, Work IQ MCP

## Code Style

- Python 3.11+ with full type annotations — the Copilot SDK and Pydantic v2 both
  rely on runtime type information, so annotations are required, not optional.
- Pydantic v2 models for all data structures — use `model_validator` not `@validator`
  (the v1 API is removed).
- `async/await` for I/O-bound operations — the MCP server and GitHub API calls are
  async; keep the event loop clean by never calling `requests.get` inside an `async def`.
- Line length: 100 characters (enforced by ruff).
- Docstrings: Google style — ruff rule D417 checks parameter documentation.
- Conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`

### Preferred patterns

```python
# ✅ Import from the public package API
from codecustodian.models import Finding, Plan

# ❌ Don't reach into private modules
from codecustodian.scanner.deprecated_api import _internal_helper

# ✅ Use structured logging (auto-masks secrets, outputs JSON in prod)
from codecustodian.logging import get_logger
logger = get_logger(__name__)
logger.info("scan_complete", findings=len(results), repo=repo_path)

# ❌ Don't use print() or plain logging.getLogger()
print(f"Found {len(results)} findings")

# ✅ New scanners inherit from BaseScanner
from codecustodian.scanner.base import BaseScanner

class MyScanner(BaseScanner):
    name = "my_scanner"
    def scan(self, repo_path: str, config: dict) -> list[Finding]:
        ...

# ❌ Don't create standalone scan functions outside the scanner framework
```

## Key Conventions

- All configuration lives in `.codecustodian.yml`, validated by Pydantic in `config/`.
  Never read environment variables directly for user-facing config — use the config loader.
- File edits are atomic with backup/rollback via `executor/`. Never write to files
  with plain `open()` during a refactoring — always go through the executor.
- Every refactoring carries a confidence score 1–10. The pipeline gates on this:
  8–10 → auto-PR, 5–7 → draft PR, <5 → proposal only.
- Scanners are registered in `scanner/__init__.py`. After adding a new scanner,
  add it to `SCANNER_REGISTRY` so the CLI and MCP server discover it.
- The 7-point safety system (`executor/safety.py`) runs before every file write:
  syntax, file_size, binary, path_traversal, encoding, secrets, blast_radius.

## MCP Server

The MCP server is the primary integration surface for VS Code Copilot Chat.

**17 Tools:** `scan_repository`, `list_scanners`, `plan_refactoring`,
`apply_refactoring`, `verify_changes`, `create_pull_request`, `calculate_roi`,
`get_business_impact`, `get_blast_radius`, `get_debt_forecast`,
`check_pypi_versions`, `get_reachability_analysis`, `synthesize_tests`,
`plan_migration`, `get_migration_status`, `send_teams_notification`,
`scan_remote_repository`

**7 Prompts:** `refactor_finding`, `scan_summary`, `roi_report`, `onboard_repo`,
`forecast_report`, `migration_assessment`, `test_coverage_gap`

**8 Resources:** `codecustodian://config`, `codecustodian://version`,
`findings://{repo}/all`, `findings://{repo}/{type}`, `config://settings`,
`dashboard://{team}/summary`, `codecustodian://scanners`,
`forecasting://{repo}/latest`

## Testing

- `pytest` with `pytest-asyncio` for async tests.
- Target: 80%+ coverage (currently 82%).
- Test layout: `tests/unit/`, `tests/integration/`, `tests/e2e/`.
- Shared fixtures in `tests/conftest.py` and `tests/fixtures/`.
- Use `@pytest.mark.asyncio` for async test functions.
- Azure e2e tests require `RUN_AZURE_E2E=1` environment variable.

## Azure Deployment

- **Azure Container Apps** at `codecustodian-dev-app.delightfuldesert-11a0292b.eastus2.azurecontainerapps.io`
- **Azure Key Vault** for secrets (GitHub token, Teams webhook URL)
- **Azure Monitor** with OpenTelemetry for observability
- **Bicep IaC** in `infra/` — `main.bicep` orchestrates all modules
- **6 GitHub Actions workflows** in `.github/workflows/`

## Dependencies

See `pyproject.toml`. Key ones:
- `github-copilot-sdk` — AI planner
- `fastmcp>=2.14.0,<3` — MCP server
- `PyGithub` — GitHub API
- `pydantic>=2.5` — data validation
- `typer` + `rich` — CLI
- `httpx` — async HTTP client
- `networkx` — dependency graph for migrations
