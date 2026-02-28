# CodeCustodian — Competitive Features & SDK Integration Guide

**Version:** 2.0 | **Date:** February 27, 2026  
**Purpose:** Comprehensive feature inventory, competitive landscape analysis, and SDK integration mapping for every CodeCustodian capability — current and planned.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Competitive Landscape](#2-competitive-landscape)
3. [Feature Inventory — Current State](#3-feature-inventory--current-state)
4. [Feature Inventory — Planned Competitive Advantages](#4-feature-inventory--planned-competitive-advantages)
5. [SDK & Integration Map](#5-sdk--integration-map)
6. [Feature-by-Feature Competitive Comparison](#6-feature-by-feature-competitive-comparison)
7. [Priority Matrix & Roadmap](#7-priority-matrix--roadmap)

---

## 1. Executive Summary

CodeCustodian is an autonomous, AI-powered technical debt management platform. It runs inside CI/CD pipelines, scans codebases for six categories of maintainability issues, uses the **GitHub Copilot SDK** for multi-turn AI reasoning to plan safe refactorings, executes changes atomically with rollback guarantees, verifies every change through tests, linting, and security scans, and creates pull requests with full AI-generated explanations.

What sets CodeCustodian apart from every competitor in the market is the combination of **detection + AI planning + safe execution + verification + PR creation** in a single autonomous pipeline. No other tool covers the full lifecycle from finding an issue to delivering a reviewed pull request.

### Core Differentiators

| Capability | CodeCustodian | Nearest Competitor |
|---|---|---|
| **AI-powered refactoring plans** | GitHub Copilot SDK multi-turn sessions with tool calling | CodeRabbit (review only, no execution) |
| **Self-healing CI** | Parses failure logs, generates patch candidates, pushes fix commits | Nobody — first in market |
| **MCP server for IDE integration** | FastMCP v2 with stdio + Streamable HTTP transports | Nobody — none offers MCP |
| **Organizational context** | Work IQ MCP for expert routing, sprint-aware timing | Nobody — no competitor uses org context |
| **Enterprise governance** | RBAC, approval gates, budget caps, audit trails, SOC 2 logs | Byteable (partial), Moderne (partial) |
| **Feedback-driven learning** | PR outcomes feed back into confidence calibration | Nobody — competitors are stateless |

---

## 2. Competitive Landscape

### 2.1 Direct Competitors

#### SonarQube / SonarCloud

| Dimension | SonarQube | CodeCustodian |
|---|---|---|
| **What it does** | Static analysis across 30+ languages. Detects bugs, code smells, security hotspots. Tracks quality gates over time. | Static analysis + AI-powered planning + automated execution + verification + PR creation. |
| **Languages** | 30+ (Java, C#, JS/TS, Python, Go, etc.) | Python (full AST), JS/TS (deprecation rules), extensible via custom rules. |
| **Auto-fix** | No. Detects issues only. Engineers fix manually. | Yes. Copilot SDK generates a refactoring plan, executor applies it, verifier confirms, PR is created. |
| **AI integration** | SonarCloud added AI summaries in 2025, but no auto-fix. | Full Copilot SDK integration: multi-turn planning, tool calling, model routing, alternatives. |
| **Pricing** | Community (free), Developer ($150/yr), Enterprise ($20K+/yr). | Open-source core. Enterprise features included. Cost is GitHub Copilot license ($19/user/month). |
| **Where CodeCustodian wins** | Goes beyond detection to actually *fix* the issues. AI reasoning produces contextual fixes, not template patches. |

#### Dependabot / Renovate

| Dimension | Dependabot + Renovate | CodeCustodian |
|---|---|---|
| **What it does** | Bumps dependency versions in manifest files. Creates PRs with version number changes. | Bumps versions *and* rewrites code when APIs change. AI-powered migration using changelogs. |
| **Breaking changes** | Cannot handle. If a bump breaks the build, PR sits open. | Copilot SDK reads the changelog/migration guide and plans the code adaptation. |
| **Scope** | Dependencies only. | Dependencies + deprecated APIs + security + code smells + TODO tracking + type coverage. |
| **Where CodeCustodian wins** | Solves the hardest dependency problem: version bump + code migration in one PR. |

#### CodeRabbit

| Dimension | CodeRabbit | CodeCustodian |
|---|---|---|
| **What it does** | AI-powered PR reviewer. Posts inline comments on every PR with code suggestions. | AI-powered *author* and reviewer. Scans proactively, creates PRs, and reviews incoming PRs. |
| **Who triggers it** | Developers open a PR, CodeRabbit reviews it. Reactive. | CodeCustodian scans on schedule or CI trigger. Proactive. PR Review Bot also reviews incoming PRs. |
| **Fix application** | Suggestions only. Developer must apply manually. | Applies fixes atomically with backup/rollback. Verified before PR creation. |
| **Where CodeCustodian wins** | Proactive vs. reactive. Creates the PR, not just reviews it. Also has a PR review mode for incoming PRs. |

#### Moderne (OpenRewrite)

| Dimension | Moderne | CodeCustodian |
|---|---|---|
| **What it does** | Deterministic, rule-based code transformations ("recipes"). Excels at large-scale migrations (Spring Boot 2→3, Java 8→17). Supports Java, Kotlin, C#. | AI-powered transformations. Not limited to pre-written recipes — Copilot SDK reasons about novel refactoring scenarios. |
| **Customization** | Write custom OpenRewrite recipes in Java. Steep learning curve. | Custom rules in `.codecustodian.yml` YAML. No code needed. AI handles the rest. |
| **Multi-repo** | Moderne DX platform supports org-wide scanning across hundreds of repos. | Planned: `org-scan` CLI command with PyGithub integration (leverages existing MultiTenantManager). |
| **Where CodeCustodian wins** | AI flexibility beats hand-written recipes. Custom rules don't need Java programming. |

#### Grit.io

| Dimension | Grit.io | CodeCustodian |
|---|---|---|
| **What it does** | GritQL pattern language for code transformations. Supports JS/TS, Python, Java. | AI-powered transformations with Copilot SDK reasoning. Custom rules via YAML config. |
| **Pattern language** | Custom DSL (GritQL) — powerful but requires learning a new language. | YAML-based custom rules with pattern/replacement fields. No new language to learn. |
| **Where CodeCustodian wins** | Lower barrier to entry. AI handles complex transformations that GritQL can't express. |

#### Snyk / Veracode

| Dimension | Snyk / Veracode | CodeCustodian |
|---|---|---|
| **What it does** | SCA (software composition analysis) and SAST (static application security testing). Snyk Code has reachability analysis. Veracode offers pipeline scanning. | Security scanning via Bandit + custom patterns. CWE references. Compliance impact tagging (PCI DSS, GDPR, SOC 2). |
| **Auto-fix** | Snyk can auto-fix some dependency vulnerabilities. Veracode: no auto-fix. | Copilot SDK generates security fixes verified by post-execution security scans. |
| **Reachability** | Snyk Code traces vulnerable paths from entry points. Expensive SaaS. | Planned: call-chain analysis from `@app.route()` entry points using existing `get_call_sites` planner tool. |
| **Where CodeCustodian wins** | Open-source. AI-powered fix generation. Security scanning is one of six scanner types, not a separate product. |

### 2.2 Adjacent Tools

| Tool | What It Does | Gap CodeCustodian Fills |
|---|---|---|
| **GitHub Copilot (in-editor)** | AI code completion in the IDE. | CodeCustodian operates *outside* the IDE — in CI/CD. Catches tech debt at pipeline time, not coding time. MCP server bridges the gap. |
| **GitHub Actions** | CI/CD automation platform. | CodeCustodian *runs on* Actions. The self-heal and PR review bot workflows use Actions as triggers. |
| **Pyright / mypy** | Type checking. | CodeCustodian detects missing types *and* auto-adds annotations via Copilot SDK. |
| **ESLint / Ruff** | Linting. | CodeCustodian uses Ruff/ESLint as *verifiers* and can auto-fix linter violations via CI self-healing. |

---

## 3. Feature Inventory — Current State

### 3.1 Scanner System (7 Scanners)

#### Deprecated API Scanner

- **What it does:** AST-based detection of deprecated function calls in Python. Resolves import aliases (`import pandas as pd`). Version-aware urgency scoring based on `deprecated_since` and `removal_version` dates.
- **Data sources:** Curated `deprecations.json` (25+ Python rules: pandas, numpy, os, collections, typing, unittest) + `deprecations_js_ts.json` (3 JS/TS rules: `fs.exists`, `new Buffer`, `util.print`).
- **Custom rules:** Users define additional rules in `.codecustodian.yml` under `scanners.deprecated_apis.custom_patterns` — pattern, replacement, severity, description. Merged into the engine at scan time.
- **SDK usage:** When creating PRs, the **GitHub Copilot SDK** plans the refactoring using the deprecation's `replacement` and `migration_guide_url` as context for multi-turn reasoning.
- **Competitive edge:** Unlike SonarQube (detect only), CodeCustodian detects *and* plans the fix. Unlike Moderne (pre-written recipes), CodeCustodian handles novel deprecation patterns via AI reasoning.

#### TODO Comment Scanner

- **What it does:** Regex-based detection of `TODO`, `FIXME`, `HACK`, `XXX` comments across all text files. Uses `git blame` to compute age. Age-based severity escalation: >180 days → high, >90 days → medium.
- **SDK usage:** **GitHub Copilot SDK** generates contextual fix plans for TODOs that describe a concrete action. The planner reads surrounding code context to understand what the TODO author intended.
- **Competitive edge:** No competitor auto-resolves TODOs. Dependabot doesn't touch comments. SonarQube tracks but doesn't fix.

#### Code Smell Scanner

- **What it does:** Cyclomatic complexity via Radon, cognitive complexity (Sonar-style), maintainability index. Detects long functions, too many parameters, deep nesting, dead code.
- **Thresholds:** All configurable in `.codecustodian.yml`. Defaults: max complexity=10, max function lines=50.
- **SDK usage:** **GitHub Copilot SDK** plans function extraction, parameter object patterns, and nesting reduction. The planner's `get_function_definition` and `get_call_sites` tools gather full context before generating a plan.
- **Competitive edge:** Radon + AI reasoning. SonarQube detects smells but can't fix them. CodeCustodian detects and proposes a decomposition plan.

#### Security Pattern Scanner

- **What it does:** Bandit subprocess with JSON output + custom regex patterns for hardcoded secrets, weak crypto (MD5, SHA1), SQL injection, command injection, deserialization, path traversal.
- **Enrichment:** CWE references per finding. Compliance impact tagging (PCI DSS, GDPR, SOC 2). Exploit scenario descriptions.
- **SDK usage:** **GitHub Copilot SDK** generates security-safe replacements. For example, replacing `os.system(cmd)` with `subprocess.run(cmd, shell=False, check=True)` — the planner reasons about the calling context to ensure the fix is correct.
- **Competitive edge:** Open-source vs. Snyk/Veracode SaaS pricing. AI-generated fixes vs. manual remediation guides.

#### Type Coverage Scanner

- **What it does:** AST-based analysis of type annotation coverage per function and per file. Reports missing return types and parameter types. Per-file and overall coverage percentages.
- **AI integration:** When `ai_suggest_types: true` is set, calls the **GitHub Copilot SDK** via `_suggest_types_with_copilot_async()` to generate precise type annotations. Uses the function source + file context as prompt input.
- **SDK usage:** Creates a dedicated `CopilotPlannerClient` session with system prompt "You are a Python typing assistant. Produce accurate, minimal annotations." Sends function source and receives a typed signature line.
- **Competitive edge:** Pyright/mypy can infer types but can't auto-apply. MonkeyType needs runtime data. CodeCustodian uses AI to suggest types without execution.

#### Dependency Upgrade Scanner

- **What it does:** Reads `requirements.txt`, `pyproject.toml`, `uv.lock`, and `poetry.lock`. Compares pinned versions against a curated recommendation catalog (`dependency_recommendations.json`) with minimum recommended versions for key packages (pydantic, httpx, pygithub, fastmcp, requests).
- **SDK usage:** Findings are passed to the **GitHub Copilot SDK** planner which reads the package's changelog/migration guide (via `migration_guide_url` metadata) and plans both the version bump *and* any necessary code changes.
- **Competitive edge:** Dependabot bumps version numbers. Renovate bumps version numbers. CodeCustodian bumps *and* migrates code.

#### Deduplication Engine

- **What it does:** `FindingDeduplicator` generates stable `dedup_key` hashes (type + file + line + description) to prevent noisy duplicate findings across scans. Uses TinyDB for persistence.
- **Why it matters:** Prevents PR spam. Competitors like Dependabot create duplicate PRs when a scan runs multiple times.

### 3.2 AI Planner (GitHub Copilot SDK)

The planner is the core AI engine, built entirely on the **GitHub Copilot SDK** (`github-copilot-sdk` package, v0.1.29+).

#### Multi-Turn Session Architecture

1. **Model routing:** Auto-selects model by finding severity. Critical/high → `gpt-5.2-codex` / `gpt-5.1-codex`. Low → `gpt-5-mini` / `gpt-4.1`. Reasoning mode available via `gpt-5.2-codex` / `gpt-5.1-codex-max` for complex logic.
2. **Tool calling:** Seven `@define_tool` decorated tools with Pydantic schemas that the AI can invoke during planning:
   - `get_function_definition` — Retrieve full source of a function with ±5 lines context
   - `get_imports` — List all imports in a file
   - `search_references` — Find all references to a symbol across the project
   - `find_test_coverage` — Locate test functions covering a target function
   - `get_call_sites` — AST-based call site analysis
   - `check_type_hints` — Analyze type annotation status
   - `get_git_history` — Git log for a specific file
3. **Session lifecycle:** `CopilotClient.start()` → `create_session()` → Turn 1 (context gathering via streaming) → Turn 2 (plan generation via `send_and_wait`) → Turn 3 (alternatives) → `session.destroy()` → `CopilotClient.stop()`.
4. **Session hooks:** `on_pre_tool_use` (audit logging + permission), `on_post_tool_use` (result capture), `on_error_occurred` (retry logic).
5. **Cost tracking:** `UsageAccumulator` tracks input/output tokens and cost per session. Aborts with `BudgetExceededError` when `max_cost_per_run` is exceeded.
6. **Azure OpenAI BYOK:** Supports custom providers for Azure OpenAI via session config `provider: { type: "azure", base_url: ..., api_key: ..., azure: { api_version: "2024-10-21" } }`.

#### Confidence Scoring

Every plan receives a confidence score (1–10) based on:

- **Test coverage** — Does the target code have tests?
- **Complexity** — Cyclomatic and cognitive complexity of the target
- **Call sites** — How many places reference the changed code?
- **Logic changes** — Are we changing behavior or just syntax?
- **Multi-file scope** — Does the fix span multiple files?

Action policy:
- **8–10:** Standard PR, auto-assign reviewers
- **5–7:** Draft PR, request senior engineer review
- **< 5:** Proposal-only mode — creates an advisory GitHub Issue, no code changes

#### Alternative Solutions

For findings with high complexity (cyclomatic > 10 or multi-file), the `AlternativeGenerator` asks the Copilot SDK for 2–3 alternative refactoring approaches with pros/cons. The recommended alternative is highlighted in the PR description.

### 3.3 Executor (Safe Code Modification)

- **Atomic writes:** Temp file → rename pattern with syntax validation via `ast.parse()`.
- **Multi-file rollback:** All files in a transaction succeed or all revert.
- **5-point safety checks:** Syntax validation, import availability, critical path protection, concurrent change detection (git SHA), secrets detection.
- **Transaction logging:** Every change recorded for forensic analysis.
- **Git workflow:** Branch `tech-debt/{category}-{file}-{timestamp}`, conventional commits with `Co-authored-by: CodeCustodian`, push, cleanup.

### 3.4 Verifier

- **Test runner:** pytest execution with JUnit XML parsing, coverage delta detection, 5-minute timeout.
- **Linter runner:** Ruff + mypy + Bandit with baseline comparison (only new violations fail).
- **Security scanner:** Post-execution Bandit + pip-audit + SARIF output.

### 3.5 CI Self-Healing (Unique — No Competitor Has This)

- **What it does:** A GitHub Action triggers on CI failure. It reads the failure log, pattern-matches for known failure types (Ruff F401, mypy incompatible-return, pytest assertion failures), generates patch candidates, and produces a healing plan.
- **How it works:** `detect_failure_signals()` extracts typed failure signals from raw logs. `build_patch_candidates()` generates concrete code fix suggestions for each signal. The `heal` CLI command orchestrates the process.
- **SDK usage:** Context from the failure analysis is passed to the **GitHub Copilot SDK** which generates more complex fixes that go beyond pattern matching.
- **Workflow:** `.github/workflows/ci-self-heal.yml` posts an idempotent healing plan as a PR comment (using `<!-- codecustodian-healing-plan -->` marker to prevent duplicates).
- **Competitive edge:** Dependabot creates PRs that break builds and walks away. Sweep.dev requires a human to file an issue. CodeCustodian *fixes its own CI failures* — true self-healing.

### 3.6 PR Review Bot

- **What it does:** Scans incoming PRs for code smells, security issues, deprecated APIs. Posts a structured risk summary as a PR comment with labels (`needs-fix`, `security-risk`, `type-issues`, `dependency-upgrade`).
- **Severity gating:** Configurable `--block-on` flag to enforce blocking on critical/high severity findings.
- **Workflow:** `.github/workflows/pr-review-bot.yml` triggers on `pull_request`, `workflow_run`, and `workflow_dispatch`.
- **SDK usage:** Review findings can be escalated to the **GitHub Copilot SDK** for AI-generated fix suggestions embedded in the review comment.
- **Competitive edge:** CodeRabbit reviews only. CodeCustodian reviews *and* can fix via the self-heal pipeline.

### 3.7 MCP Server (FastMCP v2)

CodeCustodian exposes all capabilities as an MCP server using **FastMCP v2** (`fastmcp>=2.14.0,<3`), enabling integration with VS Code Copilot Chat, Claude Desktop, and other MCP clients.

#### Architecture

- **Server:** `FastMCP(name="CodeCustodian")` with modular tool/resource/prompt registration.
- **Transports:** stdio (VS Code, Claude Desktop), Streamable HTTP (Azure Container Apps remote deployment).
- **Health check:** Custom `/health` route for Azure Container Apps probe.

#### Tools (8)

| Tool | Category | SDK integration |
|---|---|---|
| `scan_repository` | Detection | Runs all scanners, caches findings. Reports progress via `ctx.report_progress()`. |
| `list_scanners` | Discovery | Returns scanner metadata from the registry. |
| `plan_refactoring` | AI Planning | Creates a **Copilot SDK** session, runs multi-turn planning, returns `RefactoringPlan`. |
| `apply_refactoring` | Execution | Applies cached plan via secure file editor with atomic rollback. |
| `verify_changes` | Verification | Runs pytest + ruff + bandit on changed files. |
| `create_pull_request` | Integration | Creates GitHub PR via PyGithub with AI-generated narrative. |
| `calculate_roi` | Analytics | Computes ROI based on severity, type multiplier, and developer rate. |
| `get_business_impact` | Intelligence | 5-factor business impact scoring. |

#### Resources (7)

Dynamic MCP resources: `codecustodian://config`, `codecustodian://version`, `codecustodian://scanners`, `config://settings`, `findings://{repo}/all`, `findings://{repo}/{type}`, `dashboard://{team}/summary`.

#### Prompts (4)

Pre-built prompt templates: `refactor_finding`, `scan_summary`, `roi_report`, `onboard_repo`.

### 3.8 Enterprise Features

#### RBAC (Role-Based Access Control)

- 6 roles: ADMIN, SECURITY_ADMIN, TEAM_LEAD, CONTRIBUTOR, DEVELOPER, VIEWER.
- 10+ permissions scoped per org/team/repo.
- Azure AD integration via `azure-identity` (`DefaultAzureCredential`).

#### Budget Management

- Per-team monthly budget with alerts at configurable thresholds (50%, 80%, 90%, 100%).
- Hard limit enforcement → `BudgetExceededError` stops the pipeline.
- Cost-per-PR tracking.

#### Approval Workflows

- Policy-driven approval gates before plan execution and PR creation.
- Configurable per repository, category, and severity.

#### Audit Logging

- Append-only JSONL with SHA-256 tamper-evident hashes.
- Captures: actor, target files, changes, verification results, PR linkage, AI reasoning.
- Meets SOC 2 audit trail requirements.

#### Multi-Tenant Isolation

- Tenant-scoped directory layout for configuration and data.
- Per-tenant config overrides. Cross-tenant access prevention.

### 3.9 Integrations

#### Microsoft Work IQ (MCP)

**SDK:** `@microsoft/workiq` npm package, invoked via `fastmcp.Client` over stdio transport.

| Capability | Work IQ Tool Called | Business Value |
|---|---|---|
| Expert routing | `search_people` | Assigns PRs to the engineer most familiar with the affected code. |
| Sprint awareness | `get_sprint_status` | Defers low-priority PRs during sprint crunch. Avoids PR creation during code freeze. |
| Incident awareness | Part of sprint status | Pauses all non-critical automation during active incidents. |
| Organizational context | `search_documents`, `recent_messages` | Surfaces related ADRs, design docs, and recent team discussions. |

**Fallback:** When Work IQ is unavailable (no M365 license, npm not installed), the system falls back gracefully — uses git blame for reviewer assignment, no sprint gating.

#### Azure DevOps

**SDK:** `azure-devops` Python package + `httpx` async client for REST API.

- Work item creation from findings with priority mapping, tagging, and git-blame author assignment.
- Bidirectional PR-to-work-item linking.
- Sprint board state transitions based on PR lifecycle.

#### Azure Monitor / Application Insights

**SDK:** `azure-monitor-opentelemetry` distro — one-liner `configure_azure_monitor()` bootstraps traces, metrics, and logs.

- **Traces:** Distributed tracing per pipeline stage (scan → plan → execute → verify → PR) with finding metadata attributes.
- **Metrics:** Custom counters and histograms: `findings.total`, `pr.success_rate`, `cost.per_pr`, `pipeline.duration_ms`, `roi.savings`.
- **Alerts:** 4 configured rules — severity spike, budget overrun, failure rate > 10%, PR success rate < 90%.
- **Dashboard:** ARM-template Azure Monitor dashboard with 8 widgets (findings over time, PR success rate, cost savings, confidence distribution, verification pass rate, ROI, budget utilization, SLA).

#### Azure Key Vault

**SDK:** `azure-keyvault-secrets` + `azure-identity` (`DefaultAzureCredential`).

- All secrets (GitHub token, Copilot token, DevOps PAT) stored in Key Vault.
- Accessed via managed identity from Azure Container Apps.
- Secret access logged for audit trail.

### 3.10 SARIF Output

- **What it does:** Produces SARIF 2.1.0 (Static Analysis Results Interchange Format) output compatible with GitHub Code Scanning dashboard.
- **Implementation:** `sarif_formatter.py` generates stable `ruleId` values, per-result `partialFingerprints`, and repository-relative file URIs.
- **CLI:** `--output-format sarif` on both `scan` and `findings` commands.
- **Competitive edge:** Same format as CodeQL, Bandit, SonarQube. Native GitHub Security tab integration.

### 3.11 Custom Rule DSL

- **What it does:** Users define custom deprecation rules in `.codecustodian.yml` — no code changes needed.
- **Schema:** Each rule has `name`, `pattern`, `replacement`, `severity`, `description`, `deprecated_since`, `removal_version`, `migration_guide_url`.
- **Engine:** Rules are merged into the indexed rule set at scan time and processed by the same AST engine as built-in rules.
- **Competitive edge:** Moderne requires writing Java recipes. Grit.io requires learning GritQL. CodeCustodian uses YAML — any engineer can add a rule in 60 seconds.

### 3.12 VS Code / IDE Integration

CodeCustodian is immediately usable from VS Code Copilot Chat or Claude Desktop via the MCP server.

**Configuration (`mcp.json`):**
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

Developers can ask: *"Scan this file for tech debt"*, *"What deprecated APIs am I using?"*, *"Plan a fix for finding X"*, *"Calculate the ROI for fixing finding Y"* — all from within the IDE.

---

## 4. Feature Inventory — Planned Competitive Advantages

### 4.1 Multi-Language AST Scanning

**Status:** Partial (JS/TS deprecation data exists, no AST scanner)

**Gap this closes:** SonarQube supports 30+ languages. Grit.io supports JS/TS/Python/Java. CodeCustodian is currently Python-only for AST analysis.

**What to build:**
- `JavaScriptDeprecatedAPIScanner` using regex matching against `.js`/`.ts` files and the existing `deprecations_js_ts.json` database (expandable to `@babel/parser` or `tree-sitter` for true AST).
- `JavaScriptCodeSmellScanner` wrapping `eslint --format json` (parallels the Bandit wrapper pattern).
- Extend `deprecations_js_ts.json` with additional rules: React class components → hooks, `componentWillMount` lifecycle deprecations, `moment.js` → `dayjs`/`date-fns`.

**SDK integration:**
- **GitHub Copilot SDK:** Plans JS/TS refactorings using the same multi-turn session architecture. The planner's tool calling works on any file type.
- **MCP server:** `scan_repository` tool will include JS/TS findings automatically.

**Business value:** Unlocks enterprise polyglot repositories. Without multi-language support, judges and customers see a ceiling. This is table stakes for enterprise adoption.

### 4.2 Reachability Analysis for Security Findings

**Status:** Not started

**Gap this closes:** Snyk Code and Veracode offer reachability analysis — tracing whether a vulnerability is actually reachable from a public endpoint. This is expensive SaaS. CodeCustodian can do it with existing tools.

**What to build:**
- A `ReachabilityAnalyzer` that uses the existing `get_call_sites` planner tool to trace the call chain from Flask/FastAPI route handlers (`@app.route()`, `@router.get()`) and Lambda handlers (`def handler()`) down to the vulnerable function.
- Tag security findings with `reachability: "reachable"` (exposed to public traffic) or `reachability: "internal_only"` (not reachable from external endpoints).
- Auto-promote reachable vulnerabilities from their detected severity to CRITICAL.

**SDK integration:**
- **GitHub Copilot SDK:** The planner's `get_call_sites` tool already does AST-based call analysis. The reachability engine chains multiple calls to trace transitive paths.
- **MCP server:** New `get_reachability` tool for security-focused queries from the IDE.

**Business value:** Dramatically reduces false positives. Security teams get actionable findings instead of a wall of warnings. This is a premium capability that Snyk charges thousands for.

### 4.3 Org-Wide / Monorepo Scanning

**Status:** Not started

**Gap this closes:** Moderne's key selling point is scanning hundreds of repos at once. CTOs managing 500+ repos need this.

**What to build:**
- An `org-scan` CLI command that uses `PyGithub` to list all repos in a GitHub organization.
- Clones or pulls each repo into a temp directory, runs the full scan pipeline, aggregates findings into a unified report.
- Leverages the existing `MultiTenantManager` for per-repo isolation.
- Dashboard summary across all repos: total findings, top-N repos by tech debt, severity distribution.

**SDK integration:**
- **GitHub Copilot SDK:** Each repo gets its own planner session. Findings from similar patterns across repos are deduplicated.
- **Work IQ MCP:** Sprint context is per-team, not per-repo — org-scan respects this.
- **Azure DevOps:** Work items are created in the appropriate project per repo mapping.
- **MCP server:** New `scan_organization` tool and `dashboard://{org}/summary` resource.

**Business value:** Enterprise deal-breaker. Without org-wide scanning, CodeCustodian is a per-repo tool. With it, it becomes a platform.

### 4.4 Live PyPI Version Checking for Dependency Scanner

**Status:** Partial (static catalog exists, no live PyPI checking)

**Gap this closes:** The current dependency scanner checks against a curated catalog of 5 packages. Dependabot and Renovate check against the actual PyPI/npm registry.

**What to build:**
- Use `httpx` to query PyPI JSON API (`https://pypi.org/pypi/{package}/json`) for the latest version.
- Compare installed version vs. latest. Flag major version jumps as "breaking change likely."
- Fetch the release notes / changelog URL from PyPI metadata for context.
- Feed changelog content into the **GitHub Copilot SDK** to plan code migrations for breaking changes.

**SDK integration:**
- **GitHub Copilot SDK:** Receives changelog text as context input. Multi-turn session: Turn 1 reads the changelog, Turn 2 identifies breaking changes affecting the codebase, Turn 3 generates a migration plan.
- **MCP server:** Enhanced `scan_repository` output includes live version data.

**Business value:** Transforms the dependency scanner from a curated checklist into a live intelligence system. Solves the "version bump + code migration" problem that no other tool handles.

---

## 5. SDK & Integration Map

### 5.1 GitHub Copilot SDK (`github-copilot-sdk` v0.1.29+)

**Package:** `copilot` on PyPI  
**Transport:** JSON-RPC over stdio/TCP  
**Auth:** `github_token` → env `GITHUB_TOKEN` → `gh` CLI auth

| CodeCustodian Module | Copilot SDK Usage |
|---|---|
| `planner/copilot_client.py` | `CopilotClient` lifecycle, session management, model discovery, cost tracking |
| `planner/tools.py` | 7 `@define_tool` functions with Pydantic schemas for code inspection |
| `planner/planner.py` | Multi-turn session orchestration: context → plan → alternatives |
| `planner/alternatives.py` | Second-pass AI call for 2–3 alternative approaches |
| `planner/confidence.py` | Post-plan confidence scoring using finding + plan metadata |
| `scanner/type_coverage.py` | Dedicated session for AI type suggestions (`_suggest_types_with_copilot_async`) |
| `cli/ci_healer.py` | Failure analysis context fed to Copilot for complex fix generation |
| `mcp/tools.py` | `plan_refactoring` MCP tool creates Copilot sessions on demand |

**Key APIs used:**
- `CopilotClient(config)` — Client initialization
- `client.start()` / `client.stop()` — Lifecycle
- `client.list_models()` — Model discovery
- `client.create_session({model, tools, system_message, hooks, provider, streaming})` — Session creation
- `session.send_and_wait(prompt)` — Synchronous send (plan generation)
- `session.send(prompt)` — Streaming send (context gathering)
- `@define_tool(description=...)` — Tool definition with Pydantic schema
- Session hooks: `on_pre_tool_use`, `on_post_tool_use`, `on_error_occurred`

### 5.2 FastMCP v2 (`fastmcp>=2.14.0,<3`)

**Package:** `fastmcp` on PyPI  
**Transports:** stdio (local), Streamable HTTP (remote)

| CodeCustodian Module | FastMCP Usage |
|---|---|
| `mcp/server.py` | `FastMCP(name="CodeCustodian")`, `@mcp.custom_route("/health")` |
| `mcp/tools.py` | `@mcp.tool(annotations=ToolAnnotations(...))`, `Context` for progress + logging |
| `mcp/resources.py` | `@mcp.resource("uri://...")` for dynamic data |
| `mcp/prompts.py` | `@mcp.prompt` for pre-built templates |
| `mcp/cache.py` | Server-side finding cache for inter-tool state |
| `integrations/work_iq.py` | `fastmcp.Client` + `StdioTransport` to call Work IQ MCP tools |

### 5.3 Microsoft Work IQ (`@microsoft/workiq` npm)

**Protocol:** MCP over stdio  
**Client:** `fastmcp.Client` with `StdioTransport`

| Work IQ Tool | CodeCustodian Usage |
|---|---|
| `search_people` | Expert identification for PR reviewer assignment |
| `get_sprint_status` | Sprint-aware PR timing and incident detection |
| `search_documents` | Related ADRs, design docs for refactoring context |
| `recent_messages` | Recent team discussions about affected code |

### 5.4 Azure SDKs

| Package | Module | Purpose |
|---|---|---|
| `azure-devops>=7.1` | `integrations/azure_devops.py` | Work item creation, board updates, PR linking |
| `azure-monitor-opentelemetry>=1.2` | `integrations/azure_monitor.py` | Distributed tracing, metrics, dashboards |
| `azure-keyvault-secrets>=4.7` | `enterprise/secrets_manager.py` | Secret storage via managed identity |
| `azure-identity>=1.15` | Multiple modules | `DefaultAzureCredential` for all Azure services |

### 5.5 GitHub SDK

| Package | Module | Purpose |
|---|---|---|
| `PyGithub>=2.1` | `mcp/tools.py`, `cli/main.py` | PR creation, label management, issue creation |
| `GitPython>=3.1` | `executor/git_manager.py` | Branch creation, commits, push, blame |

---

## 6. Feature-by-Feature Competitive Comparison

### Full Comparison Matrix

| Feature | CodeCustodian | SonarQube | Dependabot | Renovate | CodeRabbit | Moderne | Grit.io | Snyk |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Deprecated API detection** | ✅ AST + AI fix | ✅ Detect only | ❌ | ❌ | ❌ | ✅ Recipe | ✅ Pattern | ❌ |
| **TODO tracking + age** | ✅ + auto-resolve | ✅ Track only | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Code smell detection** | ✅ Radon + AI fix | ✅ Detect only | ❌ | ❌ | ⚠️ Comments | ❌ | ❌ | ❌ |
| **Security scanning** | ✅ Bandit + AI fix | ✅ Detect only | ✅ Deps only | ❌ | ⚠️ Comments | ❌ | ❌ | ✅ SaaS |
| **Type coverage** | ✅ + AI annotation | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Dependency upgrades** | ✅ + code migration | ❌ | ✅ Version only | ✅ Version only | ❌ | ✅ Recipe | ❌ | ✅ Version only |
| **AI-powered fix planning** | ✅ Copilot SDK | ❌ | ❌ | ❌ | ⚠️ Suggestions | ❌ | ❌ | ❌ |
| **Auto-fix execution** | ✅ Atomic + rollback | ❌ | ❌ | ❌ | ❌ | ✅ Deterministic | ✅ Pattern | ❌ |
| **Self-healing CI** | ✅ Unique | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **PR review bot** | ✅ + labels + gating | ❌ | ❌ | ❌ | ✅ Core feature | ❌ | ❌ | ❌ |
| **MCP server / IDE** | ✅ FastMCP v2 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Org context (Work IQ)** | ✅ Sprint-aware | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Custom rule DSL** | ✅ YAML config | ✅ XML config | ❌ | ❌ | ❌ | ✅ Java recipes | ✅ GritQL | ❌ |
| **SARIF output** | ✅ v2.1.0 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Azure DevOps** | ✅ Work items | ✅ Plugin | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Azure Monitor** | ✅ OTel | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **RBAC + audit trail** | ✅ SOC 2 | ✅ Enterprise | ❌ | ❌ | ❌ | ✅ Enterprise | ❌ | ✅ Enterprise |
| **Feedback learning** | ✅ PR outcomes | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Budget management** | ✅ Per-team | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Multi-language** | ⚠️ Python + JS/TS partial | ✅ 30+ | N/A | N/A | ✅ All | ✅ Java/Kotlin/C# | ✅ JS/TS/Py/Java | ✅ All |
| **Reachability analysis** | 🔜 Planned | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ SaaS |
| **Org-wide scanning** | 🔜 Planned | ✅ | ✅ | ✅ | ❌ | ✅ Core feature | ❌ | ✅ |

---

## 7. Priority Matrix & Roadmap

### Immediate Wins (Low Effort, High Impact)

| # | Feature | Effort | Impact | SDK Integration |
|---|---|---|---|---|
| 1 | ~~Custom Rule DSL~~ | ✅ Done | High | Rules fed to Copilot SDK for fix planning |
| 2 | ~~SARIF Output~~ | ✅ Done | Medium | GitHub Code Scanning API upload |
| 3 | ~~VS Code MCP Config~~ | ✅ Done | Medium | FastMCP stdio transport |
| 4 | ~~AI Type Suggestions~~ | ✅ Done | Medium | Copilot SDK session per function |

### Competition-Killers (Medium Effort, Unique)

| # | Feature | Effort | Impact | SDK Integration |
|---|---|---|---|---|
| 5 | ~~Self-Healing CI~~ | ✅ Done | Very High | Copilot SDK for complex fixes |
| 6 | ~~PR Review Bot~~ | ✅ Done | High | Copilot SDK for fix suggestions |
| 7 | JS/TS Scanner | Medium | High | Copilot SDK plans JS/TS refactorings |
| 8 | Reachability Analysis | Medium | High | `get_call_sites` tool + Copilot SDK |

### Enterprise Scale (Medium Effort, Enterprise Value)

| # | Feature | Effort | Impact | SDK Integration |
|---|---|---|---|---|
| 9 | Org-Wide Scanning | Medium | High | PyGithub + MultiTenantManager + MCP |
| 10 | Live PyPI Checking | Medium | High | httpx + Copilot SDK changelog parsing |

### Feature Readiness Summary

```
Done:        8 of 10 features ████████░░ 80%
In Progress: 0 of 10 features ░░░░░░░░░░  0%
Planned:     2 of 10 features ██░░░░░░░░ 20%
```

---

*This document is generated from the CodeCustodian codebase as of February 27, 2026.*
