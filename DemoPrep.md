# CodeCustodian — Competition Demo Prep

## Submission Checklist

### Required Deliverables

| # | Deliverable | Status | Location |
|---|-------------|--------|----------|
| 1 | **Project summary (150 words max)** | TODO | Below |
| 2 | **Video (3 min max)** | TODO | Record after build |
| 3 | **Working code in GitHub repo** | DONE | `src/codecustodian/` |
| 4 | **README with architecture + setup** | DONE | `README.md`, `Docs/` |
| 5 | **Presentation deck (1-2 slides)** | TODO | `presentations/CodeCustodian.pptx` |
| 6 | **`/src` or `/app` (working code)** | DONE | `src/` |
| 7 | **`/docs` (README, prereqs, setup, deployment, arch diagram, RAI)** | DONE | `Docs/README.md`, `ARCHITECTURE.md`, `DEPLOYMENT.md`, `RESPONSIBLE_AI.md` |
| 8 | **`AGENTS.md`** | DONE | `AGENTS.md` |
| 9 | **`mcp.json`** | DONE | `mcp.json` |
| 10 | **Demo deck in `/presentations/`** | TODO | `presentations/CodeCustodian.pptx` |
| 11 | **`/customer` folder** | TODO | `customer/` |

### Bonus Points

| # | Bonus | Status | Notes |
|---|-------|--------|-------|
| B1 | **Product feedback on GHCP SDK** | TODO | Post in SDK channel + screenshot |
| B2 | **Customer testimonial release** | TODO | Signed form or validation doc |

---

## Judging Criteria → Build Plan

### 1. Enterprise Applicability, Reusability & Business Value — 35 pts (HIGHEST)

**What we have:**
- Full pipeline: scan → plan → execute → verify → PR
- Budget manager, SLA reporter, ROI calculator
- Multi-tenant, RBAC, approval workflows
- Policy templates for different org needs

**What to build to maximize score:**

| Task | Points impact | Effort |
|------|--------------|--------|
| A1. **Demo repo with planted tech debt** (15-20 realistic findings) | HIGH — makes the demo repeatable and impressive | Low |
| A2. **Live scan → PR demo script** (`scripts/demo-run.ps1`) | HIGH — "zero to PR in 60 seconds" hero moment | Low |
| A3. **Cost savings summary in pipeline output** ("Saved 47 eng hours") | HIGH — direct business value proof | Low |
| A4. **HTML ROI report** with charts (export from `report` command) | MEDIUM — leave-behind for decision makers | Medium |
| A5. **150-word project summary** (for submission) | Required | Low |

### 2. Integration with Azure / Microsoft Solutions — 25 pts

**What we have:**
- Azure Key Vault secrets manager
- Azure Container Apps deployment (Dockerfile + Bicep + CI/CD)
- Azure Monitor / App Insights (OpenTelemetry)
- Azure DevOps integration (work items)
- MCP server (FastMCP) — works with Copilot Chat
- Work IQ MCP integration
- GitHub Copilot SDK as AI engine
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
- CI workflow: lint (ruff) → test (609 tests, 82% cov, 80% gate) → security (bandit)
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
- Confidence-gated safety (8-10: PR, 5-7: draft, <5: proposal-only)
- Bandit + Trivy in CI/CD

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
and security vulnerabilities, then uses the **GitHub Copilot SDK** to plan safe refactorings
with confidence scoring (1-10).

Changes are applied atomically with backup/rollback guarantees, verified by automated
tests and linting, and submitted as pull requests with full AI reasoning — keeping
humans in control.

Built on **FastMCP v2**, CodeCustodian integrates as an MCP server in VS Code Copilot Chat.
It deploys to **Azure Container Apps** with **Key Vault** secrets, **Azure Monitor** observability,
and **Azure DevOps** work item integration.

Enterprise features include budget management, SLA reporting, ROI calculation, RBAC,
approval workflows, and a feedback loop that learns from PR outcomes to improve over time.

**609 tests, 82% coverage, 4 CI/CD workflows, Responsible AI policy.**

---

## 3-Minute Video Script (Outline)

| Time | Segment | Content |
|------|---------|---------|
| 0:00-0:20 | **Hook** | "Engineering teams spend 40% of their time on maintenance. What if an AI agent handled it autonomously?" |
| 0:20-0:40 | **Problem** | Show a real codebase with deprecated APIs, old TODOs, code smells. "This is technical debt." |
| 0:40-1:30 | **Live Demo** | Run `codecustodian scan` → show findings table. Run `codecustodian run --dry-run` → show plan with confidence scores and AI reasoning. |
| 1:30-2:00 | **Safety** | Show confidence-gated behavior: high confidence → PR, low confidence → proposal. Show eval() being blocked. |
| 2:00-2:20 | **MCP in VS Code** | Open Copilot Chat, ask CodeCustodian MCP to scan and analyze. Unique differentiator. |
| 2:20-2:40 | **Enterprise** | Flash: ROI report, budget dashboard, SLA metrics, audit log. "Enterprise-ready from day one." |
| 2:40-2:50 | **Azure Integration** | Architecture diagram: Key Vault + Container Apps + Monitor + DevOps + GitHub Actions + Copilot SDK |
| 2:50-3:00 | **Close** | "CodeCustodian: your autonomous guardian against technical debt. 609 tests. Open source. Production-ready." |

---

## Architecture Diagram (for deck and docs)

```mermaid
graph TB
    subgraph "Developer Experience"
        CLI["CLI (10 commands)"]
        MCP["MCP Server (FastMCP v2)"]
        VSCode["VS Code Copilot Chat"]
    end

    subgraph "CodeCustodian Pipeline"
        SCAN["Scanner\n5 built-in scanners"]
        PLAN["Planner\nGitHub Copilot SDK"]
        EXEC["Executor\nAtomic + Rollback"]
        VERIFY["Verifier\npytest + ruff + bandit"]
        PR["PR Creator\nGitHub API"]
        FEEDBACK["Feedback Loop\nLearning from outcomes"]
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
end
```

