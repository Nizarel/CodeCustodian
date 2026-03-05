# CodeCustodian — Competition Demo Prep

## Submission Checklist

### Required Deliverables

| # | Deliverable | Status | Location |
|---|-------------|--------|----------|
| 1 | **Project summary (150 words max)** | TODO | Below |
| 2 | **Video (3 min max)** | TODO | Record after build |
| 3 | **Working code in GitHub repo** | DONE | `src/codecustodian/` |
| 4 | **README with architecture + setup** | DONE | `README.md`, `Docs/` |
| 5 | **Presentation deck (1-2 slides)** | DONE | `presentations/CodeCustodian-Deck.html` |
| 6 | **`/src` or `/app` (working code)** | DONE | `src/` |
| 7 | **`/docs` (README, prereqs, setup, deployment, arch diagram, RAI)** | DONE | `Docs/README.md`, `ARCHITECTURE.md`, `DEPLOYMENT.md`, `RESPONSIBLE_AI.md` |
| 8 | **`AGENTS.md`** | DONE | `AGENTS.md` |
| 9 | **`mcp.json`** | DONE | `mcp.json` |
| 10 | **Demo deck in `/presentations/`** | DONE | `presentations/CodeCustodian-Deck.html` |
| 11 | **`/customer` folder** | DONE | `customer/testimonial.md` |

### Bonus Points

| # | Bonus | Status | Notes |
|---|-------|--------|-------|
| B1 | **Product feedback on GHCP SDK** | TODO | Post in SDK channel + screenshot |
| B2 | **Customer testimonial release** | DONE | `customer/testimonial.md` |

---

## Judging Criteria → Build Plan

### 1. Enterprise Applicability, Reusability & Business Value — 35 pts (HIGHEST)

**What we have:**
- Full pipeline: scan → plan → execute → verify → PR
- Budget manager, SLA reporter, ROI calculator with **HTML export**
- Multi-tenant, RBAC, approval workflows
- Policy templates for different org needs
- **NEW v0.12.0:** Diff preview in dry-run, finding deep-dive, blast radius analysis, architectural drift scanner

**What to build to maximize score:**

| Task | Points impact | Effort |
|------|--------------|--------|
| A1. **Demo repo with planted tech debt** (15-20 realistic findings) | HIGH — makes the demo repeatable and impressive | Low |
| A2. **Live scan → PR demo script** (`scripts/demo-run.ps1`) | HIGH — "zero to PR in 60 seconds" hero moment | Low |
| A3. **Cost savings summary in pipeline output** ("Saved 47 eng hours") | HIGH — direct business value proof | Low |
| A4. **HTML ROI report** with charts (export from `report` command) | DONE ✅ — `codecustodian report --format html` | Done |
| A5. **150-word project summary** (for submission) | Required | Low |

### 2. Integration with Azure / Microsoft Solutions — 25 pts

**What we have:**
- Azure Key Vault secrets manager
- Azure Container Apps deployment (Dockerfile + Bicep + CI/CD)
- Azure Monitor / App Insights (OpenTelemetry)
- Azure DevOps integration (work items)
- MCP server (FastMCP) — works with Copilot Chat (16 tools, 7 prompts)
- Work IQ MCP integration
- GitHub Copilot SDK as AI engine (12 agent profiles, 13 domain skills)
- GitHub Actions (4 workflows: ci, deploy-azure, codecustodian, security-scan)

**What to build to maximize score:**

| Task | Points impact | Effort |
|------|--------------|--------|
| B1. **MCP live demo in VS Code Copilot Chat** | HIGH — unique differentiator, already built | Low (just demo) |
| B2. **Architecture diagram showing all Azure touchpoints** | HIGH — visual proof of deep integration | Low |
| B3. **Azure Monitor dashboard screenshot/setup** | MEDIUM — shows observability is real | Medium |

**Key message:** CodeCustodian touches 6 Azure/Microsoft services: Key Vault, Container Apps, Monitor, DevOps, GitHub Copilot SDK, MCP protocol. Plus GitHub Actions for CI/CD.

### 3. Operational Readiness — 15 pts

**What we have:**
- CI workflow: lint (ruff, 0 errors) → test (826 tests, 82%+ cov, 80% gate) → security (bandit)
- Deploy workflow: test → build/push → Bicep deploy → MCP smoke test
- Security scan workflow: Bandit + Trivy (weekly schedule)
- Docker multi-stage build (non-root user, healthcheck)
- Structured logging with JSON formatter + secret masking
- Azure Container Apps with health endpoint

