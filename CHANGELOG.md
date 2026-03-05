# Changelog

All notable changes to CodeCustodian are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.15.0] — 2026-03-05

### Added — Phase 13: AI Test Synthesis, Agentic Migrations & ChatOps

#### AI Test Synthesis
- `TestSynthesizer` in `planner/test_synthesizer.py`: uses Copilot SDK to generate
  pytest regression tests for findings, validates via `ast.parse`, executes in
  subprocess, and returns `TestSynthesisResult` with pass/fail status
- `TestSynthesisResult` Pydantic model with test_code, test_count, passed flags,
  validation_errors, and discard reason tracking
- `TestSynthesisConfig` in `config/schema.py` with max_per_run, timeout_per_test,
  require_passing_original settings
- 2 new SDK tools: `check_test_syntax` (AST validation + test counting),
  `run_pytest_subset` (subprocess pytest execution) — total 9 SDK tools
- `test-synthesizer` agent profile (fast model, test-synthesis skill)
- `test-synthesis` domain skill (`.copilot_skills/test-synthesis/SKILL.md`)

#### Agentic Migrations
- `MigrationEngine` in `intelligence/migrations.py`: multi-stage framework
  migration with networkx DAG for topological dependency ordering
- `MigrationStage`, `MigrationPlan`, `MigrationPlaybook` Pydantic models
- `MigrationsConfig` with playbook support (pattern/replacement pairs),
  pr_strategy (staged/single/draft-then-merge), max_files_per_stage
- Playbook-based pattern matching OR AI-generated stages via Copilot SDK
- Execution engine: iterate stages in topo order → apply → verify → rollback
  dependents on failure (rolled_back status propagation)
- `migration-engineer` agent profile (reasoning model, framework-migrations skill)
- `framework-migrations` domain skill (`.copilot_skills/framework-migrations/SKILL.md`)

#### ChatOps — Teams Notifications
- `TeamsConnector` in `integrations/teams_chatops.py`: Adaptive Card delivery
  to Microsoft Teams via incoming webhook (httpx async)
- 5 card builders: scan_complete, pr_created, approval_needed (with approve/reject
  ActionSet), verification_failed, migration_update
- `ChatOpsNotification` Pydantic model with message_type validator, adaptive_card_json
- `ChatOpsConfig` with connector, teams_webhook_url, crunch_time_digest,
  notification_channels
- `notification-composer` agent profile (fast model, chatops-delivery skill)
- `chatops-delivery` domain skill (`.copilot_skills/chatops-delivery/SKILL.md`)

#### MCP Expansion (12 → 16 tools, 5 → 7 prompts)
- `synthesize_tests` tool: generate regression tests for a finding
- `plan_migration` tool: create multi-stage migration plan
- `get_migration_status` tool: check migration stage progress
- `send_teams_notification` tool: deliver Adaptive Card to Teams
- `migration_assessment` prompt: assess migration complexity
- `test_coverage_gap` prompt: recommend test improvements for files
- Migration storage in MCP cache (store/get/list_migrations)

#### Agent & Skill Expansion (9 → 12 agents, 10 → 13 skills)
- 3 new agent profiles: test-synthesizer, migration-engineer, notification-composer
- 3 new domain skills: test-synthesis, framework-migrations, chatops-delivery
- Updated FINDING_TYPE_SKILL_MAP for DEPRECATED_API and DEPENDENCY_UPGRADE

#### Dependencies
- Added `networkx>=3.2` for DAG-based migration ordering
- Added `botbuilder-core>=4.14.0` and `botbuilder-integration-aiohttp>=4.14.0`

#### Tests
- 62 new tests in `test_phase10_v015.py` covering all v0.15.0 features
- Updated tool count (16), prompt count (7), agent count (12) assertions
- Total: 826 unit/integration tests passing

---

## [0.14.0] — 2026-03-04

