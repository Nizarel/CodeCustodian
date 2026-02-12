# CodeCustodian Documentation

## Overview

CodeCustodian is an autonomous AI agent that detects, prioritizes, and fixes technical debt in Python codebases. It operates as a GitHub Actions workflow and MCP server, using the GitHub Copilot SDK for AI-powered refactoring.

## Contents

- [Architecture](ARCHITECTURE.md) — System design and component overview
- [Responsible AI](RESPONSIBLE_AI.md) — Safety measures and ethical guidelines
- [Deployment](DEPLOYMENT.md) — Installation and deployment guide
- [Business Value](BUSINESS_VALUE.md) — ROI and business impact analysis

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Initialize config
codecustodian init

# Scan a repository
codecustodian scan --path .

# Full pipeline
codecustodian run --path .

# MCP server
codecustodian-mcp
```

## Architecture Summary

```
Scan → De-dup → Prioritize → Plan → Execute → Verify → PR → Feedback
```

Each stage runs in isolation with rollback capability. Findings are processed sequentially with error boundaries per finding.
