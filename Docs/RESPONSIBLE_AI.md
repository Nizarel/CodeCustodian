# Responsible AI

## Overview

CodeCustodian applies Responsible AI principles to autonomous refactoring in enterprise
repositories. The system is built to keep humans in control, make decisions explainable,
protect privacy, enforce safety checks, and provide clear accountability for every change.

## 1) Human-in-the-Loop

- CodeCustodian never merges changes directly.
- Every code modification is proposed through pull requests and requires human approval.
- Policy-driven approval workflows can require additional approvers for sensitive repos,
	high-risk findings, or critical-path files.
- Low-confidence plans are downgraded to proposal mode instead of automatic execution.

## 2) Explainability

- Each pull request includes AI reasoning for why a change is recommended.
- Confidence factors (test coverage, complexity, call sites, logic risk, multi-file scope)
	are exposed to reviewers.
- Alternative approaches can be generated for complex findings to support informed choice.
- Verification outcomes (tests, linting, security checks) are attached for transparent review.

## 3) Confidence Scoring

- Confidence is scored from 1 to 10.
- Action policy:
	- **8–10**: standard PR flow
	- **5–7**: draft PR with additional reviewer scrutiny
	- **<5**: proposal-only mode (advisory issue, no direct execution)
- Thresholds are configurable per repository and can be auto-adjusted from historical feedback.

## 4) Fairness

- Reviewer and assignment recommendations prioritize expertise and current capacity,
	not organizational seniority.
- Work IQ context (team expertise, sprint load, incidents, dependency state) is used to
	route changes to the right engineers at the right time.
- The platform minimizes reviewer overload by controlling PR sizing and creation rate.

## 5) Privacy

- Secrets are managed in Azure Key Vault and accessed via managed identity.
- Structured logs redact tokens, API keys, bearer credentials, and connection-string secrets.
- Tokens are scoped to least privilege and rotated regularly.
- Source code is processed only for the refactoring workflow and is not retained beyond
	configured local storage, logs, and audit requirements.

## 6) Safety

- Multi-stage safety controls apply before, during, and after code execution.
- Pre-execution checks include syntax validation, import availability, critical path
	protection, concurrent change detection, dangerous function blocking (`eval`, `exec`,
	`compile`, `__import__`), and secret detection.
- File operations are atomic and rollback-safe.
- Path traversal and symlink edits are blocked to keep modifications within repository scope.
- Post-execution verification includes tests, linting, and security scans.

## 7) Accountability

- Every operation is recorded in structured audit logs.
- Audit entries include SHA-256 hashes for tamper-evident traceability.
- Audit records capture actor, target files, change statistics, verification status,
	and PR linkage metadata.
- Commits and PRs include co-author traceability for AI-assisted changes.

## 8) Proposal Mode and Continuous Improvement

- Proposal mode ensures the system defers to humans for uncertain or high-risk situations.
- Reviewer feedback is captured to improve planner behavior and confidence calibration.
- Historical outcomes are used to refine prompts, thresholds, and prioritization over time.
- This closed-loop design supports safe continuous improvement without removing human control.
