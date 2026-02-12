# CodeCustodian — Business Requirements Document (BRD)

**Document version:** 1.0  
**Product:** CodeCustodian  
**Purpose:** Define the business requirements and detailed feature descriptions for an autonomous technical‑debt management agent that identifies code issues and delivers reviewable remediation work as pull requests (PRs), with measurable outcomes.

---

## 1) Executive Summary

### 1.1 Product Vision
CodeCustodian helps engineering organizations **reduce technical debt continuously** by automating detection, prioritization, and delivery of safe code improvements as PRs—so teams can focus on feature delivery instead of repetitive maintenance.

### 1.2 Business Problem
Across medium–large portfolios (dozens to thousands of repositories), teams struggle to:
- Keep up with **deprecated APIs**, dependency changes, and framework upgrades.
- Address **security patterns** and hygiene issues consistently.
- Reduce **code complexity and duplication** without disrupting delivery schedules.
- Convert large backlogs of **TODO/FIXME** and “eventually” tasks into actionable work.
- Prove ROI for debt reduction with clear metrics and reporting.

### 1.3 Success Metrics (Business Outcomes)
The product will be considered successful if it achieves the following targets:
- **Efficacy:** 25–35% issue resolution rate across runs (goal benchmark: SWE-bench style measurable impact).
- **Cost efficiency:** <$0.50 average “AI cost” per refactoring.
- **Speed:** <5 minutes average time from detection to PR creation for eligible changes.
- **Quality:** 95%+ PRs pass tests/validation on first run; low manual rework.
- **Adoption:** 1,000+ repositories onboarded within 6 months of launch.

---

## 2) In Scope / Out of Scope

### 2.1 In Scope
- Automated discovery of code issues (configurable policy).
- Prioritization and packaging of issues into **reviewable PRs**.
- Quality gates (tests/linters) and PR confidence scoring.
- Reporting for leaders and teams (progress, risk, ROI).
- Governance controls (approvals, safety, auditability).
- Marketplace-style extensibility for scanners/rules.

### 2.2 Out of Scope (for this BRD)
- Implementation details (code architecture, model prompts, toolchain specifics).
- Full “hands-off” production deployment patterns.
- Real-time IDE assistant behavior (this is CI/automation-first).
- Fully autonomous merges without human review (unless explicitly enabled by policy).

---

## 3) Target Customers, Personas, and Jobs-to-be-Done

### 3.1 Primary Customer Segments
- **Enterprises** with many repos and strict governance.
- **Platform engineering / DevEx** groups responsible for standards and automation.
- **Security and compliance** teams needing consistent remediation.
- **Engineering leadership** seeking measurable productivity and quality improvements.

### 3.2 Personas
1. **Engineering Manager**
   - Wants predictable delivery while reducing debt.
   - Needs dashboards and risk reporting.

2. **Staff/Principal Engineer**
   - Wants safe refactors, consistent patterns, and control over scope.
   - Needs confidence, explanations, and easy review experience.

3. **Developer**
   - Wants PRs that are small, understandable, and pass tests.
   - Needs minimal disruption and clear rationale.

4. **Security Engineer**
   - Wants policy-driven remediation, auditing, and proof of compliance.
   - Needs consistent prioritization and traceability.

5. **Platform/DevOps Engineer**
   - Wants scalable onboarding, configuration management, and observability.
   - Needs controls, performance, and stable operations.

---

## 4) Product Principles (Business-Level)

1. **Reviewable automation:** Every change must be delivered as a PR with explanation, not “silent modification.”
2. **Safety first:** Prefer smaller, low-risk PRs over large rewrites; always respect policy constraints.
3. **Measurable ROI:** Track time saved, risk reduced, and debt resolved.
4. **Configurable control:** Organizations choose what to scan, what to fix, and when to propose changes.
5. **Extensible by design:** New scanners/rules can be added without rewriting the product.

---

## 5) End-to-End User Experience (High-Level Flow)

### 5.1 “From Scan to PR” Lifecycle
1. **Repository onboarding** (org-level or repo-level).
2. **Scheduled or triggered scan** runs (e.g., nightly, weekly, or on demand).
3. Issues are **categorized** (deprecations, security, complexity, TODOs, etc.).
4. Issues are **prioritized** and grouped into an “action plan.”
5. For eligible items, CodeCustodian generates:
   - A **PR** (or PR set) with changes,
   - An **explanation** (what/why),
   - A **confidence score** and risk notes,
   - Evidence of checks (tests/linters) when available.
6. Stakeholders review, request changes, and merge based on policy.
7. Reports show **progress**, **ROI**, and **residual risk**.

---

## 6) Detailed Business Feature Requirements

