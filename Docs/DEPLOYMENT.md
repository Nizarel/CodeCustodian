# Deployment Guide

## Local Development

```bash
# Clone
git clone https://github.com/nizarel/CodeCustodian.git
cd CodeCustodian

# Install with uv
uv sync --all-extras

# Or with pip
pip install -e ".[dev]"

# Run CLI
codecustodian --help

# Run MCP server
codecustodian-mcp
```

### CLI Commands

| Command | Description |
|---------|-------------|
| `codecustodian run` | Full pipeline (scan → plan → execute → verify → PR) |
| `codecustodian init` | Bootstrap `.codecustodian.yml` + GitHub Actions workflow |
| `codecustodian validate` | Validate configuration file |
| `codecustodian scan` | Run scanners (table/json/csv output) |
| `codecustodian findings` | List and filter findings |
| `codecustodian create-prs` | Create PRs for top-N findings |
| `codecustodian onboard` | Onboard a repository or organization |
| `codecustodian status` | Show findings + budget + SLA summary |
| `codecustodian report` | Generate ROI report (json/csv) |
| `codecustodian interactive` | InquirerPy-powered menu |
| `codecustodian version` | Print version |

### Running Tests

```bash
# Full suite
pytest

# With coverage
pytest --cov=codecustodian --cov-report=term-missing

# Integration only
pytest tests/integration/

# E2E only
pytest tests/e2e/
```

## GitHub Actions

CodeCustodian runs as a scheduled GitHub Actions workflow:

```yaml
# .github/workflows/codecustodian.yml
name: CodeCustodian
on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM UTC
  workflow_dispatch:
    inputs:
      scanners:
        description: 'Comma-separated scanners'
        default: 'all'
```

### Required Secrets

| Secret | Description |
|--------|-------------|
| `GITHUB_TOKEN` | Auto-provided by GitHub Actions |
| `COPILOT_TOKEN` | GitHub Copilot SDK token |

## Azure Container Apps

### Prerequisites

- Azure CLI installed
- Azure Container Registry (ACR)
- Azure Container Apps environment

### Deploy

```bash
# Build and push
az acr build --registry myregistry --image codecustodian:latest .

# Deploy
az containerapp create \
  --name codecustodian \
  --resource-group rg-codecustodian \
  --image myregistry.azurecr.io/codecustodian:latest \
  --environment my-env \
  --secrets github-token=<token> \
  --env-vars GITHUB_TOKEN=secretref:github-token
```

### CI/CD Pipeline

The `deploy-azure.yml` workflow automates deployment on tag push:

```bash
git tag v0.1.0
git push origin v0.1.0
```

## Docker

```bash
# Build
docker build -t codecustodian .

# Run
docker run --rm \
  -e GITHUB_TOKEN=ghp_xxx \
  -v $(pwd):/workspace \
  codecustodian run --path /workspace
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | Yes | GitHub API token |
| `COPILOT_TOKEN` | No | Copilot SDK token |
| `AZURE_DEVOPS_PAT` | No | Azure DevOps PAT |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | No | App Insights |
| `LOG_LEVEL` | No | Logging level (default: INFO) |
| `LOG_FORMAT` | No | `rich` or `json` (default: rich) |
