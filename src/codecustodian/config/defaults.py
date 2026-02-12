"""Default configuration values.

Provides a canonical default ``CodeCustodianConfig`` instance and the
raw YAML string that ships with the tool when no user config exists.
"""

from __future__ import annotations

from codecustodian.config.schema import CodeCustodianConfig

DEFAULT_CONFIG = CodeCustodianConfig()


def get_default_config() -> CodeCustodianConfig:
    """Return a fresh default configuration instance."""
    return CodeCustodianConfig()


DEFAULT_YAML = """\
version: "1.0"

scanners:
  deprecated_apis:
    enabled: true
    severity: high
    libraries:
      - pandas
      - numpy
      - requests
      - django
      - flask

  todo_comments:
    enabled: true
    max_age_days: 90
    patterns:
      - TODO
      - FIXME
      - HACK
      - XXX

  code_smells:
    enabled: true
    cyclomatic_complexity: 10
    function_length: 50
    nesting_depth: 4
    max_parameters: 5

  security_patterns:
    enabled: true

  type_coverage:
    enabled: true
    target_coverage: 80

behavior:
  max_prs_per_run: 5
  require_human_review: true
  auto_merge: false
  draft_prs_for_complex: true
  confidence_threshold: 7
  max_files_per_pr: 5
  max_lines_per_pr: 500
  auto_split_prs: true
  proposal_mode_threshold: 5
  enable_alternatives: true

github:
  pr_labels:
    - tech-debt
    - automated
    - codecustodian
  base_branch: main
  branch_prefix: tech-debt
  delete_branch_on_merge: true

azure:
  devops_org_url: ""
  devops_pat: ""
  devops_project: ""
  monitor_connection_string: ""
  tenant_id: ""
  keyvault_name: ""

work_iq:
  enabled: false
  mcp_server_url: ""
  api_key: ""

budget:
  monthly_budget: 500.0
  alert_thresholds:
    - 50
    - 80
    - 90
    - 100
  hard_limit: true

approval:
  require_plan_approval: false
  require_pr_approval: true
  approved_repos: []
  sensitive_paths:
    - "**/auth/**"
    - "**/payments/**"
    - "**/security/**"

notifications:
  severity_threshold: medium
  events:
    - pr_created
    - pipeline_failed

advanced:
  copilot:
    model_selection: auto
    temperature: 0.1
    max_tokens: 4096
    timeout: 30
    max_cost_per_run: 5.00

  git:
    author_name: CodeCustodian
    author_email: bot@codecustodian.dev

  testing:
    framework: pytest
    timeout: 300
    coverage_threshold: 80
    fail_on_coverage_decrease: true

  linting:
    tools:
      - ruff
      - mypy
      - bandit
    fail_on: new_violations_only

  exclude_paths:
    - "vendor/**"
    - "node_modules/**"
    - "*.min.js"
    - "migrations/**"
    - ".venv/**"
    - "build/**"
    - "dist/**"
"""