### Added — Phase 14: Production Intelligence & SDK Hardening

#### Predictive Debt Forecasting
- `PredictiveDebtForecaster` in `intelligence/forecasting.py`: records time-series
  snapshots of scan results, applies pure-Python linear regression, and projects
  future finding counts with confidence intervals
- `DebtSnapshot` and `DebtForecast` Pydantic models in `models.py`
- Trend classification (improving / stable / worsening) with configurable slope
  thresholds, hotspot directory identification, and recommended remediation actions
- `ForecastingConfig` in `config/schema.py` with `snapshot_dir`, `forecast_horizon_days`,
  `min_snapshots` settings

#### Code Reachability Analysis
- `ReachabilityAnalyzer` in `intelligence/reachability.py`: AST-based import graph
  builder with BFS path tracing from entry points to finding locations
- Framework-aware entry-point detection: Flask (`@app.route`), FastAPI (`@router.get`),
  Django (class-based views), Lambda (`handler(event, context)`), CLI (`__main__`)
- `ReachabilityResult` model with `reachability_tag` (entry-point / reachable /
  internal-only) for severity-aware prioritisation
- `EntryPoint` model for structured entry-point metadata

#### Live PyPI Version Intelligence
- `check_pypi()` async method on `DependencyUpgradeScanner`: queries PyPI JSON API
  via `httpx.AsyncClient` for latest version, release date, and changelog URL
- `scan_with_live_check()` enriches scan findings with `pypi_latest`,
  `pypi_release_date`, `major_version_jump`, and `changelog_url` metadata
- `DependencyUpgradeScannerConfig` extended with `live_pypi`, `pypi_timeout`,
  `cache_ttl_hours` fields

#### Enhanced Onboarding
- 6 new detection methods on `ProjectAnalyzer`: `_detect_languages()`,
  `_detect_package_managers()`, `_detect_test_frameworks()`, `_detect_ci_platform()`,
  `_detect_linters()`, `_detect_sensitive_paths()`
- `recommend_template()` auto-selects policy template based on project analysis
  (security_first for auth/payment code, deprecations_first for large codebases)
- `OnboardingManager.onboard_repo()`: auto-template, sensitive-path population,
  GitHub Actions workflow generation, health check validation
- `OnboardingConfig` in `config/schema.py` with auto-detection toggles

#### Advisory Agent Profiles
- 2 new advisory agents in `planner/agents.py`: `forecasting-analyst` (reasoning
  model, debt-forecasting skill) and `reachability-analyst` (balanced model,
  reachability-analysis + security-remediation skills)
- `get_agent_by_name()` helper for invoking advisory agents directly (not via
  finding-type routing)
- 9 total agent profiles (7 finding-mapped + 2 advisory)

#### Domain Skills (3 New Knowledge Files)
- `.copilot_skills/debt-forecasting/SKILL.md`: trend interpretation, velocity
  optimisation, sprint planning, forecasting best practices
- `.copilot_skills/live-dependency-intelligence/SKILL.md`: PyPI semver analysis,
  changelog interpretation, migration planning, transitive risk
- `.copilot_skills/reachability-analysis/SKILL.md`: entry-point patterns, call
  graph traversal, attack-surface analysis, remediation prioritisation

#### MCP Server Expansion (12 Tools, 5 Prompts)
- 3 new read-only tools: `get_debt_forecast`, `check_pypi_versions`,
  `get_reachability_analysis`
- New `forecast_report` prompt for executive forecast summaries
- Dashboard resource enhanced with forecast trend data and hotspot directories
- Forecast cache layer in `cache.py`: `store_forecast()`, `get_forecast()`, TTL-based

### Changed
- `OnboardingManager.onboard_repo()` default template: `"full_scan"` → `"auto"`
- `ScanCache`: new `_forecasts` dict + methods, updated `stats()`/`clear()`
- `intelligence/__init__.py`: exports `PredictiveDebtForecaster`, `ReachabilityAnalyzer`

