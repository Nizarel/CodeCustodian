# Contributing to CodeCustodian

Thank you for your interest in contributing! This guide covers setup, conventions,
and the contribution workflow.

## Development Setup

```bash
# 1. Fork and clone
git clone https://github.com/YOUR_USERNAME/CodeCustodian.git
cd CodeCustodian

# 2. Create virtual environment (requires Python 3.11+)
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

# 3. Install with dev dependencies
pip install -e ".[dev]"

# 4. Verify everything works
pytest
```

## Code Conventions

- **Python 3.11+** with full type annotations
- **Pydantic v2** models for all data structures
- **async/await** for I/O-bound operations
- **Line length:** 100 characters (enforced by ruff)
- **Docstrings:** Google style
- **Imports:** Use `from __future__ import annotations` in every module

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | When to use |
|--------|-------------|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `refactor:` | Code restructuring without behavior change |
| `docs:` | Documentation only |
| `test:` | Adding or updating tests |
| `chore:` | Build config, CI, dependencies |

Example: `feat: add Java scanner plugin support`

## Testing

```bash
# Run full suite
pytest

# Run with coverage
pytest --cov=codecustodian --cov-report=term-missing

# Run specific test file
pytest tests/test_pipeline.py -q

# Run only integration tests
pytest tests/integration/ -q

# Run only e2e tests
pytest tests/e2e/ -q
```

**Requirements:**
- Target 80%+ overall coverage (enforced in CI)
- Add tests for every new feature or bug fix
- Test files go in `tests/` (unit), `tests/integration/`, or `tests/e2e/`
- Use fixtures from `tests/fixtures/` when testing against sample repos

## Linting

```bash
# Ruff (lint + format)
ruff check .
ruff format .

# Type checking
mypy src/

# Security scanning
bandit -r src/ -c pyproject.toml
```

## Project Structure

```
src/codecustodian/
├── cli/            # Typer CLI commands
├── config/         # Configuration schema and defaults
├── enterprise/     # Budget, SLA, ROI, RBAC, audit
├── executor/       # Safe file editing, git, backups
├── feedback/       # Learning from PR outcomes
├── integrations/   # GitHub, Azure DevOps, Azure Monitor
├── intelligence/   # Business impact scoring, reprioritization
├── mcp/            # FastMCP server (tools, resources, prompts)
├── onboarding/     # Repo/org onboarding and policy templates
├── planner/        # GitHub Copilot SDK AI planner
├── scanner/        # Scanner registry and built-in scanners
├── verifier/       # Test runner, linter, security verification
├── models.py       # Pydantic domain models
├── pipeline.py     # Pipeline orchestrator
├── logging.py      # Structured logging with secret masking
└── exceptions.py   # Exception hierarchy
```

## Contribution Workflow

1. Create a feature branch from `master`
2. Make changes with tests
3. Run `pytest` and `ruff check .` locally
4. Commit using conventional commit format
5. Push and open a pull request
6. Address review feedback

## Adding a Custom Scanner

1. Create a class that extends `BaseScanner` from `scanner.base`
2. Implement the `scan(repo_path: str) -> list[Finding]` method
3. Register in `ScannerRegistry` or via config `module` field
4. Add tests in `tests/test_scanners.py`

## Reporting Issues

- Use GitHub Issues with a clear title and reproduction steps
- For security issues, follow the process in [SECURITY.md](SECURITY.md)
