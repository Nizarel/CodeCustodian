# CodeCustodian

<div align="center">

![CodeCustodian Logo](https://via.placeholder.com/200x200/20B2AA/FFFFFF?text=CC)

**The autonomous guardian of your codebase**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/Nizarel/CodeCustodian/actions/workflows/ci.yml/badge.svg)](https://github.com/Nizarel/CodeCustodian/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![GitHub Actions](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF?logo=github-actions)](https://github.com/features/actions)
[![Powered by GitHub Copilot](https://img.shields.io/badge/Powered%20by-GitHub%20Copilot-000000?logo=github)](https://github.com/features/copilot)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)

[Features](#-features) •
[Quick Start](#-quick-start) •
[Documentation](#-documentation) •
[Examples](#-examples) •
[Contributing](#-contributing) •
[Roadmap](#-roadmap)

</div>

---

## 🎯 What is CodeCustodian?

CodeCustodian is an **autonomous AI agent** that runs in your CI/CD pipeline, continuously scanning your codebase for maintenance opportunities and automatically creating pull requests with intelligent refactorings—**all while you sleep**.

Think of it as a **headless developer** dedicated to technical debt management, powered by GitHub Copilot SDK's advanced reasoning capabilities.

### The Problem

Engineering teams spend **40-60% of their time** on maintenance tasks:
- 🔴 Migrating deprecated APIs before they break production
- 📝 Converting ancient TODO comments into actionable work
- 🧹 Refactoring code smells that slow down development
- 🔄 Updating patterns after framework upgrades

### The Solution

CodeCustodian automates this maintenance work:
- ✅ **Scans** your codebase for issues (deprecated APIs, TODOs, code smells)
- 🤖 **Plans** refactorings using GitHub Copilot SDK (with full AI reasoning)
- ✏️ **Applies** changes safely with atomic operations and backups
- ✔️ **Verifies** correctness with automated tests and linting
- 📬 **Creates** pull requests with detailed explanations

**Result:** Your team focuses on innovation while CodeCustodian handles the janitorial work.

---

## 🌟 Key Features

### 🔍 Intelligent Scanners

| Scanner | What It Detects | Example |
|---------|----------------|---------|
| **Deprecated APIs** | Library functions marked for removal | `pandas.DataFrame.append()` → `pd.concat()` |
| **TODO Comments** | Aging technical debt markers | TODOs older than 90 days |
| **Code Smells** | Complexity and maintainability issues | Functions with cyclomatic complexity >10 |
| **Security Patterns** | Outdated security practices | MD5 hashing, hardcoded secrets |
| **Type Coverage** | Missing type annotations | Untyped function parameters |

### 🧠 GitHub Copilot SDK Integration

- **Multi-turn conversations** with AI for complex refactorings
- **Custom tools** for codebase inspection (get imports, find tests, search references)
- **Confidence scoring** (1-10) for every refactoring decision
- **Model routing**: Simple tasks use fast models, complex use deep reasoning (o1-preview)
- **Explainable AI**: Every decision includes step-by-step reasoning

### 🛡️ Safety Guarantees

- ✅ **Atomic file operations** (all-or-nothing updates)
- ✅ **Automatic backups** before every change
- ✅ **Syntax validation** (AST parsing before commit)
- ✅ **Test execution** (pytest with coverage tracking)
- ✅ **Linting verification** (ruff, mypy, bandit)
- ✅ **Rollback on failure** (automatic restoration)

### 📊 Enterprise Features

- 📈 **Analytics dashboard** (tech debt trends, PR metrics)
- 🔔 **Slack/email notifications**
- 👥 **Multi-repository management**
- 🎛️ **Configuration UI** (no YAML editing required)
- 🔐 **SOC 2 ready** (audit trails, encryption, RBAC)
- 💰 **Budget management** (per-team cost tracking and enforcement)
- 📋 **SLA & reliability reporting** (success rates, failure trends, alerts)

### 🧠 Business Intelligence & Learning

- 📊 **5-factor business impact scoring** — usage frequency, criticality, change frequency, velocity impact, regulatory risk
- 🔄 **Dynamic re-prioritization** — event-driven adjustments for production incidents, CVEs, deadlines, budget changes
- 📝 **Feedback loop** — learns from PR outcomes (merged/rejected/modified) to improve over time
- 🎯 **Team preference learning** — remembers coding preferences and injects them into AI prompts
- 🏛️ **Historical pattern recognition** — queries past refactorings across the org for similar patterns
- 📈 **Auto-adjusting confidence** — scanner success rates automatically tune confidence thresholds

---

## 🚀 Quick Start

### Prerequisites

- GitHub account with GitHub Copilot subscription ($10-19/month)
- Repository with GitHub Actions enabled
- Python 3.11+ codebase (JavaScript/TypeScript support coming Q2 2026)

### Installation (3 minutes)

#### Step 1: Add GitHub Actions Workflow

Create `.github/workflows/codecustodian.yml`:

```yaml
name: 🛡️ CodeCustodian

on:
  schedule:
    - cron: '0 2 * * *'  # Run daily at 2 AM UTC
  workflow_dispatch:      # Allow manual trigger

permissions:
  contents: write
  pull-requests: write
  issues: write

jobs:
  maintenance:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history for git blame
      
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      
      - name: Install CodeCustodian
        run: pip install codecustodian-cli
      
      - name: Run CodeCustodian
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          COPILOT_TOKEN: ${{ secrets.COPILOT_TOKEN }}
        run: |
          codecustodian run \
            --repo-path . \
            --config .codecustodian.yml \
            --max-prs 5
      
      - name: Upload results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: codecustodian-report
          path: reports/
```

#### Step 2: Add Configuration File

Create `.codecustodian.yml` in your repository root:

```yaml
version: "1.0"

# Scanner configuration
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
    thresholds:
      cyclomatic_complexity: 10
      function_length: 50
      nesting_depth: 4
      parameters: 5

# Behavior configuration
behavior:
  max_prs_per_run: 5
  require_human_review: true
  auto_merge: false
  draft_prs_for_complex: true
  confidence_threshold: 7  # Only create PRs if confidence ≥7/10

# GitHub integration
github:
  pr_labels:
    - tech-debt
    - automated
    - codecustodian
  reviewers:
    - tech-lead
  branch_prefix: "tech-debt"

# Notifications (optional)
notifications:
  slack:
    enabled: false
    webhook_url: ${SLACK_WEBHOOK_URL}
  email:
    enabled: false
    recipients:
      - team@example.com

# Advanced settings
advanced:
  copilot:
    model_selection: auto  # auto | fast | balanced | reasoning
    temperature: 0.1
    max_tokens: 4096
  
  git:
    commit_message_format: "refactor: {summary}\n\n{body}"
    branch_name_format: "{category}-{file}-{timestamp}"
  
  exclude_paths:
    - "vendor/**"
    - "node_modules/**"
    - "*.min.js"
```

#### Step 3: Add GitHub Copilot Token

1. Generate token: [GitHub Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens)
   - Scopes needed: `copilot`, `repo`, `workflow`
2. Add to repository: Settings → Secrets and variables → Actions → New repository secret
   - Name: `COPILOT_TOKEN`
   - Value: (your token)

#### Step 4: Trigger First Run

**Option A:** Wait for scheduled run (2 AM UTC)

**Option B:** Manual trigger
1. Go to Actions tab
2. Click "CodeCustodian" workflow
3. Click "Run workflow" → Run

**Expected output:**
- 5 pull requests created (or fewer, depending on findings)
- Detailed scan report in Actions artifacts
- Slack notification (if configured)

### Optional: Validate remote MCP endpoint (Azure Container Apps)

After deployment, run:

```powershell
pwsh ./scripts/smoke-mcp-remote.ps1 -Fqdn "<your-container-app-fqdn>"
```

This validates `/health`, MCP `initialize`, `tools/list`, and `tools/call` (`list_scanners`).

---

## 📖 Documentation

### Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Scanner Deep Dive](#scanner-deep-dive)
3. [Planner Module (Copilot SDK)](#planner-module)
4. [Executor & Safety](#executor--safety)
5. [Verification System](#verification-system)
6. [Configuration Reference](#configuration-reference)
7. [CLI Reference](#cli-reference)
8. [API Documentation](#api-documentation)
9. [Extending CodeCustodian](#extending-codecustodian)
10. [Troubleshooting](#troubleshooting)

---

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions Runner                     │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  CodeCustodian CLI (Python)                           │  │
│  │                                                        │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────┐ │  │
│  │  │ Scanner  │→│ Planner  │→│ Executor │→│Verify│ │  │
│  │  │ Module   │  │(Copilot) │  │ Module   │  │Module│ │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────┘ │  │
│  └───────────────────────────────────────────────────────┘  │
│                           ↓                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  GitHub API: Create Pull Requests                     │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Key Design Principles:**

1. **Pipeline Architecture**: Linear flow (scan → plan → execute → verify → PR)
2. **Fail-Fast**: Errors in any stage abort the current finding, continue to next
3. **Idempotent**: Running multiple times produces same result (deterministic)
4. **Isolated**: Each finding processed independently (parallel-safe)
5. **Transparent**: Every decision logged and auditable

---

### Scanner Deep Dive

#### How Scanners Work

Each scanner implements the `BaseScanner` interface:

```python
from typing import List
from codecustodian.scanner.base import BaseScanner, Finding

class DeprecatedAPIScanner(BaseScanner):
    def scan(self, repo_path: str) -> List[Finding]:
        """
        Scan repository for deprecated API usage.
        
        Returns:
            List of Finding objects, sorted by priority
        """
        findings = []
        
        # 1. Parse all Python files
        for py_file in self.find_python_files(repo_path):
            tree = ast.parse(py_file.read_text())
            
            # 2. Check against deprecation rules
            for node in ast.walk(tree):
                if self.is_deprecated(node):
                    findings.append(
                        Finding(
                            type="deprecated_api",
                            severity="high",
                            file=str(py_file),
                            line=node.lineno,
                            description=f"{node.name} is deprecated",
                            suggestion=self.get_replacement(node),
                            priority_score=self.calculate_priority(node)
                        )
                    )
        
        return sorted(findings, key=lambda f: f.priority_score, reverse=True)
```

#### Priority Scoring Algorithm

```python
def calculate_priority(finding: Finding) -> float:
    """
    Priority = (Severity × Urgency × Impact) / Effort
    
    Range: 0-200
    - Critical findings: 150-200
    - High priority: 100-150
    - Medium priority: 50-100
    - Low priority: 0-50
    """
    severity_weight = {
        "critical": 10,
        "high": 7,
        "medium": 4,
        "low": 2
    }
    
    urgency_weight = {
        "api_removed_soon": 3.0,    # < 6 months
        "api_deprecated_old": 2.0,  # > 1 year ago
        "api_deprecated_new": 1.5,  # < 1 year ago
        "soft_deprecation": 1.0     # No removal date
    }
    
    impact_weight = {
        "usage_frequency": finding.usage_count / 10,  # More uses = higher impact
        "file_criticality": 2.0 if "core/" in finding.file else 1.0,
        "recent_changes": 1.5 if finding.last_modified < 30 else 1.0
    }
    
    effort_factor = {
        "simple_replacement": 1.0,
        "moderate_refactor": 0.7,
        "complex_migration": 0.4
    }
    
    severity = severity_weight[finding.severity]
    urgency = urgency_weight[finding.urgency]
    impact = sum(impact_weight.values())
    effort = effort_factor[finding.complexity]
    
    return (severity * urgency * impact) / effort
```

#### Adding Custom Scanners

Create `my_scanner.py`:

```python
from codecustodian.scanner.base import BaseScanner, Finding

class MyCustomScanner(BaseScanner):
    """Detects print() statements in production code."""
    
    def scan(self, repo_path: str) -> List[Finding]:
        findings = []
        
        for py_file in Path(repo_path).rglob("*.py"):
            if "test" in str(py_file):
                continue  # Skip test files
            
            tree = ast.parse(py_file.read_text())
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and \
                   isinstance(node.func, ast.Name) and \
                   node.func.id == "print":
                    findings.append(
                        Finding(
                            type="print_statement",
                            severity="low",
                            file=str(py_file),
                            line=node.lineno,
                            description="print() found in production code",
                            suggestion="Use proper logging (logger.info)",
                            priority_score=30.0
                        )
                    )
        
        return findings
```

Register in `.codecustodian.yml`:

```yaml
scanners:
  my_custom_scanner:
    enabled: true
    module: my_scanner.MyCustomScanner
```

---

### Planner Module

#### GitHub Copilot SDK Integration

```python
from github_copilot_sdk import CopilotClient, Message, Tool

class CopilotPlanner:
    def __init__(self, token: str):
        self.client = CopilotClient(token=token)
    
    def plan_refactoring(self, finding: Finding, context: Context) -> RefactoringPlan:
        """
        Generate refactoring plan using Copilot SDK.
        
        Args:
            finding: Detected issue
            context: Code context (imports, type hints, tests, etc.)
        
        Returns:
            RefactoringPlan with code changes and AI reasoning
        """
        # 1. Build prompt with full context
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(finding, context)
        
        # 2. Define custom tools for codebase inspection
        tools = [
            Tool(
                name="get_function_definition",
                description="Get full definition of a function",
                parameters={"function_name": "str"}
            ),
            Tool(
                name="find_test_coverage",
                description="Check if tests exist for this code",
                parameters={"file_path": "str"}
            )
        ]
        
        # 3. Create Copilot session
        session = self.client.create_session(
            model=self._select_model(finding),
            temperature=0.1,
            max_tokens=4096
        )
        
        # 4. Multi-turn conversation
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt)
        ]
        
        response = session.send_messages(messages, tools=tools)
        
        # 5. Handle tool calls (if AI requests more info)
        while response.has_tool_calls():
            tool_results = self._execute_tools(response.tool_calls)
            messages.append(Message(role="assistant", content=response.content))
            messages.append(Message(role="tool", content=tool_results))
            response = session.send_messages(messages, tools=tools)
        
        # 6. Parse AI response into structured plan
        plan = self._parse_plan(response.content)
        plan.confidence_score = self._calculate_confidence(plan, context)
        plan.ai_reasoning = response.reasoning  # Copilot SDK provides reasoning
        
        return plan
    
    def _select_model(self, finding: Finding) -> str:
        """Route to appropriate model based on complexity."""
        if finding.complexity == "simple":
            return "gpt-4o-mini"  # Fast, cheap
        elif finding.complexity == "moderate":
            return "gpt-4o"       # Balanced
        else:
            return "o1-preview"   # Deep reasoning
    
    def _calculate_confidence(self, plan: RefactoringPlan, context: Context) -> int:
        """
        Score confidence 1-10 based on multiple factors.
        
        High confidence (9-10):
        - Direct 1:1 API replacement
        - Comprehensive test coverage
        - No breaking changes to function signature
        
        Low confidence (1-4):
        - Complex multi-file refactoring
        - No test coverage
        - Significant logic changes
        """
        score = 10
        
        # Deductions
        if not context.has_tests:
            score -= 3
        if plan.changes_signature:
            score -= 2
        if len(plan.files_to_change) > 3:
            score -= 2
        if plan.requires_manual_verification:
            score -= 2
        
        return max(1, score)
```

#### Prompt Engineering

**System Prompt:**

```text
You are CodeCustodian, an expert Python refactoring assistant. Your job is to 
transform deprecated or problematic code into modern, maintainable equivalents 
while preserving exact functionality.

Core Principles:
1. Preserve behavior: Never change what the code does, only how it does it
2. Minimal changes: Only modify what's necessary to fix the issue
3. Type safety: Maintain or improve type annotations
4. Readability: Prefer clarity over cleverness
5. Test compatibility: Ensure existing tests still pass

Output Format:
- Provide exact code replacements (not descriptions)
- Include line-by-line reasoning
- Specify confidence level (1-10)
- Flag any risks or assumptions

Context Provided:
- Code snippet with 10 lines before/after
- Function signature and type hints
- Import statements
- Test coverage information
- Related function call sites
```

**User Prompt Example:**

```text
Issue: pandas.DataFrame.append() is deprecated (removed in pandas 3.0)

File: src/data_processor.py
Line: 42

Code Context:
```python
# Lines 32-52
import pandas as pd
from typing import Dict, List

def process_batches(batches: List[Dict]) -> pd.DataFrame:
    """Process multiple data batches into single DataFrame."""
    result = pd.DataFrame()
    
    for batch in batches:
        new_row = pd.DataFrame([batch])
        result = result.append(new_row, ignore_index=True)  # ← ISSUE HERE
    
    return result

# Tests: tests/test_data_processor.py
# Coverage: 87% (function is covered)
# Called from: 3 locations (src/main.py:45, src/pipeline.py:102, src/api.py:33)
```

Task: Refactor to use pd.concat() while maintaining exact behavior.

Requirements:
- Preserve function signature
- Keep ignore_index=True behavior
- Maintain type hints
- Ensure tests still pass
```

---

### Executor & Safety

#### Atomic File Operations

```python
class SafeFileEditor:
    """Applies code changes with atomic operations and rollback."""
    
    def apply_changes(self, file_path: Path, old_str: str, new_str: str) -> None:
        """
        Replace old_str with new_str in file, atomically.
        
        Process:
        1. Create timestamped backup
        2. Read original content
        3. Apply string replacement (must be unique)
        4. Validate syntax (AST parse)
        5. Write to temp file
        6. Atomic rename (temp → original)
        7. Delete backup on success
        
        On any error: restore from backup
        """
        backup_path = self._create_backup(file_path)
        
        try:
            # Read original
            original = file_path.read_text()
            
            # Apply replacement
            if original.count(old_str) != 1:
                raise ValueError(f"old_str must appear exactly once, found {original.count(old_str)}")
            
            modified = original.replace(old_str, new_str, 1)
            
            # Validate syntax
            if file_path.suffix == ".py":
                ast.parse(modified)  # Raises SyntaxError if invalid
            
            # Write atomically
            temp_path = file_path.with_suffix(".tmp")
            temp_path.write_text(modified)
            temp_path.replace(file_path)  # Atomic on POSIX
            
            # Success: remove backup
            backup_path.unlink()
            
        except Exception as e:
            # Rollback
            self._restore_backup(backup_path, file_path)
            raise RuntimeError(f"Failed to apply changes: {e}")
    
    def _create_backup(self, file_path: Path) -> Path:
        """Create timestamped backup in .codecustodian-backups/"""
        backup_dir = Path(".codecustodian-backups")
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = backup_dir / f"{file_path.name}-{timestamp}.bak"
        
        shutil.copy2(file_path, backup_path)
        return backup_path
```

#### Git Workflow

```python
from git import Repo

class GitWorkflowManager:
    """Manages git operations for refactorings."""
    
    def create_refactoring_branch(self, finding: Finding) -> str:
        """
        Create feature branch for refactoring.
        
        Branch naming: tech-debt/{category}-{file}-{timestamp}
        Example: tech-debt/deprecated-api-utils-20260211-1430
        """
        repo = Repo(".")
        
        # Ensure on main and up-to-date
        repo.git.checkout("main")
        repo.git.pull("origin", "main")
        
        # Generate semantic branch name
        category = finding.type.replace("_", "-")
        file_short = Path(finding.file).stem[:20]
        timestamp = datetime.now().strftime("%Y%m%d-%H%M")
        branch_name = f"tech-debt/{category}-{file_short}-{timestamp}"
        
        # Create and checkout branch
        repo.git.checkout("-b", branch_name)
        
        return branch_name
    
    def commit_changes(self, finding: Finding, plan: RefactoringPlan) -> str:
        """
        Commit with conventional commit message format.
        
        Format:
        refactor: <summary in 50 chars>
        
        Finding: <finding-id>
        Type: <finding-type>
        Severity: <severity>
        
        Changes:
        - <file1>
        - <file2>
        
        AI Reasoning:
        <truncated reasoning from Copilot>
        
        Confidence: <score>/10
        Risk: <low/medium/high>
        
        Co-authored-by: CodeCustodian <bot@codecustodian.dev>
        """
        repo = Repo(".")
        
        # Stage all changes
        repo.git.add("-A")
        
        # Build commit message
        summary = plan.summary[:50]
        body = f"""
Finding: {finding.id}
Type: {finding.type}
Severity: {finding.severity}

Changes:
{self._format_changed_files(plan)}

AI Reasoning:
{plan.ai_reasoning[:500]}...

Confidence: {plan.confidence_score}/10
Risk: {plan.risk_level}

Co-authored-by: CodeCustodian <bot@codecustodian.dev>
"""
        
        commit_msg = f"refactor: {summary}\n\n{body.strip()}"
        
        # Commit
        repo.git.commit("-m", commit_msg)
        
        # Get commit SHA
        return repo.head.commit.hexsha
```

---

### Verification System

#### Test Execution

```python
import pytest
import json
from pathlib import Path

class TestRunner:
    """Execute tests and collect coverage."""
    
    def run_tests(self, changed_files: List[Path]) -> VerificationResult:
        """
        Run pytest on tests covering changed files.
        
        Returns:
            VerificationResult with pass/fail, coverage delta, failures
        """
        # 1. Discover relevant tests
        test_files = self._discover_tests(changed_files)
        
        # 2. Run pytest with coverage
        pytest_args = [
            "--verbose",
            "--cov=src",
            "--cov-report=json",
            "--cov-report=term",
            "--junit-xml=results.xml",
            "--tb=short",
            *[str(f) for f in test_files]
        ]
        
        exit_code = pytest.main(pytest_args)
        
        # 3. Parse results
        results = self._parse_junit_xml("results.xml")
        coverage = self._parse_coverage_json(".coverage.json")
        
        return VerificationResult(
            passed=(exit_code == 0),
            tests_run=results["total"],
            tests_passed=results["passed"],
            tests_failed=results["failed"],
            coverage_overall=coverage["overall"],
            coverage_delta=self._calculate_coverage_delta(coverage),
            failures=results["failures"] if exit_code != 0 else []
        )
    
    def _discover_tests(self, changed_files: List[Path]) -> List[Path]:
        """
        Find tests covering changed files using conventions.
        
        Strategies:
        1. Convention: test_<filename>.py
        2. Pattern: tests/**/test_*.py matching path
        3. Coverage report: files with >50% coverage of changed code
        """
        test_files = set()
        
        for changed_file in changed_files:
            # Convention-based
            test_name = f"test_{changed_file.stem}.py"
            test_path = Path("tests") / test_name
            if test_path.exists():
                test_files.add(test_path)
            
            # Pattern-based search
            for test_file in Path("tests").rglob("test_*.py"):
                if changed_file.stem in test_file.stem:
                    test_files.add(test_file)
        
        return sorted(test_files)
```

#### Linting Pipeline

```python
class LinterRunner:
    """Execute linters and collect violations."""
    
    def run_linters(self, changed_files: List[Path]) -> LintResult:
        """
        Run ruff, mypy, bandit on changed files.
        
        Returns:
            LintResult with violations per tool
        """
        results = {
            "ruff": self._run_ruff(changed_files),
            "mypy": self._run_mypy(changed_files),
            "bandit": self._run_bandit(changed_files)
        }
        
        # Only fail on NEW violations (compare to baseline)
        baseline = self._load_baseline()
        new_violations = self._filter_new(results, baseline)
        
        return LintResult(
            passed=(len(new_violations) == 0),
            ruff_violations=results["ruff"],
            mypy_errors=results["mypy"],
            bandit_issues=results["bandit"],
            new_violations=new_violations
        )
    
    def _run_ruff(self, files: List[Path]) -> List[Violation]:
        """Run ruff linter with JSON output."""
        result = subprocess.run(
            ["ruff", "check", "--output-format=json", *files],
            capture_output=True,
            text=True
        )
        
        violations = json.loads(result.stdout)
        
        return [
            Violation(
                file=v["filename"],
                line=v["location"]["row"],
                code=v["code"],
                message=v["message"],
                severity="error" if v["code"].startswith("E") else "warning"
            )
            for v in violations
        ]
```

---

### Configuration Reference

Complete `.codecustodian.yml` schema:

```yaml
# Version (required)
version: "1.0"

# Scanner Configuration
scanners:
  # Deprecated API Scanner
  deprecated_apis:
    enabled: true
    severity: high  # critical | high | medium | low
    
    # Libraries to check (with version-aware rules)
    libraries:
      - name: pandas
        deprecated_since: "1.4.0"
      - name: numpy
        deprecated_since: "1.20.0"
      - name: requests
      - name: django
      - name: flask
    
    # Custom deprecation patterns
    custom_patterns:
      - pattern: "\.iteritems\(\)"
        replacement: ".items()"
        message: "dict.iteritems() removed in Python 3"
      - pattern: "unittest\.TestCase\.assertEquals"
        replacement: "unittest.TestCase.assertEqual"
    
    # Exclusions
    exclude:
      - "migrations/**"
      - "vendor/**"
  
  # TODO Comment Tracker
  todo_comments:
    enabled: true
    max_age_days: 90
    
    patterns:
      - TODO
      - FIXME
      - HACK
      - XXX
      - NOTE
    
    # Auto-create issues for old TODOs
    auto_issue:
      enabled: true
      age_threshold: 90
      labels: ["tech-debt", "todo-cleanup"]
    
    # Notify original authors
    notify_authors: true
  
  # Code Smell Detector
  code_smells:
    enabled: true
    
    thresholds:
      cyclomatic_complexity: 10
      function_length: 50
      nesting_depth: 4
      parameters: 5
      file_length: 500
    
    detect:
      - dead_code: true
      - duplicate_code: true  # Clone detection (>6 lines)
      - long_functions: true
      - complex_conditions: true
      - god_classes: true
  
  # Security Pattern Scanner
  security_patterns:
    enabled: true
    
    detect:
      - hardcoded_secrets: true
      - weak_crypto: true  # MD5, SHA1
      - sql_injection_risk: true
      - command_injection_risk: true
      - insecure_random: true  # random.random() in security code
  
  # Type Coverage Scanner
  type_coverage:
    enabled: true
    target_coverage: 80  # % of functions with type hints
    
    strict_mode: false  # Require return types
    check_variables: false  # Check variable annotations

# Behavior Configuration
behavior:
  max_prs_per_run: 5
  
  # PR creation strategy
  pr_strategy: separate  # separate | grouped | batched
  
  # Review requirements
  require_human_review: true
  auto_merge: false
  draft_prs_for_complex: true
  
  # Confidence threshold (1-10)
  confidence_threshold: 7  # Only create PRs if ≥7
  
  # Complexity handling
  max_complexity: moderate  # simple | moderate | complex
  skip_complex_refactorings: false

# GitHub Integration
github:
  # PR configuration
  pr_labels:
    - tech-debt
    - automated
    - codecustodian
  
  pr_title_format: "🔄 {type}: {summary}"
  
  # Reviewers
  reviewers:
    - tech-lead
    - senior-dev
  
  # Team assignments
  team_reviewers:
    - core-team
  
  # Branch configuration
  base_branch: main
  branch_prefix: "tech-debt"
  
  # Auto-cleanup
  delete_branch_on_merge: true
  
  # Status checks
  require_status_checks:
    - codecustodian/verification
    - codecustodian/tests

# Notifications
notifications:
  slack:
    enabled: false
    webhook_url: ${SLACK_WEBHOOK_URL}
    
    notify_on:
      - pr_created
      - pr_merged
      - scan_completed
      - error_occurred
    
    channel: "#tech-debt"
    mention_on_error: "@tech-lead"
  
  email:
    enabled: false
    smtp_server: smtp.gmail.com
    smtp_port: 587
    from_address: bot@example.com
    
    recipients:
      - team@example.com
    
    digest: daily  # daily | weekly | immediate
  
  discord:
    enabled: false
    webhook_url: ${DISCORD_WEBHOOK_URL}

# Advanced Settings
advanced:
  # Copilot SDK configuration
  copilot:
    model_selection: auto  # auto | fast | balanced | reasoning
    
    model_override:
      simple: gpt-4o-mini
      moderate: gpt-4o
      complex: o1-preview
    
    temperature: 0.1
    max_tokens: 4096
    timeout: 30  # seconds
    
    # Cost controls
    max_cost_per_run: 5.00  # USD
    
    # Rate limiting
    rate_limit:
      requests_per_minute: 20
      concurrent_sessions: 3
  
  # Git configuration
  git:
    commit_message_format: "refactor: {summary}\n\n{body}"
    branch_name_format: "{category}-{file}-{timestamp}"
    
    author:
      name: CodeCustodian
      email: bot@codecustodian.dev
  
  # File operations
  files:
    backup_enabled: true
    backup_retention_days: 7
    backup_location: .codecustodian-backups/
    
    atomic_operations: true
    validate_syntax: true
  
  # Testing
  testing:
    framework: pytest  # pytest | unittest
    timeout: 300  # seconds
    coverage_threshold: 80  # %
    
    # Fail on coverage decrease
    fail_on_coverage_decrease: true
    
    # Parallel execution
    parallel: true
    workers: auto  # auto | 1-16
  
  # Linting
  linting:
    tools:
      - ruff
      - mypy
      - bandit
    
    fail_on: new_violations_only  # any | new_violations_only | critical_only
    
    baseline_file: .codecustodian-baseline.json
  
  # Performance
  performance:
    cache_enabled: true
    cache_ttl: 3600  # seconds
    
    parallel_scanning: true
    max_workers: 4
  
  # Exclusions
  exclude_paths:
    - "vendor/**"
    - "node_modules/**"
    - "*.min.js"
    - "migrations/**"
    - ".venv/**"
    - "build/**"
    - "dist/**"
  
  exclude_files:
    - "*.pyc"
    - "__pycache__"
  
  # Telemetry (opt-in, anonymous)
  telemetry:
    enabled: false
    endpoint: https://codecustodian.dev/api/telemetry
    
    collect:
      - scan_metrics
      - pr_success_rate
      - error_types
    
    # Never collected: code, repo names, file contents
```

---

### CLI Reference

```bash
# ── Main Commands ──────────────────────────────────────────────

# Run full pipeline (scan → plan → execute → verify → PR)
codecustodian run [OPTIONS]
#   --repo-path PATH          Path to repository (default: .)
#   --config PATH             Config file path (default: .codecustodian.yml)
#   --max-prs INT             Max PRs per run (default: 5)
#   --scan-type TYPE          Scanner filter (all|deprecated_apis|todo_comments|...)
#   --dry-run                 Preview without creating PRs
#   --verbose / -v            Verbose logging
#   --quiet / -q              Suppress non-error output
#   --debug                   Enable debug mode (full traces)
#   --log-file PATH           Log to file
#   --enable-work-iq          Enable Work IQ integration
#   --output-format FMT       Output format: table or json

# Initialize CodeCustodian in a repository
codecustodian init [PATH] [OPTIONS]
#   --template NAME           Policy template:
#                              security_first, deprecations_first,
#                              low_risk_maintenance, full_scan (default)

# Validate configuration
codecustodian validate [OPTIONS]
#   --path PATH               Config file path (default: .codecustodian.yml)

# ── Scanning ───────────────────────────────────────────────────

# Run scanners without creating PRs
codecustodian scan [OPTIONS]
#   --repo-path PATH          Repository path
#   --scanner NAME            Scanner to run (default: all)
#   --config PATH             Config file path
#   --output-format FMT       Output: table, json, or csv

# List and filter findings
codecustodian findings [OPTIONS]
#   --repo-path PATH          Repository path
#   --config PATH             Config file path
#   --type NAME               Filter by finding type
#   --severity LEVEL          Filter by severity (critical|high|medium|low)
#   --status STATE            Filter by status (open|resolved)
#   --file PATTERN            Filter by file path substring
#   --output-format FMT       Output: table, json, or csv

# ── Actions ────────────────────────────────────────────────────

# Create PRs for top N findings
codecustodian create-prs [OPTIONS]
#   --repo-path PATH          Repository path
#   --config PATH             Config file path
#   --top INT                 Top N findings to process (default: 5)
#   --dry-run                 Preview mode

# Onboard a repository or organization
codecustodian onboard [OPTIONS]
#   --repo-path PATH          Repository path
#   --org NAME                Organization name (org-level onboarding)
#   --template NAME           Onboarding template

# ── Reporting ──────────────────────────────────────────────────

# Show findings, budget, and SLA status
codecustodian status [OPTIONS]
#   --repo-path PATH          Repository path
#   --config PATH             Config file path

# Generate ROI report
codecustodian report [OPTIONS]
#   --period YYYY-MM          Report period
#   --format FMT              Report format: json or csv
#   --output PATH             Write report to file

# ── Other ──────────────────────────────────────────────────────

# Interactive menu for common workflows
codecustodian interactive [OPTIONS]
#   --repo-path PATH          Repository path
#   --config PATH             Config file path

# Show version
codecustodian version
```

#### Examples

```bash
# Run with defaults
codecustodian run

# Dry-run (preview only)
codecustodian run --dry-run

# Only scan for deprecated APIs
codecustodian run --scan-type deprecated_apis

# Create up to 10 PRs
codecustodian run --max-prs 10

# Custom config location
codecustodian run --config configs/prod.yml

# Scan and output JSON
codecustodian scan --output-format json

# Filter high-severity findings in a specific file
codecustodian findings --severity high --file utils.py

# Generate CSV ROI report
codecustodian report --format csv --output roi.csv

# Initialize with security-first template
codecustodian init --template security_first
```

---

### API Documentation

#### Python API

```python
from codecustodian import CodeCustodian
from codecustodian.config import Config

# Initialize
config = Config.from_file(".codecustodian.yml")
custodian = CodeCustodian(
    repo_path=".",
    config=config,
    github_token="ghp_xxx",
    copilot_token="ghc_xxx"
)

# Run scan
findings = custodian.scan()
print(f"Found {len(findings)} issues")

# Process findings
for finding in findings[:5]:
    # Plan refactoring
    plan = custodian.plan(finding)
    print(f"Confidence: {plan.confidence_score}/10")
    
    # Execute if high confidence
    if plan.confidence_score >= 7:
        result = custodian.execute(plan)
        
        # Verify
        verification = custodian.verify(result)
        
        # Create PR
        if verification.passed:
            pr = custodian.create_pr(result, verification)
            print(f"Created PR #{pr.number}")
```

#### REST API (Dashboard)

```bash
# Authenticate
curl -X POST https://codecustodian.dev/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"github_token": "ghp_xxx"}'

# Response: {"session_token": "jwt_xxx"}

# List repositories
curl https://codecustodian.dev/api/repositories \
  -H "Authorization: Bearer jwt_xxx"

# Get repository findings
curl https://codecustodian.dev/api/repositories/{repo_id}/findings \
  -H "Authorization: Bearer jwt_xxx"

# Get analytics
curl https://codecustodian.dev/api/repositories/{repo_id}/analytics?period=30d \
  -H "Authorization: Bearer jwt_xxx"

# Trigger manual scan
curl -X POST https://codecustodian.dev/api/repositories/{repo_id}/scan \
  -H "Authorization: Bearer jwt_xxx"
```

---

### Extending CodeCustodian

#### Custom Scanner Plugin

```python
# plugins/my_scanner.py
from codecustodian.scanner.base import BaseScanner, Finding
from typing import List

class NoAssertScanner(BaseScanner):
    """Detect raw assert statements (should use pytest.raises)."""
    
    name = "no_assert_scanner"
    description = "Detects raw assert in test files"
    
    def scan(self, repo_path: str) -> List[Finding]:
        findings = []
        
        test_files = Path(repo_path).glob("tests/**/*.py")
        
        for test_file in test_files:
            tree = ast.parse(test_file.read_text())
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Assert):
                    findings.append(
                        Finding(
                            type="raw_assert",
                            severity="low",
                            file=str(test_file),
                            line=node.lineno,
                            description="Use pytest.raises instead of assert",
                            suggestion="with pytest.raises(Exception): ...",
                            priority_score=20.0,
                            metadata={
                                "scanner": self.name
                            }
                        )
                    )
        
        return findings
```

Register:

```yaml
# .codecustodian.yml
scanners:
  no_assert_scanner:
    enabled: true
    module: plugins.my_scanner.NoAssertScanner
```

#### Custom Copilot Tool

```python
from github_copilot_sdk import Tool

def create_dependency_graph_tool():
    """Custom tool for analyzing import dependencies."""
    
    def get_dependencies(file_path: str) -> dict:
        """Return all imports and their sources."""
        tree = ast.parse(Path(file_path).read_text())
        
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend([alias.name for alias in node.names])
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module)
        
        return {"file": file_path, "imports": imports}
    
    return Tool(
        name="get_dependencies",
        description="Get all import dependencies for a file",
        parameters={"file_path": {"type": "string"}},
        function=get_dependencies
    )

# Register in planner
planner.add_tool(create_dependency_graph_tool())
```

---

### Troubleshooting

#### Common Issues

**1. `COPILOT_TOKEN` invalid**

```
Error: 401 Unauthorized - Invalid Copilot token
```

**Solution:**
- Verify token has `copilot` scope
- Regenerate token: [GitHub Settings](https://github.com/settings/tokens)
- Check token hasn't expired

---

**2. Tests failing after refactoring**

```
Error: 5 tests failed in tests/test_utils.py
```

**Solution:**
- Check verification logs in Actions artifacts
- Bot should auto-rollback on test failure
- If PR created despite failures, close and check config:
  ```yaml
  behavior:
    require_tests_pass: true  # Ensure this is set
  ```

---

**3. No PRs created**

```
Scan completed: 20 findings detected, 0 PRs created
```

**Possible causes:**
- Confidence threshold too high
  ```yaml
  behavior:
    confidence_threshold: 5  # Lower from 7
  ```
- Max PRs limit reached
  ```yaml
  behavior:
    max_prs_per_run: 10  # Increase from 5
  ```
- All findings below severity threshold

Check logs: Actions → CodeCustodian → View logs

---

**4. Rate limit exceeded**

```
Error: 403 Forbidden - API rate limit exceeded
```

**Solution:**
- GitHub Actions has separate rate limits (should be high)
- If using personal account: upgrade to GitHub Pro
- Check `advanced.copilot.rate_limit` in config

---

**5. Syntax errors in generated code**

```
Error: SyntaxError: invalid syntax in refactored code
```

**This shouldn't happen** (validation should catch it). If it does:
- File bug report with full logs
- Bot should auto-rollback
- Check backup: `.codecustodian-backups/`

---

## 📊 Examples

### Example 1: Deprecated API Migration

**Before:**
```python
import pandas as pd

def merge_dataframes(df1, df2):
    result = df1.append(df2)
    return result
```

**CodeCustodian detects:**
- Issue: `pandas.DataFrame.append()` deprecated (removed in pandas 3.0)
- Confidence: 9/10

**After (automatic PR):**
```python
import pandas as pd

def merge_dataframes(df1, df2):
    result = pd.concat([df1, df2], ignore_index=True)
    return result
```

**PR Description:**
> 🔄 **Refactor: Migrate deprecated pandas.DataFrame.append()**
> 
> **Finding:** `pandas.DataFrame.append()` is deprecated since pandas 1.4.0 and will be removed in pandas 3.0.
> 
> **Changes:**
> - Replaced `df.append()` with `pd.concat([df, ...], ignore_index=True)`
> - Preserves exact behavior including index handling
> 
> **AI Reasoning:**
> The pandas team deprecated `DataFrame.append()` in favor of `pd.concat()` for better performance and consistency. The migration is straightforward:
> - `df.append(other)` → `pd.concat([df, other])`
> - `ignore_index=True` preserves the original behavior
> 
> **Verification:**
> ✅ All tests passed (247/247)
> ✅ Coverage maintained: 84.2%
> ✅ Linting: No new violations
> 
> **Confidence:** 9/10
> **Risk:** Low

---

### Example 2: TODO Comment Resolution

**Before:**
```python
def calculate_discount(price, user_type):
    # TODO: Add support for premium members (added 2024-06-15, 8 months ago)
    if user_type == "standard":
        return price * 0.9
    return price
```

**CodeCustodian detects:**
- Issue: TODO comment aged 8 months (threshold: 90 days)
- Creates GitHub Issue with context

**GitHub Issue:**
> **TODO Cleanup: Add premium member support**
> 
> **Location:** `src/pricing.py:42`
> 
> **TODO Comment:**
> ```python
> # TODO: Add support for premium members
> ```
> 
> **Context:**
> ```python
> def calculate_discount(price, user_type):
>     # TODO: Add support for premium members
>     if user_type == "standard":
>         return price * 0.9
>     return price
> ```
> 
> **Details:**
> - Author: @john-doe
> - Age: 243 days (8 months)
> - Last modified: 2024-06-15
> 
> **Suggested Action:**
> Convert this TODO into a proper feature ticket or implement the functionality.

---

### Example 3: Code Smell Refactoring

**Before:**
```python
def process_data(data, format, validate, transform, filter, output):
    if format == "json":
        if validate:
            if transform:
                if filter:
                    # ... deeply nested logic ...
                    if output == "file":
                        # ... more nesting ...
                        pass
```

**CodeCustodian detects:**
- Issue: Cyclomatic complexity 18 (threshold: 10)
- Issue: Nesting depth 6 (threshold: 4)
- Confidence: 7/10

**After (automatic PR):**
```python
def process_data(data, format, validate, transform, filter, output):
    if format != "json":
        return _process_non_json(data, output)
    
    if not validate:
        return _process_unvalidated(data, output)
    
    processed = _apply_transform(data) if transform else data
    filtered = _apply_filter(processed) if filter else processed
    
    return _write_output(filtered, output)

def _process_non_json(data, output):
    # Extracted logic...

def _apply_transform(data):
    # Extracted logic...

def _apply_filter(data):
    # Extracted logic...

def _write_output(data, output):
    # Extracted logic...
```

---

## 🤝 Contributing

We welcome contributions! CodeCustodian thrives on community innovation.

### Ways to Contribute

1. **🐛 Report bugs** - [Open an issue](https://github.com/codecustodian/codecustodian/issues)
2. **💡 Request features** - [Feature request template](https://github.com/codecustodian/codecustodian/issues/new?template=feature_request.md)
3. **📝 Improve docs** - Documentation PRs always welcome
4. **🔌 Build plugins** - Share custom scanners and tools
5. **🧪 Add test cases** - Help improve quality
6. **🌍 Translate** - i18n support coming soon

### Development Setup

```bash
# 1. Fork and clone
git clone https://github.com/YOUR_USERNAME/codecustodian.git
cd codecustodian

# 2. Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# 3. Install development dependencies
pip install -e ".[dev]"

# 4. Install pre-commit hooks
pre-commit install

# 5. Run tests
pytest

# 6. Run linting
ruff check .
mypy src/

# 7. Create feature branch
git checkout -b feature/my-amazing-feature

# 8. Make changes, commit, push
git commit -m "feat: add amazing feature"
git push origin feature/my-amazing-feature

# 9. Open pull request on GitHub
```

### Contribution Guidelines

- **Code style:** Follow PEP 8, enforced by ruff
- **Type hints:** All functions must have type annotations
- **Tests:** Add tests for new features (target: 80%+ coverage)
- **Docs:** Update README and docstrings
- **Commits:** Use [Conventional Commits](https://www.conventionalcommits.org/)

---

## 🗺️ Roadmap

### Q1 2026 (Current) ✅
- [x] Core scanning engine (deprecated APIs, TODOs, code smells)
- [x] GitHub Copilot SDK integration
- [x] GitHub Actions workflow
- [x] Basic CLI
- [x] Safety guarantees (atomic operations, backups, rollback)
- [x] MCP Server with FastMCP (10 tools, resources, prompts)
- [x] Azure integrations (Key Vault, Container Apps, Monitor)
- [x] Enterprise features (RBAC, multi-tenant, approval workflows, budget)
- [x] Business intelligence (5-factor impact scoring, dynamic re-prioritization)
- [x] Feedback & learning (PR outcomes, preferences, historical patterns)
- [x] SLA & reliability reporting
- [x] Security hardening (path traversal guards, dangerous function detection, secret scanning)
- [x] Responsible AI policy (human-in-the-loop, explainability, proposal mode)
- [x] Audit logging with tamper-evident hashes
- [x] Full CLI with 10 commands (run, init, validate, scan, onboard, status, report, findings, create-prs, interactive)
- [x] 609 tests, 82% coverage (80% gate met)

### Q2 2026 🚧
- [ ] **JavaScript/TypeScript support**
- [ ] **Dashboard (analytics, multi-repo view)**
- [ ] **VS Code extension** (read-only monitoring)
- [ ] **Custom scanner marketplace**
- [ ] **Slack/Discord integrations**
- [ ] **Advanced confidence scoring** (ML-based)

### Q3 2026 🔮
- [ ] **Java support**
- [ ] **Go support**
- [ ] **Security scanner** (CVE detection, OWASP top 10)
- [ ] **Performance optimizer** (detect N+1 queries, memory leaks)
- [ ] **GitLab CI/CD support**
- [ ] **Enterprise features** (SSO, RBAC, on-premise)

### Q4 2026 🌟
- [ ] **AI-powered architecture suggestions**
- [ ] **Automated dependency upgrades** (with code migration)
- [ ] **Code generation** (from issues/specs)
- [ ] **Multi-language refactoring** (cross-language patterns)
- [ ] **SOC 2 Type II certification**

[Vote on features](https://github.com/codecustodian/codecustodian/discussions/categories/feature-requests)

---

## 📜 License

MIT License - see [LICENSE](LICENSE) file for details.

**tl;dr:** Use commercially, modify, distribute freely. Just keep the copyright notice.

---

## 🙏 Acknowledgments

Built with:
- [GitHub Copilot SDK](https://github.com/features/copilot) - AI reasoning engine
- [PyGithub](https://github.com/PyGithub/PyGithub) - GitHub API wrapper
- [Ruff](https://github.com/astral-sh/ruff) - Lightning-fast Python linter
- [pytest](https://pytest.org/) - Testing framework

Inspired by:
- **Dependabot** - Automated dependency management
- **Byteable** - Enterprise autonomous refactoring
- **AutoCodeRover** - AI-powered issue resolution

Special thanks to early adopters and contributors! 🎉

---

## 📞 Support & Community

- **Documentation:** [docs.codecustodian.dev](https://docs.codecustodian.dev) (coming soon)
- **Discord:** [Join our community](https://discord.gg/codecustodian)
- **Discussions:** [GitHub Discussions](https://github.com/codecustodian/codecustodian/discussions)
- **Issues:** [Bug reports](https://github.com/codecustodian/codecustodian/issues)
- **Email:** support@codecustodian.dev
- **Twitter:** [@codecustodian](https://twitter.com/codecustodian)

---

## 💰 Pricing

### Open Source (Free Forever)
- ✅ Unlimited repositories
- ✅ Self-hosted (your infrastructure)
- ✅ All core features
- ✅ Community support
- **Price:** $0

### Pro ($19/month per organization)
- ✅ Everything in Open Source
- ✅ Cloud dashboard with analytics
- ✅ Multi-repository overview
- ✅ Slack/email notifications
- ✅ Priority support
- ✅ 30-day money-back guarantee
- **Price:** $19/month

### Enterprise (Custom Pricing)
- ✅ Everything in Pro
- ✅ On-premise deployment
- ✅ SSO/SAML authentication
- ✅ Dedicated support & SLA
- ✅ Custom integrations
- ✅ Training & onboarding
- ✅ Legal & compliance assistance
- **Price:** Contact sales

[Start free trial](https://codecustodian.dev/pricing) (no credit card required)

---

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=codecustodian/codecustodian&type=Date)](https://star-history.com/#codecustodian/codecustodian&Date)

---

<div align="center">

**Made with ❤️ by developers, for developers**

[Website](https://codecustodian.dev) • [Documentation](https://docs.codecustodian.dev) • [Discord](https://discord.gg/codecustodian) • [Twitter](https://twitter.com/codecustodian)

</div>