### Tests
- 3 new test files: `test_forecasting.py`, `test_reachability.py`, `test_live_pypi.py`
- Extended `test_onboarding.py` with 10 new detection method tests
- Extended `test_skills_agents.py` with 7 new advisory agent tests
- Updated `test_mcp_server.py` and `test_full_workflow.py` for 12 tools / 5 prompts
- **766 unit/integration tests + 98 e2e tests passing**, zero regressions

---

## [0.13.0] — 2026-03-03

### Added — Phase 13: SDK Showcase — Domain Skills, Custom Agents, Multi-Session

#### Domain Skills (SKILL.md Knowledge System)
- 7 SKILL.md knowledge files in `.copilot_skills/`: `security-remediation`,
  `api-migration`, `code-quality`, `python-typing`, `todo-resolution`,
  `dependency-management`, `general-refactoring`
- `SkillRegistry` in `planner/skills.py`: discovers, parses YAML front-matter +
  Markdown body, maps `FindingType` → relevant skills, formats for injection
- Skills injected into Copilot SDK `system_message.content` — gives each session
  deep, domain-specific expertise (OWASP patterns, migration tables, refactoring
  catalogs, typing idioms, etc.)
- Custom skill directories supported via `CopilotConfig.custom_skill_dir`

#### Custom Agent Profiles (7 Specialized AI Personas)
- `AgentProfile` Pydantic model in `planner/agents.py` with system prompt overlay,
  model preference, skill set, and optional tool filter
- 7 predefined agents: `security-auditor` (reasoning model), `modernization-expert`,
  `quality-architect`, `type-advisor` (fast), `task-resolver` (fast),
  `dependency-expert`, `general-refactorer` (fallback)
- `FindingType` → agent routing: each finding type is automatically routed to the
  most appropriate specialist agent
- Agent `model_preference` overrides `CopilotConfig.model_selection` per-finding
- Agents configurable via `CopilotConfig.enable_agents` (default: `True`)

#### Multi-Session (Session Pooling with Infinite Sessions)
- Session pool in `Planner`: reuses sessions across findings handled by the same
  agent — avoids redundant session creation overhead
- Leverages SDK `infinite_sessions: {enabled: true, background_compaction_threshold:
  0.80, buffer_exhaustion_threshold: 0.95}` for long-lived sessions
- `Planner.close_sessions()` destroys all pooled sessions at pipeline shutdown
- Pipeline calls `close_sessions()` before `client.stop()` for clean lifecycle
- Configurable via `CopilotConfig.session_reuse` (default: `True`)

### Changed
- `CopilotPlannerClient.select_model()`: new `preference` kwarg for agent-level override
- `CopilotPlannerClient.create_session()`: new `skill_context` and `session_reuse` kwargs
- `CopilotConfig`: 3 new fields — `enable_agents`, `custom_skill_dir`, `session_reuse`
- `Planner.__init__()`: initializes `SkillRegistry` and session pool
- `Planner.plan_refactoring()`: agent selection → skill loading → composite system
  prompt → model preference → tool filtering → session reuse (7-step flow)
- `Pipeline._plan()`: calls `planner.close_sessions()` before `client.stop()`
- `planner/__init__.py`: re-exports `AgentProfile`, `SkillRegistry`, `SkillDefinition`,
  `select_agent`, `get_agent_tools`, `list_agents`

### Tests
- 42 new tests in `tests/test_skills_agents.py` covering skill parsing, registry,
  agent selection, tool filtering, session pooling, config extensions, and planner
  integration
- **720 tests passing** (excluding pre-existing e2e FastMCP compatibility failures),
  zero regressions

---

## [0.12.0] — 2026-03-02

### Added — Phase 12: Demo-Critical Features (5 Features, 28 New Tests)