**What to build to maximize score:**

| Task | Points impact | Effort |
|------|--------------|--------|
| C1. **README badges** (CI, coverage, Python version, license) | MEDIUM — instant credibility signal | Low |
| C2. **Run CI on GitHub and screenshot green checks** | HIGH — proof it works | Low |

### 4. Security, Governance & Responsible AI — 15 pts

**What we have:**
- `SECURITY.md` with disclosure policy
- `Docs/RESPONSIBLE_AI.md` (8 sections: human-in-loop, explainability, confidence, fairness, privacy, safety, accountability, proposal mode)
- Audit logger with SHA-256 tamper-evident hashes
- Path traversal + symlink blocking
- Dangerous function detection (eval, exec, compile, __import__)
- Secret detection in pre-execution validation
- **Blast radius gate** — blocks changes touching >N files
- Confidence-gated safety (8-10: PR, 5-7: draft, <5: proposal-only)
- Bandit + Trivy in CI/CD
- **7-point safety check system** (syntax, file_size, binary, path_traversal, encoding, secrets, blast_radius)

**What to build to maximize score:**

| Task | Points impact | Effort |
|------|--------------|--------|
| D1. **Demo the safety system in video** (eval blocked, path traversal rejected, low-confidence → proposal) | HIGH — shows RAI is real, not docs-only | Low (already built) |
| D2. **RAI notes in Docs/ README** (link to RESPONSIBLE_AI.md) | Already done | Done |

### 5. Storytelling, Clarity & "Amplification Ready" — 15 pts

**What to build to maximize score:**

| Task | Points impact | Effort |
|------|--------------|--------|
| E1. **3-min video script** (structured: problem → solution → live demo → results → enterprise value) | CRITICAL — this IS the judging experience | Medium |
| E2. **1-2 slide deck** (business value + architecture diagram) | Required | Medium |
| E3. **Clean GitHub repo** (no stale files, good README, badges) | MEDIUM | Low |

---

## Priority Build Order (Optimized for Judging Rubric)

### Phase A — Foundation (Must-have for submission)

| # | Task | Rubric | Effort |
|---|------|--------|--------|
| 1 | **Demo repo** with planted tech debt (15-20 findings) | 35pt + 15pt | Low |
| 2 | **Demo script** (`scripts/demo-run.ps1`) — scan → PR in 60 seconds | 35pt + 15pt | Low |
| 3 | **150-word project summary** | Required | Low |
| 4 | **Architecture diagram** (Mermaid → PNG) showing all Azure/MS integrations | 25pt + 15pt | Low |
| 5 | **1-2 slide deck** (business value + arch diagram) in `/presentations/` | Required + 15pt | Medium |

### Phase B — Competitive Edge

| # | Task | Rubric | Effort |
|---|------|--------|--------|
| 6 | **Cost savings summary** in pipeline output/report | 35pt | Low |
| 7 | **HTML ROI report** with charts | 35pt | Medium |
| 8 | **README badges** (CI status, coverage, Python, license) | 15pt | Low |
| 9 | **Customer validation document** in `/customer/` | Bonus | Low |

### Phase C — Video & Polish

| # | Task | Rubric | Effort |
|---|------|--------|--------|
| 10 | **Video script** (3 min, structured) | 15pt | Medium |
| 11 | **Record video** (demo repo → scan → PR → MCP in VS Code → ROI report) | Required | Medium |
| 12 | **SDK feedback screenshot** | Bonus | Low |

---

## 150-Word Project Summary (Draft)

**CodeCustodian** is an autonomous AI agent that eliminates technical debt at enterprise
scale. It scans Python codebases for deprecated APIs, aging TODO comments, code smells,
security vulnerabilities, type coverage gaps, and architectural drift, then uses the
**GitHub Copilot SDK** to plan safe refactorings with confidence scoring (1-10).

Changes are applied atomically with 7-point safety checks (including blast radius
analysis and secret detection), verified by automated tests and linting, and submitted
as pull requests with full AI reasoning — keeping humans in control.

Built on **FastMCP v2**, CodeCustodian integrates as an MCP server in VS Code Copilot Chat
with 16 tools, 7 prompts, and 12 agent profiles (including advisory analysts for debt
forecasting and code reachability). It deploys to **Azure Container Apps** with
**Key Vault** secrets, **Azure Monitor** observability, and **Azure DevOps** work item
integration.