> Format: Each requirement includes a **description**, **primary users**, **business value**, and **acceptance criteria**.

### 6.1 Repository Onboarding & Setup

#### BR-ONB-001: Self-service onboarding (Org / Repo)
- **Description:** Enable onboarding at organization level (multiple repos) and individual repo level with minimal steps.
- **Primary users:** Platform/DevOps, Engineering managers.
- **Business value:** Faster adoption, consistent governance, reduced setup friction.
- **Acceptance criteria:**
  - Admin can enroll an organization and select eligible repositories.
  - Admin can exclude repos by policy (archived, sensitive, experimental).
  - Onboarding status shows “configured / scanning / blocked / requires approval.”

#### BR-ONB-002: Policy templates (Starter packs)
- **Description:** Provide ready-to-use policy templates (e.g., “Security First”, “Deprecations First”, “Low-Risk Maintenance”).
- **Primary users:** Platform/DevOps, Security.
- **Business value:** Accelerates time-to-value; reduces configuration errors.
- **Acceptance criteria:**
  - At least 3 templates exist.
  - Templates are editable and can be cloned per org/team.

---

### 6.2 Issue Discovery (Scanning) & Classification

#### BR-SCN-001: Multi-category scanning
- **Description:** Detect issues across categories including:
  - Deprecated API usage
  - Security patterns/hygiene risks
  - Code complexity / maintainability smells
  - Long-lived TODO/FIXME items
- **Primary users:** Developers, Staff engineers, Security.
- **Business value:** Reduces incidents, accelerates upgrades, improves code quality.
- **Acceptance criteria:**
  - Each finding includes category, severity, location, and rationale.
  - Findings are de-duplicated across runs (no noisy repeats).

#### BR-SCN-002: Severity and impact scoring
- **Description:** Each finding receives a business-friendly score for **severity** and **impact** (risk, cost of delay, maintainability).
- **Primary users:** Engineering managers, Security.
- **Business value:** Enables prioritization aligned with risk and delivery goals.
- **Acceptance criteria:**
  - Scoring model is transparent (explainable factors).
  - Users can tune weights (e.g., prioritize security vs maintainability).

#### BR-SCN-003: Scanner marketplace / extensibility
- **Description:** Support a marketplace-like catalog of scanners/rules so orgs can add domain-specific checks (e.g., internal frameworks).
- **Primary users:** Platform engineering, Staff engineers.
- **Business value:** Reusability, broader applicability, long-term product growth.
- **Acceptance criteria:**
  - Admin can enable/disable scanners from a catalog.
  - Each scanner declares what it detects and typical remediation outcomes.

---

### 6.3 Prioritization & Work Packaging

#### BR-PLN-001: Action plan generation
- **Description:** Turn findings into an “action plan” that groups related fixes into logical PR units (small, reviewable).
- **Primary users:** Developers, Staff engineers.
- **Business value:** Improves review throughput and lowers merge risk.
- **Acceptance criteria:**
  - Each plan lists proposed PRs with scope summary, impacted files, and estimated risk.
  - Plans can be reviewed/approved before PR creation (policy optional).

#### BR-PLN-002: Configurable PR sizing rules
- **Description:** Allow rules that limit PR size (max files, max lines changed, category bundling).
- **Primary users:** Staff engineers, Platform/DevOps.
- **Business value:** Maintains developer trust and prevents “mega PR” fatigue.
- **Acceptance criteria:**
  - Admin can set PR limits.
  - System splits work into multiple PRs when limits are exceeded.

#### BR-PLN-003: Backlog-aware prioritization
- **Description:** Align recommendations with existing engineering priorities by supporting “ignore/waive/defer” workflows and linking to team backlogs.
- **Primary users:** Engineering managers, Developers.
- **Business value:** Prevents wasted effort; respects team roadmap.
- **Acceptance criteria:**
  - Findings can be marked: ignore, defer until date, or track as work item.
  - Reports distinguish “resolved vs waived vs deferred.”

---

### 6.4 PR Creation & Review Experience

#### BR-PR-001: PR creation with clear narrative
- **Description:** Every PR must include:
  - What changed
  - Why it matters (risk/benefit)
  - How to validate (tests/checks run)
  - Any potential risks/rollbacks
- **Primary users:** Developers, Reviewers, Security.
- **Business value:** Faster reviews, higher trust, fewer regressions.
- **Acceptance criteria:**
  - PR description uses a consistent template.
  - Links to findings and evidence are included.

#### BR-PR-002: Confidence scoring and “human effort estimate”
- **Description:** Provide a 1–10 confidence score and a simple estimate of expected reviewer effort (e.g., low/medium/high).
- **Primary users:** Reviewers, Engineering managers.
- **Business value:** Helps teams decide what to merge quickly vs scrutinize.
- **Acceptance criteria:**
  - Score is shown in PR and dashboards.
  - Score includes explanation factors (e.g., touched area, test results).

