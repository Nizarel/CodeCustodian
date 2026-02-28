# CodeCustodian — Tools & Usage Guide

**Version:** 0.10.0 | **Last Updated:** February 21, 2026

---

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [CLI Commands](#cli-commands)
4. [MCP Server](#mcp-server)
5. [MCP Tools Reference](#mcp-tools-reference)
6. [MCP Resources Reference](#mcp-resources-reference)
7. [MCP Prompts Reference](#mcp-prompts-reference)
8. [Configuration](#configuration)
9. [Azure Integration](#azure-integration)
10. [Work IQ Integration](#work-iq-integration)
11. [Troubleshooting](#troubleshooting)

---

## Overview

CodeCustodian is an autonomous AI agent for technical debt management. It scans codebases for deprecated APIs, TODO comments, code smells, security issues, and missing type annotations — then uses the GitHub Copilot SDK to plan safe refactorings, applies them atomically, verifies with tests and linting, and creates pull requests.

**Pipeline:**

```
Scan → De-dup → Prioritize → Plan → Execute → Verify → PR → Feedback
```

CodeCustodian operates in three modes:

- **CLI** — `codecustodian` command for local or CI/CD usage
- **MCP Server** — `codecustodian-mcp` for Copilot Chat, VS Code, Claude Desktop
- **GitHub Actions** — Automated scheduling via `.github/workflows/codecustodian.yml`

---

## Installation

### From source

```bash
git clone https://github.com/Nizarel/CodeCustodian.git
cd CodeCustodian
pip install -e ".[dev]"
```

### Verify

```bash
codecustodian version
# CodeCustodian v0.10.0
```

### Initialize a repository

```bash
cd your-project
codecustodian init
# Creates .codecustodian.yml with sensible defaults
```

---

## CLI Commands

### `codecustodian run` — Full Pipeline

Runs the complete scan → plan → execute → verify → PR pipeline.

```bash
codecustodian run \
  --repo-path . \
  --config .codecustodian.yml \
  --max-prs 5 \
  --dry-run \
  --output-format json
```

| Option | Default | Description |
|--------|---------|-------------|
| `--repo-path` | `.` | Path to repository root |
| `--config` | `.codecustodian.yml` | Configuration file path |
| `--max-prs` | `5` | Maximum PRs to create per run |
| `--scan-type` | `all` | Comma-separated scanner types |
| `--dry-run` | `false` | Scan and plan only, no execution |
| `--verbose` | `false` | Verbose logging |
| `--quiet` | `false` | Suppress non-critical output |
| `--debug` | `false` | Debug-level logging |
| `--log-file` | — | Write logs to file |
| `--enable-work-iq` | `false` | Enable Work IQ context |
| `--azure-devops-project` | — | Azure DevOps project |
| `--output-format` | `table` | Output: `table`, `json`, `csv` |

### `codecustodian scan` — Scan Only

```bash
codecustodian scan --repo-path . --scanner all --output-format json
```

| Option | Default | Description |
|--------|---------|-------------|
| `--repo-path` | `.` | Repository path |
| `--scanner` | `all` | Scanner: `deprecated_apis`, `todo_comments`, `code_smells`, `security_patterns`, `type_coverage`, or `all` |
| `--config` | `.codecustodian.yml` | Configuration file |
| `--output-format` | `table` | Output: `table`, `json`, `csv` |

### `codecustodian init` — Bootstrap Configuration

```bash
codecustodian init --template security_first
```

Templates: `security_first`, `deprecations_first`, `low_risk_maintenance`, `full_scan`

### `codecustodian config` — Manage Configuration

```bash
codecustodian config --show          # Full resolved config as JSON
codecustodian config --get behavior.max_prs_per_run   # Dot-notation lookup
codecustodian config --validate      # Validate .codecustodian.yml
```

### `codecustodian status` — Show Status

```bash
codecustodian status --repo-path .
```

Displays findings count, budget usage, SLA status, last run summary.

### `codecustodian findings` — List/Filter Findings

```bash
codecustodian findings --type security --severity critical --output-format json
```

### `codecustodian create-prs` — Create PRs for Top Findings

```bash
codecustodian create-prs --top 3 --dry-run
```

### `codecustodian report` — Generate ROI Report

```bash
codecustodian report --period monthly --format json --output roi-report.json
```

### `codecustodian validate` — Validate Config

```bash
codecustodian validate --path .codecustodian.yml
```

### `codecustodian onboard` — Onboard Repository

```bash
codecustodian onboard --repo-path . --template security_first
```

### `codecustodian interactive` — Interactive Menu

```bash
codecustodian interactive
```

InquirerPy-powered menu with options: Show high-priority findings, Create PRs, View ROI summary, Configure scanners, Scan history, Generate report.

### `codecustodian version` — Show Version

```bash
codecustodian version
```

### `codecustodian heal` — CI Self-Healing

Analyze CI failure logs and suggest or apply fixes automatically.

```bash
codecustodian heal \
  --log-file ci-output.log \
  --auto-fix \
  --create-pr
```

| Option | Default | Description |
|--------|---------|-------------|
| `--log-file` | — | Path to CI log file |
| `--auto-fix` | `false` | Apply suggested fixes automatically |
| `--create-pr` | `false` | Create a PR with the fix |

### `codecustodian review-pr` — PR Review Bot

Run automated review on a pull request with severity gating and labels.

```bash
codecustodian review-pr \
  --pr-number 42 \
  --severity-gate high \
  --add-labels
```

| Option | Default | Description |
|--------|---------|-------------|
| `--pr-number` | — | PR number to review |
| `--severity-gate` | `high` | Block PR if findings at or above this severity |
| `--add-labels` | `false` | Add severity labels to the PR |

---

## MCP Server

### Starting the Server

**Stdio (local — VS Code / Claude Desktop):**

```bash
codecustodian-mcp
```

**Streamable HTTP (remote — Azure Container Apps):**

```bash
codecustodian-mcp --transport streamable-http --host 0.0.0.0 --port 8000
```

### Client Configuration (`mcp.json`)

```json
{
  "mcpServers": {
    "codecustodian": {
      "command": "codecustodian-mcp",
      "args": []
    },
    "work-iq": {
      "command": "npx",
      "args": ["-y", "@microsoft/workiq", "mcp"]
    }
  }
}
```

### Remote Client (Azure Container Apps)

```json
{
  "mcpServers": {
    "codecustodian": {
      "url": "https://codecustodian-prod-app.greenforest-c49f3fb9.eastus2.azurecontainerapps.io/mcp"
    }
  }
}
```

### Health Endpoint

```bash
curl https://your-fqdn/health
# {"status": "ok", "version": "0.10.0"}
```

---

## MCP Tools Reference

### 1. `scan_repository`

Scan a repository for technical debt issues.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `repo_path` | `string` | `"."` | Repository root path |
| `scanners` | `string` | `"all"` | Comma-separated scanners or `"all"` |
| `config_path` | `string` | `".codecustodian.yml"` | Config file path |

**Returns:** `{ total, findings[], summary: { by_type, by_severity } }`

Findings are cached for downstream tools. First 50 returned; full set cached server-side. Progress reported via MCP notifications.

---

### 2. `list_scanners`

List available scanners with marketplace metadata.

**Parameters:** None

**Returns:** Array of `{ name, description, detects, enabled }`

**Scanners:**

| Name | Detects |
|------|---------|
| `deprecated_apis` | Deprecated library function calls |
| `todo_comments` | Aging TODO-style comments |
| `code_smells` | Complexity and maintainability issues |
| `security_patterns` | Security vulnerabilities (Bandit + custom) |
| `type_coverage` | Functions missing type annotations |
| `dependency_upgrades` | Outdated or unpinned dependencies |

---

### 3. `plan_refactoring`

Generate an AI-powered refactoring plan using the GitHub Copilot SDK.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `finding_id` | `string` | Yes | Finding ID from `scan_repository` |
| `repo_path` | `string` | No | Repository root (default `"."`) |

**Returns:** `RefactoringPlan` with: `id`, `finding_id`, `summary`, `changes[]`, `confidence_score` (1–10), `risk_level`, `ai_reasoning`, `alternatives[]`

**Notes:** Requires prior `scan_repository` call. Uses Copilot SDK multi-turn reasoning with ±10 lines of code context. Plans cached for `apply_refactoring`.

---

### 4. `apply_refactoring`

Apply a cached refactoring plan. **Destructive** — creates file backups.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `plan_id` | `string` | Yes | Plan ID from `plan_refactoring` |
| `repo_path` | `string` | No | Repository root (default `"."`) |

**Returns:** `{ plan_id, success, changed_files[] }`

**Safety:** Atomic operations with backup/rollback. 6-point safety check (path traversal, file size, binary detection, syntax validation, encoding, symlink).

---

### 5. `verify_changes`

Run tests and linters on changed files.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `changed_files` | `string[]` | Yes | Modified file paths |
| `repo_path` | `string` | No | Repository root (default `"."`) |

**Returns:** `{ passed, stages: { tests: { passed, tests_run, coverage }, lint: { passed, violations } } }`

---

### 6. `create_pull_request`

Create a GitHub pull request for a completed refactoring.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `finding_id` | `string` | Yes | Finding ID |
| `plan_id` | `string` | Yes | Plan ID |
| `repo_path` | `string` | No | Repository root (default `"."`) |

**Returns:** `{ number, url, title, branch, draft, labels[], reviewers[] }`

**Requires:** `GITHUB_TOKEN` environment variable.

---

### 7. `calculate_roi`

Calculate return-on-investment metrics for fixing a finding.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `finding_id` | `string` | Yes | Finding ID |

**Returns:** `{ finding_id, estimated_manual_hours, cost_of_inaction_usd, automated_fix_cost_usd, roi_percentage, risk_reduction }`

**Model:** Severity → hours (critical=8h, high=4h, medium=2h, low=1h). Type multiplier (security=3×, deprecated_api=1.5×). Developer rate: $75/hr. Automated cost: $0.50.

---

### 8. `get_business_impact`

5-factor business impact analysis.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `finding_id` | `string` | Yes | Finding ID |
| `repo_path` | `string` | No | Repository root (default `"."`) |

**Returns:** `{ finding_id, total_score, factors: { usage_frequency, criticality, change_frequency, velocity_impact, regulatory_risk }, business_impact_level, sla_risk, recommendation }`

**Levels:** >500 = critical, >200 = high, >100 = medium, else low.

---

## MCP Resources Reference

| URI | Description |
|-----|-------------|
| `codecustodian://config` | Default configuration as YAML |
| `codecustodian://version` | Current version string |
| `codecustodian://scanners` | Available scanners list |
| `config://settings` | Active configuration as JSON |
| `findings://{repo_name}/all` | All cached findings for a repository |
| `findings://{repo_name}/{type}` | Findings filtered by type |
| `dashboard://{team_name}/summary` | Dashboard: counts by severity/type + plans |

---

## MCP Prompts Reference

| Prompt | Parameters | Purpose |
|--------|------------|---------|
| `refactor_finding` | `finding_type`, `file_path`, `line`, `description` | Analyze and fix a specific finding |
| `scan_summary` | `total_findings`, `repo_name` | Prioritize scan results |
| `roi_report` | `team_name`, `period` | Generate ROI report template |
| `onboard_repo` | `repo_url`, `language` | Onboard a new repository |

---

## Configuration

### Minimal

```yaml
version: "1.0"
```

### Full Schema

```yaml
version: "1.0"

scanners:
  deprecated_apis:
    enabled: true
    severity: high
    libraries: [pandas, numpy, requests, django, flask]
  todo_comments:
    enabled: true
    severity: medium
    max_age_days: 90
  code_smells:
    enabled: true
    max_complexity: 10
    max_function_lines: 50
  security_patterns:
    enabled: true
    severity: critical
  type_coverage:
    enabled: true
    min_coverage_percent: 80

behavior:
  max_prs_per_run: 5
  confidence_threshold: 7
  proposal_mode_threshold: 5
  max_files_per_pr: 5
  max_lines_per_pr: 500

budget:
  monthly_budget: 500.0
  hard_limit: true

approval:
  require_plan_approval: false
  require_pr_approval: true

sla:
  enabled: true

learning:
  enabled: true
  target_success_rate: 0.9

business_impact:
  usage_weight: 100
  criticality_weight: 50
  change_frequency_weight: 30
  velocity_impact_weight: 40
  regulatory_risk_weight: 80

azure:
  keyvault_name: ""
  monitor_connection_string: ""
  devops_org_url: ""

work_iq:
  enabled: false

advanced:
  copilot:
    model_selection: auto
    max_tokens: 4096
    timeout: 30
```

### Confidence Thresholds

- **≥ 7** → Auto-execute, verify, create PR
- **5–6** → Create advisory proposal (no code changes)
- **< 5** → Skip

---

## Azure Integration

### Deployed Resources (eastus2)

| Resource | Name |
|----------|------|
| Container App | `codecustodian-prod-app` |
| Container Registry | `codecustodianprodacr` |
| Key Vault | `codecustodian-prod-kv` |
| Log Analytics | `codecustodian-prod-law` |
| App Insights | `codecustodian-prod-ai` |
| VNet | `codecustodian-prod-vnet` |
| Managed Identity | `codecustodian-prod-id` |
| Dashboard | `codecustodian-prod-dashboard` |
| Alert Rules | 4 (severity spike, budget, failure rate, PR success) |

**Live FQDN:** `https://codecustodian-prod-app.greenforest-c49f3fb9.eastus2.azurecontainerapps.io`

### CI/CD

The GitHub Actions workflow `.github/workflows/deploy-azure.yml` builds a Docker image, pushes to ACR, and deploys to Container Apps on every push to `master`.

### Azure DevOps

```yaml
azure:
  devops_org_url: "https://dev.azure.com/myorg"
  devops_project: "MyProject"
```

Creates work items for findings with severity-to-priority mapping.

### Azure Monitor Metrics

- `findings.total` — Total findings per scan
- `pr.success_rate` — PR merge success rate
- `roi.savings` — Cost savings (USD)
- `pipeline.duration_ms` — Pipeline execution time

---

## Work IQ Integration

Microsoft Work IQ provides organizational context for intelligent PR timing and reviewer assignment.

### Enable

```yaml
work_iq:
  enabled: true
```

### MCP Configuration

```json
{
  "mcpServers": {
    "work-iq": {
      "command": "npx",
      "args": ["-y", "@microsoft/workiq", "mcp"]
    }
  }
}
```

### Capabilities

| Feature | Description |
|---------|-------------|
| Expert lookup | Best reviewer based on file history and expertise |
| Sprint awareness | Defers PRs during sprint end or code freeze |
| Capacity planning | Skips PRs when team capacity > 90% |
| Org context | Related docs, Teams discussions, meetings |
| Effort estimation | Trivial / small / medium / large per finding type |
| Priority sorting | Severity + type-based intelligent ordering |

### Decision Logic (`should_create_pr_now`)

| Condition | Action |
|-----------|--------|
| Code freeze active | Defer (unless critical security) |
| Sprint ends in < 3 days + low priority | Defer |
| Active incidents + low priority | Defer |
| Team capacity > 90% | Defer |
| All clear | Create PR |

### Graceful Fallback

If the Work IQ MCP server is unavailable, all methods return safe defaults:
- Expert lookup → empty result
- Sprint context → no freeze, 0 days remaining
- PR decision → `True` (proceed with PR)
- Org context → empty lists

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No Copilot token" | Set `GITHUB_TOKEN` or `GITHUB_COPILOT_TOKEN` env var |
| "Work IQ timed out" | Ensure `npx` is available; falls back gracefully |
| "ACR image not found" | `az acr build --registry codecustodianprodacr --image codecustodian:latest .` |
| Import errors | `pip install -e ".[dev]"` |
| MCP connection refused | Check `codecustodian-mcp` is running; verify port/URL |
| Budget exceeded | Increase `budget.monthly_budget` or set `hard_limit: false` |

### Log Levels

```bash
codecustodian run --verbose    # INFO
codecustodian run --debug      # DEBUG
codecustodian run --log-file output.log
```

### Running Tests

```bash
# All tests (excluding live Azure)
pytest -m "not azure_e2e"

# Post-deployment e2e tests
pytest tests/e2e/test_azure_deployment.py -v -m azure_e2e

# With coverage
pytest --cov=codecustodian --cov-report=term-missing
```
