# CodeCustodian — Detailed Step-by-Step Implementation Plan

**Version:** 3.1 — Business-Aligned Challenge Edition (Updated with verified PyPI versions)  
**Date:** February 11, 2026  
**Challenge Deadline:** March 7, 2026, 10 PM PST  
**Source Documents:**  
- [features-requirements.md](features-requirements.md) — Detailed technical feature requirements  
- [features-requirements-challenge-optimized.md](features-requirements-challenge-optimized.md) — Challenge scoring alignment  
- [business-requirements.md](business-requirements.md) — Business requirements, GTM, pricing, competitive analysis  
- [CodeCustodian_BRD.md](CodeCustodian_BRD.md) — Business Requirements Document (personas, governance, policies)  
**Purpose:** Actionable implementation guide aligned with judging criteria, business requirements, and enterprise readiness using latest FastMCP and GitHub Copilot SDK

---

## Table of Contents

1. [Implementation Overview](#1-implementation-overview)
2. [Pre-Implementation Setup](#2-pre-implementation-setup)
3. [Phase 1 — Core Architecture & Policy System (Week 1)](#3-phase-1--core-architecture--policy-system-week-1)
4. [Phase 2 — Scanner Modules (Week 1–2)](#4-phase-2--scanner-modules-week-12)
5. [Phase 3 — AI Planner with GitHub Copilot SDK (Week 2)](#5-phase-3--ai-planner-with-github-copilot-sdk-week-2)
6. [Phase 4 — Executor & Verifier (Week 2)](#6-phase-4--executor--verifier-week-2)
7. [Phase 5 — GitHub & Azure DevOps Integration (Week 3)](#7-phase-5--github--azure-devops-integration-week-3)
8. [Phase 6 — MCP Server with FastMCP (Week 3)](#8-phase-6--mcp-server-with-fastmcp-week-3)
9. [Phase 7 — Azure Integrations & Enterprise Features (Week 3)](#9-phase-7--azure-integrations--enterprise-features-week-3)
10. [Phase 8 — Business Intelligence, Feedback & Learning (Week 3–4)](#10-phase-8--business-intelligence-feedback--learning-week-34)
11. [Phase 9 — Security, RAI & Observability (Week 4)](#11-phase-9--security-rai--observability-week-4)
12. [Phase 10 — Testing, CLI & Polish (Week 4)](#12-phase-10--testing-cli--polish-week-4)
13. [Phase 11 — Challenge Deliverables (Week 4)](#13-phase-11--challenge-deliverables-week-4)
14. [Technology Validation Notes](#14-technology-validation-notes)
15. [Risk Register & Mitigations](#15-risk-register--mitigations)
16. [Dependency Graph](#16-dependency-graph)
17. [Success Metrics & KPIs](#17-success-metrics--kpis)
18. [Challenge Scoring Strategy](#18-challenge-scoring-strategy)

---

## 1. Implementation Overview

### Architecture Summary

CodeCustodian follows a **linear pipeline architecture** with feedback loops:

```
Onboard → Scan → De-dup → Prioritize → Plan → Execute → Verify → PR/Proposal → Feedback
```

Enhanced with **Azure ecosystem integrations** and **business intelligence**:

```
                    ┌─────────────────┐
                    │  Azure Monitor   │ (Observability)
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
   ┌──────────┐    │  CodeCustodian   │    ┌──────────────┐
   │  GitHub   │◄──┤  Agent Pipeline  ├──►│ Azure DevOps │
   │  Repos    │   │                  │   │  Work Items  │
   └──────────┘    └────────┬────────┘    └──────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ Copilot SDK  │   │  FastMCP     │   │  Work IQ MCP │
│ (AI Planner) │   │  (MCP Server)│   │  (Context)   │
└──────────────┘   └──────────────┘   └──────────────┘
         │                                     │
         ▼                                     ▼
┌──────────────┐                      ┌──────────────┐
│  Feedback &  │                      │  Business    │
│  Learning    │                      │  Intelligence│
└──────────────┘                      └──────────────┘
```

**Timeline:** 4 weeks to challenge deadline (March 7, 2026)

### Business Targets (from BRD)

| Metric | Target | Source |
|---|---|---|
| Issue resolution rate | 25–35% per run | BRD §1.3 |
| AI cost per refactoring | < $0.50 average | BRD §1.3 |
| Detection to PR time | < 5 minutes | BRD §1.3 |
| PR first-run pass rate | 95%+ | BRD §1.3 |
| Target adoption (6 mo) | 1,000+ repos | BRD §1.3 |
| Annual savings per team | $60,000–$130,000 | BR-001 |
| Payback period | ≤ 3 months | BR-001 |
| PR merge rate | 95%+ | BR-002 |
| Production incidents | 0 from automated changes | BR-002 |

### Key Technology Decisions — Validated Against PyPI (Feb 11, 2026)

| Technology | Pin | Latest on PyPI | Status | Notes |
|---|---|---|---|---|
| **FastMCP** | `>=2.14.0,<3` | 2.14.5 | ✅ Stable | Pin `<3` — v3 in beta. Standalone by Prefect. Enterprise auth, Streamable HTTP. |
| **GitHub Copilot SDK** | `>=0.1.23` | 0.1.23 | ✅ Tech Preview | JSON-RPC, `CopilotClient`, `@define_tool`, streaming, custom providers. |
| **Azure DevOps** | `>=7.1.0b4` | 7.1.0b4 | ✅ Stable | Work items, PR linking, sprint boards. |
| **Azure Monitor OTel** | `>=1.2.0` | 1.6.4 | ✅ Stable | OpenTelemetry distro with Azure exporter. |
| **Azure Key Vault** | `>=4.7.0` | 4.10.0 | ✅ Stable | Secret storage with managed identity. |
| **Azure Identity** | `>=1.15.0` | 1.25.2 | ✅ Stable | `DefaultAzureCredential`, managed identity. |
| **PyGithub** | `>=2.1.1` | 2.6.0 | ✅ Stable | GitHub REST API wrapper. |
| **GitPython** | `>=3.1.40` | 3.1.44 | ✅ Stable | Git blame, branching, commits, diffs. |
| **Typer** | `>=0.9.0` | 0.15.3 | ✅ Stable | CLI framework with Rich. |
| **Pydantic** | `>=2.5.0` | 2.12.5 | ✅ Stable | Config validation, tool schema generation. |
| **Radon** | `>=6.0.1` | 6.0.1 | ✅ Stable | Cyclomatic complexity, maintainability index. |
| **Bandit** | `>=1.7.5` | 1.9.0 | ✅ Stable | Security pattern scanning (JSON mode). |
| **Ruff** | `>=0.1.7` | 0.11.5 | ✅ Stable | Fast Python linter with JSON output. |
| **httpx** | `>=0.25.0` | 0.28.1 | ✅ Stable | Async HTTP client. |
| **TinyDB** | `>=4.8.0` | 4.8.2 | ✅ Stable | Local finding/feedback store. |
| **PyYAML** | `>=6.0.1` | 6.0.2 | ✅ Stable | YAML config parsing. |
| **astroid** | `>=3.0.1` | 3.3.9 | ✅ Stable | AST analysis for code smells. |
| **InquirerPy** | `>=0.3.4` | 0.3.4 | ⚠️ Unmaintained | Last release Jun 2022. Consider replacing later. |

**Removed from original plan:**
- ~~`msrest>=0.7.1`~~ — Deprecated; pulled transitively by `azure-devops`.
- ~~`toml>=0.10.2`~~ — Unnecessary; Python 3.11+ has `tomllib` in stdlib.

---

## 2. Pre-Implementation Setup

### Step 2.1 — Repository Initialization

**Duration:** 0.5 day  
**Requirements covered:** FR-ARCH-002, FR-ARCH-003, BR-ONB-001

```bash
# 1. Initialize project with uv
uv init codecustodian
cd codecustodian

# 2. Create virtual environment
uv venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

# 3. Set Python version
echo "3.11" > .python-version
```

**Tasks:**
- [x] Create GitHub repository
- [x] Initialize with `uv init`
- [x] Create directory structure (business-aligned):

```
codecustodian/
├── src/
│   └── codecustodian/
│       ├── __init__.py
│       ├── models.py
│       ├── pipeline.py
│       ├── logging.py
│       ├── scanner/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── registry.py               # ScannerRegistry + marketplace catalog (BR-SCN-003)
│       │   ├── deduplication.py           # Finding de-dup across runs (BR-SCN-001)
│       │   ├── deprecated_api.py
│       │   ├── todo_comments.py
│       │   ├── code_smells.py
│       │   ├── security.py
│       │   ├── type_coverage.py
│       │   └── data/
│       │       └── deprecations.json
│       ├── planner/
│       │   ├── __init__.py
│       │   ├── copilot_client.py          # GitHub Copilot SDK wrapper
│       │   ├── tools.py                   # @define_tool definitions
│       │   ├── prompts.py
│       │   ├── confidence.py
│       │   ├── alternatives.py            # Alternative solution generation (FR-PLAN-102)
│       │   └── planner.py
│       ├── executor/
│       │   ├── __init__.py
│       │   ├── file_editor.py
│       │   ├── backup.py
│       │   ├── safety_checks.py           # 5-point pre-execution safety (FR-EXEC-101)
│       │   └── git_manager.py
│       ├── verifier/
│       │   ├── __init__.py
│       │   ├── test_runner.py
│       │   ├── linter.py
│       │   └── security_scanner.py        # Trivy + TruffleHog + SARIF (FR-VERIFY-102)
│       ├── integrations/
│       │   ├── __init__.py
│       │   ├── github_integration/
│       │   │   ├── __init__.py
│       │   │   ├── pr_creator.py
│       │   │   ├── pr_interaction.py      # @codecustodian comment bot (FR-UX-100)
│       │   │   ├── issues.py
│       │   │   └── comments.py
│       │   ├── azure_devops.py            # Azure DevOps work items + Azure Repos PR
│       │   ├── azure_monitor.py           # Azure Monitor telemetry
│       │   └── work_iq.py                 # Microsoft Work IQ MCP
│       ├── enterprise/
│       │   ├── __init__.py
│       │   ├── roi_calculator.py          # ROI metrics (FR-COST-101)
│       │   ├── multi_tenant.py            # Multi-tenant support (BR-ENT-001)
│       │   ├── rbac.py                    # RBAC with Azure AD (FR-SEC-101)
│       │   ├── budget_manager.py          # Per-team budget tracking (FR-COST-100)
│       │   ├── approval_workflows.py      # Plan/PR approval gates (BR-GOV-002)
│       │   ├── sla_reporter.py            # SLA & reliability metrics (BR-ENT-002)
│       │   └── secrets_manager.py         # Azure Key Vault integration (FR-SEC-102)
│       ├── onboarding/
│       │   ├── __init__.py
│       │   ├── onboard.py                 # Org/repo self-service onboarding (BR-ONB-001)
│       │   └── policy_templates.py        # Starter policy packs (BR-ONB-002)
│       ├── feedback/
│       │   ├── __init__.py
│       │   ├── learning.py                # PR outcome feedback loop (FR-LEARN-100)
│       │   ├── history.py                 # Historical pattern recognition (FR-LEARN-101)
│       │   └── preferences.py             # Team/engineer preference store
│       ├── intelligence/
│       │   ├── __init__.py
│       │   ├── business_impact.py         # 5-factor business impact scoring (FR-PRIORITY-100)
│       │   ├── reprioritization.py        # Dynamic re-prioritization (FR-PRIORITY-101)
│       │   └── notifications.py           # Notification engine (BR-NOT-001)
│       ├── mcp/
│       │   ├── __init__.py
│       │   ├── server.py                  # FastMCP server
│       │   ├── tools.py                   # MCP tool definitions
│       │   ├── resources.py               # MCP resources
│       │   └── prompts.py                 # MCP prompts
│       ├── config/
│       │   ├── __init__.py
│       │   ├── schema.py
│       │   ├── defaults.py
│       │   └── policies.py                # Policy management (BR-CFG-001/002)
│       └── cli/
│           ├── __init__.py
│           └── main.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── fixtures/
├── docs/
│   ├── README.md
│   ├── ARCHITECTURE.md
│   ├── RESPONSIBLE_AI.md
│   ├── DEPLOYMENT.md
│   └── BUSINESS_VALUE.md
├── presentations/
│   └── CodeCustodian.pptx
├── customer/
│   └── testimonial.md
├── feedback/
│   └── sdk-feedback.md
├── scripts/
│   ├── upload_metrics.py
│   ├── generate_summary.py
│   └── deploy-to-azure.sh               # One-click Azure deployment (FR-DEPLOY-100)
├── AGENTS.md                              # Custom instructions for Copilot
├── mcp.json                               # Work IQ MCP server config
├── pyproject.toml
├── Dockerfile
├── .codecustodian.yml
├── .github/
│   └── workflows/
│       ├── codecustodian.yml              # Main CI/CD workflow
│       ├── ci.yml                         # Lint + test
│       ├── security-scan.yml              # Security scanning
│       └── deploy-azure.yml              # Azure Container Apps deploy
└── README.md
```

### Step 2.2 — Dependency Installation

**Duration:** 0.5 day  
**Requirements covered:** FR-ARCH-003

Create `pyproject.toml`:

```toml
[project]
name = "codecustodian"
version = "0.1.0"
description = "Autonomous AI agent for technical debt management powered by GitHub Copilot SDK"
requires-python = ">=3.11"
dependencies = [
    # ── GitHub Copilot SDK (AI Planning) ──
    "github-copilot-sdk>=0.1.23",         # GitHub Copilot CLI JSON-RPC SDK

    # ── MCP Server (FastMCP) ──
    "fastmcp>=2.14.0,<3",                 # FastMCP v2 production framework
    
    # ── GitHub & Git ──
    "PyGithub>=2.1.1",
    "GitPython>=3.1.40",
    
    # ── Azure Integrations ──
    "azure-devops>=7.1.0b4",              # Azure DevOps REST API
    "azure-monitor-opentelemetry>=1.2.0", # Azure Monitor + OpenTelemetry
    "azure-keyvault-secrets>=4.7.0",      # Azure Key Vault secrets (FR-SEC-102)
    "azure-identity>=1.15.0",             # Managed identity for Azure services
    "opentelemetry-api>=1.20.0",
    "opentelemetry-sdk>=1.20.0",
    # NOTE: msrest removed — deprecated, pulled transitively by azure-devops
    
    # ── Configuration ──
    "pyyaml>=6.0.1",
    "pydantic>=2.5.0",
    
    # ── CLI ──
    "typer>=0.9.0",
    "rich>=13.7.0",
    "InquirerPy>=0.3.4",                  # Interactive CLI prompts (FR-UX-300)
    
    # ── Analysis ──
    "radon>=6.0.1",
    "astroid>=3.0.1",
    "bandit>=1.7.5",
    
    # ── Utilities ──
    "httpx>=0.25.0",
    # NOTE: toml removed — Python 3.11+ has tomllib in stdlib
    "tinydb>=4.8.0",                       # Local finding/feedback store (FR-LEARN-100)
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.3",
    "pytest-cov>=4.1.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.1.7",
    "mypy>=1.7.1",
    "vcrpy>=6.0.0",
]

[project.scripts]
codecustodian = "codecustodian.cli.main:app"
codecustodian-mcp = "codecustodian.mcp.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

Install:
```bash
uv add github-copilot-sdk "fastmcp>=2.14.0,<3" PyGithub GitPython \
    azure-devops azure-monitor-opentelemetry azure-keyvault-secrets azure-identity \
    opentelemetry-api opentelemetry-sdk msrest \
    pyyaml pydantic typer rich InquirerPy radon astroid bandit httpx toml tinydb

uv add --dev pytest pytest-cov pytest-asyncio ruff mypy vcrpy
```

### Step 2.3 — CI/CD Pipeline Setup

**Duration:** 0.5 day  
**Requirements covered:** FR-TEST-001, FR-OPS-001, BR-QA-001

**Tasks:**
- [x] Create `.github/workflows/ci.yml` with lint, test, security scan, coverage gate (80%)
- [x] Create `.github/workflows/security-scan.yml` with Bandit + Trivy + TruffleHog
- [x] Create `.github/workflows/deploy-azure.yml` for Azure Container Apps
- [x] Create `.github/workflows/codecustodian.yml` for scheduled daily runs
- [x] Configure `ruff.toml` and `mypy.ini`

---

## 3. Phase 1 — Core Architecture & Policy System (Week 1)

### Step 3.1 — Data Models & Exception Hierarchy

**Duration:** 1.5 days  
**Requirements covered:** FR-ARCH-004, FR-ARCH-005, BR-SCN-002  
**File:** `src/codecustodian/models.py`

**Tasks:**
- [x] **3.1.1** Define `Finding` dataclass with all fields:
  - `id`, `type`, `severity`, `file`, `line`, `description`, `suggestion`
  - `priority_score`, `business_impact_score` (NEW — FR-PRIORITY-100)
  - `metadata`, `context`, `timestamp`
  - `dedup_key` (NEW — hash for cross-run de-duplication, BR-SCN-001)
  - `reviewer_effort_estimate` (NEW — low/medium/high, BR-PR-002)
- [x] **3.1.2** Define `CodeContext` dataclass:
  - `code`, `line_start`, `line_end`, `function_signature`, `imports`
  - `has_tests`, `coverage_percentage`, `call_sites`, `last_modified`
  - `usage_frequency` (NEW — telemetry-based, FR-PRIORITY-100)
  - `criticality_level` (NEW — critical path detection)
- [x] **3.1.3** Define `RefactoringPlan` Pydantic model:
  - `summary`, `reasoning`, `changes: List[CodeChange]`, `risks`
  - `requires_manual_verification`, `confidence_factors`, `confidence_score`
  - `alternatives: List[AlternativeSolution]` (NEW — FR-PLAN-102)
  - `reviewer_effort: str` (NEW — BR-PR-002)
- [x] **3.1.4** Define `AlternativeSolution` Pydantic model (NEW — FR-PLAN-102):
  - `name`, `description`, `pros: List[str]`, `cons: List[str]`
  - `changes: List[CodeChange]`, `confidence_score`, `recommended: bool`
- [x] **3.1.5** Define `CodeChange` Pydantic model:
  - `file`, `old_code`, `new_code`, `line_start`, `line_end`
- [x] **3.1.6** Define `VerificationResult` dataclass
- [x] **3.1.7** Define `ProposalResult` Pydantic model (NEW — BR-PR-003):
  - `finding`, `recommended_steps: List[str]`, `estimated_effort`, `risks`
  - `is_proposal_only: bool` (no code changes, advisory only)
- [x] **3.1.8** Define custom exception hierarchy:
  - `CodeCustodianError` → `ScannerError`, `PlannerError`, `ExecutorError`, `VerifierError`, `GitHubAPIError`, `AzureIntegrationError`, `BudgetExceededError` (NEW), `ApprovalRequiredError` (NEW)

### Step 3.2 — Configuration & Policy System

**Duration:** 2 days  
**Requirements covered:** FR-CONFIG-001, BR-CFG-001, BR-CFG-002, BR-ONB-002  
**Files:** `src/codecustodian/config/schema.py`, `src/codecustodian/config/defaults.py`, `src/codecustodian/config/policies.py`

**Tasks:**
- [x] **3.2.1** Implement `CodeCustodianConfig` Pydantic model hierarchy:
  - `ScannersConfig` → `DeprecatedAPIConfig`, `TODOConfig`, `CodeSmellConfig`
  - `BehaviorConfig`:
    - `max_prs_per_run`, `confidence_threshold`
    - `max_files_per_pr: int = 5` (NEW — BR-PLN-002)
    - `max_lines_per_pr: int = 500` (NEW — BR-PLN-002)
    - `auto_split_prs: bool = True` (NEW — BR-PLN-002: split when limits exceeded)
    - `proposal_mode_threshold: int = 5` (NEW — BR-PR-003: confidence below this → proposal only)
    - `enable_alternatives: bool = True` (NEW — FR-PLAN-102)
  - `GitHubConfig` (pr_labels, reviewers, branch_prefix)
  - `CopilotConfig` (model, reasoning_effort, streaming, provider)
  - `AzureConfig` (devops_org_url, devops_pat, devops_project, monitor_connection_string, tenant_id, keyvault_name)
  - `WorkIQConfig` (enabled, mcp_server_url, api_key)
  - `BudgetConfig` (NEW — FR-COST-100):
    - `monthly_budget: float = 500`, `alert_thresholds: list = [50, 80, 90, 100]`
    - `hard_limit: bool = True`
  - `NotificationsConfig` (NEW — BR-NOT-001):
    - `channels: List[str]`, `severity_threshold: str`, `events: List[str]`
  - `ApprovalConfig` (NEW — BR-GOV-002):
    - `require_plan_approval: bool`, `require_pr_approval: bool`
    - `approved_repos: List[str]`, `sensitive_paths: List[str]`

- [x] **3.2.2** Implement `PolicyManager` (NEW — BR-CFG-001, BR-CFG-002):
  ```python
  class PolicyManager:
      """Central policy management with org-wide + per-repo overrides."""
      
      def __init__(self, org_policy: dict, repo_overrides: dict = None):
          self.org_policy = org_policy
          self.repo_overrides = repo_overrides or {}
      
      def get_effective_policy(self, repo_name: str) -> dict:
          """Merge org-wide policy with repo-specific overrides."""
          base = deepcopy(self.org_policy)
          if repo_name in self.repo_overrides:
              deep_merge(base, self.repo_overrides[repo_name])
          return base
      
      def is_path_allowed(self, file_path: str, repo_name: str) -> bool:
          """Check allowlist/denylist controls (BR-CFG-002)."""
          policy = self.get_effective_policy(repo_name)
          for pattern in policy.get("denylist", []):
              if fnmatch(file_path, pattern):
                  return False
          allowlist = policy.get("allowlist", ["**"])
          return any(fnmatch(file_path, p) for p in allowlist)
      
      def should_use_proposal_mode(self, file_path: str, finding_type: str) -> bool:
          """Check if proposal-only mode required for this path/type."""
          ...
  ```

- [x] **3.2.3** Implement policy templates (BR-ONB-002):
  - **"Security First"**: security scanner enabled, confidence ≥ 8, denylist = `["**/auth/**", "**/payments/**"]`
  - **"Deprecations First"**: deprecated_api scanner priority, aggressive PR sizing
  - **"Low-Risk Maintenance"**: confidence ≥ 9, max 3 files per PR, TODO + type_coverage only
  - **"Full Scan"**: all scanners, balanced settings

- [x] **3.2.4** Implement config merging: defaults ← org policy ← repo override ← env vars ← CLI args
- [x] **3.2.5** Create default `.codecustodian.yml` template with all options documented
- [x] **3.2.6** Add Pydantic validators for cross-field constraints

### Step 3.3 — Pipeline Orchestrator

**Duration:** 1.5 days  
**Requirements covered:** FR-ARCH-001, BR-PLN-001, BR-PLN-002, BR-QA-002  
**File:** `src/codecustodian/pipeline.py`

**Tasks:**
- [x] **3.3.1** Implement `Pipeline` class with sequential stage execution:
  ```
  scan() → dedup() → prioritize() → plan() → [approve?] → execute() → verify() → create_pr_or_proposal()
  ```
- [x] **3.3.2** Implement fail-fast per-finding behavior
- [x] **3.3.3** Implement finding prioritization with business impact scoring
- [x] **3.3.4** Implement dry-run mode (scan + plan only, no execution)
- [x] **3.3.5** Implement **proposal mode** (BR-PR-003, BR-QA-002):
  - If confidence < `proposal_mode_threshold`: create advisory issue, not PR
  - If policy requires proposal mode for sensitive paths: skip execution
  - If quality gates fail and can't be fixed: downgrade to proposal
- [x] **3.3.6** Implement **configurable PR sizing** (BR-PLN-002):
  - Group related findings into logical PR units
  - Split when max_files_per_pr or max_lines_per_pr exceeded
  - Create multiple smaller PRs instead of one mega-PR
- [x] **3.3.7** Implement **approval gates** (BR-GOV-002):
  - Plan approval checkpoint: pause and await approval before execution
  - Configurable per repo/category/severity
- [x] **3.3.8** Add structured logging at each stage transition
- [x] **3.3.9** Add OpenTelemetry tracing spans per stage (Azure Monitor integration)

### Step 3.4 — Onboarding System

**Duration:** 0.5 day  
**Requirements covered:** BR-ONB-001, BR-ONB-002  
**Files:** `src/codecustodian/onboarding/onboard.py`, `src/codecustodian/onboarding/policy_templates.py`

**Tasks:**
- [x] **3.4.1** Implement `OnboardingManager`:
  ```python
  class OnboardingManager:
      def onboard_organization(self, org_name: str, template: str = "full_scan") -> dict:
          """Enroll an org with a policy template. Returns status per repo."""
          repos = self.github.list_repos(org_name)
          eligible = [r for r in repos if not r.archived and not r.private_sensitive]
          for repo in eligible:
              self.configure_repo(repo, template)
          return {"configured": len(eligible), "excluded": len(repos) - len(eligible)}
      
      def onboard_repo(self, repo_path: str, template: str = "full_scan") -> dict:
          """Onboard single repo with policy template."""
          ...
      
      def get_onboarding_status(self, org_or_repo: str) -> str:
          """Return: configured | scanning | blocked | requires_approval"""
          ...
  ```
- [ ] **3.4.2** Implement policy template selection via CLI `init` command (deferred to Phase 6 — CLI)
- [ ] **3.4.3** Create `.codecustodian.yml` + GitHub Action workflow on onboard (deferred to Phase 6 — CLI)

### Step 3.5 — Structured Logging & Azure Monitor Telemetry

**Duration:** 1 day  
**Requirements covered:** FR-OBS-001, FR-OBS-002, FR-AZURE-003  
**Files:** `src/codecustodian/logging.py`, `src/codecustodian/integrations/azure_monitor.py`

**Tasks:**
- [ ] **3.5.1** Implement `JSONFormatter` for structured JSON log output (deferred — current logger sufficient)
- [x] **3.5.2** Implement Azure Monitor integration with OpenTelemetry:
  ```python
  from azure.monitor.opentelemetry import configure_azure_monitor
  from opentelemetry import trace, metrics

  class ObservabilityProvider:
      def __init__(self, connection_string: str):
          configure_azure_monitor(connection_string=connection_string)
          self.tracer = trace.get_tracer("codecustodian")
          self.meter = metrics.get_meter("codecustodian")
          
          # Custom metrics
          self.findings_counter = self.meter.create_counter("codecustodian.findings.total")
          self.pr_success_rate = self.meter.create_histogram("codecustodian.pr.success_rate")
          self.cost_savings = self.meter.create_counter("codecustodian.roi.savings")
          self.cost_per_pr = self.meter.create_histogram("codecustodian.cost.per_pr")
          self.pipeline_duration = self.meter.create_histogram("codecustodian.pipeline.duration_ms")
  ```
- [x] **3.5.3** Implement distributed tracing spans (FR-OBS-101):
  - Parent: `refactoring_pipeline`, Children: `scan`, `plan` (with `copilot_sdk_call`, `tool_execution`), `execute`, `verify`, `create_pr`
  - Attributes: `finding.id`, `finding.type`, `ai.model`, `ai.tokens_used`, `ai.cost`, `test.pass_rate`, `pr.number`
- [x] **3.5.4** Implement SLA metrics collection (BR-ENT-002):
  - Run success rate, time to PR, failure reasons

**Tests to write:**
- [x] `tests/test_models.py` — Serialization, validation, priority, dedup_key, AlternativeSolution, ProposalResult
- [x] `tests/test_config.py` — YAML loading, defaults, merging, new config models (Azure, Budget, Approval, WorkIQ)
- [x] `tests/test_pipeline.py` — Orchestration, PR sizing, proposal mode, approval gates, dedup
- [x] `tests/test_exceptions.py` — Exception hierarchy, GitHubAPIError, BudgetExceededError, ApprovalRequiredError
- [x] `tests/test_policies.py` — PolicyManager, path controls, env overrides, deep merge
- [x] `tests/test_observability.py` — ObservabilityProvider, AzureMonitorEmitter, SLA metrics

---

## 4. Phase 2 — Scanner Modules (Week 1–2)

### Step 4.1 — Base Scanner Interface & De-duplication

**Duration:** 1.5 days  
**Requirements covered:** FR-SCAN-001, FR-SCAN-002, BR-SCN-001, BR-SCN-003  
**Files:** `src/codecustodian/scanner/base.py`, `src/codecustodian/scanner/registry.py`, `src/codecustodian/scanner/deduplication.py`

**Tasks:**
- [x] **4.1.1** Implement `BaseScanner` ABC with:
  - `name`, `description`, `enabled` class attributes
  - `scan(repo_path: str) -> List[Finding]` abstract method
  - `is_excluded(file_path, exclude_patterns)` using `fnmatch`
  - `calculate_priority(finding) -> float` using the priority algorithm
- [x] **4.1.2** Implement priority algorithm (FR-SCAN-002):
  - `Priority = (severity_weight × urgency × impact) / effort`
  - Range 0–200; severity weights: critical=10, high=7, medium=4, low=2
- [x] **4.1.3** Implement `ScannerRegistry` for dynamic scanner discovery (BR-SCN-003):
  ```python
  class ScannerRegistry:
      """Marketplace-style catalog for scanner plugins."""
      _scanners: dict[str, type[BaseScanner]] = {}
      
      @classmethod
      def register(cls, scanner_class: type[BaseScanner]):
          cls._scanners[scanner_class.name] = scanner_class
      
      @classmethod
      def get_enabled(cls, config) -> list[BaseScanner]:
          return [s() for s in cls._scanners.values() if config.is_enabled(s.name)]
      
      @classmethod
      def list_catalog(cls) -> list[dict]:
          """List all available scanners with descriptions and outcomes."""
          return [{"name": s.name, "description": s.description, "detects": s.detects}
                  for s in cls._scanners.values()]
  ```
- [x] **4.1.4** Implement `FindingDeduplicator` (NEW — BR-SCN-001):
  ```python
  class FindingDeduplicator:
      """De-duplicate findings across runs to prevent noisy repeats."""
      
      def __init__(self, db_path: str = ".codecustodian/findings.db"):
          self.db = TinyDB(db_path)
      
      def dedup_key(self, finding: Finding) -> str:
          """Generate stable hash: type + file + line_range + description_hash."""
          content = f"{finding.type}:{finding.file}:{finding.line}:{hash(finding.description)}"
          return hashlib.sha256(content.encode()).hexdigest()[:16]
      
      def filter_new(self, findings: list[Finding]) -> list[Finding]:
          """Return only findings not seen in previous runs."""
          seen = {r["dedup_key"] for r in self.db.all()}
          new_findings = []
          for f in findings:
              key = self.dedup_key(f)
              if key not in seen:
                  new_findings.append(f)
                  self.db.insert({"dedup_key": key, "finding_id": f.id, "first_seen": datetime.utcnow().isoformat()})
          return new_findings
      
      def mark_resolved(self, finding_id: str):
          """Mark finding as resolved (for trend tracking)."""
          ...
  ```
- [x] **4.1.5** Implement file-walking utility respecting `.gitignore`, exclude patterns, and denylist (BR-CFG-002)

### Step 4.2 — Deprecated API Scanner

**Duration:** 2 days  
**Requirements covered:** FR-SCAN-010 through FR-SCAN-014, FR-SCAN-100  
**Files:** `src/codecustodian/scanner/deprecated_api.py`, `src/codecustodian/scanner/data/deprecations.json`

**Tasks:**
- [x] **4.2.1** Create deprecation database JSON (FR-SCAN-011):
  - **pandas**: `DataFrame.append`, `DataFrame.swaplevel`, `read_table` defaults
  - **numpy**: `np.matrix`, `np.bool`, `np.int`, `np.float`, `np.complex`, `np.object`, `np.str`
  - **os**: `os.popen`, `os.system`
  - **collections**: `collections.MutableMapping` → `collections.abc.MutableMapping`
  - **typing**: deprecated aliases (`typing.List` → `list` for Python 3.9+)
  - **unittest**: `assertEquals` → `assertEqual`
  - Each entry includes: `deprecated_in`, `removed_in`, `replacement`, `migration_guide_url` (FR-SCAN-100)
- [x] **4.2.2** Implement `DeprecatedAPIVisitor(ast.NodeVisitor)` (FR-SCAN-012)
- [x] **4.2.3** Implement import alias resolution
- [x] **4.2.4** Implement version-aware detection with urgency scoring (FR-SCAN-014)
- [x] **4.2.5** Implement usage frequency counting across repo (FR-SCAN-013)

### Step 4.3 — TODO Comment Scanner

**Duration:** 1 day  
**Requirements covered:** FR-SCAN-020 through FR-SCAN-023, FR-SCAN-103  
**File:** `src/codecustodian/scanner/todo_comments.py`

**Tasks:**
- [x] **4.3.1** Implement regex pattern matching for TODO, FIXME, HACK, XXX (FR-SCAN-021)
- [x] **4.3.2** Implement Git blame integration with age calculation (FR-SCAN-022)
- [x] **4.3.3** Implement age-based severity mapping
- [x] **4.3.4** Implement auto-issue creation flag for TODO > 90 days (FR-SCAN-023, FR-SCAN-103)
- [x] **4.3.5** Include author attribution from git blame (FR-SCAN-103)

### Step 4.4 — Code Smell Scanner

**Duration:** 1.5 days  
**Requirements covered:** FR-SCAN-030 through FR-SCAN-033, FR-SCAN-102  
**File:** `src/codecustodian/scanner/code_smells.py`

**Tasks:**
- [x] **4.4.1** Implement radon cyclomatic complexity integration (FR-SCAN-031)
- [x] **4.4.2** Implement cognitive complexity (Sonar-style) (NEW — FR-SCAN-102)
- [x] **4.4.3** Implement additional detectors: long functions, too many parameters, deep nesting, dead code
- [x] **4.4.4** Implement maintainability index composite score (NEW — FR-SCAN-102)
- [x] **4.4.5** Make all thresholds configurable (FR-SCAN-033)

### Step 4.5 — Security Pattern Scanner

**Duration:** 1.5 days  
**Requirements covered:** FR-SCAN-040 through FR-SCAN-043, FR-SCAN-101  
**File:** `src/codecustodian/scanner/security.py`

**Tasks:**
- [x] **4.5.1** Run Bandit as subprocess with JSON output (FR-SCAN-041)
- [x] **4.5.2** Implement custom security patterns: hardcoded secrets, weak crypto, SQL injection, command injection, deserialization, path traversal (FR-SCAN-042, FR-SCAN-101)
- [x] **4.5.3** Implement severity mapping with CWE references (FR-SCAN-043)
- [x] **4.5.4** Include exploit scenario description per finding (NEW — FR-SCAN-101)
- [x] **4.5.5** Include compliance impact per finding: PCI DSS, GDPR, SOC 2 (NEW — FR-SCAN-101)

### Step 4.6 — Type Coverage Scanner

**Duration:** 0.5 day  
**Requirements covered:** FR-SCAN-050 through FR-SCAN-052, FR-SCAN-104  
**File:** `src/codecustodian/scanner/type_coverage.py`

**Tasks:**
- [x] **4.6.1** Implement `TypeCoverageVisitor(ast.NodeVisitor)` (FR-SCAN-051)
- [x] **4.6.2** Implement per-file and overall coverage reporting (FR-SCAN-052)
- [x] **4.6.3** Implement AI-inferred type suggestions ranked by business value (FR-SCAN-104) *(stub — deferred to Phase 3)*

---

## 5. Phase 3 — AI Planner with GitHub Copilot SDK (Week 2)

> **GitHub Copilot SDK — Validated on PyPI (v0.1.23, released Feb 6, 2026):**
>
> The `github-copilot-sdk` package provides programmatic control of GitHub Copilot CLI via JSON-RPC with:
> - `CopilotClient` for session management (stdio and TCP transports)
> - `@define_tool` decorator with Pydantic models for type-safe tool definitions
> - Streaming with `assistant.message_delta` events
> - Custom providers (OpenAI, **Azure OpenAI**, Anthropic) — BYOK
> - Session hooks (`on_pre_tool_use`, `on_post_tool_use`, `on_error_occurred`)
> - Infinite sessions with automatic context compaction
>
> **Requirements:** Python 3.9+, GitHub Copilot CLI installed and accessible.
> SDK is in technical preview — wrap behind abstraction for future stability.

### Step 5.1 — Copilot SDK Client Integration

**Duration:** 2 days  
**Requirements covered:** FR-PLAN-001, FR-PLAN-002, FR-PLAN-100  
**Files:** `src/codecustodian/planner/copilot_client.py`, `src/codecustodian/planner/models.py`

**Tasks:**
- [x] **5.1.1** Implement `CopilotClientWrapper` using the real SDK:
  ```python
  import asyncio
  from copilot import CopilotClient
  
  class CopilotClientWrapper:
      """Wrapper around github-copilot-sdk for CodeCustodian AI planning."""
      
      def __init__(self, config: CopilotConfig):
          self.config = config
          self.client = CopilotClient({
              "log_level": "info",
              "auto_start": True,
              "auto_restart": True,
              "github_token": config.github_token,
          })
      
      async def start(self):
          await self.client.start()
      
      async def create_planning_session(self, model: str = "gpt-5", tools: list = None):
          """Create a multi-turn Copilot session for refactoring planning (FR-PLAN-100)."""
          session_config = {
              "model": model,
              "streaming": self.config.streaming,
              "tools": tools or [],
              "system_message": {"content": self._build_system_prompt()},
              "hooks": {
                  "on_pre_tool_use": self._on_pre_tool_use,
                  "on_post_tool_use": self._on_post_tool_use,
                  "on_error_occurred": self._on_error_occurred,
              },
          }
          
          # Use Azure OpenAI provider if configured (BYOK)
          if self.config.azure_provider:
              session_config["provider"] = {
                  "type": "azure",
                  "base_url": self.config.azure_provider.base_url,
                  "api_key": self.config.azure_provider.api_key,
                  "azure": {"api_version": "2024-10-21"},
              }
          
          if self.config.reasoning_effort and model in ["o1-preview", "o1", "gpt-5"]:
              session_config["reasoning_effort"] = self.config.reasoning_effort
          
          return await self.client.create_session(session_config)
      
      async def stop(self):
          await self.client.stop()
  ```

- [x] **5.1.2** Implement model selection strategy (FR-PLAN-002):
  - `"auto"`: simple → `gpt-4o-mini`, moderate → `gpt-4o`, complex → `gpt-5`
  - `"fast"`: always `gpt-4o-mini`
  - `"balanced"`: always `gpt-4o`
  - `"reasoning"`: `gpt-5` with `reasoning_effort: "high"`

- [x] **5.1.3** Implement cost tracking via event monitoring:
  - Track tokens per session, accumulate cost per run
  - Abort if `max_cost_per_run` exceeded → raise `BudgetExceededError`

- [x] **5.1.4** Implement streaming response handling:
  ```python
  done = asyncio.Event()
  full_response = []
  
  def on_event(event):
      if event.type.value == "assistant.message_delta":
          full_response.append(event.data.delta_content or "")
      elif event.type.value == "session.idle":
          done.set()
  
  session.on(on_event)
  await session.send({"prompt": prompt_text})
  await done.wait()
  ```

### Step 5.2 — Custom Tool Definitions with @define_tool

**Duration:** 2 days  
**Requirements covered:** FR-PLAN-010, FR-PLAN-011  
**File:** `src/codecustodian/planner/tools.py`

**Tasks:**
- [x] **5.2.1** Implement `get_function_definition` tool:
  ```python
  from pydantic import BaseModel, Field
  from copilot import define_tool
  
  class GetFunctionParams(BaseModel):
      file_path: str = Field(description="Path to the Python file")
      function_name: str = Field(description="Name of the function to retrieve")
  
  @define_tool(description="Get the full definition of a Python function with surrounding context")
  async def get_function_definition(params: GetFunctionParams) -> str:
      source = read_file(params.file_path)
      tree = ast.parse(source)
      for node in ast.walk(tree):
          if isinstance(node, ast.FunctionDef) and node.name == params.function_name:
              lines = source.splitlines()
              start = max(0, node.lineno - 6)
              end = min(len(lines), node.end_lineno + 5)
              return "\n".join(f"{i+1:4d} | {lines[i]}" for i in range(start, end))
      return f"Function '{params.function_name}' not found in {params.file_path}"
  ```
- [x] **5.2.2** Implement `find_test_coverage` tool
- [x] **5.2.3** Implement `search_references` tool
- [x] **5.2.4** Implement `get_imports` tool
- [x] **5.2.5** Implement `get_call_sites` tool
- [x] **5.2.6** Implement `check_type_hints` tool
- [x] **5.2.7** Implement `get_git_history` tool (NEW — for context gathering in Turn 2)
- [x] **5.2.8** Register all tools with the Copilot session

### Step 5.3 — Prompt Engineering

**Duration:** 1 day  
**Requirements covered:** FR-PLAN-020, FR-PLAN-021  
**File:** `src/codecustodian/planner/prompts.py`

**Tasks:**
- [x] **5.3.1** Implement system prompt template:
  - Core principles: preserve behavior, minimal changes, type safety, readability
  - Output JSON schema specification for `RefactoringPlan`
  - When confidence < threshold, output `ProposalResult` instead
  - When `enable_alternatives=True`, include 2-3 alternative approaches (FR-PLAN-102)
- [x] **5.3.2** Implement user prompt template — finding details, code context, function signature, imports
- [x] **5.3.3** Implement prompt variants per finding type
- [x] **5.3.4** Token budget management (truncate context if exceeding window)

### Step 5.4 — Alternative Solution Generation

**Duration:** 1 day  
**Requirements covered:** FR-PLAN-102  
**File:** `src/codecustodian/planner/alternatives.py`

**Tasks:**
- [x] **5.4.1** Implement `AlternativeGenerator`:
  ```python
  class AlternativeGenerator:
      """Generate 2-3 alternative refactoring approaches for complex findings."""
      
      async def generate_alternatives(
          self, finding: Finding, session, primary_plan: RefactoringPlan
      ) -> list[AlternativeSolution]:
          """For complex findings (complexity > threshold), request alternatives."""
          prompt = f"""You generated this refactoring plan: {primary_plan.summary}
          Now generate 2 alternative approaches with different tradeoffs.
          For each: name, description, pros, cons, changes, confidence."""
          
          response = await self._send_and_wait(session, prompt)
          return self._parse_alternatives(response)
      
      def select_recommended(self, alternatives: list[AlternativeSolution]) -> AlternativeSolution:
          """Mark the highest-confidence alternative as recommended."""
          ...
  ```
- [x] **5.4.2** Enable alternative generation only for complex findings (cyclomatic > 10 or multi-file)
- [x] **5.4.3** Include alternatives in PR description for engineer selection (FR-PLAN-102)

### Step 5.5 — Session Hooks, Confidence & Planner Orchestrator

**Duration:** 1 day  
**Requirements covered:** FR-PLAN-030, FR-PLAN-040, FR-PLAN-101  
**Files:** `src/codecustodian/planner/confidence.py`, `src/codecustodian/planner/planner.py`

**Tasks:**
- [x] **5.5.1** Implement session hooks for audit trail:
  ```python
  async def on_pre_tool_use(input, invocation):
      logger.info(f"Copilot calling tool: {input['toolName']}")
      return {"permissionDecision": "allow"}
  
  async def on_error_occurred(input, invocation):
      logger.error(f"Error in {input['errorContext']}: {input['error']}")
      return {"errorHandling": "retry"}
  ```

- [x] **5.5.2** Implement confidence scoring algorithm (FR-PLAN-101):
  - Score 1-10 with named factors: test_coverage, complexity, call_sites, logic_changes, multi_file
  - Automatic actions based on confidence:
    - **≥ 8**: Normal PR, auto-assign to team
    - **5–7**: Draft PR, request senior engineer review
    - **< 5**: Proposal-only mode (BR-PR-003) — create advisory issue, no code changes

- [x] **5.5.3** Implement reviewer effort estimation (NEW — BR-PR-002):
  - **Low**: single-file, direct replacement, confidence ≥ 8
  - **Medium**: multi-file or signature changes, confidence 5–7
  - **High**: complex logic, many call sites, confidence < 5

- [x] **5.5.4** Implement `Planner` orchestrator with multi-turn support (FR-PLAN-100):
  ```python
  class Planner:
      async def plan_refactoring(self, finding: Finding) -> RefactoringPlan | ProposalResult:
          session = await self.copilot.create_planning_session(
              model=self._select_model(finding),
              tools=self.tool_definitions,
          )
          
          # Turn 1: Initial assessment
          # Turn 2: Context gathering (AI uses tools)
          # Turn 3: Refactoring plan generation
          # Turn 4: Validation / clarifying questions if needed
          
          plan = await self._execute_planning_session(session, finding)
          plan.confidence_score = self._calculate_confidence(plan, finding)
          plan.reviewer_effort = self._estimate_effort(plan, finding)
          
          # Generate alternatives for complex findings
          if self.config.enable_alternatives and finding.complexity > 10:
              plan.alternatives = await self.alt_generator.generate_alternatives(
                  finding, session, plan
              )
          
          # Downgrade to proposal if confidence too low (BR-PR-003)
          if plan.confidence_score < self.config.proposal_mode_threshold:
              return self._convert_to_proposal(plan, finding)
          
          await session.destroy()
          return plan
  ```

**Tests to write for Phase 3:**
- [x] `tests/unit/test_planner.py` — Mock CopilotClient, parsing, confidence, proposal mode
- [x] `tests/unit/test_tools.py` — Each tool with fixture repos
- [x] `tests/unit/test_alternatives.py` — Alternative generation and selection

---

## 6. Phase 4 — Executor & Verifier (Week 2)

### Step 6.1 — Pre-Execution Safety Checks

**Duration:** 1 day  
**Requirements covered:** FR-EXEC-101 (NEW)  
**File:** `src/codecustodian/executor/safety_checks.py`

> **5-Point Safety System (from business-requirements.md FR-EXEC-101):** Every refactoring must pass ALL checks before execution begins. Failure on any check aborts or downgrades to proposal mode.

**Tasks:**
- [x] **6.1.1** Implement `SafetyCheckRunner`:
  ```python
  class SafetyCheckRunner:
      """5-point pre-execution safety system (FR-EXEC-101)."""
      
      async def run_all_checks(self, plan: RefactoringPlan, finding: Finding) -> SafetyResult:
          results = []
          results.append(await self.check_syntax(plan))
          results.append(await self.check_import_availability(plan))
          results.append(await self.check_critical_path(plan, finding))
          results.append(await self.check_concurrent_changes(plan))
          results.append(await self.check_secrets(plan))
          
          if any(r.failed for r in results):
              return SafetyResult(passed=False, failures=results, action="abort_or_propose")
          return SafetyResult(passed=True, failures=[], action="proceed")
  ```

- [x] **6.1.2** **Check 1 — Syntax Validation**: Parse new code with `ast.parse()`, reject if syntax errors
- [x] **6.1.3** **Check 2 — Import Availability**: Verify all imports in new code are available, check for typos
- [x] **6.1.4** **Check 3 — Critical Path Protection**: Identify critical files (`main.py`, `__init__.py`, API endpoints); require confidence ≥ 9 for critical files; escalate to senior review
- [x] **6.1.5** **Check 4 — Concurrent Change Detection**: Check if file modified since scan (git SHA mismatch); abort and re-scan if stale
- [x] **6.1.6** **Check 5 — Secrets Detection**: Scan new code for hardcoded secrets (API keys, passwords, tokens); block if found; alert security team

### Step 6.2 — Safe File Editor

**Duration:** 1.5 days  
**Requirements covered:** FR-EXEC-001, FR-EXEC-002, FR-EXEC-100  
**Files:** `src/codecustodian/executor/file_editor.py`, `src/codecustodian/executor/backup.py`

**Tasks:**
- [x] **6.2.1** Implement `SafeFileEditor.apply_changes()`:
  1. Run 5-point safety checks (6.1)
  2. Create timestamped backup in `.codecustodian-backups/`
  3. Validate `old_code` appears exactly once
  4. Replace `old_code` with `new_code`
  5. Validate syntax using `ast.parse()`
  6. Atomic write via temp file + rename
  7. On error: restore from backup
- [x] **6.2.2** Implement backup retention policy (7 days default)
- [x] **6.2.3** Implement multi-file change support with **atomic rollback** (FR-EXEC-100):
  - All files succeed or all revert
  - Transaction log for forensic analysis
- [x] **6.2.4** Handle edge cases (read-only, binary, encoding, >10MB)

### Step 6.3 — Git Workflow Manager

**Duration:** 1.5 days  
**Requirements covered:** FR-EXEC-010  
**File:** `src/codecustodian/executor/git_manager.py`

**Tasks:**
- [x] **6.3.1** Implement `create_refactoring_branch()`: `tech-debt/{category}-{file}-{timestamp}`
- [x] **6.3.2** Implement `commit_changes()`: conventional commit with `Co-authored-by: CodeCustodian`
- [x] **6.3.3** Implement `push_branch()` with auth error handling
- [x] **6.3.4** Implement cleanup (switch back, delete local branch)

### Step 6.4 — Test Runner (Verifier)

**Duration:** 1 day  
**Requirements covered:** FR-VERIFY-001, FR-VERIFY-002, FR-VERIFY-100  
**File:** `src/codecustodian/verifier/test_runner.py`

**Tasks:**
- [x] **6.4.1** Test discovery: convention (`test_<filename>.py`), pattern (`test_*.py`), full suite for critical files
- [x] **6.4.2** `pytest.main()` execution with coverage, JUnit XML, 5-minute timeout, 4 workers
- [x] **6.4.3** Parse JUnit XML results
- [x] **6.4.4** Coverage delta calculation — reject if coverage decreases
- [x] **6.4.5** Distinguish pre-existing failures from new failures (FR-VERIFY-100)

### Step 6.5 — Linting & Security Verification Pipeline

**Duration:** 1.5 days  
**Requirements covered:** FR-VERIFY-010, FR-VERIFY-101, FR-VERIFY-102  
**Files:** `src/codecustodian/verifier/linter.py`, `src/codecustodian/verifier/security_scanner.py`

**Tasks:**
- [x] **6.5.1** `_run_ruff()` — subprocess + JSON parse (FR-VERIFY-101)
- [x] **6.5.2** `_run_mypy()` — subprocess + JSON parse (FR-VERIFY-101)
- [x] **6.5.3** `_run_bandit()` — subprocess + JSON parse (FR-VERIFY-101)
- [x] **6.5.4** Baseline comparison (only fail on NEW violations)
- [x] **6.5.5** Implement enhanced security scanning (NEW — FR-VERIFY-102):
  ```python
  class SecurityScanner:
      async def scan_containers(self, dockerfile_path: str) -> list:
          """Trivy container scanning for CVEs in base images."""
          result = subprocess.run(["trivy", "image", "--format", "json", ...])
          ...
      
      async def scan_secrets(self, repo_path: str) -> list:
          """TruffleHog secrets scanning."""
          result = subprocess.run(["trufflehog", "filesystem", "--json", repo_path])
          ...
      
      async def scan_dependencies(self, requirements_path: str) -> list:
          """Check for known vulnerable package versions."""
          ...
      
      def generate_sarif(self, findings: list) -> dict:
          """Generate SARIF report for GitHub Security tab."""
          ...
  ```

---

## 7. Phase 5 — GitHub & Azure DevOps Integration (Week 3)

### Step 7.1 — PR Creator with Rich Narrative

**Duration:** 1.5 days  
**Requirements covered:** FR-GITHUB-001, FR-UX-100, BR-PR-001, BR-PR-002  
**File:** `src/codecustodian/integrations/github_integration/pr_creator.py`

**Tasks:**
- [ ] **7.1.1** Initialize PyGithub client, validate token
- [ ] **7.1.2** `create_pr()` with comprehensive narrative template (BR-PR-001):
  - Summary, Finding details, AI Reasoning, Changes, Risks
  - Verification results (tests, linting, security)
  - Confidence score with factor breakdown
  - Reviewer effort estimate (low/medium/high) (BR-PR-002)
  - Alternatives section if generated (FR-PLAN-102)
  - Work IQ expert recommendation
  - Cost and time-saved estimate
- [ ] **7.1.3** Set `draft=True` if confidence < 7, add comprehensive labels (FR-UX-101):
  - Category: `tech-debt`, `security`, `performance`
  - Priority: `P1-critical`, `P2-high`, `P3-medium`, `P4-low`
  - Status: `ready-for-review`, `draft`, `needs-senior-review`
  - Risk: `low-risk`, `medium-risk`, `high-risk`
  - Effort: `effort-low`, `effort-medium`, `effort-high`
  - Confidence: `confidence-high`, `confidence-medium`, `confidence-low`
- [ ] **7.1.4** Implement proposal-only creation (BR-PR-003):
  - Create GitHub Issue (not PR) with step-by-step remediation guidance
  - Label as `proposal`, include recommended steps and estimated effort

### Step 7.2 — PR Interaction Bot

**Duration:** 1.5 days  
**Requirements covered:** FR-UX-100, BR-NOT-002 (NEW)  
**File:** `src/codecustodian/integrations/github_integration/pr_interaction.py`

> **NEW from business-requirements.md:** Engineers should be able to interact with CodeCustodian via PR comments. This enables clarification, modification requests, and feedback without leaving GitHub.

**Tasks:**
- [ ] **7.2.1** Implement webhook listener for PR comment events:
  ```python
  class PRInteractionBot:
      COMMANDS = {
          "why": self._explain_decision,
          "alternatives": self._show_alternatives,
          "modify": self._modify_pr,
          "feedback": self._record_feedback,
          "smaller": self._split_pr,
          "propose": self._convert_to_proposal,
      }
      
      async def handle_comment(self, comment: str, pr_number: int):
          """Parse @codecustodian commands from PR comments."""
          if not comment.strip().startswith("@codecustodian"):
              return
          command = self._parse_command(comment)
          handler = self.COMMANDS.get(command.action)
          if handler:
              response = await handler(command, pr_number)
              await self.github.create_pr_comment(pr_number, response)
  ```
- [ ] **7.2.2** `@codecustodian why` — Explain AI reasoning for specific change
- [ ] **7.2.3** `@codecustodian alternatives` — Show alternative approaches
- [ ] **7.2.4** `@codecustodian modify <instruction>` — Re-generate plan with modification
- [ ] **7.2.5** `@codecustodian feedback: <preference>` — Record team/engineer preference (FR-LEARN-100)
- [ ] **7.2.6** `@codecustodian smaller` — Auto-split PR into smaller PRs (BR-PLN-002)
- [ ] **7.2.7** `@codecustodian propose` — Convert PR to proposal-only

### Step 7.3 — Issue Creator & PR Comments

**Duration:** 0.5 day  
**Requirements covered:** FR-GITHUB-010  
**Files:** `src/codecustodian/integrations/github_integration/issues.py`, `src/codecustodian/integrations/github_integration/comments.py`

**Tasks:**
- [ ] **7.3.1** `create_issue_from_todo()` with duplicate detection
- [ ] **7.3.2** Inline PR comments with AI reasoning
- [ ] **7.3.3** Summary comment with audit trail (`<details>` block)

### Step 7.4 — Azure DevOps Integration

**Duration:** 1.5 days  
**Requirements covered:** FR-AZURE-001, FR-AZURE-100, FR-AZURE-101  
**File:** `src/codecustodian/integrations/azure_devops.py`

**Tasks:**
- [ ] **7.4.1** Implement `AzureDevOpsIntegration` class:
  ```python
  from azure.devops.connection import Connection
  from msrest.authentication import BasicAuthentication
  
  class AzureDevOpsIntegration:
      def __init__(self, organization_url: str, pat: str):
          credentials = BasicAuthentication('', pat)
          self.connection = Connection(base_url=organization_url, creds=credentials)
          self.work_item_client = self.connection.clients.get_work_item_tracking_client()
          self.git_client = self.connection.clients.get_git_client()
  ```

- [ ] **7.4.2** Implement `create_work_item_from_finding()` (FR-AZURE-100):
  - Priority mapping: 150-200 → P1, 100-150 → P2, 50-100 → P3, 0-50 → P4
  - Tags: `tech-debt`, `codecustodian`, `automated`, `<finding-type>`
  - Assigned To: original code author from git blame
  - Lifecycle: Created → In Progress (PR created) → Done (PR merged) → Closed (finding gone)
- [ ] **7.4.3** Implement `link_pr_to_work_item()`: bidirectional artifact link
- [ ] **7.4.4** Implement `update_sprint_board()`: move items between states based on PR status
- [ ] **7.4.5** Implement Azure Repos PR creation (NEW — FR-AZURE-101):
  - For teams using Azure Repos instead of GitHub
  - Respect existing branch policies (required reviewers, build validation)
  - AI responds to reviewer comments via Copilot SDK

---

## 8. Phase 6 — MCP Server with FastMCP (Week 3)

> **FastMCP v2.14.5 — Validated on PyPI (released Feb 3, 2026):**
>
> FastMCP is the standard production-ready framework for MCP servers by Prefect.
> - `from fastmcp import FastMCP` — standalone import
> - `@mcp.tool` decorator with automatic JSON Schema generation
> - Enterprise auth (Azure, GitHub, Auth0), Streamable HTTP, proxy, composition
> - `Context` for logging, progress, LLM sampling
> - In-memory testing via `Client(mcp)` — no process/network needed
> - Pin to `fastmcp<3` (v3.0 in beta)

### Step 8.1 — FastMCP Server Scaffold

**Duration:** 1 day  
**Requirements covered:** FR-EXT-001  
**File:** `src/codecustodian/mcp/server.py`

**Tasks:**
- [ ] **8.1.1** Initialize FastMCP server:
  ```python
  from fastmcp import FastMCP, Context
  
  mcp = FastMCP(name="CodeCustodian")
  ```
- [ ] **8.1.2** Add health check custom route for Azure Container Apps
- [ ] **8.1.3** Add stdio and HTTP entry points

### Step 8.2 — Expose Scanners as MCP Tools

**Duration:** 2 days  
**Requirements covered:** FR-EXT-001  
**File:** `src/codecustodian/mcp/tools.py`

**Tasks:**
- [ ] **8.2.1** Implement `scan_repository` tool (readOnlyHint)
- [ ] **8.2.2** Implement `plan_refactoring` tool with alternatives support
- [ ] **8.2.3** Implement `apply_refactoring` tool (destructiveHint)
- [ ] **8.2.4** Implement `verify_changes` tool (readOnlyHint)
- [ ] **8.2.5** Implement `create_pull_request` tool (destructiveHint)
- [ ] **8.2.6** Implement `calculate_roi` tool (readOnlyHint)
- [ ] **8.2.7** Implement `get_business_impact` tool (NEW — FR-PRIORITY-100)
- [ ] **8.2.8** Implement `list_scanners` tool (NEW — BR-SCN-003 marketplace catalog)

### Step 8.3 — Expose Findings as MCP Resources

**Duration:** 0.5 day  
**File:** `src/codecustodian/mcp/resources.py`

**Tasks:**
- [ ] **8.3.1** Implement `findings://{repo_name}/all` resource
- [ ] **8.3.2** Implement `findings://{repo_name}/{finding_type}` resource
- [ ] **8.3.3** Implement `config://settings` resource
- [ ] **8.3.4** Implement `dashboard://{team_name}/summary` resource (NEW — FR-UX-200)
- [ ] **8.3.5** Implement scan history resource

### Step 8.4 — MCP Prompts

**Duration:** 0.5 day  
**File:** `src/codecustodian/mcp/prompts.py`

**Tasks:**
- [ ] **8.4.1** Implement `refactor_finding` prompt
- [ ] **8.4.2** Implement `scan_summary` prompt
- [ ] **8.4.3** Implement `roi_report` prompt (NEW)
- [ ] **8.4.4** Implement `onboard_repo` prompt (NEW — BR-ONB-001)

### Step 8.5 — MCP Server Deployment & Testing

**Duration:** 0.5 day

**Tasks:**
- [ ] **8.5.1** Test with FastMCP CLI: `fastmcp run src/codecustodian/mcp/server.py`
- [ ] **8.5.2** Test with in-memory `Client(mcp)` pattern
- [ ] **8.5.3** Test with Claude Desktop (stdio)
- [ ] **8.5.4** Test HTTP transport for remote deployment

---

## 9. Phase 7 — Azure Integrations & Enterprise Features (Week 3)

### Step 9.1 — Microsoft Work IQ MCP Integration

**Duration:** 1.5 days  
**Requirements covered:** FR-WORKIQ-100, FR-WORKIQ-101, FR-WORKIQ-102 (15 bonus points!)  
**File:** `src/codecustodian/integrations/work_iq.py`

**Tasks:**
- [ ] **9.1.1** Implement `WorkIQContextProvider`:
  - `get_expert_for_finding()` — Expert identification with capacity check (FR-WORKIQ-100)
  - `get_sprint_context()` — Sprint status, velocity, incidents (FR-WORKIQ-101)
  - `should_create_pr_now()` — Sprint-aware PR timing (defer during crunch)
  - `get_organizational_context()` — Dependency check, roadmap alignment, team expertise (FR-WORKIQ-102)
- [ ] **9.1.2** Create `mcp.json` configuration file
- [ ] **9.1.3** Integrate Work IQ into pipeline: auto-assign PRs, defer PRs, skip during incidents, align with roadmap

### Step 9.2 — Budget Manager

**Duration:** 0.5 day  
**Requirements covered:** FR-COST-100 (NEW)  
**File:** `src/codecustodian/enterprise/budget_manager.py`

**Tasks:**
- [ ] **9.2.1** Implement `BudgetManager`:
  ```python
  class BudgetManager:
      """Per-team budget tracking with alerts and enforcement (FR-COST-100)."""
      
      def __init__(self, team_id: str, monthly_budget: float, alert_thresholds: list):
          self.team_id = team_id
          self.monthly_budget = monthly_budget
          self.alert_thresholds = alert_thresholds  # [50, 80, 90, 100]
          self.spent = 0.0
      
      def record_cost(self, amount: float, description: str):
          self.spent += amount
          pct = (self.spent / self.monthly_budget) * 100
          for threshold in self.alert_thresholds:
              if pct >= threshold and not self._alert_sent(threshold):
                  self._send_alert(threshold, pct)
          if pct >= 100 and self.hard_limit:
              raise BudgetExceededError(f"Team {self.team_id} budget exhausted: ${self.spent:.2f}/${self.monthly_budget:.2f}")
      
      def get_summary(self) -> dict:
          return {
              "spent": self.spent,
              "budget": self.monthly_budget,
              "remaining": self.monthly_budget - self.spent,
              "utilization_pct": (self.spent / self.monthly_budget) * 100,
              "cost_per_pr": self.spent / max(self.pr_count, 1),
              "projection": self._project_end_of_month(),
          }
  ```

### Step 9.3 — ROI Calculator & Reporting

**Duration:** 0.5 day  
**Requirements covered:** FR-COST-101, BR-RPT-003  
**File:** `src/codecustodian/enterprise/roi_calculator.py`

**Tasks:**
- [ ] **9.3.1** Implement `ROICalculator` with configurable labor cost assumptions (BR-RPT-003):
  - Costs: API + infrastructure + setup
  - Savings: hours saved × cost/hour × automation rate
  - Outputs: net savings, payback period, annual ROI %, productivity gain %
- [ ] **9.3.2** Implement monthly ROI report generation (exportable PDF/CSV)
- [ ] **9.3.3** Implement before/after comparison summaries (BR-RPT-003)

### Step 9.4 — Multi-Tenant, RBAC & Approval Workflows

**Duration:** 1.5 days  
**Requirements covered:** BR-ENT-001, FR-SEC-101, BR-GOV-001, BR-GOV-002  
**Files:** `src/codecustodian/enterprise/multi_tenant.py`, `src/codecustodian/enterprise/rbac.py`, `src/codecustodian/enterprise/approval_workflows.py`

**Tasks:**
- [ ] **9.4.1** Implement `MultiTenantManager` (BR-ENT-001):
  - Team registration with isolated configs, budgets, Azure DevOps project mapping
  - Cross-tenant data access prevention
- [ ] **9.4.2** Implement `RBACManager` with Azure AD (FR-SEC-101, BR-GOV-001):
  - Roles: VIEWER, CONTRIBUTOR (approve PRs), ADMIN (configure scanners, budgets), SECURITY_ADMIN (override security blocks)
  - Scoped per org/team/repo
  - Permission enforcement on every API request
- [ ] **9.4.3** Implement `ApprovalWorkflowManager` (NEW — BR-GOV-002):
  ```python
  class ApprovalWorkflowManager:
      """Policy-driven approval gates for plan and PR creation."""
      
      async def request_plan_approval(self, plan: RefactoringPlan, repo: str) -> bool:
          """For sensitive repos/categories, pause and request approval before execution."""
          if self._requires_plan_approval(repo, plan.finding_type):
              approval = await self._create_approval_request(plan)
              await self._notify_approvers(approval)
              return await self._wait_for_approval(approval, timeout=3600)
          return True  # Auto-approved
      
      def _requires_plan_approval(self, repo: str, finding_type: str) -> bool:
          """Check policy: does this repo/category need plan approval?"""
          policy = self.policy_manager.get_effective_policy(repo)
          return repo in policy.get("approval_required_repos", []) or \
                 finding_type in policy.get("approval_required_categories", [])
  ```

### Step 9.5 — Secrets Manager & Azure Key Vault

**Duration:** 0.5 day  
**Requirements covered:** FR-SEC-102 (NEW)  
**File:** `src/codecustodian/enterprise/secrets_manager.py`

**Tasks:**
- [ ] **9.5.1** Implement `SecretsManager`:
  ```python
  from azure.keyvault.secrets import SecretClient
  from azure.identity import DefaultAzureCredential
  
  class SecretsManager:
      """Azure Key Vault integration — no secrets in env vars or source (FR-SEC-102)."""
      
      def __init__(self, vault_name: str):
          vault_url = f"https://{vault_name}.vault.azure.net"
          self.client = SecretClient(vault_url=vault_url, credential=DefaultAzureCredential())
      
      def get_secret(self, name: str) -> str:
          return self.client.get_secret(name).value
      
      def get_github_token(self) -> str:
          return self.get_secret("github-token")
      
      def get_copilot_token(self) -> str:
          return self.get_secret("copilot-token")
      
      def get_devops_pat(self) -> str:
          return self.get_secret("devops-pat")
  ```
- [ ] **9.5.2** Integrate with Container App managed identity
- [ ] **9.5.3** Secret access logging for audit trail

### Step 9.6 — Notification Engine

**Duration:** 0.5 day  
**Requirements covered:** BR-NOT-001 (NEW)  
**File:** `src/codecustodian/intelligence/notifications.py`

**Tasks:**
- [ ] **9.6.1** Implement `NotificationEngine`:
  ```python
  class NotificationEngine:
      """Configurable notification system (BR-NOT-001)."""
      
      async def notify(self, event_type: str, payload: dict):
          """Route notifications based on config."""
          config = self.config.notifications
          if event_type not in config.events:
              return
          
          for channel in config.channels:
              if channel == "github":
                  await self._github_notification(event_type, payload)
              elif channel == "email":
                  await self._email_notification(event_type, payload)
              elif channel == "teams":
                  await self._teams_webhook(event_type, payload)
      
      # Event types: new_pr, high_severity_finding, validation_failure,
      #              approval_requested, budget_alert, scan_complete
  ```

### Step 9.7 — Azure Container Apps Deployment

**Duration:** 0.5 day  
**Requirements covered:** FR-DEPLOY-100

**Tasks:**
- [ ] **9.7.1** Create `Dockerfile`
- [ ] **9.7.2** Create `scripts/deploy-to-azure.sh` one-click deployment (FR-DEPLOY-100):
  - Create resource group, ACR, Container App
  - Configure Key Vault with managed identity
  - Set up Azure Monitor workspace
  - Deploy dashboards
  - Health check verification
  - Auto-scaling: 1-10 instances, scale-to-zero when idle
- [ ] **9.7.3** Create `.github/workflows/deploy-azure.yml`

---

## 10. Phase 8 — Business Intelligence, Feedback & Learning (Week 3–4)

> **NEW PHASE — from business-requirements.md:** These capabilities make CodeCustodian a continuously improving platform rather than a static tool. Feedback loops, business impact scoring, and dynamic re-prioritization are key differentiators from competitors (Byteable AI, AutoCodeRover, Moderne).

### Step 10.1 — Business Impact Scoring

**Duration:** 1 day  
**Requirements covered:** FR-PRIORITY-100 (NEW)  
**File:** `src/codecustodian/intelligence/business_impact.py`

**Tasks:**
- [ ] **10.1.1** Implement 5-factor `BusinessImpactScorer`:
  ```python
  class BusinessImpactScorer:
      """5-factor business impact scoring (FR-PRIORITY-100).
      
      Score = (Usage × 100) + (Criticality × 50) + (ChangeFreq × 30) 
              + (VelocityImpact × 40) + (RegulatoryRisk × 80)
      """
      
      async def score(self, finding: Finding, repo_path: str) -> float:
          usage = await self._get_usage_frequency(finding)         # Telemetry
          criticality = self._get_criticality(finding)             # Critical path analysis
          change_freq = self._get_change_frequency(finding)        # Git history
          velocity = await self._get_velocity_impact(finding)      # Azure DevOps blocked items
          regulatory = self._get_regulatory_risk(finding)          # PII/financial annotation
          
          return (usage * 100) + (criticality * 50) + (change_freq * 30) + \
                 (velocity * 40) + (regulatory * 80)
      
      def _get_criticality(self, finding: Finding) -> float:
          """Identify critical path code: payments, auth, data processing."""
          critical_patterns = ["payment", "auth", "billing", "security", "crypto"]
          if any(p in finding.file.lower() for p in critical_patterns):
              return 10.0
          return 3.0
      
      def _get_regulatory_risk(self, finding: Finding) -> float:
          """Check for PII, financial data, healthcare records handling."""
          regulated_patterns = ["pii", "credit_card", "ssn", "hipaa", "gdpr"]
          ...
  ```

### Step 10.2 — Dynamic Re-Prioritization

**Duration:** 0.5 day  
**Requirements covered:** FR-PRIORITY-101 (NEW)  
**File:** `src/codecustodian/intelligence/reprioritization.py`

**Tasks:**
- [ ] **10.2.1** Implement event-driven re-prioritization:
  ```python
  class DynamicReprioritizer:
      """Re-evaluate priorities based on changing context (FR-PRIORITY-101)."""
      
      async def handle_event(self, event_type: str, payload: dict):
          if event_type == "production_incident":
              # Elevate all findings in affected file
              await self._elevate_file_findings(payload["file_path"], boost=200)
          elif event_type == "cve_announced":
              # Re-scan for affected patterns, create emergency PRs
              await self._emergency_security_scan(payload["cve_id"])
          elif event_type == "deadline_approaching":
              # Elevate deprecation warnings for upcoming library upgrade
              await self._elevate_library_findings(payload["library"])
          elif event_type == "budget_exceeded":
              # Pause non-critical, continue only high-priority
              await self._pause_non_critical()
          elif event_type == "team_capacity_change":
              # Adjust PR creation rate based on Work IQ
              await self._adjust_rate(payload["team_id"])
  ```

### Step 10.3 — Feedback Loop & Learning System

**Duration:** 1.5 days  
**Requirements covered:** FR-LEARN-100, FR-LEARN-101, BR-NOT-002 (NEW)  
**Files:** `src/codecustodian/feedback/learning.py`, `src/codecustodian/feedback/history.py`, `src/codecustodian/feedback/preferences.py`

**Tasks:**
- [ ] **10.3.1** Implement `FeedbackCollector` (FR-LEARN-100):
  ```python
  class FeedbackCollector:
      """Track PR outcomes to learn and improve over time."""
      
      def __init__(self, db: TinyDB):
          self.db = db
      
      def record_outcome(self, pr_number: int, outcome: dict):
          """Record: accepted, rejected, modified-before-merge."""
          self.db.insert({
              "pr_number": pr_number,
              "outcome": outcome["status"],       # merged | rejected | modified
              "confidence_was": outcome["confidence"],
              "modifications": outcome.get("modifications", []),
              "reviewer": outcome.get("reviewer"),
              "review_time_hours": outcome.get("review_time"),
              "timestamp": datetime.utcnow().isoformat(),
          })
      
      def get_scanner_success_rate(self, scanner_type: str) -> float:
          """If scanner has < 90% success → increase confidence threshold."""
          records = self.db.search(where("scanner_type") == scanner_type)
          merged = len([r for r in records if r["outcome"] == "merged"])
          return merged / max(len(records), 1)
  ```

- [ ] **10.3.2** Implement `PreferenceStore` (from `@codecustodian feedback` commands):
  ```python
  class PreferenceStore:
      """Store team/engineer preferences learned from feedback."""
      
      def record_preference(self, team_or_user: str, preference: str):
          """e.g., 'prefer async/await over callbacks'"""
          ...
      
      def get_preferences(self, team: str, user: str = None) -> list[str]:
          """Return all learned preferences for prompt injection."""
          ...
  ```

- [ ] **10.3.3** Implement `HistoricalPatternRecognizer` (FR-LEARN-101):
  ```python
  class HistoricalPatternRecognizer:
      """Query historical refactorings across org for similar patterns."""
      
      async def find_similar(self, finding: Finding) -> list[dict]:
          """Find similar past refactorings and their outcomes."""
          # Search by finding type + library + pattern
          similar = self.db.search(
              (where("finding_type") == finding.type) &
              (where("library") == finding.metadata.get("library"))
          )
          return [{
              "team": r["team"],
              "success_rate": r["success_rate"],
              "common_modifications": r["modifications"],
              "recommendation": r["learned_recommendation"],
          } for r in similar]
  ```

- [ ] **10.3.4** Inject learned preferences into Copilot SDK prompts:
  - Append team preferences to system prompt
  - Include similar historical patterns as context
  - Auto-adjust confidence thresholds based on scanner success rates

### Step 10.4 — SLA & Reliability Reporting

**Duration:** 0.5 day  
**Requirements covered:** BR-ENT-002 (NEW)  
**File:** `src/codecustodian/enterprise/sla_reporter.py`

**Tasks:**
- [ ] **10.4.1** Implement `SLAReporter`:
  - Track: run success rate, average time to PR, failure reasons, failure trends
  - Alert on abnormal failure spikes
  - Dashboard metrics export to Azure Monitor

---

## 11. Phase 9 — Security, RAI & Observability (Week 4)

### Step 11.1 — Security Hardening

**Duration:** 1 day  
**Requirements covered:** FR-SEC-001 through FR-SEC-003, FR-SEC-100

**Tasks:**
- [ ] **11.1.1** Secrets management: Azure Key Vault (9.5), mask tokens in logs, validate at startup
- [ ] **11.1.2** Code execution safety: path traversal prevention, 10MB limit, no `eval`
- [ ] **11.1.3** Complete audit trail (FR-SEC-100): JSON log with SHA-256 hashing for every action:
  - timestamp, event_type, finding_id, file_path, actor, changes, ai_reasoning, confidence_score, verification results, pr_number, approver, merge_date
  - Primary: Azure Monitor Logs (KQL queryable)
  - Backup: Azure Blob Storage (immutable, 7-year retention configurable)
- [ ] **11.1.4** Run Bandit on CodeCustodian's own codebase
- [ ] **11.1.5** Add `SECURITY.md`

### Step 11.2 — Responsible AI Compliance

**Duration:** 0.5 day  
**Requirements covered:** FR-SEC-001 (RAI — 15 pts)

**Tasks:**
- [ ] **11.2.1** Create `docs/RESPONSIBLE_AI.md`:
  - **Human-in-the-loop**: All refactorings require human review before merge
  - **Explainability**: Every PR includes detailed AI reasoning from Copilot SDK
  - **Confidence scoring**: 1-10 with factor breakdown
  - **Fairness**: PRs assigned by expertise (Work IQ), not seniority
  - **Privacy**: Code never leaves tenant, token minimization
  - **Safety**: Rollback, test verification, manual override, fail-safe, 5-point safety checks
  - **Accountability**: Co-authored-by traceability, audit logs, SHA-256 hashes
  - **Proposal mode**: AI knows when to defer to humans (confidence < 5)

### Step 11.3 — Observability Dashboard

**Duration:** 0.5 day  
**Requirements covered:** FR-OBS-100, FR-OBS-101

**Tasks:**
- [ ] **11.3.1** Create Azure Monitor dashboard definition (ARM template):
  - **Widget 1**: Findings over time by type (line chart)
  - **Widget 2**: PR success rate (target 95%+)
  - **Widget 3**: Cost savings (weekly, cumulative)
  - **Widget 4**: Confidence score distribution (histogram)
  - **Widget 5**: Verification pass rate + MTTR
  - **Widget 6**: ROI metrics (hours saved, cost per PR, payback)
  - **Widget 7**: Budget utilization per team (NEW — FR-COST-100)
  - **Widget 8**: SLA metrics (run success rate, time-to-PR) (NEW — BR-ENT-002)
- [ ] **11.3.2** Configure alerts:
  - PR success rate below 90% → increase confidence threshold
  - Cost exceeds budget → pause non-critical
  - High-severity finding spike → notify security
  - Pipeline failure rate > 10% → ops alert

---

## 12. Phase 10 — Testing, CLI & Polish (Week 4)

### Step 12.1 — CLI Implementation

**Duration:** 2 days  
**Requirements covered:** FR-CLI-001, FR-UX-300  
**File:** `src/codecustodian/cli/main.py`

**Tasks:**
- [ ] **12.1.1** `run` command: `--repo-path`, `--config`, `--max-prs`, `--scan-type`, `--dry-run`, `--enable-work-iq`, `--azure-devops-project`, `--output-format json`
- [ ] **12.1.2** `init` command: create `.codecustodian.yml` + workflow, select policy template (BR-ONB-001/002)
- [ ] **12.1.3** `validate` command: check config
- [ ] **12.1.4** `scan` command: scanner-only with Rich table + JSON/CSV export
- [ ] **12.1.5** `onboard` command: org/repo onboarding with status display (NEW — BR-ONB-001)
- [ ] **12.1.6** `status` command: show findings, PRs, budget, SLA metrics (NEW)
- [ ] **12.1.7** `report` command: generate ROI report in PDF/CSV (NEW — BR-RPT-001)
- [ ] **12.1.8** `findings` command: filter by type, severity, status (NEW)
- [ ] **12.1.9** `create-prs` command: create PRs for top N findings
- [ ] **12.1.10** `version` and `help` commands
- [ ] **12.1.11** **Interactive mode** (NEW — FR-UX-300):
  ```python
  @app.command()
  def interactive():
      """Launch interactive menu-driven mode."""
      from InquirerPy import inquirer
      
      while True:
          action = inquirer.select(
              message="What would you like to do?",
              choices=[
                  "Show high-priority findings",
                  "Create PRs for top 5 findings",
                  "View cost summary & ROI",
                  "Configure scanners",
                  "View scan history",
                  "Generate report",
                  "Exit",
              ],
          ).execute()
          
          if action == "Exit":
              break
          # Route to appropriate handler...
  ```

### Step 12.2 — Comprehensive Testing

**Duration:** 2 days  
**Requirements covered:** FR-TEST-001 through FR-TEST-003

**Tasks:**
- [ ] **12.2.1** Achieve 80%+ coverage, 90%+ for executor and verifier
- [ ] **12.2.2** Integration tests: pipeline with fixture repo, mock Copilot SDK, real Git
- [ ] **12.2.3** E2E test: full workflow with real fixture repository
- [ ] **12.2.4** FastMCP in-memory testing with `Client(mcp)`
- [ ] **12.2.5** Test: proposal mode (confidence < 5 → issue, not PR)
- [ ] **12.2.6** Test: PR sizing (auto-split when limits exceeded)
- [ ] **12.2.7** Test: finding de-duplication across runs
- [ ] **12.2.8** Test: budget enforcement (BudgetExceededError)
- [ ] **12.2.9** Test: approval workflows (pause awaiting approval)
- [ ] **12.2.10** Test: safety checks (5-point system, abort on failure)
- [ ] **12.2.11** Create fixture repositories with known issues

### Step 12.3 — Documentation

**Duration:** 1 day

**Tasks:**
- [ ] **12.3.1** Write top-level `README.md`: quick start, architecture diagram, setup, competitive advantages
- [ ] **12.3.2** Write `docs/ARCHITECTURE.md` with pipeline, integrations, data flow diagrams
- [ ] **12.3.3** Write `docs/DEPLOYMENT.md` for Azure Container Apps (one-click guide)
- [ ] **12.3.4** Write `docs/BUSINESS_VALUE.md` with case study, ROI metrics, before/after
- [ ] **12.3.5** Create `AGENTS.md` with custom Copilot agent instructions:
  ```markdown
  # CodeCustodian Agent Instructions

  You are CodeCustodian, an autonomous AI agent for technical debt management.

  ## Core Responsibilities
  1. Scan codebases for maintainability issues via static analysis
  2. Plan safe refactorings using GitHub Copilot SDK multi-turn reasoning
  3. Execute changes with atomic operations, 5-point safety checks, and verification
  4. Create PRs with detailed explanations OR proposals for high-risk items

  ## Context Sources
  - **Work IQ MCP**: Team context, expertise, sprint timelines, org context
  - **Azure DevOps**: Work items, sprint velocity, project dependencies
  - **GitHub**: Git history, blame, test coverage, CI/CD status
  - **Feedback**: Team preferences, historical patterns, scanner success rates

  ## Decision Framework
  Consider: Safety, Impact, Timing (Work IQ), Expertise (Work IQ), Business Value (ROI), Budget

  ## Safety Constraints
  - Never refactor without passing 5-point safety checks
  - Create proposal (not PR) when confidence < 5
  - Never create PRs during active incidents (query Work IQ)
  - Respect denylist paths and approval workflow policies
  ```

---

## 13. Phase 11 — Challenge Deliverables (Week 4)

### Step 13.1 — GitHub Actions Workflows

**Duration:** 0.5 day

**Tasks:**
- [ ] **13.1.1** Finalize `.github/workflows/codecustodian.yml` (daily scheduled run)
- [ ] **13.1.2** Finalize `.github/workflows/security-scan.yml`
- [ ] **13.1.3** Finalize `.github/workflows/deploy-azure.yml`

### Step 13.2 — Presentation & Video

**Duration:** 1 day

**Tasks:**
- [ ] **13.2.1** Create `presentations/CodeCustodian.pptx` (1-2 slides):
  - Slide 1: Business value ($60K–$130K/year savings, 2-month payback, 95%+ PR acceptance)
  - Slide 2: Architecture with Azure integrations + competitive differentiators
- [ ] **13.2.2** Record 3-minute demo video:
  - [0:00-0:30] Problem hook (300+ deprecation warnings)
  - [0:30-1:30] Live demo: `codecustodian run` creating PRs + `@codecustodian why` interaction
  - [1:30-2:30] Azure Monitor dashboard + ROI metrics + budget tracking
  - [2:30-3:00] Call to action

### Step 13.3 — Customer Validation & SDK Feedback

**Duration:** 0.5 day

**Tasks:**
- [ ] **13.3.1** Complete `customer/testimonial.md` (10 bonus pts)
- [ ] **13.3.2** Complete `feedback/sdk-feedback.md` (10 bonus pts):
  - Positive: `@define_tool` with Pydantic, streaming, session hooks
  - Requests: built-in token metrics, auto-retry, streaming for long responses
  - Share in Teams channel + screenshot

### Step 13.4 — 150-Word Summary

**Duration:** 0.25 day

**Tasks:**
- [ ] **13.4.1** Draft and polish summary:
  > **CodeCustodian: Autonomous Technical Debt Management for Enterprise**
  >
  > CodeCustodian is a GitHub Copilot SDK-powered AI agent that autonomously manages technical debt. Running in CI/CD pipelines, it scans for deprecated APIs, security vulnerabilities, code smells, and aging TODOs—then uses Copilot SDK's multi-turn reasoning with `@define_tool` to plan safe refactorings with alternative approaches. The agent executes changes atomically with 5-point safety checks, runs comprehensive verification, and creates PRs with detailed AI explanations—or advisory proposals for high-risk items.
  >
  > **Enterprise:** Saves $60K–$130K/year per team. Integrated with Azure DevOps (work items), Microsoft Work IQ MCP (context-aware expert routing), Azure Monitor (observability), Azure Key Vault (secrets), and Azure Container Apps (deployment). SOC 2 audit trails, RBAC, budget management, feedback-driven learning, Responsible AI compliance.
  >
  > **MCP Server:** Built with FastMCP v2, exposes tools, resources, and prompts for IDE integration.

---

## 14. Technology Validation Notes

### 14.1 — FastMCP (Validated Against PyPI v2.14.5 + gofastmcp.com)

| Feature | FastMCP v2.14.5 (Stable) | FastMCP v3.0 (Beta) | CodeCustodian Decision |
|---|---|---|---|
| Import | `from fastmcp import FastMCP` | Same | Standalone package, NOT `from mcp.server.fastmcp` |
| Tools | `@mcp.tool` (no parens), `@mcp.tool(name=..., tags=..., annotations=...)` | Adds `timeout`, `version` | Use v2 decorator API |
| Resources | `@mcp.resource("uri://{param}")` | Same | Template URIs for dynamic data |
| Prompts | `@mcp.prompt` | Same | Simple decorator pattern |
| Context | `ctx: Context` — logging, progress, sampling, resource access | Same | Use `await ctx.info()`, `await ctx.report_progress()` |
| Auth | Google, GitHub, **Azure**, Auth0, WorkOS, Discord, JWT, API Keys | Same | Use Azure provider for enterprise |
| Transports | stdio (default), HTTP (`mcp.run(transport="http")`), SSE (legacy) | Same + auto-reload | stdio for dev, HTTP for production |
| Composition | `mcp.mount()` (live), `mcp.import_server()` (static) | Same | Mount Work IQ server |
| Testing | `Client(mcp)` — in-memory, no process/network | Same | Use for unit tests |
| OpenAPI | `FastMCP.from_openapi()`, `FastMCP.from_fastapi()` | Same | Optional: expose as REST API |
| Custom Routes | `@mcp.custom_route("/health")` | Same | Health check for Azure Container Apps |
| Install | `pip install "fastmcp<3"` or `uv add "fastmcp>=2.14.0,<3"` | `pip install "fastmcp>=3.0.0b2"` | Pin to v2 for production |

### 14.2 — GitHub Copilot SDK (Validated Against PyPI v0.1.23)

The `github-copilot-sdk` package **IS available on PyPI** (v0.1.23, released Feb 6, 2026).

| Feature | Details | CodeCustodian Usage |
|---|---|---|
| Client | `CopilotClient(config)` — JSON-RPC over stdio/TCP | Wrap in `CopilotClientWrapper` |
| Sessions | `client.create_session({"model": "gpt-5"})` | One session per finding (multi-turn) |
| Tools | `@define_tool` + Pydantic `BaseModel` | Code analysis tools for AI |
| Events | `assistant.message`, `assistant.message_delta`, `session.idle` | Stream refactoring plans |
| Hooks | `on_pre_tool_use`, `on_post_tool_use`, `on_error_occurred` | Audit logging, error handling |
| Streaming | `streaming: True` in session config | Progressive output |
| Custom Providers | `provider: {"type": "azure", "base_url": "..."}` | Azure OpenAI BYOK |
| Infinite Sessions | Auto context compaction | Long analysis sessions |
| Reasoning | `reasoning_effort: "high"` for o1/gpt-5 | Complex decisions |
| Models | `gpt-5`, `claude-sonnet-4.5`, `gpt-4o-mini`, etc. | Auto-select by complexity |

### 14.3 — Azure Services Integration Summary

| Azure Service | Package | Purpose | Challenge Points |
|---|---|---|---|
| **Azure DevOps** | `azure-devops>=7.1` | Work items, PR linking, sprint boards, Azure Repos PRs | 10+ pts |
| **Azure Monitor** | `azure-monitor-opentelemetry>=1.2` | Distributed tracing, custom metrics, dashboards | Part of Ops (15 pts) |
| **Azure Key Vault** | `azure-keyvault-secrets>=4.7` | Secret storage, managed identity, rotation | Part of Security (15 pts) |
| **Azure Container Apps** | CLI deployment | Production hosting with auto-scaling, scale-to-zero | Part of Ops |
| **Azure AD** | `azure-identity` | RBAC, tenant auth, managed identity | Part of Security |
| **Work IQ MCP** | `@microsoft/work-iq-mcp` (npm) | Expert routing, sprint timing, org context | **15 bonus pts** |

### 14.4 — Bandit Integration Notes

```python
result = subprocess.run(["bandit", "-f", "json", "-r", repo_path], capture_output=True, text=True)
data = json.loads(result.stdout)
```

---

## 15. Risk Register & Mitigations

| # | Risk | Prob | Impact | Mitigation |
|---|---|---|---|---|
| 1 | **Copilot SDK breaking changes** (tech preview) | Medium | High | Wrap in `CopilotClientWrapper` abstraction. Pin `>=0.1.23,<0.2`. Session hooks for error recovery. |
| 2 | **Copilot CLI not installed in CI** | Medium | High | Document install steps. `COPILOT_CLI_PATH` env override. Fallback to Azure OpenAI provider. |
| 3 | **FastMCP v2→v3 migration** | Low | Low | Pin `fastmcp<3`. v2.14.5 is production-ready. |
| 4 | **AI generates unsafe code** | Medium | Critical | 5-point safety checks. AST validation. Git backup + atomic rollback. Test gate. Draft PR for low confidence. Proposal mode for very low confidence. |
| 5 | **Rate limiting on Copilot SDK** | Medium | Medium | Session hooks detect errors. `on_error_occurred` with retry. Cost tracking with budget cap. |
| 6 | **Azure DevOps auth failures** | Low | Medium | Validate PAT at startup. Clear errors. Graceful degradation. |
| 7 | **Work IQ MCP unavailable** | Medium | Low | Feature-flag `--enable-work-iq`. Fallback to git blame for reviewer assignment. |
| 8 | **Multi-file refactoring failures** | Medium | High | Atomic rollback. Full test suite. Cap at max_files_per_pr. |
| 9 | **Challenge deadline pressure** | High | Critical | 4-week timeline. Prioritize: core → Copilot SDK → Azure → polish. |
| 10 | **Token/secret leakage** | Low | Critical | Azure Key Vault. Audit all logging. Mask errors. Never log API bodies. |
| 11 | **Low adoption — engineers don't trust AI** (NEW) | Medium | High | Transparent reasoning. Confidence scoring. Start low-risk/high-value. Proposal mode. Feedback loop. |
| 12 | **PR noise / spam fatigue** (NEW) | Medium | Medium | PR sizing limits. Sprint-aware timing (Work IQ). Policy-based throttling. De-duplication across runs. |
| 13 | **Budget overruns** (NEW) | Medium | Medium | Per-team budget caps. Alerts at 50/80/90/100%. Hard stop at limit. Cheaper models when possible. |
| 14 | **Competitive threat (Byteable AI, Moderne)** (NEW) | High | Medium | Open-source core (community moat). Microsoft ecosystem lock-in. Scanner marketplace. Continuous learning. |
| 15 | **Cross-team breaking changes** (NEW) | Low | High | Work IQ org context queries. Preserve backwards compatibility. Deprecation warnings before breaking. |

---

## 16. Dependency Graph

```
Week 1:     [Models] ──→ [Config + Policies] ──→ [Pipeline + PR Sizing + Proposal Mode]
               │              │                        │
               │              ├──→ [Onboarding]        ├──→ [Azure Monitor Telemetry]
               │              │                        │
               ▼              ▼                        ▼
Week 1-2:   [Base Scanner + Registry + Dedup] ──→ [Deprecated API Scanner]
               │                                  [TODO Scanner]
               │                                  [Code Smell Scanner (+ Cognitive)]
               │                                  [Security Scanner (+ CWE/Compliance)]
               │                                  [Type Coverage Scanner]
               │
               ▼
Week 2:     [Copilot SDK Client] ──→ [@define_tool Tools] ──→ [Prompts]
               │                            │
               │                            ├──→ [Alternative Generator]
               │                            │
               ▼                            ▼
            [Planner + Confidence + Effort] ──→ [Safety Checks (5-point)]
               │                                        │
               ▼                                        ▼
            [File Editor + Atomic Rollback] ──→ [Git Manager] ──→ [Verifier + Security Scanner]
               │
               ▼
Week 3:     [PR Creator + Labels + Proposal Mode] ──→ [PR Interaction Bot]
               │
               ├──→ [Azure DevOps Integration + Azure Repos PRs]
               │
               ├──→ [FastMCP Server] ──→ [MCP Tools + Resources + Prompts]
               │
               ├──→ [Work IQ Integration]
               │
               ├──→ [Budget Manager] ──→ [ROI Calculator + Reporting]
               │
               ├──→ [Multi-Tenant] ──→ [RBAC] ──→ [Approval Workflows]
               │
               ├──→ [Secrets Manager (Key Vault)]
               │
               └──→ [Notification Engine]
               
Week 3-4:  [Business Impact Scorer] ──→ [Dynamic Re-Prioritizer]
               │
               └──→ [Feedback Collector] ──→ [Preference Store] ──→ [Historical Patterns]
               │
               └──→ [SLA Reporter]

Week 4:     [Security Hardening + Audit Trail] ──→ [RAI Docs] ──→ [Observability Dashboard]
               │
               ├──→ [CLI (full + interactive)] ──→ [Tests (80%+)] ──→ [Docs]
               │
               ├──→ [Azure Container Apps Deploy]
               │
               └──→ [Presentation] ──→ [Video] ──→ [Testimonial] ──→ [SDK Feedback]
```

### Critical Path

**Models → Config/Policies → Pipeline → Scanner → Copilot SDK Client → Planner → Safety Checks → File Editor → PR Creator → FastMCP Server → CLI → Tests → Submit**

Parallel tracks (after Week 2): Azure integrations, enterprise features, business intelligence, feedback system.

---

## 17. Success Metrics & KPIs

> **Source:** BRD §12, business-requirements.md §12

### Product Metrics

| Metric | Target | Frequency |
|---|---|---|
| PR acceptance rate | 95%+ | Daily |
| PR review time (avg) | < 4 hours | Weekly |
| Test pass rate | 98%+ | Daily |
| Confidence score (avg) | 8.5 / 10 | Weekly |
| Findings per repository | 50–200 | Monthly |
| PRs created per month | 50+ per team | Monthly |
| Detection to PR time | < 5 minutes | Per run |
| Issue resolution rate | 25–35% per run | Per run |

### Business Metrics

| Metric | Target | Frequency |
|---|---|---|
| Hours saved per team | 80+ hours / month | Monthly |
| Cost savings per team | $6,000+ / month | Monthly |
| ROI | 1,000%+ | Quarterly |
| Payback period | < 3 months | One-time |
| Customer retention | 95%+ | Quarterly |
| AI cost per refactoring | < $0.50 | Weekly |

### Operational Metrics

| Metric | Target | Frequency |
|---|---|---|
| Uptime | 99.5%+ | Daily |
| Pipeline latency (P95) | < 500ms per finding | Hourly |
| Cost per PR | < $0.50 | Weekly |
| MTTR (failures) | < 5 minutes | Per incident |
| Security incidents | 0 (from automated changes) | Continuous |
| Budget utilization | < 100% per team | Daily |

### Adoption Metrics (Go-To-Market)

| Metric | 3 months | 6 months | 12 months |
|---|---|---|---|
| Active teams | 10 | 50 | 200 |
| Repositories | 100 | 500 | 2,000 |
| PRs created | 1,000 | 10,000 | 100,000 |
| Savings generated | $100K | $500K | $2M |

---

## 18. Challenge Scoring Strategy

### Target: 125+ / 135 Points

| Category | Points | Strategy | Key Deliverables |
|---|---|---|---|
| **Enterprise value** | 30 | ROI calculator, multi-tenant, scanner marketplace, budget mgmt, feedback learning, business impact scoring | `roi_calculator.py`, `budget_manager.py`, `business_impact.py`, case study |
| **Azure/Microsoft** | 25 | Azure DevOps (work items + Azure Repos PRs), Monitor, Container Apps, Key Vault | `azure_devops.py`, `azure_monitor.py`, `secrets_manager.py`, `deploy-azure.yml` |
| **Operational readiness** | 15 | GitHub Actions, observability, one-click deploy, SLA reporting, budget alerts | 4 workflows, Azure Monitor dashboard, `sla_reporter.py` |
| **Security & RAI** | 15 | RBAC, audit logs, 5-point safety, Key Vault, Responsible AI, approval workflows | `RESPONSIBLE_AI.md`, `rbac.py`, `safety_checks.py`, `approval_workflows.py` |
| **Storytelling** | 15 | Case study, video, testimonial, competitive analysis | Video, deck, `BUSINESS_VALUE.md` |
| **BONUS: Work IQ** | **15** | MCP integration: expert routing, sprint timing, org context | `work_iq.py`, `mcp.json` |
| **BONUS: Customer** | **10** | Internal team testimonial | `customer/testimonial.md` |
| **BONUS: Feedback** | **10** | SDK feedback in Teams + screenshot | `feedback/sdk-feedback.md` |
| **TOTAL** | **135** | Target: **125+** | |

---

## Summary of Deliverables by Phase

| Phase | Duration | Key Deliverables | Requirements |
|---|---|---|---|
| Pre-Implementation | 1 day | Repo, deps, CI/CD workflows | FR-ARCH-002/003, BR-ONB-001 |
| Phase 1: Core + Policy | 6.5 days | Models (w/ dedup, effort, alternatives), Config + Policies, Pipeline (PR sizing, proposal mode, approval gates), Onboarding, Telemetry | FR-ARCH, FR-CONFIG, BR-CFG, BR-ONB, BR-PLN, BR-PR-003, BR-GOV-002 |
| Phase 2: Scanners | 6.5 days | 5 scanners + registry + de-dup + marketplace catalog | FR-SCAN, BR-SCN |
| Phase 3: AI Planner | 7 days | Copilot SDK client, @define_tool, prompts, alternatives, confidence, proposal mode, feedback injection | FR-PLAN, FR-LEARN |
| Phase 4: Executor + Verifier | 6.5 days | 5-point safety checks, file editor, Git manager, test runner, linter, security scanner (Trivy/TruffleHog) | FR-EXEC, FR-VERIFY |
| Phase 5: GitHub + Azure DevOps | 5 days | PR creator (rich labels, proposals), **PR interaction bot**, issues, Azure DevOps (work items + Azure Repos PRs) | FR-GITHUB, FR-AZURE-100/101, FR-UX-100, BR-NOT-002 |
| Phase 6: MCP Server | 4 days | FastMCP v2 server, tools (incl. business impact), resources (incl. dashboard), prompts | FR-EXT-001 |
| Phase 7: Azure + Enterprise | 5.5 days | Work IQ MCP, **budget manager**, ROI calculator, multi-tenant, RBAC, **approval workflows**, **Key Vault**, **notifications**, Container Apps | FR-COST, FR-SEC-102, BR-ENT, BR-GOV, BR-NOT, FR-DEPLOY |
| Phase 8: BI + Learning | 3.5 days | **Business impact scoring**, **dynamic re-prioritization**, **feedback loop**, **preferences**, **historical patterns**, **SLA reporting** | FR-PRIORITY, FR-LEARN, BR-ENT-002 |
| Phase 9: Security & RAI | 2 days | Security hardening, audit trail, Responsible AI, observability dashboard | FR-SEC, FR-OBS |
| Phase 10: Testing & Polish | 5 days | CLI (full + interactive), 80%+ coverage, docs, AGENTS.md | FR-CLI, FR-TEST, FR-UX-300 |
| Phase 11: Deliverables | 2.25 days | Workflows, presentation, video, testimonial, SDK feedback, summary | Challenge submission |

**Total timeline:** 4 weeks (by March 7, 2026 deadline)

---

**END OF IMPLEMENTATION PLAN v3.0**

| Document | Details |
|---|---|
| Implementation Plan | v3.0 — Business-Aligned Challenge Edition |
| Phases | 11 + pre-implementation |
| Timeline | 4 weeks (deadline: March 7, 2026) |
| Source documents | 4 (features-requirements, challenge-optimized, business-requirements, BRD) |
| Technology validations | FastMCP v2.14.5, GitHub Copilot SDK v0.1.23, Azure DevOps, Monitor, Key Vault |
| Challenge target | 125+ / 135 points |
| New from BRDs | Onboarding, policy system, proposal mode, PR interaction bot, alternative solutions, 5-point safety checks, feedback/learning system, business impact scoring, dynamic re-prioritization, budget management, approval workflows, Key Vault, notifications, SLA reporting, interactive CLI, enhanced security scanning |
