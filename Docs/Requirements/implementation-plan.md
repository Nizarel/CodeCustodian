# CodeCustodian - Detailed Step-by-Step Implementation Plan

**Version:** 1.0  
**Date:** February 11, 2026  
**Source:** [features-requirements.md](features-requirements.md)  
**Purpose:** Actionable implementation guide with dependency-aware sequencing, technology validation, and MCP integration roadmap

---

## Table of Contents

1. [Implementation Overview](#1-implementation-overview)
2. [Pre-Implementation Setup](#2-pre-implementation-setup)
3. [Phase 1 — Core Architecture (Week 1–2)](#3-phase-1--core-architecture-week-12)
4. [Phase 2 — Scanner Modules (Week 3–4)](#4-phase-2--scanner-modules-week-34)
5. [Phase 3 — AI Planner Module (Week 5)](#5-phase-3--ai-planner-module-week-5)
6. [Phase 4 — Executor & Verifier (Week 6)](#6-phase-4--executor--verifier-week-6)
7. [Phase 5 — GitHub Integration (Week 7)](#7-phase-5--github-integration-week-7)
8. [Phase 6 — Testing & Polish (Week 8)](#8-phase-6--testing--polish-week-8)
9. [Phase 7 — Security & Beta Launch (Week 9–10)](#9-phase-7--security--beta-launch-week-910)
10. [Phase 8 — MCP Integration (Q2 2026)](#10-phase-8--mcp-integration-q2-2026)
11. [Technology Validation Notes](#11-technology-validation-notes)
12. [Risk Register & Mitigations](#12-risk-register--mitigations)
13. [Dependency Graph](#13-dependency-graph)

---

## 1. Implementation Overview

### Architecture Summary

CodeCustodian follows a **linear pipeline architecture**:

```
Scanner → Planner → Executor → Verifier → PR Creator
```

Each module is independently testable. The implementation order follows data-flow dependencies: you cannot build the Planner without the Finding dataclass from Scanner, you cannot build the Executor without the RefactoringPlan from Planner, etc.

### Key Technology Decisions Validated Against Online Docs

| Technology | Status | Notes |
|---|---|---|
| **MCP Python SDK** | ✅ `mcp[cli]` v1.26.0 stable (v2 pre-alpha) | Use **v1.x** for production. `MCPServer` (v2) or `FastMCP` (v1.x). Server exposes tools, resources, prompts via JSON-RPC 2.0. Transports: stdio, SSE, Streamable HTTP. |
| **GitHub Copilot SDK** | ⚠️ `github-copilot-sdk` is **not a public PyPI package** as of Feb 2026 | The requirements assume a hypothetical SDK. Implementation should use **GitHub Models API** (Azure AI Inference) or **GitHub Copilot Extensions API** as the real backend. Wrap behind an abstraction layer. |
| **PyGithub** | ✅ v2.1.1+ stable | Complete GitHub REST API wrapper for PR creation, issues, comments. |
| **GitPython** | ✅ v3.1.40+ stable | Git operations: blame, branching, commits, diffs. |
| **Typer** | ✅ v0.9.0+ stable | CLI framework with Rich integration. |
| **Pydantic** | ✅ v2.5.0+ stable | Config validation, model parsing. |
| **Radon** | ✅ v6.0.1+ stable | Cyclomatic complexity, maintainability index. |
| **Bandit** | ✅ v1.7.5+ stable | Security pattern scanning. |
| **Ruff** | ✅ v0.1.7+ stable | Fast Python linter with JSON output. |

---

## 2. Pre-Implementation Setup

### Step 2.1 — Repository Initialization

**Duration:** 1 day  
**Requirements covered:** FR-ARCH-002, FR-ARCH-003

```bash
# 1. Initialize project with uv (recommended by MCP Python SDK docs)
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
- [ ] Create GitHub repository `codecustodian/codecustodian`
- [ ] Initialize with `uv init` for modern Python project management
- [ ] Create directory structure matching FR-ARCH-002:

```
codecustodian/
├── src/
│   └── codecustodian/
│       ├── __init__.py
│       ├── scanner/
│       ├── planner/
│       ├── executor/
│       ├── verifier/
│       ├── github_integration/
│       ├── config/
│       ├── cli/
│       └── api/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── fixtures/
├── docs/
├── pyproject.toml
├── .codecustodian.yml        # Example config
├── .github/
│   └── workflows/
│       └── ci.yml
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
description = "Autonomous AI agent for technical debt management"
requires-python = ">=3.11"
dependencies = [
    # GitHub & Git
    "PyGithub>=2.1.1",
    "GitPython>=3.1.40",
    
    # Configuration
    "pyyaml>=6.0.1",
    "pydantic>=2.5.0",
    
    # CLI
    "typer>=0.9.0",
    "rich>=13.7.0",
    
    # Analysis
    "radon>=6.0.1",
    "astroid>=3.0.1",
    "bandit>=1.7.5",
    
    # AI (abstraction layer — see Step 5.1)
    "openai>=1.10.0",          # For GitHub Models API access
    "httpx>=0.25.0",           # HTTP client for API calls
    
    # Utilities
    "toml>=0.10.2",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.3",
    "pytest-cov>=4.1.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.1.7",
    "mypy>=1.7.1",
    "vcrpy>=6.0.0",           # API response recording
]
mcp = [
    "mcp[cli]>=1.26.0",       # MCP Python SDK (Q2 2026)
]

[project.scripts]
codecustodian = "codecustodian.cli.main:app"
```

Install:
```bash
uv add PyGithub GitPython pyyaml pydantic typer rich radon astroid bandit openai httpx toml
uv add --dev pytest pytest-cov pytest-asyncio ruff mypy vcrpy
```

### Step 2.3 — CI/CD Pipeline Setup

**Duration:** 0.5 day  
**Requirements covered:** FR-TEST-001

**Tasks:**
- [ ] Create `.github/workflows/ci.yml` with:
  - Lint (`ruff check`, `mypy`)
  - Test (`pytest --cov`)
  - Security scan (`bandit -r src/`)
  - Coverage gate (80% minimum)
- [ ] Create `.github/workflows/release.yml` for PyPI publishing
- [ ] Configure `ruff.toml` and `mypy.ini`

---

## 3. Phase 1 — Core Architecture (Week 1–2)

### Step 3.1 — Data Models & Exception Hierarchy

**Duration:** 2 days  
**Requirements covered:** FR-ARCH-004, FR-ARCH-005  
**File:** `src/codecustodian/models.py`

**Tasks:**
- [ ] **3.1.1** Define `Finding` dataclass with all fields from FR-ARCH-004:
  - `id`, `type`, `severity`, `file`, `line`, `description`, `suggestion`
  - `priority_score`, `metadata`, `context`, `timestamp`
- [ ] **3.1.2** Define `CodeContext` dataclass:
  - `code`, `line_start`, `line_end`, `function_signature`, `imports`
  - `has_tests`, `coverage_percentage`, `call_sites`, `last_modified`
- [ ] **3.1.3** Define `RefactoringPlan` Pydantic model (FR-PLAN-040):
  - `summary`, `reasoning`, `changes: List[CodeChange]`, `risks`
  - `requires_manual_verification`, `confidence_factors`, `confidence_score`
- [ ] **3.1.4** Define `CodeChange` Pydantic model:
  - `file`, `old_code`, `new_code`, `line_start`, `line_end`
- [ ] **3.1.5** Define `VerificationResult` dataclass (FR-VERIFY-001)
- [ ] **3.1.6** Define custom exception hierarchy (FR-ARCH-005):
  - `CodeCustodianError` → `ScannerError`, `PlannerError`, `ExecutorError`, `VerifierError`, `GitHubAPIError`

**Validation criteria:**
- All models serializable to JSON
- Pydantic models validate input on construction
- 100% type annotation coverage on all model classes

### Step 3.2 — Configuration System

**Duration:** 2 days  
**Requirements covered:** FR-CONFIG-001  
**Files:** `src/codecustodian/config/schema.py`, `src/codecustodian/config/defaults.py`

**Tasks:**
- [ ] **3.2.1** Implement `CodeCustodianConfig` Pydantic model hierarchy:
  - `ScannersConfig` → `DeprecatedAPIConfig`, `TODOConfig`, `CodeSmellConfig`
  - `BehaviorConfig` (max_prs_per_run, confidence_threshold, etc.)
  - `GitHubConfig` (pr_labels, reviewers, branch_prefix)
  - `CopilotConfig` (model_selection, temperature, max_tokens, max_cost_per_run)
- [ ] **3.2.2** Implement `from_yaml()` classmethod for loading `.codecustodian.yml`
- [ ] **3.2.3** Implement config merging: defaults ← file ← env vars ← CLI args
- [ ] **3.2.4** Create default `.codecustodian.yml` template with all options documented
- [ ] **3.2.5** Add Pydantic validators for cross-field constraints

**Validation criteria:**
- `CodeCustodianConfig()` with no args produces valid defaults
- Invalid YAML raises clear `ConfigurationError` with field path
- All config values are accessible via strongly typed properties

### Step 3.3 — Pipeline Orchestrator

**Duration:** 2 days  
**Requirements covered:** FR-ARCH-001  
**File:** `src/codecustodian/pipeline.py`

**Tasks:**
- [ ] **3.3.1** Implement `Pipeline` class with sequential stage execution:
  ```
  scan() → plan() → execute() → verify() → create_pr()
  ```
- [ ] **3.3.2** Implement fail-fast per-finding behavior:
  - Error in one finding → log, skip, continue to next
  - Error in infrastructure (Git, GitHub API) → abort run
- [ ] **3.3.3** Implement finding prioritization and batching:
  - Sort findings by `priority_score` descending
  - Respect `max_prs_per_run` limit
  - Respect `confidence_threshold` gate
- [ ] **3.3.4** Implement dry-run mode (scan + plan only, no execution)
- [ ] **3.3.5** Add structured logging at each stage transition (FR-OBS-001)
- [ ] **3.3.6** Add timing metrics per stage (FR-OBS-002)

**Validation criteria:**
- Pipeline handles empty findings list gracefully
- Pipeline handles scanner-only mode (no planner/executor)
- Each stage is replaceable (dependency injection)

### Step 3.4 — Structured Logging

**Duration:** 1 day  
**Requirements covered:** FR-OBS-001, FR-OBS-002  
**File:** `src/codecustodian/logging.py`

**Tasks:**
- [ ] **3.4.1** Implement `JSONFormatter` for structured JSON log output
- [ ] **3.4.2** Configure logging levels: DEBUG, INFO, WARNING, ERROR
- [ ] **3.4.3** Add context fields to all log entries: `timestamp`, `level`, `module`, `finding_id`, `stage`
- [ ] **3.4.4** Implement metrics collection:
  - Findings per scan, PRs per run, confidence distribution
  - Time per stage, cost per refactoring

**Tests to write:**
- [ ] `tests/unit/test_models.py` — Serialization, validation, priority calculation
- [ ] `tests/unit/test_config.py` — YAML loading, defaults, merging, validation
- [ ] `tests/unit/test_pipeline.py` — Orchestration logic with mocked stages

---

## 4. Phase 2 — Scanner Modules (Week 3–4)

### Step 4.1 — Base Scanner Interface

**Duration:** 1 day  
**Requirements covered:** FR-SCAN-001, FR-SCAN-002  
**File:** `src/codecustodian/scanner/base.py`

**Tasks:**
- [ ] **4.1.1** Implement `BaseScanner` ABC with:
  - `name`, `description`, `enabled` class attributes
  - `scan(repo_path: str) -> List[Finding]` abstract method
  - `is_excluded(file_path, exclude_patterns)` using `fnmatch`
  - `calculate_priority(finding) -> float` using the priority algorithm
- [ ] **4.1.2** Implement priority algorithm (FR-SCAN-002):
  - `Priority = (severity_weight × urgency × impact) / effort`
  - Range 0–200
  - Severity weights: critical=10, high=7, medium=4, low=2
- [ ] **4.1.3** Implement `ScannerRegistry` for dynamic scanner discovery:
  - Auto-discover all `BaseScanner` subclasses
  - Filter by enabled/disabled in config
  - Filter by `scan_type` CLI argument
- [ ] **4.1.4** Implement file-walking utility:
  - Walk `repo_path`, yield `.py` files
  - Respect `exclude_paths` from config (vendor, node_modules, .venv)
  - Respect `.gitignore` patterns

### Step 4.2 — Deprecated API Scanner

**Duration:** 3 days  
**Requirements covered:** FR-SCAN-010 through FR-SCAN-014  
**Files:** `src/codecustodian/scanner/deprecated_api.py`, `src/codecustodian/scanner/data/deprecations.json`

**Tasks:**
- [ ] **4.2.1** Create deprecation database JSON (FR-SCAN-011):
  - **pandas**: `DataFrame.append`, `DataFrame.swaplevel`, `read_table` defaults
  - **numpy**: `np.matrix`, `np.bool`, `np.int`, `np.float`, `np.complex`, `np.object`, `np.str`
  - **os**: `os.popen`, `os.system` (security implications)
  - **collections**: `collections.MutableMapping` → `collections.abc.MutableMapping`
  - **typing**: deprecated aliases (e.g., `typing.List` → `list` for Python 3.9+)
  - **unittest**: `assertEquals` → `assertEqual`
  - Include: `deprecated_since`, `removed_in`, `replacement`, `reason`, `severity`, `documentation` URL
- [ ] **4.2.2** Implement `DeprecatedAPIVisitor(ast.NodeVisitor)` (FR-SCAN-012):
  - `visit_Call` → Check function/method calls against DB
  - `visit_Import` / `visit_ImportFrom` → Check import statements
  - `get_full_name()` → Resolve `pd.DataFrame.append` from import aliases
  - Handle star imports and alias resolution
- [ ] **4.2.3** Implement import alias resolution:
  - Track `import pandas as pd` → map `pd` to `pandas`
  - Track `from pandas import DataFrame` → map `DataFrame` to `pandas.DataFrame`
- [ ] **4.2.4** Implement version-aware detection (FR-SCAN-014):
  - Parse `requirements.txt`, `pyproject.toml`, `setup.py`, `setup.cfg` for versions
  - Only flag APIs deprecated in the installed/specified version
- [ ] **4.2.5** Implement usage frequency counting (FR-SCAN-013):
  - Count occurrences per deprecated API across all files
  - Higher usage → higher priority_score

### Step 4.3 — TODO Comment Scanner

**Duration:** 2 days  
**Requirements covered:** FR-SCAN-020 through FR-SCAN-023  
**File:** `src/codecustodian/scanner/todo_comments.py`

**Tasks:**
- [ ] **4.3.1** Implement regex pattern matching (FR-SCAN-021):
  - Patterns: `TODO`, `FIXME`, `HACK`, `XXX`, `NOTE` (configurable)
  - Extract comment text after pattern
  - Handle inline comments and block comments
- [ ] **4.3.2** Implement Git blame integration (FR-SCAN-022):
  - Use `GitPython` `repo.blame('HEAD', file_path)`
  - Extract commit date and author for each TODO line
  - Calculate age in days
- [ ] **4.3.3** Implement age-based severity:
  - `> 180 days` → severity: medium
  - `> 90 days` → severity: low
  - `< 90 days` → skip (configurable via `max_age_days`)
- [ ] **4.3.4** Implement auto-issue creation flag (FR-SCAN-023):
  - If `> 180 days` and `auto_issue: true` in config
  - Set finding metadata `create_issue: true`
  - Will be handled in GitHub Integration phase

### Step 4.4 — Code Smell Scanner

**Duration:** 2 days  
**Requirements covered:** FR-SCAN-030 through FR-SCAN-033  
**File:** `src/codecustodian/scanner/code_smells.py`

**Tasks:**
- [ ] **4.4.1** Implement radon cyclomatic complexity integration (FR-SCAN-031):
  - Use `cc_visit()` for per-function complexity
  - Use `mi_visit()` for file-level maintainability index
  - Map radon ranks (A–F) to severity levels
- [ ] **4.4.2** Implement additional code smell detectors (FR-SCAN-032):
  - **Long functions**: AST `FunctionDef` with `end_lineno - lineno > threshold`
  - **Too many parameters**: `len(node.args.args) > threshold`
  - **Deep nesting**: Walk AST counting `If/For/While/With/Try` depth
  - **Dead code**: Functions/classes defined but never referenced (cross-file AST search)
- [ ] **4.4.3** Make all thresholds configurable (FR-SCAN-033):
  - Default: complexity=10, function_length=50, parameters=5, nesting_depth=4
  - Read from `config.scanners.code_smells.thresholds`

### Step 4.5 — Security Pattern Scanner

**Duration:** 2 days  
**Requirements covered:** FR-SCAN-040 through FR-SCAN-043  
**File:** `src/codecustodian/scanner/security.py`

**Tasks:**
- [ ] **4.5.1** Implement Bandit integration (FR-SCAN-041):
  - Initialize `BanditManager` with project config
  - Run `discover_files()` + `run_tests()`
  - Convert Bandit results to `Finding` objects with CWE references
- [ ] **4.5.2** Implement custom security patterns (FR-SCAN-042):
  - Hardcoded secrets (regex on password/api_key/token assignments)
  - Weak crypto (MD5, SHA1, `random.random`)
  - SQL injection patterns (`execute` with string formatting)
  - Command injection (`os.system`, `subprocess` with `shell=True`)
- [ ] **4.5.3** Implement severity mapping (FR-SCAN-043):
  - critical: hardcoded secrets, SQL injection, command injection
  - high: weak crypto, insecure random, unsafe deserialization
  - medium: missing security headers
  - low: weak SSL config

### Step 4.6 — Type Coverage Scanner

**Duration:** 1 day  
**Requirements covered:** FR-SCAN-050 through FR-SCAN-052  
**File:** `src/codecustodian/scanner/type_coverage.py`

**Tasks:**
- [ ] **4.6.1** Implement `TypeCoverageVisitor(ast.NodeVisitor)` (FR-SCAN-051):
  - Visit `FunctionDef` and `AsyncFunctionDef`
  - Check `node.returns` for return type annotation
  - Check `arg.annotation` for parameter type (skip `self`, `cls`)
  - Track `typed_functions / total_functions` ratio
- [ ] **4.6.2** Implement coverage reporting (FR-SCAN-052):
  - Report per-file and overall type coverage percentage
  - Only create findings for functions below threshold (default 80%)
  - Low severity since type hints are non-breaking

**Tests to write for Phase 2:**
- [ ] `tests/unit/test_scanners.py` — Each scanner with fixture files
- [ ] `tests/fixtures/sample_repos/` — Create repos with known issues:
  - `deprecated_apis/` — Files using `pd.DataFrame.append`, `np.matrix`
  - `old_todos/` — Files with dated TODOs
  - `complex_code/` — Functions with high complexity
  - `security_issues/` — Files with hardcoded secrets, SQL injection
  - `untyped_code/` — Files missing type annotations

---

## 5. Phase 3 — AI Planner Module (Week 5)

> **CRITICAL IMPLEMENTATION NOTE:** The requirements reference `github_copilot_sdk` which is not a real public Python package. Based on the current GitHub ecosystem (Feb 2026), the implementation must use one of:
>
> 1. **GitHub Models API** — Access GPT-4o, GPT-4o-mini, o1-preview via Azure AI Inference endpoint at `https://models.inference.ai.azure.com` using a GitHub PAT
> 2. **OpenAI-compatible API** — Use `openai` Python package pointed at GitHub Models endpoint
> 3. **Direct GitHub Copilot Chat Extensions** — Build as a Copilot Extension (server-sent events)
>
> **Recommended approach:** Use the `openai` Python package with GitHub Models API endpoint. This gives access to the same models referenced in the requirements (gpt-4o, gpt-4o-mini, o1-preview) through a familiar API. Wrap this behind an abstraction layer (`CopilotClient`) so it can be swapped for a real Copilot SDK when/if one becomes available.

### Step 5.1 — AI Client Abstraction Layer

**Duration:** 2 days  
**Requirements covered:** FR-PLAN-001, FR-PLAN-002  
**Files:** `src/codecustodian/planner/copilot_client.py`, `src/codecustodian/planner/models.py`

**Tasks:**
- [ ] **5.1.1** Define `AIClient` protocol/interface:
  ```python
  class AIClient(Protocol):
      async def create_session(self, model: str, temperature: float, max_tokens: int) -> "AISession": ...
  
  class AISession(Protocol):
      async def send_messages(self, messages: List[Message], tools: List[Tool]) -> AIResponse: ...
  ```
- [ ] **5.1.2** Implement `GitHubModelsClient(AIClient)`:
  - Use `openai.AsyncOpenAI` with `base_url="https://models.inference.ai.azure.com"`
  - Auth via `GITHUB_TOKEN` environment variable
  - Map tool definitions to OpenAI function calling format
  - Handle streaming and non-streaming responses
- [ ] **5.1.3** Implement model selection strategy (FR-PLAN-002):
  - `"auto"` mode: simple → `gpt-4o-mini`, moderate → `gpt-4o`, complex → `o1-preview`
  - `"fast"` mode: always `gpt-4o-mini`
  - `"balanced"` mode: always `gpt-4o`
  - `"reasoning"` mode: always `o1-preview`
- [ ] **5.1.4** Implement cost tracking:
  - Track input/output tokens per request
  - Accumulate cost per run using model pricing
  - Abort if `max_cost_per_run` exceeded
- [ ] **5.1.5** Implement retry logic with exponential backoff:
  - Retry on 429 (rate limit), 500, 503
  - Max 3 retries, respect `Retry-After` headers

### Step 5.2 — Custom Tool Definitions

**Duration:** 2 days  
**Requirements covered:** FR-PLAN-010, FR-PLAN-011  
**File:** `src/codecustodian/planner/tools.py`

**Tasks:**
- [ ] **5.2.1** Implement `get_function_definition` tool:
  - Input: `file_path`, `function_name`
  - Parse AST, find function node, extract source with 5 lines context
  - Return as string with line numbers
- [ ] **5.2.2** Implement `find_test_coverage` tool:
  - Input: `file_path`
  - Check convention: `test_<filename>.py` in `tests/`
  - Return `{has_tests, test_files, coverage_percentage}`
- [ ] **5.2.3** Implement `search_references` tool:
  - Input: `symbol_name`, `file_path`
  - Walk all `.py` files, parse AST, find `ast.Name` nodes matching symbol
  - Return list of `{file, line, context}` dicts
- [ ] **5.2.4** Implement `get_imports` tool:
  - Input: `file_path`
  - Parse AST, extract all `Import` and `ImportFrom` nodes
  - Return structured import list
- [ ] **5.2.5** Implement `get_call_sites` tool:
  - Input: `function_name`, `file_path`
  - Find all places the function is called across the codebase
  - Return call sites with context
- [ ] **5.2.6** Implement `check_type_hints` tool:
  - Input: `file_path`, `function_name`
  - Return missing type annotations for parameters and return type
- [ ] **5.2.7** Convert all tools to OpenAI function-calling JSON Schema format:
  - Each tool needs `name`, `description`, `parameters` (JSON Schema)
  - Register tools with the AI session

### Step 5.3 — Prompt Engineering

**Duration:** 1 day  
**Requirements covered:** FR-PLAN-020, FR-PLAN-021  
**File:** `src/codecustodian/planner/prompts.py`

**Tasks:**
- [ ] **5.3.1** Implement system prompt template (FR-PLAN-020):
  - Core principles: preserve behavior, minimal changes, type safety, readability
  - Output JSON schema specification
  - Available tools documentation
  - Strict output format instructions
- [ ] **5.3.2** Implement user prompt template (FR-PLAN-021):
  - Finding details section (type, severity, file, line, description)
  - Code context section (10 lines before/after)
  - Function signature section
  - Import statements section
  - Additional info (tests, coverage, call sites, last modified)
- [ ] **5.3.3** Implement prompt variants per finding type:
  - Deprecated API: include replacement docs, migration examples
  - TODO: include age, author, original context
  - Code smell: include complexity metrics, suggested patterns
  - Security: include CWE reference, severity justification
- [ ] **5.3.4** Implement token budget management:
  - Estimate token count for prompt + context
  - Truncate code context if exceeding model's context window
  - Reserve tokens for response

### Step 5.4 — Multi-Turn Conversation & Confidence Scoring

**Duration:** 1 day  
**Requirements covered:** FR-PLAN-030, FR-PLAN-040  
**Files:** `src/codecustodian/planner/confidence.py`, `src/codecustodian/planner/planner.py`

**Tasks:**
- [ ] **5.4.1** Implement multi-turn tool call loop:
  - Send initial messages with tools
  - While response has tool calls → execute tools → append results → resend
  - Max iterations: 5 (prevent infinite loops)
  - Timeout: 60 seconds per turn
- [ ] **5.4.2** Implement response parsing (FR-PLAN-040):
  - Extract JSON from markdown code fences (`\`\`\`json ... \`\`\``)
  - Validate with Pydantic `RefactoringPlan` model
  - Handle malformed responses with retry (up to 2 retries with clarification prompt)
- [ ] **5.4.3** Implement confidence scoring algorithm (FR-PLAN-030):
  - Start at 10
  - Deductions: no tests (−3), low coverage (−1), signature change (−2), multi-file (−2), manual verification (−2), high complexity (−1), logic changes (−1)
  - Boosts: simple replacement (+1), high coverage >90% (+1)
  - Clamp to [1, 10]
- [ ] **5.4.4** Implement confidence threshold gate:
  - If `confidence_score < config.behavior.confidence_threshold` → skip or draft PR
  - Log reasoning for low-confidence findings

**Tests to write for Phase 3:**
- [ ] `tests/unit/test_planner.py` — Mock AI responses, test parsing, confidence scoring
- [ ] `tests/unit/test_tools.py` — Each tool with fixture repos
- [ ] `tests/unit/test_prompts.py` — Template rendering, token estimation
- [ ] `tests/fixtures/mock_responses/` — Recorded AI API responses (VCR.py)

---

## 6. Phase 4 — Executor & Verifier (Week 6)

### Step 6.1 — Safe File Editor

**Duration:** 2 days  
**Requirements covered:** FR-EXEC-001, FR-EXEC-002  
**Files:** `src/codecustodian/executor/file_editor.py`, `src/codecustodian/executor/backup.py`

**Tasks:**
- [ ] **6.1.1** Implement `SafeFileEditor.apply_changes()`:
  1. Create timestamped backup in `.codecustodian-backups/`
  2. Read original file content
  3. Validate `old_code` appears exactly once (raise `ValueError` if 0 or >1)
  4. Replace `old_code` with `new_code`
  5. Validate syntax for `.py` files using `ast.parse()`
  6. Write to temp file in same directory
  7. Atomic rename: `tmp_path.replace(file_path)`
  8. Delete backup on success
  9. On any error: restore from backup, re-raise
- [ ] **6.1.2** Implement backup retention policy (FR-EXEC-002):
  - Default: 7 days retention
  - Cleanup on each run: delete backups older than retention period
  - Configurable via `config.behavior.backup_retention_days`
- [ ] **6.1.3** Implement multi-file change support:
  - Accept `List[CodeChange]` from `RefactoringPlan`
  - Apply changes in order, backing up all files first
  - If any change fails: rollback ALL files to backups
- [ ] **6.1.4** Handle edge cases:
  - Read-only files → clear error message
  - Binary files → skip
  - Files with encoding issues → detect encoding, preserve it
  - Very large files (>10MB per FR-SEC-002) → skip with warning

### Step 6.2 — Git Workflow Manager

**Duration:** 2 days  
**Requirements covered:** FR-EXEC-010  
**File:** `src/codecustodian/executor/git_manager.py`

**Tasks:**
- [ ] **6.2.1** Implement `create_refactoring_branch()`:
  - Ensure clean working tree (stash if needed)
  - Check out base branch (configurable, default `main`)
  - Pull latest from remote
  - Create branch: `tech-debt/{category}-{file_stem}-{YYYYMMDD-HHMM}`
  - Handle branch name conflicts (append suffix)
- [ ] **6.2.2** Implement `commit_changes()`:
  - Stage specified files with `git add`
  - Build conventional commit message format:
    ```
    refactor: <summary in 50 chars>
    
    Finding: <id>
    Type: <type>
    Severity: <severity>
    
    Changes:
    - <file1>
    - <file2>
    
    AI Reasoning:
    <truncated reasoning>
    
    Confidence: <score>/10
    Risk: <low/medium/high>
    
    Co-authored-by: CodeCustodian <bot@codecustodian.dev>
    ```
  - Commit with message
  - Return commit SHA
- [ ] **6.2.3** Implement `push_branch()`:
  - Push to remote with `--set-upstream`
  - Handle authentication errors clearly
- [ ] **6.2.4** Implement cleanup:
  - Switch back to base branch after PR creation
  - Delete local branch if PR created successfully
  - Handle merge conflicts (abort and log)

### Step 6.3 — Test Runner (Verifier)

**Duration:** 1.5 days  
**Requirements covered:** FR-VERIFY-001, FR-VERIFY-002  
**File:** `src/codecustodian/verifier/test_runner.py`

**Tasks:**
- [ ] **6.3.1** Implement test discovery:
  - Convention-based: `test_<filename>.py`
  - Pattern-based: `tests/**/test_*.py` matching changed file stems
  - Fallback: run ALL tests if no specific tests found
- [ ] **6.3.2** Implement pytest execution:
  - Use `pytest.main()` programmatically
  - Args: `--verbose`, `--tb=short`, `--cov=<src>`, `--cov-report=json`, `--junit-xml`
  - Timeout: 300 seconds (5 min per FR-PERF-001)
  - Capture stdout/stderr
- [ ] **6.3.3** Parse JUnit XML results:
  - Total, passed, failed, skipped counts
  - Failure details (test name, message, traceback)
- [ ] **6.3.4** Parse coverage JSON:
  - Overall coverage percentage
  - Per-file coverage for changed files
- [ ] **6.3.5** Implement coverage delta calculation (FR-VERIFY-002):
  - Store baseline in `.codecustodian-baseline.json`
  - Delta = current − baseline
  - Update baseline if coverage improved or unchanged

### Step 6.4 — Linting Pipeline (Verifier)

**Duration:** 1.5 days  
**Requirements covered:** FR-VERIFY-010  
**File:** `src/codecustodian/verifier/linter.py`

**Tasks:**
- [ ] **6.4.1** Implement `_run_ruff()`:
  - Execute `ruff check --output-format=json <files>`
  - Parse JSON array of violations
  - Map to `Violation` objects
- [ ] **6.4.2** Implement `_run_mypy()`:
  - Execute `mypy --show-error-codes --output=json <files>`
  - Parse line-delimited JSON output
  - Map to `Violation` objects
- [ ] **6.4.3** Implement `_run_bandit()`:
  - Execute `bandit -f json -r <files>`
  - Parse JSON results
  - Map to `Violation` objects
- [ ] **6.4.4** Implement baseline comparison:
  - Only fail on NEW violations (not pre-existing)
  - Load baseline from `.codecustodian-lint-baseline.json`
  - New violation = present in current but not in baseline
  - Save baseline if no new violations

**Tests to write for Phase 4:**
- [ ] `tests/unit/test_executor.py` — File editor with temp files, backup/restore
- [ ] `tests/unit/test_git_manager.py` — Git operations with temp repos
- [ ] `tests/unit/test_verifier.py` — Test runner and linter with fixture projects
- [ ] `tests/integration/test_pipeline.py` — End-to-end with mock AI, real Git

---

## 7. Phase 5 — GitHub Integration (Week 7)

### Step 7.1 — PR Creator

**Duration:** 2 days  
**Requirements covered:** FR-GITHUB-001  
**File:** `src/codecustodian/github_integration/pr_creator.py`

**Tasks:**
- [ ] **7.1.1** Implement `PRCreator.__init__()`:
  - Initialize `Github(token)` from PyGithub
  - Get `repo` object via `github.get_repo(repo_name)`
  - Validate token permissions (check for `repo` scope)
- [ ] **7.1.2** Implement `create_pr()`:
  - Generate title with emoji prefix per finding type (max 72 chars)
  - Generate rich PR body with sections:
    - Summary, Finding details, AI Reasoning, Changes (diff preview)
    - Risks, Verification results (tests, coverage, linting)
    - Confidence scoreboard with factor indicators
    - Footer with CodeCustodian attribution
  - Set `draft=True` if `confidence_score < 7`
  - Add labels from config (`tech-debt`, `automated`)
  - Request reviewers from config
- [ ] **7.1.3** Implement error handling:
  - 422 Unprocessable → branch doesn't exist or no diff
  - 403 Forbidden → token permission issue
  - Rate limiting → retry with backoff

### Step 7.2 — Issue Creator

**Duration:** 1 day  
**Requirements covered:** FR-GITHUB-010  
**File:** `src/codecustodian/github_integration/issues.py`

**Tasks:**
- [ ] **7.2.1** Implement `create_issue_from_todo()`:
  - Title: `TODO Cleanup: <todo_text[:50]>`
  - Body: location, code context, author, age, suggested action
  - Labels: `tech-debt`, `todo-cleanup`
  - Assignee: original author (if GitHub user exists)
- [ ] **7.2.2** Implement duplicate detection:
  - Search existing open issues for same file/line combo
  - Skip creation if duplicate found

### Step 7.3 — PR Comment Automation

**Duration:** 1 day  
**Requirements covered:** FR-COMP-005  
**File:** `src/codecustodian/github_integration/comments.py`

**Tasks:**
- [ ] **7.3.1** Implement inline PR comments:
  - Add review comments on specific changed lines
  - Include AI reasoning for each change
- [ ] **7.3.2** Implement summary comment:
  - Post overall summary as first PR comment
  - Include confidence score, risks, verification status
- [ ] **7.3.3** Implement audit trail comment (FR-COMP-001):
  - JSON-formatted audit log as collapsed `<details>` block
  - Includes timestamp, finding_id, action, changes, verification

**Tests to write for Phase 5:**
- [ ] `tests/unit/test_pr_creator.py` — Mock PyGithub, test title/body generation
- [ ] `tests/unit/test_issues.py` — Mock issue creation, duplicate detection
- [ ] `tests/integration/test_github_api.py` — VCR-recorded GitHub API interactions

---

## 8. Phase 6 — Testing & Polish (Week 8)

### Step 8.1 — CLI Implementation

**Duration:** 2 days  
**Requirements covered:** FR-CLI-001  
**File:** `src/codecustodian/cli/main.py`

**Tasks:**
- [ ] **8.1.1** Implement `run` command:
  - Options: `--repo-path`, `--config`, `--max-prs`, `--scan-type`, `--dry-run`, `--verbose`, `--debug`
  - Rich console output with progress bars and tables
  - Summary table at end showing all findings and their status
- [ ] **8.1.2** Implement `init` command:
  - Create `.codecustodian.yml` with documented defaults
  - Create `.github/workflows/codecustodian.yml` GitHub Action
  - Interactive prompts for initial configuration
- [ ] **8.1.3** Implement `validate` command:
  - Parse and validate config file
  - Report any issues with clear messages
- [ ] **8.1.4** Implement `scan` command (scan-only, no AI):
  - Run all scanners
  - Display findings in Rich table
  - Export to JSON/CSV
- [ ] **8.1.5** Implement `version` and `help` commands

### Step 8.2 — Comprehensive Testing

**Duration:** 3 days  
**Requirements covered:** FR-TEST-001 through FR-TEST-003

**Tasks:**
- [ ] **8.2.1** Achieve 80%+ overall coverage, 90%+ for executor and verifier
- [ ] **8.2.2** Create integration test suite:
  - `test_pipeline.py` — Full pipeline with fixture repo, mock AI, real Git
  - `test_github_api.py` — VCR-recorded API interactions
- [ ] **8.2.3** Create E2E test:
  - `test_full_workflow.py` — Scan → Plan → Execute → Verify → (mock) PR creation
  - Use a real fixture repository with known issues
- [ ] **8.2.4** Create fixture repositories:
  - `tests/fixtures/sample_repos/healthy/` — Clean repo, no findings expected
  - `tests/fixtures/sample_repos/deprecated/` — Known deprecated API usage
  - `tests/fixtures/sample_repos/complex/` — High-complexity functions
  - `tests/fixtures/sample_repos/insecure/` — Security vulnerabilities
- [ ] **8.2.5** Mock strategy:
  - Mock AI API responses using VCR.py recordings
  - Mock GitHub API using VCR.py
  - Use `tmp_path` fixture for Git operations
  - Mock subprocess calls for linter execution

### Step 8.3 — Documentation

**Duration:** 1 day

**Tasks:**
- [ ] **8.3.1** Write `README.md` with:
  - Quick start (3-step install)
  - Configuration reference
  - Scanner descriptions
  - CLI reference
  - Architecture diagram
- [ ] **8.3.2** Write `CONTRIBUTING.md`
- [ ] **8.3.3** Add type stubs and docstrings to all public APIs
- [ ] **8.3.4** Create example `.codecustodian.yml` for different project types

---

## 9. Phase 7 — Security & Beta Launch (Week 9–10)

### Step 9.1 — Security Hardening

**Duration:** 2 days  
**Requirements covered:** FR-SEC-001 through FR-SEC-003

**Tasks:**
- [ ] **9.1.1** Secrets management (FR-SEC-001):
  - Audit all logging: ensure no token/secret leakage
  - Use `GITHUB_TOKEN` environment variable only (never config file)
  - Validate token permissions at startup
  - Mask token in error messages
- [ ] **9.1.2** Code execution safety (FR-SEC-002):
  - Validate all file paths: prevent path traversal with `os.path.realpath()` check
  - Enforce 10MB file size limit
  - No `eval()`, `exec()`, or dynamic code execution
  - Sanitize all AI-generated code before writing
- [ ] **9.1.3** Audit trail (FR-SEC-003):
  - Generate JSON audit log for every refactoring decision
  - Include: timestamp, finding_id, action, user, changes, verification, pr_number
  - Store in `.codecustodian-audit/` directory
  - SOC 2-compliant format (FR-COMP-001)
- [ ] **9.1.4** Run `bandit` on CodeCustodian's own codebase
- [ ] **9.1.5** Add security policy `SECURITY.md`

### Step 9.2 — Performance Optimization

**Duration:** 1 day  
**Requirements covered:** FR-PERF-001 through FR-PERF-003

**Tasks:**
- [ ] **9.2.1** Parallel scanning (FR-PERF-002):
  - Use `concurrent.futures.ProcessPoolExecutor(max_workers=4)`
  - Each scanner runs in parallel across files
  - Target: 1000 files < 30 seconds
- [ ] **9.2.2** API cost optimization (FR-PERF-003):
  - Implement token caching for repeated context lookups
  - Select cheapest model meeting confidence threshold
  - Rate limit: max 20 requests/minute
- [ ] **9.2.3** Performance benchmarks:
  - Create benchmark script with medium-sized repo (500 files)
  - Measure time per stage
  - Set CI gates for regression

### Step 9.3 — GitHub Action & Marketplace

**Duration:** 2 days

**Tasks:**
- [ ] **9.3.1** Create `action.yml` for GitHub Actions Marketplace:
  ```yaml
  name: 'CodeCustodian'
  description: 'Autonomous AI agent for technical debt management'
  inputs:
    github-token:
      description: 'GitHub token with repo scope'
      required: true
    config-path:
      description: 'Path to .codecustodian.yml'
      default: '.codecustodian.yml'
    max-prs:
      description: 'Max PRs to create per run'
      default: '5'
  runs:
    using: 'composite'
    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install codecustodian
      - run: codecustodian run --max-prs ${{ inputs.max-prs }}
  ```
- [ ] **9.3.2** Create example workflow for users
- [ ] **9.3.3** Publish to PyPI
- [ ] **9.3.4** Submit to GitHub Marketplace

---

## 10. Phase 8 — MCP Integration (Q2 2026)

> **Based on MCP Python SDK documentation (v1.26.0, v2 pre-alpha — reviewed Feb 2026):**
>
> The MCP (Model Context Protocol) is an open standard for connecting AI applications to external systems via JSON-RPC 2.0. MCP servers expose **Tools** (executable functions), **Resources** (read-only data), and **Prompts** (interaction templates).
>
> **Key decisions for CodeCustodian MCP integration:**
> - Use **MCP Python SDK v1.x** (`mcp[cli]>=1.26.0`) for production stability (v2 is pre-alpha)
> - For v1.x: Use `FastMCP` class; for v2: Use `MCPServer` class
> - Transport: Start with **stdio** for local development, then add **Streamable HTTP** for remote deployment
> - Expose CodeCustodian scanners as MCP **Tools** and findings as MCP **Resources**

### Step 10.1 — MCP Server Scaffold

**Duration:** 2 days  
**Requirements covered:** FR-EXT-001  
**File:** `src/codecustodian/mcp/server.py`

**Tasks:**
- [ ] **10.1.1** Initialize MCP server:
  ```python
  # Using MCP Python SDK v1.x (FastMCP)
  from mcp.server.fastmcp import FastMCP
  
  mcp = FastMCP("codecustodian")
  ```
  OR (if using v2 MCPServer — available if stable by Q2 2026):
  ```python
  from mcp.server.mcpserver import MCPServer
  
  mcp = MCPServer("codecustodian")
  ```
- [ ] **10.1.2** Add lifespan for initialization:
  - Load CodeCustodian config
  - Initialize scanner registry
  - Initialize Git repository context
- [ ] **10.1.3** Configure transports:
  - **stdio** for local IDE integration (VS Code, Claude Desktop)
  - **Streamable HTTP** for remote server deployment

### Step 10.2 — Expose Scanners as MCP Tools

**Duration:** 3 days  
**Requirements covered:** FR-EXT-001  
**File:** `src/codecustodian/mcp/tools.py`

> **MCP Tool requirements (from MCP docs):**
> - Tools are executable functions that AI applications invoke
> - Defined with name, description, and JSON Schema `inputSchema`
> - Can return text, images, or structured data
> - Support progress reporting via `ctx.report_progress()`

**Tasks:**
- [ ] **10.2.1** Implement `scan_repository` tool:
  ```python
  @mcp.tool()
  async def scan_repository(
      repo_path: str, 
      scanner_type: str = "all",
      ctx: Context
  ) -> str:
      """Scan a repository for technical debt issues.
      
      Args:
          repo_path: Path to the repository to scan
          scanner_type: Type of scanner (all, deprecated_api, todo_comments, code_smells, security, type_coverage)
      """
      # Run scanners with progress reporting
      await ctx.report_progress(progress=0.0, total=1.0, message="Starting scan...")
      findings = run_scanners(repo_path, scanner_type)
      await ctx.report_progress(progress=1.0, total=1.0, message=f"Found {len(findings)} issues")
      return format_findings_as_text(findings)
  ```
- [ ] **10.2.2** Implement `plan_refactoring` tool:
  ```python
  @mcp.tool()
  async def plan_refactoring(finding_id: str) -> str:
      """Generate an AI-powered refactoring plan for a specific finding."""
      # Retrieve finding, generate plan via AI client
      ...
  ```
- [ ] **10.2.3** Implement `apply_refactoring` tool:
  ```python
  @mcp.tool()
  async def apply_refactoring(plan_id: str, dry_run: bool = True) -> str:
      """Apply a refactoring plan to the codebase.
      
      Args:
          plan_id: ID of the plan to apply
          dry_run: If true, preview changes without applying
      """
      ...
  ```
- [ ] **10.2.4** Implement `verify_changes` tool:
  ```python
  @mcp.tool()
  async def verify_changes(changed_files: list[str]) -> str:
      """Run tests and linters on changed files."""
      ...
  ```
- [ ] **10.2.5** Implement `create_pull_request` tool:
  ```python
  @mcp.tool()
  async def create_pull_request(branch_name: str, finding_id: str) -> str:
      """Create a GitHub PR for the applied changes."""
      ...
  ```

### Step 10.3 — Expose Findings as MCP Resources

**Duration:** 1 day  
**Requirements covered:** FR-EXT-001  
**File:** `src/codecustodian/mcp/resources.py`

> **MCP Resource requirements (from MCP docs):**
> - Resources are read-only data sources (like GET endpoints)
> - Identified by URIs (e.g., `findings://repo/deprecated-api`)
> - Can be direct resources (fixed URI) or templates (dynamic URI with parameters)
> - Support subscriptions for change notifications

**Tasks:**
- [ ] **10.3.1** Implement findings resource:
  ```python
  @mcp.resource("findings://{repo_name}/all")
  def get_all_findings(repo_name: str) -> str:
      """Get all findings for a repository."""
      findings = load_cached_findings(repo_name)
      return json.dumps([f.to_dict() for f in findings])
  
  @mcp.resource("findings://{repo_name}/{finding_type}")
  def get_findings_by_type(repo_name: str, finding_type: str) -> str:
      """Get findings filtered by type."""
      ...
  ```
- [ ] **10.3.2** Implement config resource:
  ```python
  @mcp.resource("config://settings")
  def get_config() -> str:
      """Get current CodeCustodian configuration."""
      return config.model_dump_json(indent=2)
  ```
- [ ] **10.3.3** Implement scan history resource:
  ```python
  @mcp.resource("history://{repo_name}/scans")
  def get_scan_history(repo_name: str) -> str:
      """Get scan history for a repository."""
      ...
  ```

### Step 10.4 — MCP Prompts

**Duration:** 1 day  
**File:** `src/codecustodian/mcp/prompts.py`

> **MCP Prompt requirements (from MCP docs):**
> - Prompts are reusable interaction templates
> - User-controlled (require explicit invocation)
> - Can be parameterized

**Tasks:**
- [ ] **10.4.1** Implement refactoring prompt:
  ```python
  @mcp.prompt(title="Refactor Tech Debt")
  def refactor_finding(finding_id: str, approach: str = "safe") -> str:
      """Guide the AI through refactoring a specific finding.
      
      Args:
          finding_id: The UUID of the finding to refactor
          approach: safe (minimal changes) or aggressive (full rewrite)
      """
      return f"""Review finding {finding_id} and create a refactoring plan.
      Approach: {approach}
      Use scan_repository and plan_refactoring tools to analyze and fix."""
  ```
- [ ] **10.4.2** Implement scan summary prompt:
  ```python
  @mcp.prompt(title="Scan Summary")
  def scan_summary(repo_path: str) -> str:
      """Summarize technical debt in a repository."""
      return f"""Scan {repo_path} using scan_repository tool, then provide a summary:
      - Total findings by severity
      - Top 5 most critical issues
      - Recommended fix priority"""
  ```

### Step 10.5 — MCP Server Deployment & Testing

**Duration:** 1 day

**Tasks:**
- [ ] **10.5.1** Add MCP server entry point:
  ```python
  # src/codecustodian/mcp/server.py
  def main():
      mcp.run(transport="stdio")  # For local
      # or: mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
  ```
- [ ] **10.5.2** Add to `pyproject.toml`:
  ```toml
  [project.scripts]
  codecustodian = "codecustodian.cli.main:app"
  codecustodian-mcp = "codecustodian.mcp.server:main"
  ```
- [ ] **10.5.3** Test with MCP Inspector:
  ```bash
  uv run mcp dev src/codecustodian/mcp/server.py
  # Opens MCP Inspector UI to test tools, resources, prompts
  ```
- [ ] **10.5.4** Test with Claude Desktop:
  - Add to `claude_desktop_config.json`:
  ```json
  {
    "mcpServers": {
      "codecustodian": {
        "command": "uv",
        "args": ["--directory", "/path/to/codecustodian", "run", "codecustodian-mcp"]
      }
    }
  }
  ```
- [ ] **10.5.5** Test with VS Code (if MCP support available):
  - Configure as VS Code MCP server
  - Verify tool discovery and execution

---

## 11. Technology Validation Notes

### 11.1 — MCP Python SDK (Validated Against Official Docs)

| Feature | v1.x (Stable) | v2 (Pre-alpha) | CodeCustodian Decision |
|---|---|---|---|
| Server class | `FastMCP` | `MCPServer` | Use `FastMCP` for initial release; migrate to `MCPServer` when v2 stabilizes |
| Tools | `@mcp.tool()` decorator | `@mcp.tool()` decorator | Same API — migration is trivial |
| Resources | `@mcp.resource("uri://template")` | `@mcp.resource("uri://template")` | Same API |
| Prompts | `@mcp.prompt()` | `@mcp.prompt(title="...")` | v2 adds `title` parameter |
| Transports | stdio, SSE | stdio, SSE, Streamable HTTP | Use stdio initially, add HTTP later |
| Context | `ctx: Context` parameter injection | `ctx: Context` parameter injection | Same pattern |
| Progress | `await ctx.report_progress()` | `await ctx.report_progress()` | Same API |
| Authentication | N/A | OAuth 2.1 `TokenVerifier` | Add when deploying as remote server |
| Install | `pip install "mcp[cli]"` | Same | Use `uv add "mcp[cli]"` |

**Key finding:** The v2 `MCPServer` API is very close to v1 `FastMCP`. The main differences are:
- v2 adds structured output validation against JSON Schema
- v2 adds `_meta` field for client-only data
- v2 adds `Streamable HTTP` transport for production deployments
- v2 adds lifespan management with typed context

**Recommendation:** Start with v1.x `FastMCP` for initial MCP integration. The tool/resource/prompt definitions will be forward-compatible.

### 11.2 — GitHub Copilot SDK (Not Publicly Available)

The requirements reference `github-copilot-sdk ^0.1.0` which does not exist on PyPI. Based on current GitHub offerings:

**Available alternatives:**
1. **GitHub Models API** — Best fit. Provides access to GPT-4o, GPT-4o-mini, o1-preview via `https://models.inference.ai.azure.com` using GitHub PAT. Uses OpenAI-compatible API.
2. **GitHub Copilot Extensions** — For building chat-based extensions. Uses SSE protocol. More suitable for the MCP integration phase.
3. **Azure OpenAI** — Enterprise alternative with same models.

**Implementation approach:**
```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=os.environ["GITHUB_TOKEN"]
)

response = await client.chat.completions.create(
    model="gpt-4o",  # or "gpt-4o-mini", "o1-preview"
    messages=[...],
    tools=[...],     # Function calling
    temperature=0.1,
    max_tokens=4096
)
```

This provides the same capabilities as the hypothetical `github-copilot-sdk`: model selection, tool calling, multi-turn conversations.

### 11.3 — Bandit Integration Notes

Bandit's programmatic API (`bandit.core.manager.BanditManager`) is not well-documented and may break between versions. **Safer approach:** Run bandit as a subprocess with JSON output:

```python
result = subprocess.run(
    ["bandit", "-f", "json", "-r", repo_path, "-c", bandit_config_path],
    capture_output=True, text=True
)
data = json.loads(result.stdout)
```

This is more stable across Bandit versions and matches how ruff and mypy are invoked.

---

## 12. Risk Register & Mitigations

| # | Risk | Probability | Impact | Mitigation |
|---|---|---|---|---|
| 1 | **GitHub Copilot SDK doesn't materialize** | Medium | High | Already mitigated: use GitHub Models API via OpenAI client. Wrap behind `AIClient` protocol for swappability. |
| 2 | **MCP SDK v2 has breaking changes** | Medium | Medium | Use v1.x `FastMCP` initially. API surface for tools/resources/prompts is stable across versions. |
| 3 | **AI generates unsafe code** | Medium | Critical | AST syntax validation before writing. Git backup + rollback. Test verification gate. Draft PR for low-confidence changes. |
| 4 | **Rate limiting on GitHub Models API** | High | Medium | Implement exponential backoff. Use cheapest model (gpt-4o-mini) for simple tasks. Cache repeated context lookups. Track cost per run. |
| 5 | **Bandit programmatic API breaks** | Low | Low | Use subprocess invocation with JSON output. More stable interface. |
| 6 | **Multi-file refactoring causes cascading failures** | Medium | High | Atomic rollback for all files on any failure. Run full test suite after multi-file changes. Cap multi-file changes at 5 files. |
| 7 | **Poor AI refactoring quality** | Medium | High | Confidence scoring gate. Human review required for low-confidence. Iterative multi-turn conversation for more context. |
| 8 | **Test suite takes too long** | Low | Medium | Run only relevant tests (by changed file). 300-second timeout. Parallel test execution. |
| 9 | **Git conflicts with concurrent runs** | Low | Medium | Lock file mechanism for concurrent runs. Branch name timestamps prevent collisions. Clean working tree check before each finding. |
| 10 | **Token/secret leakage in logs** | Low | Critical | Audit all logging paths. Use `GITHUB_TOKEN` env var only. Mask tokens in error messages. Never log API request/response bodies. |

---

## 13. Dependency Graph

```
Week 1-2:  [Models] ──→ [Config] ──→ [Pipeline] ──→ [Logging]
              │            │
              ▼            ▼
Week 3-4:  [Base Scanner] ──→ [Deprecated API Scanner]
              │                [TODO Scanner]
              │                [Code Smell Scanner]
              │                [Security Scanner]
              │                [Type Coverage Scanner]
              │
              ▼
Week 5:    [AI Client] ──→ [Tools] ──→ [Prompts] ──→ [Confidence] ──→ [Planner]
              │
              ▼
Week 6:    [File Editor] ──→ [Git Manager] ──→ [Test Runner] ──→ [Linter]
              │                                     │
              ▼                                     ▼
Week 7:    [PR Creator] ──→ [Issue Creator] ──→ [Comments]
              │
              ▼
Week 8:    [CLI] ──→ [Integration Tests] ──→ [E2E Tests] ──→ [Docs]
              │
              ▼
Week 9-10: [Security] ──→ [Performance] ──→ [GitHub Action] ──→ [PyPI Release]
              │
              ▼
Q2 2026:   [MCP Server] ──→ [MCP Tools] ──→ [MCP Resources] ──→ [MCP Prompts]
```

### Critical Path

The critical path runs through:

**Models → Config → Pipeline → Base Scanner → AI Client → File Editor → PR Creator → CLI → Release**

Any delay on these items directly impacts the ship date. Scanner modules, verification, and MCP integration can proceed in parallel where dependencies are met.

---

## Summary of Deliverables by Phase

| Phase | Duration | Key Deliverables | Requirements Covered |
|---|---|---|---|
| Pre-Implementation | 2 days | Repo, deps, CI | FR-ARCH-002, FR-ARCH-003 |
| Phase 1: Core Architecture | 2 weeks | Models, Config, Pipeline, Logging | FR-ARCH-001/004/005, FR-CONFIG-001, FR-OBS-001/002 |
| Phase 2: Scanners | 2 weeks | 5 scanner modules + fixtures | FR-SCAN-001 through FR-SCAN-052 |
| Phase 3: AI Planner | 1 week | AI client, tools, prompts, confidence | FR-PLAN-001 through FR-PLAN-040 |
| Phase 4: Executor + Verifier | 1 week | File editor, Git manager, test runner, linter | FR-EXEC-001/002/010, FR-VERIFY-001/002/010 |
| Phase 5: GitHub Integration | 1 week | PR creation, issues, comments | FR-GITHUB-001/010, FR-COMP-001/002/003/005 |
| Phase 6: Testing & Polish | 1 week | CLI, 80%+ coverage, docs | FR-CLI-001, FR-TEST-001/002/003 |
| Phase 7: Security & Beta | 2 weeks | Security hardening, perf, Action, release | FR-SEC-001/002/003, FR-PERF-001/002/003 |
| Phase 8: MCP Integration | Q2 2026 | MCP server with tools, resources, prompts | FR-EXT-001 |

**Total MVP timeline:** 10 weeks (Phases 1–7)  
**MCP Integration:** Q2 2026 add-on (1–2 weeks)

---

**END OF IMPLEMENTATION PLAN**

| Document | Word Count | Requirements Mapped |
|---|---|---|
| Implementation Plan | ~4,500 | 150+ from features-requirements.md |
| Phases | 8 + pre-implementation | 10-week MVP + Q2 MCP |
| Technology validations | 3 (MCP SDK, GitHub Copilot SDK, Bandit) | All verified against online docs |
