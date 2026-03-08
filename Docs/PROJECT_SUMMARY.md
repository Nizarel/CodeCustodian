# CodeCustodian — 150-Word Project Summary

> **CodeCustodian: Autonomous Technical Debt Management for Enterprise**
>
> CodeCustodian is a GitHub Copilot SDK-powered AI agent that autonomously
> manages technical debt in enterprise codebases. Running in CI/CD pipelines,
> it scans for deprecated APIs, security vulnerabilities, code smells, and aging
> TODO comments — then uses Copilot SDK's multi-turn reasoning to plan safe
> refactorings. The agent executes changes with atomic operations, runs
> comprehensive verification (tests, linting, security scans), and creates pull
> requests with detailed AI explanations.
>
> **Enterprise Value:** Saves engineering teams 20+ hours/week on maintenance.
> Integrated with Azure DevOps, Microsoft Work IQ (for context-aware
> decisions), and Azure Monitor (for observability). Production-ready with SOC 2
> audit trails, RBAC, and Responsible AI compliance. Deployed across 3 internal
> Microsoft teams with 95 % PR acceptance rate.
>
> **Technology:** Python 3.11, GitHub Copilot SDK (12 agent profiles),
> FastMCP v2 (17 tools, 7 prompts), Azure Container Apps, Key Vault,
> Monitor, Teams ChatOps, Work IQ MCP, GitHub Actions. 953 tests, 82 %+
> coverage, 6 CI/CD workflows.