#### BR-PR-003: Optional “proposal mode” (no code changes)
- **Description:** For high-risk items, the system may produce a proposal-only PR/comment containing recommended steps without applying changes.
- **Primary users:** Staff engineers, Security.
- **Business value:** Enables safe planning for sensitive refactors.
- **Acceptance criteria:**
  - Policy can require proposal mode for certain categories/severities.
  - Proposal output includes step-by-step remediation guidance.

---

### 6.5 Validation, Quality Gates, and Safety

#### BR-QA-001: Policy-based quality gates
- **Description:** PRs must respect org-defined gates, such as:
  - Tests passing (required or best-effort)
  - Lint/format checks
  - Security scanning checks
- **Primary users:** Platform/DevOps, Security, Engineering managers.
- **Business value:** Prevents regressions and ensures compliance.
- **Acceptance criteria:**
  - Each PR indicates which gates ran and outcomes.
  - If gates fail, PR is labeled “needs attention” with next steps.

#### BR-QA-002: Auto-rollback / abort behavior
- **Description:** If the system cannot meet policy constraints (e.g., tests fail, change too risky), it must **abort** or **downgrade** to proposal mode.
- **Primary users:** Developers, Platform/DevOps.
- **Business value:** Preserves trust; prevents disruptive changes.
- **Acceptance criteria:**
  - Policy defines failure thresholds.
  - The system never “forces” a PR that violates a hard gate.

---

### 6.6 Governance, Permissions, and Auditability

#### BR-GOV-001: Role-based permissions (RBAC)
- **Description:** Support roles such as:
  - Org admin (full control)
  - Repo admin
  - Reviewer/approver
  - Viewer (read-only)
- **Primary users:** Platform/DevOps, Security.
- **Business value:** Enterprise readiness and compliance.
- **Acceptance criteria:**
  - Role-based controls for enabling scanners, approving plans, and PR creation.
  - Roles can be scoped per org/team/repo.

#### BR-GOV-002: Approval workflows
- **Description:** For sensitive repos or categories, require approvals at:
  - Plan approval (before PR creation)
  - PR approval (before merge)
- **Primary users:** Security, Staff engineers, Engineering managers.
- **Business value:** Enables controlled adoption in regulated environments.
- **Acceptance criteria:**
  - Policies define which repos/categories require approvals.
  - Audit trail records who approved what and when.

#### BR-GOV-003: Audit trail and evidence retention
- **Description:** Maintain an audit log for scans, decisions, PR outputs, and overrides.
- **Primary users:** Security, Compliance, Leadership.
- **Business value:** Traceability, compliance reporting, post-incident analysis.
- **Acceptance criteria:**
  - Logs include timestamps, actor, repo, action, outcome.
  - Retention period is configurable.

---

### 6.7 Reporting, Dashboards, and ROI

#### BR-RPT-001: Executive dashboard
- **Description:** Provide portfolio-level view showing:
  - Resolved issues by category/severity
  - Trend lines over time
  - Estimated time saved and risk reduced
  - Adoption across repos/teams
- **Primary users:** Engineering leadership, Managers.
- **Business value:** Demonstrates measurable ROI and supports investment decisions.
- **Acceptance criteria:**
  - Dashboard supports filtering by org/team/repo/time.
  - Exports available (CSV/PDF).

#### BR-RPT-002: Team-level operational dashboard
- **Description:** Provide team-level workflows:
  - Upcoming PRs and proposals
  - Failed validations needing attention
  - Deferred/waived items
  - Top risky areas
- **Primary users:** Developers, Staff engineers.
- **Business value:** Keeps workflow actionable; reduces noise.
- **Acceptance criteria:**
  - Shows “what needs review now.”
  - Supports SLA tracking (e.g., time-to-review).

#### BR-RPT-003: ROI model and “before/after” summaries
- **Description:** Quantify value using:
  - Estimated engineer-hours saved
  - Reduction in vulnerability exposure window
  - Reduction in deprecation upgrade time
  - Reduction in complexity hotspots
- **Primary users:** Leadership, Finance stakeholders, Platform teams.
- **Business value:** Enables budgeting, prioritization, and scaling decisions.
- **Acceptance criteria:**
  - ROI model assumptions are documented.
  - Users can tune labor cost assumptions per org.

---

### 6.8 Notifications & Collaboration

#### BR-NOT-001: Notification rules
- **Description:** Notify stakeholders for:
  - New PRs created
  - High-severity findings
  - Validation failures
  - Approvals requested
