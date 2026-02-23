# CodeCustodian — E2E Demo Test Plan

> Generated: 2026-02-23  
> Azure Container App: `codecustodian-prod-app.greenforest-c49f3fb9.eastus2.azurecontainerapps.io`  
> Status: **Azure deployment verified ✅ (v0.10.0, health OK, 8 tools, 5 scanners)**

---

## Architecture Under Test

```
Pipeline: Scan → Dedup → Prioritize → Plan → Execute → Verify → PR → Feedback
AI Engine: GitHub Copilot SDK (github-copilot-sdk)
MCP Server: FastMCP v2 (streamable-http on Azure, stdio locally)
Demo Target: demo/sample-enterprise-app/ (4 files, 15-20 planted issues)
```

---

## Phase 1 — Azure Deployment Verification

### 1.1 Quick Smoke Test (run first — fastest signal)

```powershell
.\scripts\smoke-mcp-remote.ps1 `
  -Fqdn "codecustodian-prod-app.greenforest-c49f3fb9.eastus2.azurecontainerapps.io" `
  -TimeoutSeconds 120
```

**Expected output:**
```
Health OK (version=0.10.0)
Session established: <id>
Tools available: 8
Tool call OK (list_scanners), result_count=5
MCP smoke test passed
```

> Note: `min replicas = 0` — first call after idle may take 30-60s (cold start). Use `-TimeoutSeconds 180` if it times out.

### 1.2 Full Azure E2E Suite

```powershell
pytest tests/e2e/test_azure_deployment.py -v -m azure_e2e
```

### 1.3 Verified Azure Resources

| Resource | Name | Status |
|---|---|---|
| Resource Group | `Custodian-Rg` | To verify |
| Container App | `codecustodian-prod-app` | ✅ Running |
| Container App Environment | `codecustodian-prod-env` | ✅ Running |
| Container Registry | `codecustodianprodacr` | To verify |
| Key Vault | `codecustodian-prod-kv` | To verify |
| Application Insights | `codecustodian-prod-ai` | To verify |
| Log Analytics | `codecustodian-prod-law` | To verify |

---

## Phase 2 — Local CLI E2E Suite

All tests in `tests/e2e/test_full_workflow.py`, marked `@pytest.mark.e2e`.

### 2.1 `TestDemoAppScanners` — All 5 scanners vs realistic demo target

| Test | What it verifies |
|---|---|
| `test_scan_demo_app_all_five_types` | All 5 scanner types found in single pass |
| `test_scan_demo_app_security_critical` | Critical findings from `auth.py` (secrets, SQL injection, `eval`, `pickle`) |
| `test_scan_demo_app_deprecated_apis` | Deprecated `df.append()`, `df.iteritems()`, `np.float()` from `data_processor.py` |
| `test_scan_demo_app_code_smells` | `normalize_prices()` cyclomatic complexity / nesting depth |
| `test_scan_demo_app_type_coverage` | `api_handlers.py` zero type annotations |
| `test_scan_demo_app_todo_comments` | Module-level TODO in `utils.py` |
| `test_scan_demo_app_security_scanner_only` | `--scanner security_patterns` single-filter works |
| `test_scan_demo_app_multi_scanner_filter` | `--scanner deprecated_apis,todo_comments` filter |

### 2.2 `TestPipelineDryRun` — Full pipeline output structure

| Test | What it verifies |
|---|---|
| `test_dry_run_full_result_structure` | Result has `findings`, `plans`, `proposals`, `cost_savings_estimate`, `total_duration_seconds`, `errors` |
| `test_dry_run_cost_savings_estimate` | `cost_savings_estimate` is a positive float > 0 |
| `test_dry_run_plans_have_confidence` | Each plan has `confidence_score` between 1-10 |
| `test_dry_run_proposals_list_present` | `proposals` is a list |
| `test_dry_run_no_duplicate_findings` | No duplicate `dedup_key` values |

### 2.3 `TestCLICommands` — All 10 CLI commands

| Test | Command |
|---|---|
| `test_cli_scan_table_format` | `scan --output-format table` |
| `test_cli_scan_csv_format` | `scan --output-format csv` |
| `test_cli_findings_severity_filter` | `findings --severity critical` |
| `test_cli_findings_type_filter` | `findings --type security` |
| `test_cli_validate_command` | `validate --config .codecustodian.yml` |
| `test_cli_init_creates_config` | `init` in tempdir creates `.codecustodian.yml` |
| `test_cli_status_command` | `status` exits 0 |
| `test_cli_report_command` | `report` exits 0 |
| `test_cli_onboard_command` | `onboard --repo-path demo/sample-enterprise-app` exits 0 |
| `test_cli_interactive_help` | `interactive --help` exits 0 |

