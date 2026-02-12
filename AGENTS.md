# CodeCustodian — Custom Instructions for GitHub Copilot

## Project Overview

CodeCustodian is an autonomous AI agent for technical debt management. It scans
codebases for deprecated APIs, TODO comments, code smells, and security issues,
then uses the GitHub Copilot SDK to plan safe refactorings, applies them
atomically, verifies with tests + linting, and creates pull requests.

## Architecture

- **Pipeline:** Scan → De-dup → Prioritize → Plan → Execute → Verify → PR
- **AI Engine:** GitHub Copilot SDK (`github-copilot-sdk`)
- **MCP Server:** FastMCP v2 for Model Context Protocol
- **Integrations:** GitHub (PyGithub), Azure DevOps, Azure Monitor, Work IQ MCP

## Code Style

- Python 3.11+ with full type annotations
- Pydantic v2 models for all data structures
- `async/await` for I/O-bound operations
- Conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`
- Line length: 100 characters (ruff)
- Docstrings: Google style

## Key Conventions

- All configuration via `.codecustodian.yml` with Pydantic validation
- Structured logging through `codecustodian.logging.get_logger()`
- Scanners implement `BaseScanner` ABC from `scanner.base`
- File edits are atomic with backup/rollback
- Every refactoring needs a confidence score 1–10

## Testing

- pytest with `pytest-asyncio`
- Target: 80%+ coverage
- Test files: `tests/unit/`, `tests/integration/`, `tests/e2e/`
- Fixtures in `tests/fixtures/`

## Dependencies

See `pyproject.toml` for the full list. Key ones:
- `github-copilot-sdk` — AI planner
- `fastmcp>=2.14.0,<3` — MCP server
- `PyGithub` — GitHub API
- `pydantic>=2.5` — Data validation
- `typer` + `rich` — CLI
