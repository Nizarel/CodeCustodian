# Changelog

All notable changes to CodeCustodian are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