### 2.4 `TestEnterpriseFeaturesE2E` — Budget / SLA / ROI / Audit / RBAC

| Test | Component |
|---|---|
| `test_roi_calculator_report` | `ROICalculator.generate_report()` → positive `estimated_savings_usd` |
| `test_sla_reporter_records_and_reports` | `SLAReporter.record_run()` → persisted, `generate_report()` → SLAReport |
| `test_budget_manager_tracks_cost` | `BudgetManager.record_cost()` → running total increases |
| `test_audit_logger_tamper_evident_hash` | `AuditLogger.log()` → entry has SHA-256 hash, `compute_hash()` validates |
| `test_rbac_admin_has_all_permissions` | `check_permission(ADMIN, *)` → all True |
| `test_rbac_viewer_limited_permissions` | `check_permission(VIEWER, EXECUTE)` → False |
| `test_multi_tenant_isolation` | `MultiTenantManager.get_tenant_dirs()` → separate dirs per tenant |
| `test_approval_workflow_request_approve` | `ApprovalWorkflowManager.request_approval()` + `approve()` → APPROVED status |

### 2.5 `TestSafetyChecksE2E` — Security validations

| Test | What is blocked |
|---|---|
| `test_safety_blocks_eval_in_new_code` | `eval("user_input")` in proposed changes → `passed=False` |
| `test_safety_blocks_exec_in_new_code` | `exec(data)` in proposed changes → `passed=False` |
| `test_safety_blocks_hardcoded_secret` | `sk-abc123...` OpenAI key in new content → `passed=False` |
| `test_safety_blocks_aws_key` | `AKIA...` AWS access key → `passed=False` |
| `test_safety_allows_clean_code` | Clean replacement code → `passed=True` |

### 2.6 `TestFeedbackIntelligenceE2E` — Learning loop

| Test | Component |
|---|---|
| `test_feedback_store_record_and_retrieve` | `FeedbackStore.record()` + `get_accuracy_stats()` → stats updated |
| `test_preference_store_record_and_retrieve` | `PreferenceStore.record_preference()` + `get_preferences()` → list returned |
| `test_historical_pattern_recognizer` | `HistoricalPatternRecognizer.record_refactoring()` + `find_similar()` → SimilarPattern |

### 2.7 `TestMCPServerLocal` — Local MCP server in-process

| Test | Tool/Resource |
|---|---|
| `test_mcp_list_tools_returns_eight` | `tools/list` → 8 tools |
| `test_mcp_list_scanners_returns_five` | `tools/call list_scanners` → 5 scanners |
| `test_mcp_scan_repository_returns_findings` | `tools/call scan_repository demo/sample-enterprise-app` → ≥5 findings |
| `test_mcp_calculate_roi_returns_savings` | `tools/call calculate_roi` → positive savings |
| `test_mcp_get_business_impact` | `tools/call get_business_impact` → valid impact data |
| `test_mcp_resource_version` | `codecustodian://version` → semver string |
| `test_mcp_resource_config` | `codecustodian://config` → contains YAML |
| `test_mcp_resource_scanners` | `codecustodian://scanners` → lists scanner names |
| `test_mcp_resource_config_settings` | `config://settings` → JSON with version key |
| `test_mcp_resource_findings_all` | `findings://myrepo/all` → JSON after scan |
| `test_mcp_resource_dashboard` | `dashboard://team-alpha/summary` → has `total_findings` |
| `test_mcp_prompts_list` | `prompts/list` → 4 prompts |
| `test_mcp_prompt_refactor_finding` | `prompts/get refactor_finding` → message content |

---

## Phase 3 — Azure Remote E2E Extensions

Extensions to `tests/e2e/test_azure_deployment.py`.

### `TestMCPToolsExtended`

| Test | Tool |
|---|---|
| `test_calculate_roi_tool_returns_savings` | `calculate_roi {}` → savings ≥ 0 |
| `test_get_business_impact_tool_returns_score` | `get_business_impact {}` → content not empty |
| `test_plan_refactoring_missing_finding_returns_error` | `plan_refactoring {finding_id: "fake123"}` → error message |

