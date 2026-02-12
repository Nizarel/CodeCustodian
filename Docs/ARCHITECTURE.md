# Architecture

## System Overview

CodeCustodian follows a linear pipeline architecture:

```
┌──────────┐   ┌─────────┐   ┌────────────┐   ┌────────┐   ┌─────────┐   ┌──────────┐   ┌──────┐   ┌──────────┐
│  Scanner │──▶│ De-dup  │──▶│ Prioritize │──▶│ Planner│──▶│Executor │──▶│ Verifier │──▶│  PR  │──▶│ Feedback │
└──────────┘   └─────────┘   └────────────┘   └────────┘   └─────────┘   └──────────┘   └──────┘   └──────────┘
```

## Components

### Scanner (`src/codecustodian/scanner/`)

Plugin-based scanner system with a registry pattern:

- **BaseScanner** — Abstract base class for all scanners
- **ScannerRegistry** — Dynamic scanner registration and discovery
- **Built-in scanners:**
  - `deprecated_api` — AST-based deprecated API detection
  - `todo_comments` — TODO/FIXME tracking with age
  - `code_smells` — Complexity analysis (cyclomatic, nesting)
  - `security` — Bandit wrapper for vulnerability scanning
  - `type_coverage` — Missing type annotation detection

### Planner (`src/codecustodian/planner/`)

AI-powered refactoring planning using GitHub Copilot SDK:

- **CopilotPlannerClient** — SDK wrapper with model routing
- **Tools** — `@define_tool` functions for code inspection
- **Prompts** — System/user prompt templates
- **Confidence** — 1-10 confidence scoring
- **Alternatives** — Multi-approach solution generation

### Executor (`src/codecustodian/executor/`)

Safe code modification with atomic operations:

- **SafeFileEditor** — Atomic file writes (temp → rename)
- **BackupManager** — Timestamped backup/restore
- **SafetyChecks** — 5-point pre-execution validation
- **GitManager** — Branch creation, commits, push

### Verifier (`src/codecustodian/verifier/`)

Post-execution validation:

- **TestRunner** — pytest execution with coverage
- **LinterRunner** — ruff + mypy checking
- **SecurityVerifier** — Bandit + Trivy scanning

### Integrations (`src/codecustodian/integrations/`)

- **GitHub** — PR creation, comments, issues
- **Azure DevOps** — Work items, board integration
- **Azure Monitor** — Telemetry and observability

### MCP Server (`src/codecustodian/mcp/`)

Model Context Protocol server for AI assistant integration:

- **Tools** — `scan_repository`, `validate_config`, `list_scanners`
- **Resources** — Config, version, scanner list
- **Prompts** — Finding analysis, prioritization, plan review

## Data Flow

1. **Finding** — Detected issue with file, line, severity, type
2. **RefactoringPlan** — AI-generated fix with changes, confidence, risk
3. **ExecutionResult** — Applied changes with backup paths
4. **VerificationResult** — Test/lint/security results
5. **PullRequestInfo** — Created PR with number, URL, branch

## Configuration

Hierarchical configuration resolution:
```
Organization → Team → Repository → CLI flags
```

Config file: `.codecustodian.yml`
