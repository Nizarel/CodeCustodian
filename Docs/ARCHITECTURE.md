# Architecture

## System Overview

CodeCustodian follows a linear pipeline architecture with feedback:

```
┌──────────┐   ┌─────────┐   ┌────────────┐   ┌────────┐   ┌─────────┐   ┌──────────┐   ┌──────┐   ┌──────────┐
│  Scanner │──▶│ De-dup  │──▶│ Prioritize │──▶│ Planner│──▶│Executor │──▶│ Verifier │──▶│  PR  │──▶│ Feedback │
└──────────┘   └─────────┘   └────────────┘   └────────┘   └─────────┘   └──────────┘   └──────┘   └──────────┘
      │                            ▲                                                                     │
      │                            │                                                                     │
      │                     ┌──────┴──────┐                                                              │
      └─────────────────────│ Intelligence │◀─────────────────────────────────────────────────────────────┘
                            └─────────────┘
```

## Components

### CLI (`src/codecustodian/cli/`)

Typer-powered command-line interface with Rich console output.

| Command | Description |
|---------|-------------|
| `run` | Full pipeline execution (scan → plan → execute → verify → PR) |
| `init` | Bootstrap `.codecustodian.yml` and GitHub Actions workflow |
| `validate` | Validate configuration file |
| `scan` | Run scanners without creating PRs |
| `onboard` | Onboard a repository or organization |
| `status` | Show findings, budget, and SLA summary |
| `report` | Generate ROI report (JSON or CSV) |
| `findings` | List and filter findings by type/severity/file |
| `create-prs` | Create PRs for top-N findings via pipeline |
| `interactive` | InquirerPy-powered menu for common workflows |

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
- **Confidence** — 1-10 confidence scoring with feedback-driven adjustment
- **Alternatives** — Multi-approach solution generation

### Executor (`src/codecustodian/executor/`)

Safe code modification with atomic operations:

- **SafeFileEditor** — Atomic file writes (temp → rename) with path-traversal and symlink guards
- **BackupManager** — Timestamped backup/restore with session management
- **SafetyChecks** — Multi-point pre-execution validation (syntax, imports, concurrent changes, dangerous functions, secrets, critical paths)
- **GitManager** — Branch creation, commits, push, stash/pop

### Verifier (`src/codecustodian/verifier/`)

Post-execution validation:

- **TestRunner** — pytest execution with coverage delta tracking
- **LinterRunner** — ruff + mypy + bandit checking with baseline comparison
- **SecurityVerifier** — Bandit + pip-audit + SARIF scanning

### Integrations (`src/codecustodian/integrations/`)

- **GitHub** — PR creation, comments, issues, interaction bot
- **Azure DevOps** — Work items, board integration
- **Azure Monitor** — Telemetry and observability via OpenTelemetry

### Enterprise (`src/codecustodian/enterprise/`)

Enterprise features for team and organizational use:

- **BudgetManager** — Per-team cost tracking, alerts, and enforcement
- **SLAReporter** — Run tracking, success/failure rates, trend analysis, alerts
- **ROICalculator** — Monthly ROI reports with CSV and JSON export
- **ApprovalWorkflows** — Policy-driven approval gates
- **MultiTenantManager** — Organization-level multi-repo management
- **RBACManager** — Role-based access control
- **NotificationEngine** — Slack, Teams, email, webhook notifications
- **SecretsManager** — Azure Key Vault integration
- **AuditLogger** — Append-only JSONL with SHA-256 tamper-evident hashes

### Intelligence (`src/codecustodian/intelligence/`)

Business intelligence and dynamic prioritization:

- **BusinessImpactScorer** — 5-factor scoring: usage frequency, criticality, change frequency, velocity impact, regulatory risk
- **DynamicReprioritizer** — Event-driven priority adjustments (production incidents, CVEs, deadlines, budget changes)

### Feedback (`src/codecustodian/feedback/`)

Learning from PR outcomes and team behavior:

- **FeedbackCollector** — TinyDB-backed PR outcome tracking (merged/rejected/modified), per-scanner success rates, auto-adjusted confidence thresholds
- **PreferenceStore** — Team and user coding preferences with prompt injection
- **HistoricalPatternRecognizer** — Cross-org refactoring lookup with similarity scoring

### Onboarding (`src/codecustodian/onboarding/`)

Repository and organization onboarding:

- **ProjectAnalyzer** — Analyzes repository structure and generates configuration
- **PolicyTemplates** — Pre-built templates: `security_first`, `deprecations_first`, `low_risk_maintenance`, `full_scan`
- **OnboardingManager** — Repo-level and org-level onboarding orchestration

### MCP Server (`src/codecustodian/mcp/`)

Model Context Protocol server for AI assistant integration (FastMCP v2):

- **Tools** — `scan_repository`, `validate_config`, `list_scanners`, `get_finding_details`, `plan_refactoring`, `get_business_impact`, `get_sla_report`, `get_roi_report`
- **Resources** — Config, version, scanner list, finding cache
- **Prompts** — Finding analysis, prioritization, plan review, scan summary

## Data Flow

1. **Finding** — Detected issue with file, line, severity, type, priority score
2. **RefactoringPlan** — AI-generated fix with changes, confidence, risk, reasoning
3. **ExecutionResult** — Applied changes with backup paths and git metadata
4. **VerificationResult** — Test/lint/security results with coverage delta
5. **PullRequestInfo** — Created PR with number, URL, branch, description
6. **FeedbackRecord** — PR outcome (merged/rejected/modified) for learning

## Configuration

Hierarchical configuration resolution:
```
Organization → Team → Repository → CLI flags
```

Config file: `.codecustodian.yml` with Pydantic v2 validation.

Sections: `scanners`, `behavior`, `github`, `budget`, `approval`, `sla`,
`learning`, `business_impact`, `work_iq`, `azure`, `notifications`, `advanced`.

## Testing

```
tests/
├── unit/           # (individual module tests at tests/ level)
├── integration/    # Pipeline integration tests
├── e2e/            # End-to-end CLI workflow tests
└── fixtures/       # Sample repository with known findings
```

- **609 tests**, 82.26% overall coverage
- `pytest` with `pytest-asyncio`, `pytest-cov`
- Coverage gate: 80% (enforced via `pyproject.toml`)
- Critical-path executor+verifier coverage: 90.20%