### `TestMCPResourcesExtended`

| Test | Resource |
|---|---|
| `test_read_scanners_resource` | `codecustodian://scanners` → lists scanner names |
| `test_read_dashboard_resource` | `dashboard://test-team/summary` → JSON with `total_findings` |
| `test_read_findings_all_resource` | `findings://test-repo/all` → JSON with `findings` key |

---

## Phase 4 — Demo Rehearsal

```powershell
.\scripts\demo-run.ps1 -SkipPause
```

**5-step demo script checks:**

| Step | Command | Expected |
|---|---|---|
| 1 | `scan demo/sample-enterprise-app` | ≥15 findings across 5 scanner types |
| 2 | JSON grouping by type + severity | Security: RED, High: MAGENTA, Medium: YELLOW |
| 3 | Cost estimate | Shows `$XXX saved` with manual vs auto cost |
| 4 | `run --dry-run --output-format json` | Lists findings + plans, no errors |
| 5 | `findings --severity critical --output-format table` | Shows auth.py security issues |

---

## Running the Full Suite

```powershell
# 1. Quick smoke (Azure live check)
.\scripts\smoke-mcp-remote.ps1 -Fqdn codecustodian-prod-app.greenforest-c49f3fb9.eastus2.azurecontainerapps.io

# 2. Local comprehensive E2E
pytest tests/e2e/test_full_workflow.py -v -m e2e

# 3. Azure remote E2E
pytest tests/e2e/test_azure_deployment.py -v -m azure_e2e

# 4. Combined with coverage
pytest tests/e2e/ -v --cov=codecustodian --cov-report=term-missing

# 5. Demo rehearsal
.\scripts\demo-run.ps1 -SkipPause
```

---

## Planted Issues in Demo App

| File | Type | Severity | Issue |
|---|---|---|---|
| `auth.py` | security | critical | Hardcoded `DATABASE_PASSWORD`, `STRIPE_API_KEY`, `AWS_SECRET_KEY` |
| `auth.py` | security | critical | MD5 password hashing |
| `auth.py` | security | critical | `os.system()` command injection |
| `auth.py` | security | critical | SQL injection via f-string |
| `auth.py` | security | critical | `eval()` code injection |
| `auth.py` | security | high | `pickle.load()` insecure deserialization |
| `auth.py` | security | high | `yaml.load()` unsafe loader |
| `auth.py` | security | high | `subprocess.run(shell=True)` |
| `data_processor.py` | deprecated_api | high | `df.append()` (pandas) |
| `data_processor.py` | deprecated_api | high | `df.iteritems()` (pandas 1.5) |
| `data_processor.py` | deprecated_api | high | `np.float()` alias |
| `data_processor.py` | code_smell | medium | `normalize_prices()` 7-level nesting, 7 params |
| `data_processor.py` | code_smell | medium | Dead code `_unused_legacy_helper`, `_old_batch_merger` |
| `api_handlers.py` | type_coverage | low | Zero type annotations across 6+ functions |
| `utils.py` | deprecated_api | high | `collections.MutableMapping` (Python 3.10+) |
| `utils.py` | deprecated_api | medium | `os.popen()` deprecated |
| `utils.py` | todo_comment | low | Module-level TODO to delete file |

---

## Key Files

| File | Purpose |
|---|---|
| [tests/e2e/test_full_workflow.py](tests/e2e/test_full_workflow.py) | Local CLI E2E (expanded) |
| [tests/e2e/test_azure_deployment.py](tests/e2e/test_azure_deployment.py) | Azure remote E2E |
| [scripts/smoke-mcp-remote.ps1](scripts/smoke-mcp-remote.ps1) | Quick Azure smoke test |
| [scripts/demo-run.ps1](scripts/demo-run.ps1) | Full demo rehearsal script |
| [demo/sample-enterprise-app/](demo/sample-enterprise-app/) | Realistic demo target |
| [src/codecustodian/mcp/server.py](src/codecustodian/mcp/server.py) | MCP server implementation |
| [src/codecustodian/enterprise/](src/codecustodian/enterprise/) | Enterprise features modules |
| [src/codecustodian/executor/safety_checks.py](src/codecustodian/executor/safety_checks.py) | Safety validator |