#### Diff Preview in Dry-Run Mode
- `_print_diff_preview()` in CLI renders unified diffs via `difflib.unified_diff`
  with Rich `Syntax` highlighting in a bordered panel
- Hooked into the `run --dry-run` command: plans with `FileChange.old_content` /
  `new_content` show coloured diff output automatically

#### Finding Deep-Dive CLI Command
- New `codecustodian finding <id>` command for full finding inspection
- Rich panel displays: ID, type, severity, file:line, priority, business impact,
  scanner, description, suggestion, and metadata
- Code context rendered with `Syntax` and line highlighting
- Matches by ID substring for convenience

#### Interactive HTML ROI Report
- `ROICalculator.export_html()` generates a standalone HTML report
- GitHub dark-theme CSS, 4 hero cards (Savings, Net ROI, Hours Saved, Total Fixes)
- Chart.js 4 CDN: bar chart (Savings vs Cost by type), doughnut chart (fix distribution)
- Summary table + breakdown by finding type — no external Python dependencies
- CLI: `codecustodian report --format html [--output file.html]`

#### Blast Radius Analysis (Section 4.7)
- New `intelligence/blast_radius.py`: `BlastRadiusAnalyzer` builds AST-parsed
  import graph, BFS traversal quantifies downstream impact
- `BlastRadiusReport` Pydantic model: `directly_affected`, `transitively_affected`,
  `affected_tests`, `radius_score` (0.0–1.0), `risk_level`
- Safety Check #7 in `executor/safety_checks.py`: auto-downgrades to proposal mode
  when `radius_score > 0.30` (30% of codebase affected)
- MCP Tool #9: `get_blast_radius` (read-only) for pre-change impact queries

#### Architectural Drift Detection Scanner (Section 4.9)
- New 7th scanner: `ArchitecturalDriftScanner` extending `BaseScanner`
- Three checks: circular dependency detection (DFS), layer boundary violations
  (configurable forbidden imports), module size violations (>600 lines default)
- Default layer rules: cli/mcp → presentation, scanner/planner/executor/verifier/
  intelligence → domain, enterprise → service, integrations/config → infrastructure
- Registered in `scanner/registry.py`; CLI aliases: `architectural_drift`, `architecture`

### Changed
- MCP server: 8 → 9 tools (added `get_blast_radius`)
- Safety checks: 6 → 7 (added blast radius gate)
- Scanner registry: 6 → 7 scanners (added `architectural_drift`)
- FastMCP server init: `on_duplicate_tools=` → `on_duplicate=` (API compatibility)
- `report` command: `--format` now accepts `json`, `csv`, or `html`

### Tests
- 28 new tests in `tests/test_new_features.py`
- Updated `test_executor.py` and `test_mcp_server.py` for new feature assertions
- **674 tests passing**, zero regressions from new features

---

## [0.11.0] — 2026-02-23

### Added — Multi-Language Scanner Support

#### Language Coverage (FR-SCAN-110)
- `TodoCommentScanner` and `SecurityScanner` now scan Go, C#, JavaScript, TypeScript,
  Java, and Python (previously Python-only)
- New `BaseScanner.find_files(extensions)` method for multi-extension file discovery
  with `.gitignore` and config-driven exclusion (backward-compatible alongside `find_python_files`)
