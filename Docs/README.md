# CodeCustodian Documentation

## Overview

CodeCustodian is an autonomous AI agent that detects, prioritizes, and fixes
technical debt in Python codebases. It operates as a CLI tool, GitHub Actions
workflow, and MCP server, using the GitHub Copilot SDK for AI-powered refactoring.

## Documentation Map

| Document | Description |
|----------|-------------|
| [Feature Architecture](FEATURE_ARCHITECTURE.md) | Detailed architecture for every subsystem, SDK integration flows, data models, Mermaid diagrams, deployment topology, and security layers |
| [Competitive Features](COMPETITIVE_FEATURES.md) | Feature inventory, competitive landscape (SonarQube, Dependabot, CodeRabbit, etc.), SDK usage details, and roadmap |
| [Tools & Usage](TOOLS_AND_USAGE.md) | Complete CLI reference, MCP tools / resources / prompts, configuration schema, Azure integration |
| [Deployment](DEPLOYMENT.md) | Installation, Docker, GitHub Actions, Azure Container Apps deployment guide |
| [Responsible AI](RESPONSIBLE_AI.md) | Human-in-the-loop, explainability, safety checks, privacy, and accountability |
| [Project Summary](PROJECT_SUMMARY.md) | 150-word elevator pitch |

### Requirements (planning documents)

| Document | Description |
|----------|-------------|
| [Business Requirements](Requirements/business-requirements.md) | Full BRD — stakeholders, market analysis, business requirements, go-to-market |
| [Features & Challenge Spec](Requirements/features-requirements-challenge-optimized.md) | Technical feature requirements organized by challenge scoring categories |
| [Implementation Plan](Requirements/implementation-plan.md) | Phased build plan (Phases 1–11) with task checklists and dependency graph |

### Root-level files

- [CONTRIBUTING.md](../CONTRIBUTING.md) — Development setup and contribution workflow
- [CHANGELOG.md](../CHANGELOG.md) — Version history (Phases 1–10)
- [SECURITY.md](../SECURITY.md) — Security policy and vulnerability disclosure
- [AGENTS.md](../AGENTS.md) — Custom instructions for GitHub Copilot

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

# MCP server
codecustodian-mcp
```

> **Full CLI reference:** See [TOOLS_AND_USAGE.md](TOOLS_AND_USAGE.md#cli-commands)