Enterprise features include budget management, SLA reporting, HTML ROI reports, RBAC,
approval workflows, predictive debt forecasting, live PyPI intelligence, and a feedback
loop that learns from PR outcomes.

**826 tests, 82%+ coverage, 4 CI/CD workflows, 0 lint errors, Responsible AI policy.**

---

## 3-Minute Video Script (Outline)

| Time | Segment | Content |
|------|---------|---------|
| 0:00-0:20 | **Hook** | "Engineering teams spend 40% of their time on maintenance. What if an AI agent handled it autonomously?" |
| 0:20-0:40 | **Problem** | Show a real codebase with deprecated APIs, old TODOs, code smells. "This is technical debt." |
| 0:40-1:10 | **Live Demo: Scan** | Run `codecustodian scan --repo-path demo/sample-enterprise-app` → show 60 findings with severity colors, bar chart, and ROI estimate. |
| 1:10-1:30 | **Finding Deep-Dive** | Run `codecustodian finding "sql injection"` → show detailed view with CWE, exploit scenario, compliance refs. |
| 1:30-1:50 | **Dry-Run + Diff Preview** | Run `codecustodian run --dry-run --max-prs 1` → show diff preview of proposed changes before any code is touched. |
| 1:50-2:05 | **Safety** | Show 7-point safety system: blast radius gate, secret detection, confidence-gated behavior. eval() blocked. |
| 2:05-2:20 | **MCP in VS Code** | Open Copilot Chat → use `get_debt_forecast` tool to show trend prediction → use `check_pypi_versions` to show live dependency intelligence → use `get_reachability_analysis` to show dead code detection. "16 tools, 7 prompts, 12 agents." |
| 2:20-2:35 | **Enterprise** | HTML ROI report, budget dashboard, SLA metrics, audit log. "Enterprise-ready from day one." |
| 2:35-2:50 | **Azure Integration** | Architecture diagram: Key Vault + Container Apps + Monitor + DevOps + GitHub Actions + Copilot SDK |
| 2:50-3:00 | **Close** | "CodeCustodian: your autonomous guardian against technical debt. 826 tests. Zero lint errors. Production-ready." |

---

## Architecture Diagram (for deck and docs)

```mermaid
graph TB
    subgraph "Developer Experience"
        CLI["CLI (14+ commands)"]
        MCP["MCP Server (FastMCP v2)\n16 tools, 7 prompts"]
        VSCode["VS Code Copilot Chat"]
    end

    subgraph "CodeCustodian Pipeline"
        SCAN["Scanner\n7 built-in scanners"]
        PLAN["Planner\nGitHub Copilot SDK\n12 agent profiles"]
        EXEC["Executor\nAtomic + Rollback"]
        VERIFY["Verifier\npytest + ruff + bandit"]
        PR["PR Creator\nGitHub API"]
        FEEDBACK["Feedback Loop\nLearning from outcomes"]
    end

    subgraph "Intelligence Layer (v0.14.0)"
        FORECAST["Debt Forecasting\nTrend prediction"]
        REACH["Reachability Analysis\nDead code detection"]
        PYPI["Live PyPI Intelligence\nReal-time version checks"]
    end

    subgraph "Azure & Microsoft"
        KV["Azure Key Vault\nSecrets"]
        ACA["Azure Container Apps\nDeployment"]
        MON["Azure Monitor\nOpenTelemetry"]
        ADO["Azure DevOps\nWork Items"]
        GHA["GitHub Actions\nCI/CD (4 workflows)"]
        COPILOT["GitHub Copilot SDK\nAI Reasoning"]
    end

    subgraph "Enterprise"
        BUDGET["Budget Manager"]
        SLA["SLA Reporter"]
        ROI["ROI Calculator"]
        RBAC["RBAC + Approvals"]
        AUDIT["Audit Logger\nSHA-256 tamper-evident"]
    end

    CLI --> SCAN
    VSCode --> MCP
    MCP --> SCAN

    SCAN --> PLAN
    PLAN --> EXEC
    EXEC --> VERIFY
    VERIFY --> PR
    PR --> FEEDBACK
    FEEDBACK --> PLAN

    PLAN --> COPILOT
    EXEC --> KV
    PR --> GHA
    MON --> ACA
    ADO --> PLAN

    SCAN --> BUDGET
    PR --> SLA
    SLA --> ROI
    RBAC --> EXEC
    EXEC --> AUDIT

    SCAN --> FORECAST
    SCAN --> REACH
    SCAN --> PYPI
    FORECAST --> MCP
    REACH --> MCP
    PYPI --> MCP
end
```