- **Primary users:** Developers, Security, Managers.
- **Business value:** Faster response; reduces missed reviews.
- **Acceptance criteria:**
  - Users can configure notification channels and thresholds.
  - Notifications include actionable links and summaries.

#### BR-NOT-002: Comment-based interaction
- **Description:** Allow reviewers to interact via comments:
  - Request clarification
  - Ask for smaller scope
  - Ask for proposal instead of changes
- **Primary users:** Reviewers, Staff engineers.
- **Business value:** Keeps collaboration in existing workflows.
- **Acceptance criteria:**
  - Standard comment commands or structured options are supported.
  - System response is visible and traceable.

---

### 6.9 Configuration & Policy Management (Business View)

#### BR-CFG-001: Central policy management
- **Description:** Provide a central place to manage:
  - Enabled categories/scanners
  - Thresholds for severity
  - PR sizing limits
  - Approval requirements
  - Exclusions (paths, repos, file types)
- **Primary users:** Platform/DevOps, Security.
- **Business value:** Consistent governance and easy scaling across repos.
- **Acceptance criteria:**
  - Policies can be applied org-wide and overridden per repo.
  - Changes are versioned and auditable.

#### BR-CFG-002: Allowlist/denylist controls
- **Description:** Define what is allowed:
  - Allowed refactor types (e.g., formatting, migrations)
  - Disallowed areas (e.g., payments, auth)
- **Primary users:** Security, Staff engineers.
- **Business value:** Prevents unacceptable changes in sensitive areas.
- **Acceptance criteria:**
  - Controls support directory/file pattern matching.
  - Changes in denied areas trigger proposal mode or block.

---

### 6.10 Enterprise Readiness

#### BR-ENT-001: Multi-tenant support (Business requirement)
- **Description:** Support multiple organizations/teams with separation of data, policies, and reporting.
- **Primary users:** Enterprise admins, Platform teams.
- **Business value:** Enables SaaS / large enterprise deployment with isolation.
- **Acceptance criteria:**
  - Tenants have separate policies and dashboards.
  - Cross-tenant data access is not possible.

#### BR-ENT-002: SLA and reliability reporting
- **Description:** Track and report operational reliability:
  - Run success rate
  - Average time to PR
  - Failure reasons and trends
- **Primary users:** Platform/DevOps, Leadership.
- **Business value:** Supports operational excellence and scaling.
- **Acceptance criteria:**
  - Reliability metrics visible to admins.
  - Alerts on abnormal failure spikes.

---

## 7) Non-Functional Business Requirements (No technical implementation)

### 7.1 Performance Expectations
- The product must support continuous scanning across large portfolios with predictable throughput.
- The product must avoid disrupting developer workflows (no excessive PR spam; policy-based throttling).

### 7.2 Trust & Explainability
- Every recommendation and PR must be explainable in plain language.
- Confidence and risk must be communicated clearly to non-experts.

### 7.3 Security & Compliance (Business-level)
- Support permissions, approvals, and audit trails appropriate for regulated environments.
- Provide configurable retention for findings and evidence.

---

## 8) MVP and Roadmap (Business Scope)

### 8.1 MVP (Launch)
- Onboarding + basic policy templates
- Core scanning categories (deprecation, security hygiene, complexity, TODO)
- Action plan generation + PR creation template
- Confidence scoring + validation result reporting
- Basic dashboards (team + executive)

### 8.2 Near-Term Enhancements (Next releases)
- Scanner marketplace with curated catalog
- Advanced approval workflows and fine-grained RBAC
- Deeper ROI modeling and exportable reports
- Proposal-only mode expansions for sensitive areas
- Portfolio throttling and intelligent scheduling

---

## 9) Assumptions & Dependencies
- Repositories use a PR-based workflow and accept automated PRs for maintenance.
- Teams have baseline tests/validation processes (or accept best-effort validation).
- Leadership supports an “automation with review” operating model.

---

## 10) Risks & Mitigations (Business View)
- **Trust risk (PRs feel noisy or risky):** Mitigate with strict policy, small PR sizing, proposal mode, and clear explanations.
- **Adoption risk (teams ignore PRs):** Mitigate with dashboards, notifications, SLA targets, and manager reporting.
- **Value perception risk:** Mitigate with ROI modeling and before/after progress snapshots.
- **Compliance concerns:** Mitigate with approvals, audit trail, retention, and access controls.

---

## 11) Acceptance Criteria (Product-Level)
The product is ready for broad rollout when:
1. It can onboard repos with policy templates and generate findings reliably.
2. It can generate PRs with consistent narrative + confidence scoring.
3. It demonstrates measurable improvements aligned to success metrics.
4. Governance features (RBAC, approvals, audit) meet enterprise needs.
5. Dashboards show progress and ROI clearly for leadership and teams.
