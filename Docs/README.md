# CodeCustodian Documentation

## Overview

CodeCustodian is an autonomous AI agent that detects, prioritizes, and fixes technical debt in Python codebases. It operates as a CLI tool, GitHub Actions workflow, and MCP server, using the GitHub Copilot SDK for AI-powered refactoring.

## Contents

- [Architecture](ARCHITECTURE.md) — System design, component map, and data flow
- [Tools & Usage](TOOLS_AND_USAGE.md) — Complete CLI, MCP tools, resources, prompts, and configuration reference
- [Responsible AI](RESPONSIBLE_AI.md) — Safety measures and ethical guidelines
- [Deployment](DEPLOYMENT.md) — Installation, Docker, GitHub Actions, Azure Container Apps
- [Business Value](BUSINESS_VALUE.md) — ROI analysis and competitive comparison
- [Requirements](Requirements/) — Feature requirements and challenge specs

Also see the root-level files:
- [CONTRIBUTING.md](../CONTRIBUTING.md) — Development setup and contribution workflow
- [CHANGELOG.md](../CHANGELOG.md) — Version history (Phases 1–10)
- [SECURITY.md](../SECURITY.md) — Security policy and vulnerability disclosure

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Initialize config
codecustodian init

# Scan a repository
codecustodian scan --repo-path .

# Full pipeline (dry-run)
codecustodian run --dry-run

# Show status (findings + budget + SLA)
codecustodian status

# Interactive menu
codecustodian interactive

# MCP server
codecustodian-mcp
```

## Architecture Summary

```
Scan → De-dup → Prioritize → Plan → Execute → Verify → PR → Feedback
```

Each stage runs in isolation with rollback capability. Findings are processed sequentially with error boundaries per finding. The feedback loop refines confidence and prioritization over time.

## CLI Commands

| Command | Description |
|---------|-------------|
| `run` | Full pipeline (scan → plan → execute → verify → PR) |
| `init` | Bootstrap config and GitHub Actions workflow |
| `validate` | Validate `.codecustodian.yml` |
| `scan` | Run scanners (table/json/csv output) |
| `findings` | Filter findings by type, severity, file, status |
| `create-prs` | Create PRs for top-N findings |
| `onboard` | Onboard repo or organization |
| `status` | Findings + budget + SLA summary |
| `report` | ROI report (json/csv) |
| `interactive` | InquirerPy-powered menu |
| `version` | Print version |