- Unified comment regex covers `#` (Python/Shell), `//` (Go/C#/JS/TS/Java),
  and `/* */` block comments in a single pass
- `language` field added to `Finding.metadata` for all TODO and security findings

#### New Security Patterns
- **C#**: `Process.Start()` command injection, `SqlCommand` string-concat SQL injection,
  `new MD5/SHA1Managed` weak crypto
- **Go**: `exec.Command()` command injection, `db.Query/Exec` string-concat SQL injection,
  `"crypto/md5"` / `"crypto/sha1"` import detection
- **Java**: `Runtime.getRuntime().exec()` command injection,
  `Statement.executeQuery/executeUpdate` string-concat SQL injection,
  `MessageDigest.getInstance("MD5"/"SHA-1")` weak crypto

#### Configuration
- `TodoScannerConfig.languages` and `SecurityScannerConfig.languages` fields added
  (default: `["py","go","cs","js","ts","java"]`) — user-configurable via `.codecustodian.yml`

#### Tests & Fixtures
- 16 new tests across `TestFindFiles`, `TestTodoScannerMultiLang`, `TestSecurityScannerMultiLang`
- New fixture files: `tests/fixtures/sample_repo/main.go`, `Service.cs`, `UserRepository.java`
- **625 tests passing**, zero regressions

---

## [0.10.0] — 2026-02-21

### Added — Phase 10: CLI Commands, Integration Tests & Coverage Closure

#### CLI Commands (FR-CLI-100)
- 10 fully implemented CLI commands: `run`, `init`, `validate`, `scan`, `onboard`,
  `status`, `report`, `findings`, `create-prs`, `interactive`
- Shared `_scan_findings()` and `_filter_findings()` helpers for consistent scanner invocation
- `_print_findings()` supports table, JSON, and CSV output formats
- `init` command applies policy templates and bootstraps `.github/workflows/codecustodian.yml`
- `status` aggregates findings by type/severity, budget utilization, and SLA metrics
- `report` generates ROI reports in JSON or CSV via `ROICalculator`
- `findings` supports filtering by type, severity, status, and file pattern
- `create-prs` delegates to Pipeline with configurable top-N and dry-run
- `interactive` provides InquirerPy-powered menu loop for common workflows

#### Integration & E2E Tests
- 2 async integration tests in `tests/integration/test_pipeline_integration.py`
  (dry-run pipeline on real git repo, full mocked path with execute/verify/PR)
- 2 end-to-end tests in `tests/e2e/test_full_workflow.py`
  (scan detection against fixture repo, dry-run pipeline JSON output)

#### Coverage Closure
- 21 verifier deep tests (`tests/test_verifier.py`) — TestRunner, LinterRunner, SecurityVerifier
- 25 executor additional/edge-case tests (`tests/test_executor_additional.py`,
  `tests/test_executor_edge_cases.py`) — GitManager, SafetyChecks, FileEditor, Backup
- 18 pipeline tests with 5 new `TestPipelineProcessFinding` paths
- 7 onboarding tests, 4 logging tests, 12 CLI tests
- **609 tests passing**, 82.26% overall coverage (≥80% gate met)
- Critical-path executor+verifier coverage: 90.20%

---

## [0.9.0] — 2026-02-18

### Added — Phase 9: Security Hardening, Responsible AI & Observability

#### Security Hardening
- Path traversal and symlink blocking in `SafeFileEditor`
- Dangerous function detection (`eval`, `exec`, `compile`, `__import__`) in safety checks
- Secret detection (tokens, API keys, bearer credentials) in pre-execution validation
- Repository-boundary enforcement for all file operations

#### Responsible AI
- `Docs/RESPONSIBLE_AI.md` — 8-section policy covering human-in-the-loop,
  explainability, confidence scoring, fairness, privacy, safety, accountability,
  and proposal mode

#### Audit & Observability
- `AuditLogger` with append-only JSONL and SHA-256 tamper-evident hashes
- `_JsonFormatter` structured log formatter with secret masking
- `SECURITY.md` security policy and disclosure process

#### Tests
- 7 tests in `tests/test_phase9_security.py` covering audit logging, path traversal
  blocking, dangerous function detection, JSON log masking, and secret redaction

---

## [0.8.0] — 2026-02-15

### Added — Phase 8: Business Intelligence, Feedback & Learning

#### Business Impact Scoring (FR-PRIORITY-100)
- 5-factor `BusinessImpactScorer` in `intelligence/business_impact.py`:
  usage frequency, criticality, change frequency, velocity impact, regulatory risk
- Configurable `ScoringWeights` for per-org tuning
- `ImpactBreakdown` model with detailed factor descriptions
- Batch scoring via `score_batch()` for full-scan prioritization
- MCP `get_business_impact` tool upgraded from hardcoded mapping to real scorer

#### Dynamic Re-Prioritization (FR-PRIORITY-101)
- Event-driven `DynamicReprioritizer` in `intelligence/reprioritization.py`
- Event types: `production_incident`, `cve_announced`, `deadline_approaching`,
  `budget_exceeded`, `team_capacity_change`, plus custom events
- Priority boosts, finding pausing, and capacity-based rate limiting
- Event audit log for traceability

#### Feedback Loop & Learning (FR-LEARN-100, FR-LEARN-101, BR-NOT-002)
- `FeedbackCollector` in `feedback/learning.py` — TinyDB-backed PR outcome tracking
  (merged / rejected / modified), per-scanner and per-team success rates,
  auto-suggested confidence threshold adjustments
- `PreferenceStore` in `feedback/preferences.py` — team and user coding preferences
  with dedup, prompt injection via `get_preferences_for_prompt()`
- `HistoricalPatternRecognizer` in `feedback/history.py` — cross-org historical
  refactoring lookup with scored similarity matching and prompt context generation

#### SLA & Reliability Reporting (BR-ENT-002)
- `SLAReporter` in `enterprise/sla_reporter.py` — TinyDB-backed run tracking,
  success/failure rates, failure trend analysis (stable / degrading / improving),
  spike alerts, team filtering, CSV and Markdown export
- Automatic forwarding to Azure Monitor via `ObservabilityProvider.record_sla_metrics()`

#### Integration & Configuration
- Planner `build_finding_prompt()` accepts `preferences` and `historical_context`
- Planner `calculate_confidence()` accepts `scanner_adjustment` from learning data
- Pipeline wires `BusinessImpactScorer` and `SLAReporter` when enabled
- Config schema: `SLAConfig`, `LearningConfig`, `BusinessImpactConfig` models
- Updated `__init__.py` exports for `feedback`, `intelligence`, and `enterprise`

#### Tests
- 55 new tests in `tests/test_phase8_intelligence.py` covering all Phase 8 modules
- All TinyDB-backed classes include `close()` for Windows file-lock safety

### Changed
- `mcp/tools.py` `get_business_impact` now uses real 5-factor scorer (backward-compatible
  `sla_risk` and `business_impact_level` keys preserved)

---

## [0.7.0] — 2026-02-14

### Added — Phase 7: Azure Integrations & Enterprise Features
- Work IQ MCP integration (expert identification, capacity, org context)
- Budget manager (per-team cost tracking, alerts, enforcement)
- ROI calculator with monthly report generation
- Multi-tenant manager, RBAC manager, approval workflow manager
- Secrets manager (Azure Key Vault integration)
- Notification engine (Slack, Teams, email, webhook)
- Azure Container Apps deployment (Dockerfile, Bicep, deploy script, CI/CD)

---

## [0.6.0] — 2026-02-13

### Added — Phase 6: MCP Server with FastMCP
- FastMCP v2 server with 10 tools, 5 resources, 4 prompts
- In-memory testing via `Client(mcp)` pattern
- Scan cache for cross-tool state sharing

---

## [0.5.0] — 2026-02-12

### Added — Phases 1–5
- Core scanning engine (deprecated APIs, TODOs, code smells, security, type coverage)
- GitHub Copilot SDK planner with multi-turn conversations and tool use
- Atomic file executor with backup/rollback
- Verification system (pytest, ruff, mypy, bandit)
- GitHub integration (PR creator, interaction bot, issue creator)
- Pipeline orchestrator with OpenTelemetry tracing

---

## [0.1.0] — 2026-02-10

### Added
- Project scaffold, `pyproject.toml`, CI workflow
