# Responsible AI

## Overview

CodeCustodian is designed with safety-first principles. All automated code changes go through multiple validation gates before being proposed as pull requests.

## Safety Measures

### 1. Human-in-the-Loop

CodeCustodian never merges code directly. All changes are proposed as pull requests requiring human review and approval.

### 2. Confidence Gating

Every refactoring plan receives a confidence score (1-10). Plans below the configured threshold (default: 7) are converted to issues instead of PRs.

### 3. Pre-Execution Safety Checks

5-point validation before any code modification:
1. File exists and is writable
2. No uncommitted changes in target file
3. Syntax validation of proposed changes
4. Change scope within acceptable limits
5. No protected files modified

### 4. Atomic Operations

All file modifications use atomic writes (temp file → rename) with automatic backup. On any failure, the original file is restored.

### 5. Post-Execution Verification

After applying changes:
- Full test suite execution
- Lint/type checking (ruff + mypy)
- Security scanning (Bandit)
- Automatic rollback if any check fails

### 6. Scope Limitations

- Maximum files per PR (configurable, default: 10)
- Protected file detection (CI configs, build files)
- Signature change detection
- Risk level assessment (low/medium/high)

## Transparency

- Every PR includes AI reasoning and confidence scores
- Alternative approaches are listed for review
- Audit logs record all operations
- Feedback loops capture reviewer decisions for improvement

## Data Handling

- No source code is stored permanently
- Scan results are cached locally only
- GitHub tokens use minimal required scopes
- Azure Key Vault for secret management in production

## Bias Mitigation

- Scanners use deterministic rules, not ML-based pattern matching
- Confidence scoring is formula-based with documented factors
- Feedback loops enable correction over time
