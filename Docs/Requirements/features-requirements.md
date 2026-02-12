# CodeCustodian - Detailed Features Requirements Documentation

**Version:** 1.0  
**Date:** February 11, 2026  
**Purpose:** Comprehensive technical specification for GitHub Copilot Agents  
**Target:** Input document for building CodeCustodian using GitHub Copilot SDK

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Competitive Analysis](#competitive-analysis)
3. [Core Architecture Requirements](#core-architecture-requirements)
4. [Scanner Module Requirements](#scanner-module-requirements)
5. [Planner Module Requirements (GitHub Copilot SDK)](#planner-module-requirements)
6. [Executor Module Requirements](#executor-module-requirements)
7. [Verification Module Requirements](#verification-module-requirements)
8. [GitHub Integration Requirements](#github-integration-requirements)
9. [Configuration System Requirements](#configuration-system-requirements)
10. [CLI Requirements](#cli-requirements)
11. [API Requirements](#api-requirements)
12. [Testing & Quality Requirements](#testing-quality-requirements)
13. [Security & Compliance Requirements](#security-compliance-requirements)
14. [Performance & Scalability Requirements](#performance-scalability-requirements)
15. [Observability & Logging Requirements](#observability-logging-requirements)
16. [Future Extensibility Requirements](#future-extensibility-requirements)

---

## 1. Executive Summary

### Project Vision

CodeCustodian is an autonomous AI agent for technical debt management that operates in CI/CD pipelines using GitHub Copilot SDK for intelligent refactoring decisions. It combines static analysis, AI-powered planning, safe execution, and comprehensive verification to automatically improve codebases.

### Key Differentiators from Competitors

| Feature | CodeCustodian | Byteable | AutoCodeRover | Moderne |
|---------|---------------|----------|---------------|---------|
| **AI Engine** | GitHub Copilot SDK | Multi-agent (Anthropic/OpenAI) | LLM-based (Claude/GPT) | Rule-based OpenRewrite |
| **Target** | Technical debt management | Enterprise refactoring | Bug fixing | Large-scale migrations |
| **Pricing** | Open Source + Pro | Enterprise only | Open Source | Enterprise |
| **CI/CD Native** | ✅ GitHub Actions first | ✅ Azure DevOps, GH, Jenkins | ⚠️ Limited | ✅ Pipeline-ready |
| **Confidence Scoring** | ✅ 1-10 with reasoning | ✅ With compliance | ⚠️ Success rate only | ❌ Deterministic |
| **Multi-turn AI** | ✅ Full conversation | ✅ Multi-agent | ✅ Iterative search | ❌ Single-pass |
| **MCP Integration** | ✅ Planned Q2 2026 | ❌ | ❌ | ❌ |

### Success Metrics

- **Efficacy Target:** 25-35% issue resolution rate (SWE-bench-lite equivalent for tech debt)
- **Cost Target:** < $0.50 USD per refactoring task
- **Time Target:** < 5 minutes per PR creation
- **Quality Target:** 95%+ test pass rate after refactoring
- **Adoption Target:** 1000+ repositories in first 6 months

---

## 2. Competitive Analysis

### 2.1 Byteable AI Code Auditor

**Strengths to Learn From:**
1. **Compliance-Grade Reporting:** SOC 2 / ISO 27001 audit trails with every refactor
2. **Natural Language Explanations:** Plain-language summaries alongside diffs
3. **Before/After Diff Visualization:** Git-style diffs with rationale
4. **Multi-Repo Support:** Handles monoliths and microservices
5. **DevOps Integration:** Direct PR comments in Azure DevOps, GitHub, Jenkins

**CodeCustodian Implementation:**
- **FR-COMP-001:** Generate SOC 2-compliant audit logs for every refactoring decision
- **FR-COMP-002:** Include natural language explanations in all PR descriptions
- **FR-COMP-003:** Create unified diff format with syntax highlighting for PR previews
- **FR-COMP-004:** Support monorepo scanning with per-directory configuration
- **FR-COMP-005:** Integrate with GitHub PR comments API for inline feedback

### 2.2 AutoCodeRover

**Strengths to Learn From:**
1. **AST-Based Search:** Uses abstract syntax tree for precise code understanding
2. **Iterative Context Retrieval:** Multi-turn search to narrow down root cause
3. **Spectrum-Based Fault Localization:** Uses test results to sharpen context
4. **Cost Efficiency:** $0.43 USD average per task
5. **Speed:** 7 minutes average completion time

**CodeCustodian Implementation:**
- **FR-COMP-006:** Use Python AST module for all code analysis (not regex-based)
- **FR-COMP-007:** Implement iterative search pattern in Copilot SDK tool calls
- **FR-COMP-008:** Run existing test suite to identify hotspots before refactoring
- **FR-COMP-009:** Optimize token usage: use gpt-4o-mini for simple tasks, o1-preview for complex
- **FR-COMP-010:** Set 10-minute timeout for all refactoring operations

### 2.3 Moderne

**Strengths to Learn From:**
1. **Deterministic Transformations:** Predictable, rule-based refactoring
2. **Recipe System:** Reusable refactoring patterns
3. **Large-Scale Execution:** Multi-repository coordination
4. **Version Control Integration:** Automatic commit/PR creation

**CodeCustodian Implementation:**
- **FR-COMP-011:** Create reusable scanner patterns (similar to Moderne recipes)
- **FR-COMP-012:** Support batch operations across multiple findings
- **FR-COMP-013:** Version control all refactoring decisions for reproducibility
- **FR-COMP-014:** Automatic rollback on verification failure

### 2.4 GitHub Copilot Workspace (2026)

**Strengths to Learn From:**
1. **Multi-file Editing:** Plan and execute changes across multiple files
2. **Natural Language Planning:** Describe intent, Copilot generates plan
3. **Workspace Versioning:** History tracking for all changes
4. **Mobile Support:** Edit from anywhere (future consideration)

**CodeCustodian Implementation:**
- **FR-COMP-015:** Support multi-file refactorings in single PR
- **FR-COMP-016:** Natural language issue descriptions → automated plans
- **FR-COMP-017:** Version all intermediate states (scan → plan → execute → verify)
- **FR-COMP-018:** Dashboard for workspace history (Q2 2026 feature)

---

## 3. Core Architecture Requirements

### 3.1 System Architecture

**FR-ARCH-001:** **Pipeline Architecture**
- Linear data flow: Scanner → Planner → Executor → Verifier → PR Creator
- Each stage must be independently testable
- Fail-fast behavior: abort current finding on error, continue to next

**FR-ARCH-002:** **Modular Design**
```
codecustodian/
├── scanner/
│   ├── base.py              # BaseScanner interface
│   ├── deprecated_api.py    # Deprecated API scanner
│   ├── todo_comments.py     # TODO comment scanner
│   ├── code_smells.py       # Complexity scanner
│   ├── security.py          # Security pattern scanner
│   └── type_coverage.py     # Type annotation scanner
├── planner/
│   ├── copilot_client.py    # GitHub Copilot SDK wrapper
│   ├── tools.py             # Custom tool definitions
│   ├── prompts.py           # Prompt templates
│   └── confidence.py        # Confidence scoring logic
├── executor/
│   ├── file_editor.py       # Safe file operations
│   ├── git_manager.py       # Git workflow automation
│   └── backup.py            # Backup/restore logic
├── verifier/
│   ├── test_runner.py       # Pytest execution
│   ├── linter.py            # Ruff, mypy, bandit integration
│   └── coverage.py          # Coverage analysis
├── github_integration/
│   ├── pr_creator.py        # GitHub API for PRs
│   ├── issues.py            # Issue creation for TODOs
│   └── comments.py          # PR comment automation
├── config/
│   ├── schema.py            # Configuration validation
│   └── defaults.py          # Default settings
├── cli/
│   └── main.py              # CLI entry point
└── api/
    └── server.py            # REST API (future)
```

**FR-ARCH-003:** **Dependency Management**
Required Python packages:
```toml
[project.dependencies]
python = "^3.11"
github-copilot-sdk = "^0.1.0"  # GitHub Copilot SDK (Technical Preview)
PyGithub = "^2.1.1"            # GitHub API client
GitPython = "^3.1.40"          # Git operations
pyyaml = "^6.0.1"              # YAML config parsing
pydantic = "^2.5.0"            # Config validation
typer = "^0.9.0"               # CLI framework
rich = "^13.7.0"               # Terminal formatting
pytest = "^7.4.3"              # Test runner
pytest-cov = "^4.1.0"          # Coverage plugin
ruff = "^0.1.7"                # Linter
mypy = "^1.7.1"                # Type checker
bandit = "^1.7.5"              # Security linter
radon = "^6.0.1"               # Complexity metrics
astroid = "^3.0.1"             # AST analysis
toml = "^0.10.2"               # TOML parsing
```

**FR-ARCH-004:** **State Management**
- Each finding must maintain isolated state
- No shared mutable state between findings
- State stored in Finding dataclass:
```python
@dataclass
class Finding:
    id: str                    # UUID
    type: str                  # Scanner type
    severity: str              # critical | high | medium | low
    file: str                  # Absolute path
    line: int                  # Line number
    description: str           # Human-readable summary
    suggestion: str            # Recommended fix
    priority_score: float      # 0-200
    metadata: Dict[str, Any]   # Scanner-specific data
    context: CodeContext       # Surrounding code
    timestamp: datetime        # Discovery time
```

**FR-ARCH-005:** **Error Handling Strategy**
- Use custom exception hierarchy:
  - `CodeCustodianError` (base)
  - `ScannerError`
  - `PlannerError`
  - `ExecutorError`
  - `VerifierError`
  - `GitHubAPIError`
- Log all exceptions with full traceback
- Never silently swallow errors
- Provide actionable error messages

---

## 4. Scanner Module Requirements

### 4.1 Base Scanner Interface

**FR-SCAN-001:** **BaseScanner Abstract Class**
```python
from abc import ABC, abstractmethod
from typing import List
from dataclasses import dataclass

class BaseScanner(ABC):
    """Base class for all code scanners."""
    
    name: str                  # Scanner identifier
    description: str           # What it detects
    enabled: bool = True       # Can be disabled in config
    
    @abstractmethod
    def scan(self, repo_path: str) -> List[Finding]:
        """
        Scan repository and return findings.
        
        Args:
            repo_path: Absolute path to repository root
            
        Returns:
            List of Finding objects, sorted by priority_score descending
        """
        pass
    
    def is_excluded(self, file_path: str, exclude_patterns: List[str]) -> bool:
        """Check if file should be excluded from scanning."""
        pass
    
    def calculate_priority(self, finding: Finding) -> float:
        """Calculate priority score (0-200)."""
        pass
```

**FR-SCAN-002:** **Finding Priority Algorithm**
```python
def calculate_priority(finding: Finding) -> float:
    """
    Priority = (Severity × Urgency × Impact) / Effort
    
    Range: 0-200
    - 150-200: Critical (security, breaking changes)
    - 100-150: High (deprecated APIs, complex smells)
    - 50-100: Medium (old TODOs, moderate complexity)
    - 0-50: Low (type hints, minor optimizations)
    """
    severity_weight = {
        "critical": 10,
        "high": 7,
        "medium": 4,
        "low": 2
    }
    
    # Urgency based on time sensitivity
    urgency = calculate_urgency(finding)  # 1.0-3.0
    
    # Impact based on usage and criticality
    impact = calculate_impact(finding)    # 1.0-5.0
    
    # Effort based on complexity
    effort = calculate_effort(finding)    # 0.4-1.0
    
    return (severity_weight[finding.severity] * urgency * impact) / effort
```

### 4.2 Deprecated API Scanner

**FR-SCAN-010:** **Deprecated API Detection**

**Approach:** AST-based import and call analysis

**Data Sources:**
1. **Built-in Rules:** Hardcoded deprecation database
2. **Package Metadata:** Parse deprecation warnings from installed packages
3. **Online Database:** (Optional) Fetch from codecustodian.dev API

**Implementation Requirements:**
- **FR-SCAN-011:** Maintain deprecation database in JSON format:
```json
{
  "pandas": {
    "DataFrame.append": {
      "deprecated_since": "1.4.0",
      "removed_in": "3.0.0",
      "replacement": "pd.concat([df1, df2], ignore_index=True)",
      "reason": "Performance and consistency",
      "severity": "high",
      "documentation": "https://pandas.pydata.org/docs/whatsnew/v1.4.0.html"
    }
  },
  "numpy": {
    "np.matrix": {
      "deprecated_since": "1.20.0",
      "removed_in": "2.0.0",
      "replacement": "np.ndarray",
      "reason": "Confusion between matrix and ndarray semantics",
      "severity": "medium",
      "documentation": "https://numpy.org/doc/stable/release/1.20.0-notes.html"
    }
  }
}
```

- **FR-SCAN-012:** AST visitor pattern:
```python
import ast
from typing import List

class DeprecatedAPIVisitor(ast.NodeVisitor):
    def __init__(self, deprecation_db: Dict):
        self.findings: List[Finding] = []
        self.deprecation_db = deprecation_db
        
    def visit_Call(self, node: ast.Call) -> None:
        """Check function/method calls."""
        func_name = self.get_full_name(node.func)
        if func_name in self.deprecation_db:
            self.findings.append(
                self.create_finding(node, func_name)
            )
        self.generic_visit(node)
    
    def visit_Import(self, node: ast.Import) -> None:
        """Check import statements."""
        for alias in node.names:
            if alias.name in self.deprecation_db:
                self.findings.append(
                    self.create_finding(node, alias.name)
                )
        self.generic_visit(node)
    
    def get_full_name(self, node: ast.AST) -> str:
        """Resolve fully qualified name (e.g., 'pd.DataFrame.append')."""
        # Handle ast.Attribute, ast.Name, etc.
        pass
```

- **FR-SCAN-013:** Usage frequency tracking:
  - Count number of times deprecated API is used
  - Higher usage = higher priority

- **FR-SCAN-014:** Version-aware detection:
  - Parse `requirements.txt`, `pyproject.toml`, `setup.py` to get package versions
  - Only flag APIs deprecated in installed version or earlier

### 4.3 TODO Comment Scanner

**FR-SCAN-020:** **TODO Comment Detection**

**Approach:** Regex + Git blame for age calculation

**Implementation Requirements:**
- **FR-SCAN-021:** Pattern matching:
```python
import re
from datetime import datetime, timedelta

TODO_PATTERNS = [
    r'#\s*TODO[:\s]+(.*)',
    r'#\s*FIXME[:\s]+(.*)',
    r'#\s*HACK[:\s]+(.*)',
    r'#\s*XXX[:\s]+(.*)',
    r'#\s*NOTE[:\s]+(.*)',
]

def scan_todos(file_path: str, max_age_days: int = 90) -> List[Finding]:
    findings = []
    
    with open(file_path, 'r') as f:
        for line_num, line in enumerate(f, start=1):
            for pattern in TODO_PATTERNS:
                match = re.search(pattern, line)
                if match:
                    # Get commit date using git blame
                    commit_date = git_blame(file_path, line_num)
                    age_days = (datetime.now() - commit_date).days
                    
                    if age_days > max_age_days:
                        findings.append(
                            Finding(
                                type="todo_comment",
                                severity="medium" if age_days > 180 else "low",
                                file=file_path,
                                line=line_num,
                                description=f"TODO aged {age_days} days",
                                suggestion="Convert to GitHub Issue or implement",
                                metadata={
                                    "age_days": age_days,
                                    "todo_text": match.group(1),
                                    "author": git_author(file_path, line_num)
                                }
                            )
                        )
    
    return findings
```

- **FR-SCAN-022:** Git blame integration:
```python
from git import Repo

def git_blame(file_path: str, line_num: int) -> datetime:
    """Get commit date for specific line."""
    repo = Repo(".", search_parent_directories=True)
    blame = repo.blame('HEAD', file_path)
    
    for commit, lines in blame:
        if line_num in lines:
            return commit.committed_datetime
    
    return datetime.now()  # Fallback
```

- **FR-SCAN-023:** Auto-issue creation:
  - If TODO > 180 days old, automatically create GitHub Issue
  - Mention original author in issue
  - Label: `tech-debt`, `todo-cleanup`

### 4.4 Code Smell Scanner

**FR-SCAN-030:** **Complexity Detection**

**Approach:** Use `radon` library for cyclomatic complexity

**Implementation Requirements:**
- **FR-SCAN-031:** Radon integration:
```python
from radon.complexity import cc_visit, cc_rank
from radon.metrics import mi_visit, mi_rank

def scan_complexity(file_path: str, threshold: int = 10) -> List[Finding]:
    findings = []
    
    with open(file_path, 'r') as f:
        code = f.read()
    
    # Cyclomatic complexity
    blocks = cc_visit(code)
    for block in blocks:
        if block.complexity > threshold:
            findings.append(
                Finding(
                    type="code_smell",
                    severity=get_severity_from_rank(cc_rank(block.complexity)),
                    file=file_path,
                    line=block.lineno,
                    description=f"High cyclomatic complexity: {block.complexity}",
                    suggestion="Refactor into smaller functions",
                    metadata={
                        "complexity": block.complexity,
                        "function_name": block.name,
                        "rank": cc_rank(block.complexity)
                    }
                )
            )
    
    # Maintainability index
    mi_score = mi_visit(code, multi=True)
    if mi_score < 20:  # Low maintainability
        findings.append(
            Finding(
                type="maintainability",
                severity="high",
                file=file_path,
                line=1,
                description=f"Low maintainability index: {mi_score:.1f}",
                suggestion="Consider refactoring this file",
                metadata={"mi_score": mi_score}
            )
        )
    
    return findings
```

- **FR-SCAN-032:** Additional code smells:
  - **Long functions:** > 50 lines (configurable)
  - **Too many parameters:** > 5 parameters
  - **Deep nesting:** > 4 levels
  - **Dead code detection:** Using AST to find unreachable code
  - **Duplicate code:** Clone detection (> 6 identical lines)

- **FR-SCAN-033:** Thresholds (configurable):
```yaml
code_smells:
  thresholds:
    cyclomatic_complexity: 10
    function_length: 50
    parameters: 5
    nesting_depth: 4
    maintainability_index: 20
    duplicate_lines: 6
```

### 4.5 Security Pattern Scanner

**FR-SCAN-040:** **Security Vulnerability Detection**

**Approach:** Use `bandit` library + custom patterns

**Implementation Requirements:**
- **FR-SCAN-041:** Bandit integration:
```python
from bandit.core import manager as bandit_manager
from bandit.core import config as bandit_config

def scan_security(repo_path: str) -> List[Finding]:
    findings = []
    
    # Initialize bandit
    config = bandit_config.BanditConfig()
    mgr = bandit_manager.BanditManager(config, 'file')
    
    # Scan all Python files
    mgr.discover_files([repo_path], recursive=True)
    mgr.run_tests()
    
    # Convert bandit results to Finding objects
    for result in mgr.results:
        findings.append(
            Finding(
                type="security",
                severity=result.severity.lower(),
                file=result.fname,
                line=result.lineno,
                description=result.text,
                suggestion=result.recommendation,
                metadata={
                    "test_id": result.test_id,
                    "confidence": result.confidence,
                    "cwe": result.cwe
                }
            )
        )
    
    return findings
```

- **FR-SCAN-042:** Custom security patterns:
```python
SECURITY_PATTERNS = {
    "hardcoded_secret": {
        "pattern": r'(password|api_key|secret_key|token)\s*=\s*["\'][^"\']+["\']',
        "severity": "critical",
        "description": "Hardcoded secret detected"
    },
    "weak_crypto": {
        "pattern": r'(hashlib\.(md5|sha1)|random\.random)',
        "severity": "high",
        "description": "Weak cryptography used"
    },
    "sql_injection": {
        "pattern": r'execute\(.*%.*\)|cursor\.execute\(.*\+.*\)',
        "severity": "critical",
        "description": "Potential SQL injection"
    }
}
```

- **FR-SCAN-043:** Priority rules:
  - **Critical:** Hardcoded secrets, SQL injection, command injection
  - **High:** Weak crypto (MD5, SHA1), insecure random
  - **Medium:** Unsafe deserialization, XXE vulnerabilities
  - **Low:** Missing security headers, weak SSL config

### 4.6 Type Coverage Scanner

**FR-SCAN-050:** **Type Annotation Detection**

**Approach:** AST analysis for missing type hints

**Implementation Requirements:**
- **FR-SCAN-051:** Type hint checker:
```python
import ast
from typing import List

class TypeCoverageVisitor(ast.NodeVisitor):
    def __init__(self):
        self.findings: List[Finding] = []
        self.total_functions = 0
        self.typed_functions = 0
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.total_functions += 1
        
        # Check if function has return type annotation
        has_return_type = node.returns is not None
        
        # Check if all parameters have type annotations
        has_param_types = all(
            arg.annotation is not None 
            for arg in node.args.args 
            if arg.arg != 'self'
        )
        
        if has_return_type and has_param_types:
            self.typed_functions += 1
        else:
            self.findings.append(
                Finding(
                    type="type_coverage",
                    severity="low",
                    file=self.current_file,
                    line=node.lineno,
                    description=f"Function '{node.name}' missing type hints",
                    suggestion="Add type annotations for parameters and return type",
                    metadata={
                        "function_name": node.name,
                        "has_return_type": has_return_type,
                        "has_param_types": has_param_types
                    }
                )
            )
        
        self.generic_visit(node)
    
    def coverage_percentage(self) -> float:
        if self.total_functions == 0:
            return 100.0
        return (self.typed_functions / self.total_functions) * 100
```

- **FR-SCAN-052:** Coverage target:
  - Default: 80% type coverage
  - Configurable per project
  - Report overall coverage in summary

---

## 5. Planner Module Requirements (GitHub Copilot SDK)

### 5.1 GitHub Copilot SDK Integration

**FR-PLAN-001:** **Copilot Client Initialization**
```python
from github_copilot_sdk import CopilotClient, Message, Tool, Session

class CopilotPlanner:
    def __init__(self, token: str, config: PlannerConfig):
        self.client = CopilotClient(token=token)
        self.config = config
        self.tools = self._register_tools()
    
    def plan_refactoring(
        self, 
        finding: Finding, 
        context: CodeContext
    ) -> RefactoringPlan:
        """Generate refactoring plan using Copilot SDK."""
        
        # 1. Select appropriate model
        model = self._select_model(finding)
        
        # 2. Build prompts
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(finding, context)
        
        # 3. Create session
        session = self.client.create_session(
            model=model,
            temperature=self.config.temperature,  # Default: 0.1
            max_tokens=self.config.max_tokens      # Default: 4096
        )
        
        # 4. Multi-turn conversation
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt)
        ]
        
        response = session.send_messages(messages, tools=self.tools)
        
        # 5. Handle tool calls (iterative)
        while response.has_tool_calls():
            tool_results = self._execute_tools(response.tool_calls, context)
            messages.append(Message(role="assistant", content=response.content))
            messages.append(Message(role="tool", content=tool_results))
            response = session.send_messages(messages, tools=self.tools)
        
        # 6. Parse response into structured plan
        plan = self._parse_plan(response.content, finding)
        
        # 7. Calculate confidence score
        plan.confidence_score = self._calculate_confidence(plan, context)
        plan.ai_reasoning = response.reasoning  # Copilot SDK provides reasoning
        
        return plan
```

**FR-PLAN-002:** **Model Selection Strategy**
```python
def _select_model(self, finding: Finding) -> str:
    """
    Route to appropriate model based on complexity.
    
    Model selection hierarchy:
    - Simple (1:1 replacements): gpt-4o-mini (fast, cheap)
    - Moderate (logic changes): gpt-4o (balanced)
    - Complex (multi-file): o1-preview (deep reasoning)
    """
    
    if self.config.model_selection == "auto":
        if finding.metadata.get("complexity") == "simple":
            return "gpt-4o-mini"
        elif finding.metadata.get("complexity") == "moderate":
            return "gpt-4o"
        else:
            return "o1-preview"
    else:
        # Manual override from config
        return self.config.model_override.get(
            finding.metadata.get("complexity", "moderate"),
            "gpt-4o"
        )
```

### 5.2 Custom Tool Definitions

**FR-PLAN-010:** **Codebase Inspection Tools**

GitHub Copilot SDK allows defining custom tools that the AI can invoke. These tools must conform to JSON Schema.

```python
def _register_tools(self) -> List[Tool]:
    """Register custom tools for Copilot to use."""
    return [
        self._get_function_definition_tool(),
        self._find_test_coverage_tool(),
        self._search_references_tool(),
        self._get_imports_tool(),
        self._get_call_sites_tool(),
        self._check_type_hints_tool()
    ]

def _get_function_definition_tool(self) -> Tool:
    """Tool: Get full function definition."""
    def get_function_definition(file_path: str, function_name: str) -> str:
        """
        Get complete function definition with context.
        
        Args:
            file_path: Path to Python file
            function_name: Name of function
            
        Returns:
            Function source code with 5 lines before/after
        """
        tree = ast.parse(Path(file_path).read_text())
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                # Get source with context
                lines = Path(file_path).read_text().splitlines()
                start = max(0, node.lineno - 5)
                end = min(len(lines), node.end_lineno + 5)
                return "\n".join(lines[start:end])
        
        return f"Function '{function_name}' not found"
    
    return Tool(
        name="get_function_definition",
        description="Get the complete source code of a function with surrounding context",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the Python file"
                },
                "function_name": {
                    "type": "string",
                    "description": "Name of the function"
                }
            },
            "required": ["file_path", "function_name"]
        },
        function=get_function_definition
    )

def _find_test_coverage_tool(self) -> Tool:
    """Tool: Check if tests exist for code."""
    def find_test_coverage(file_path: str) -> Dict[str, Any]:
        """
        Find tests covering a file.
        
        Returns:
            {
                "has_tests": bool,
                "test_files": List[str],
                "coverage_percentage": float
            }
        """
        # Convention: test_<filename>.py
        file_name = Path(file_path).stem
        test_name = f"test_{file_name}.py"
        test_path = Path("tests") / test_name
        
        has_tests = test_path.exists()
        
        # TODO: Run pytest-cov to get actual coverage
        coverage = 0.0
        if has_tests:
            coverage = 75.0  # Placeholder
        
        return {
            "has_tests": has_tests,
            "test_files": [str(test_path)] if has_tests else [],
            "coverage_percentage": coverage
        }
    
    return Tool(
        name="find_test_coverage",
        description="Check if tests exist for a file and get coverage information",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to check"
                }
            },
            "required": ["file_path"]
        },
        function=find_test_coverage
    )

def _search_references_tool(self) -> Tool:
    """Tool: Find all references to a symbol."""
    def search_references(symbol_name: str, file_path: str) -> List[Dict[str, Any]]:
        """
        Find all references to a function/class/variable.
        
        Returns:
            List of {file, line, context} dicts
        """
        references = []
        
        # Search all Python files
        for py_file in Path(".").rglob("*.py"):
            tree = ast.parse(py_file.read_text())
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id == symbol_name:
                    references.append({
                        "file": str(py_file),
                        "line": node.lineno,
                        "context": get_line_context(py_file, node.lineno, 3)
                    })
        
        return references
    
    return Tool(
        name="search_references",
        description="Find all references to a symbol (function, class, variable) in the codebase",
        parameters={
            "type": "object",
            "properties": {
                "symbol_name": {
                    "type": "string",
                    "description": "Name of the symbol to search for"
                },
                "file_path": {
                    "type": "string",
                    "description": "File where symbol is defined"
                }
            },
            "required": ["symbol_name", "file_path"]
        },
        function=search_references
    )
```

**FR-PLAN-011:** **Additional Tool Requirements**
- `get_imports_tool()`: List all imports in a file
- `get_call_sites_tool()`: Find all call sites of a function
- `check_type_hints_tool()`: Verify type annotations exist
- `get_class_hierarchy_tool()`: Get inheritance chain
- `find_similar_code_tool()`: Find similar refactoring patterns

### 5.3 Prompt Engineering

**FR-PLAN-020:** **System Prompt Template**
```python
SYSTEM_PROMPT = """
You are CodeCustodian, an expert Python refactoring assistant. Your job is to 
transform deprecated or problematic code into modern, maintainable equivalents 
while preserving exact functionality.

## Core Principles
1. **Preserve behavior**: Never change what the code does, only how it does it
2. **Minimal changes**: Only modify what's necessary to fix the issue
3. **Type safety**: Maintain or improve type annotations
4. **Readability**: Prefer clarity over cleverness
5. **Test compatibility**: Ensure existing tests still pass

## Output Requirements
You MUST provide your response in the following JSON format:

```json
{
  "summary": "Brief one-line description of the refactoring",
  "reasoning": "Step-by-step explanation of your approach",
  "changes": [
    {
      "file": "path/to/file.py",
      "old_code": "exact code to replace (must appear exactly once)",
      "new_code": "replacement code",
      "line_start": 42,
      "line_end": 45
    }
  ],
  "risks": [
    "List of potential risks or assumptions"
  ],
  "requires_manual_verification": false,
  "confidence_factors": {
    "has_tests": true,
    "changes_signature": false,
    "multi_file": false,
    "logic_complexity": "low"
  }
}
```

## Context Provided
You will receive:
- **Finding**: The detected issue (deprecated API, TODO, code smell, etc.)
- **Code context**: 10 lines before and after the issue
- **Function signature**: Type hints and parameter information
- **Import statements**: All imports in the file
- **Test coverage**: Whether tests exist for this code
- **Call sites**: Where this code is used

## Tools Available
You can call these tools to gather more information:
- `get_function_definition`: Get full source of a function
- `find_test_coverage`: Check test coverage
- `search_references`: Find all usages of a symbol
- `get_imports`: List all imports
- `get_call_sites`: Find all call sites

Use tools when you need more context to make a confident decision.
"""
```

**FR-PLAN-021:** **User Prompt Template**
```python
def _build_user_prompt(self, finding: Finding, context: CodeContext) -> str:
    """Build user prompt with finding and context."""
    
    return f"""
## Issue Detected

**Type:** {finding.type}
**Severity:** {finding.severity}
**File:** {finding.file}
**Line:** {finding.line}

**Description:**
{finding.description}

**Suggestion:**
{finding.suggestion}

## Code Context

```python
# Lines {context.line_start}-{context.line_end}
{context.code}
```

## Function Signature

```python
{context.function_signature}
```

## Imports

```python
{chr(10).join(context.imports)}
```

## Additional Information

- **Tests exist:** {"Yes" if context.has_tests else "No"}
- **Test coverage:** {context.coverage_percentage:.1f}%
- **Number of call sites:** {len(context.call_sites)}
- **Last modified:** {context.last_modified.strftime("%Y-%m-%d")}

## Task

Refactor the code to fix the issue while maintaining exact behavior. 
Provide your response in the required JSON format.

If you need more information, use the available tools before providing your final answer.
"""
```

### 5.4 Confidence Scoring

**FR-PLAN-030:** **Confidence Calculation Algorithm**
```python
def _calculate_confidence(self, plan: RefactoringPlan, context: CodeContext) -> int:
    """
    Calculate confidence score (1-10).
    
    High confidence (9-10):
    - Direct 1:1 API replacement
    - Comprehensive test coverage (>80%)
    - No breaking changes to function signature
    - Simple logic (cyclomatic complexity <5)
    
    Medium confidence (5-8):
    - Moderate refactoring
    - Partial test coverage (40-80%)
    - Minor signature changes
    - Moderate logic (complexity 5-10)
    
    Low confidence (1-4):
    - Complex multi-file refactoring
    - No test coverage (<40%)
    - Significant signature changes
    - Complex logic (complexity >10)
    """
    
    score = 10  # Start at maximum
    
    # Deduction factors
    if not context.has_tests:
        score -= 3
    elif context.coverage_percentage < 80:
        score -= 1
    
    if plan.changes_signature:
        score -= 2
    
    if len(plan.files_to_change) > 3:
        score -= 2
    
    if plan.requires_manual_verification:
        score -= 2
    
    if context.complexity > 10:
        score -= 1
    
    if plan.metadata.get("logic_changes", False):
        score -= 1
    
    # Boost factors
    if plan.metadata.get("simple_replacement", False):
        score += 1
    
    if context.coverage_percentage > 90:
        score += 1
    
    return max(1, min(10, score))
```

### 5.5 Response Parsing

**FR-PLAN-040:** **Parse JSON Response**
```python
import json
from pydantic import BaseModel, Field
from typing import List, Dict, Any

class CodeChange(BaseModel):
    file: str
    old_code: str
    new_code: str
    line_start: int
    line_end: int

class RefactoringPlan(BaseModel):
    summary: str
    reasoning: str
    changes: List[CodeChange]
    risks: List[str] = Field(default_factory=list)
    requires_manual_verification: bool = False
    confidence_factors: Dict[str, Any]
    confidence_score: int = 0  # Calculated separately
    ai_reasoning: str = ""     # From Copilot SDK

def _parse_plan(self, response_content: str, finding: Finding) -> RefactoringPlan:
    """Parse AI response into structured plan."""
    
    try:
        # Extract JSON from response (may have markdown fences)
        json_str = self._extract_json(response_content)
        data = json.loads(json_str)
        
        # Validate and parse with Pydantic
        plan = RefactoringPlan(**data)
        
        # Add metadata
        plan.finding_id = finding.id
        plan.finding_type = finding.type
        
        return plan
        
    except json.JSONDecodeError as e:
        raise PlannerError(f"Failed to parse AI response as JSON: {e}")
    except Exception as e:
        raise PlannerError(f"Failed to create refactoring plan: {e}")

def _extract_json(self, content: str) -> str:
    """Extract JSON from markdown code fences."""
    
    # Pattern: ```json\n{...}\n```
    match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
    if match:
        return match.group(1)
    
    # Pattern: ```\n{...}\n```
    match = re.search(r'```\s*(.*?)\s*```', content, re.DOTALL)
    if match:
        return match.group(1)
    
    # Assume entire content is JSON
    return content
```

---

## 6. Executor Module Requirements

### 6.1 Safe File Operations

**FR-EXEC-001:** **Atomic File Editor**
```python
from pathlib import Path
import shutil
import tempfile
from datetime import datetime
import ast

class SafeFileEditor:
    """Applies code changes with atomic operations and rollback."""
    
    def __init__(self, backup_dir: Path = Path(".codecustodian-backups")):
        self.backup_dir = backup_dir
        self.backup_dir.mkdir(exist_ok=True)
    
    def apply_changes(self, file_path: Path, old_str: str, new_str: str) -> None:
        """
        Replace old_str with new_str in file, atomically.
        
        Process:
        1. Create timestamped backup
        2. Read original content
        3. Apply string replacement (must be unique)
        4. Validate syntax (AST parse for Python)
        5. Write to temp file
        6. Atomic rename (temp → original)
        7. Delete backup on success
        
        On any error: restore from backup
        
        Raises:
            ValueError: If old_str doesn't appear exactly once
            SyntaxError: If new code has syntax errors
            RuntimeError: On file operation failure
        """
        
        backup_path = self._create_backup(file_path)
        
        try:
            # Read original
            original = file_path.read_text()
            
            # Apply replacement (must be unique)
            occurrences = original.count(old_str)
            if occurrences != 1:
                raise ValueError(
                    f"old_str must appear exactly once, found {occurrences} occurrences"
                )
            
            modified = original.replace(old_str, new_str, 1)
            
            # Validate syntax for Python files
            if file_path.suffix == ".py":
                try:
                    ast.parse(modified)
                except SyntaxError as e:
                    raise SyntaxError(f"New code has syntax error: {e}")
            
            # Write atomically
            with tempfile.NamedTemporaryFile(
                mode='w',
                dir=file_path.parent,
                delete=False
            ) as tmp:
                tmp.write(modified)
                tmp_path = Path(tmp.name)
            
            # Atomic rename (POSIX)
            tmp_path.replace(file_path)
            
            # Success: remove backup
            backup_path.unlink()
            
        except Exception as e:
            # Rollback
            self._restore_backup(backup_path, file_path)
            raise RuntimeError(f"Failed to apply changes: {e}")
    
    def _create_backup(self, file_path: Path) -> Path:
        """Create timestamped backup."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_name = f"{file_path.name}-{timestamp}.bak"
        backup_path = self.backup_dir / backup_name
        
        shutil.copy2(file_path, backup_path)
        
        return backup_path
    
    def _restore_backup(self, backup_path: Path, original_path: Path) -> None:
        """Restore file from backup."""
        if backup_path.exists():
            shutil.copy2(backup_path, original_path)
```

**FR-EXEC-002:** **Backup Retention Policy**
- Keep backups for 7 days (configurable)
- Cleanup old backups automatically
- Option to disable backups (not recommended)

### 6.2 Git Workflow Manager

**FR-EXEC-010:** **Git Operations**
```python
from git import Repo
from typing import List
from datetime import datetime

class GitWorkflowManager:
    """Manages git operations for refactorings."""
    
    def __init__(self, repo_path: str = "."):
        self.repo = Repo(repo_path, search_parent_directories=True)
    
    def create_refactoring_branch(self, finding: Finding) -> str:
        """
        Create feature branch for refactoring.
        
        Branch naming: tech-debt/{category}-{file}-{timestamp}
        Example: tech-debt/deprecated-api-utils-20260211-1430
        """
        
        # Ensure on main and up-to-date
        self.repo.git.checkout("main")
        self.repo.git.pull("origin", "main")
        
        # Generate semantic branch name
        category = finding.type.replace("_", "-")
        file_short = Path(finding.file).stem[:20]
        timestamp = datetime.now().strftime("%Y%m%d-%H%M")
        branch_name = f"tech-debt/{category}-{file_short}-{timestamp}"
        
        # Create and checkout branch
        self.repo.git.checkout("-b", branch_name)
        
        return branch_name
    
    def commit_changes(
        self, 
        finding: Finding, 
        plan: RefactoringPlan,
        changed_files: List[Path]
    ) -> str:
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
        
        # Stage all changes
        for file in changed_files:
            self.repo.git.add(str(file))
        
        # Build commit message
        summary = plan.summary[:50]
        changes_list = "\n".join(f"- {f}" for f in changed_files)
        reasoning = plan.ai_reasoning[:500] + "..." if len(plan.ai_reasoning) > 500 else plan.ai_reasoning
        
        body = f"""
Finding: {finding.id}
Type: {finding.type}
Severity: {finding.severity}

Changes:
{changes_list}

AI Reasoning:
{reasoning}

Confidence: {plan.confidence_score}/10
Risk: {self._calculate_risk_level(plan)}

Co-authored-by: CodeCustodian <bot@codecustodian.dev>
"""
        
        commit_msg = f"refactor: {summary}\n\n{body.strip()}"
        
        # Commit
        self.repo.git.commit("-m", commit_msg)
        
        # Get commit SHA
        return self.repo.head.commit.hexsha
    
    def push_branch(self, branch_name: str) -> None:
        """Push branch to remote."""
        self.repo.git.push("origin", branch_name, set_upstream=True)
    
    def _calculate_risk_level(self, plan: RefactoringPlan) -> str:
        """Calculate risk level based on plan."""
        if plan.confidence_score >= 8:
            return "low"
        elif plan.confidence_score >= 5:
            return "medium"
        else:
            return "high"
```

---

## 7. Verification Module Requirements

### 7.1 Test Runner

**FR-VERIFY-001:** **Pytest Execution**
```python
import pytest
import json
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class VerificationResult:
    passed: bool
    tests_run: int
    tests_passed: int
    tests_failed: int
    coverage_overall: float
    coverage_delta: float
    failures: List[Dict[str, Any]]
    duration: float

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
            "--tb=short",
            f"--cov={self._get_src_dir()}",
            "--cov-report=json:.coverage.json",
            "--cov-report=term",
            "--junit-xml=.pytest-results.xml",
            "--timeout=300",  # 5 minute timeout
            *[str(f) for f in test_files]
        ]
        
        start_time = time.time()
        exit_code = pytest.main(pytest_args)
        duration = time.time() - start_time
        
        # 3. Parse results
        junit_results = self._parse_junit_xml(".pytest-results.xml")
        coverage = self._parse_coverage_json(".coverage.json")
        
        return VerificationResult(
            passed=(exit_code == 0),
            tests_run=junit_results["total"],
            tests_passed=junit_results["passed"],
            tests_failed=junit_results["failed"],
            coverage_overall=coverage["overall"],
            coverage_delta=self._calculate_coverage_delta(coverage),
            failures=junit_results["failures"] if exit_code != 0 else [],
            duration=duration
        )
    
    def _discover_tests(self, changed_files: List[Path]) -> List[Path]:
        """
        Find tests covering changed files.
        
        Strategies:
        1. Convention: test_<filename>.py
        2. Pattern: tests/**/test_*.py matching path
        3. All tests if critical file changed
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
        
        # If no specific tests found, run all
        if not test_files:
            test_files = set(Path("tests").rglob("test_*.py"))
        
        return sorted(test_files)
```

**FR-VERIFY-002:** **Coverage Delta Calculation**
```python
def _calculate_coverage_delta(self, current_coverage: Dict) -> float:
    """
    Calculate coverage change from baseline.
    
    Returns:
        Positive number if coverage improved, negative if decreased
    """
    
    baseline_path = Path(".codecustodian-baseline.json")
    
    if not baseline_path.exists():
        # First run, create baseline
        with open(baseline_path, 'w') as f:
            json.dump(current_coverage, f)
        return 0.0
    
    with open(baseline_path, 'r') as f:
        baseline = json.load(f)
    
    delta = current_coverage["overall"] - baseline["overall"]
    
    # Update baseline if improved
    if delta >= 0:
        with open(baseline_path, 'w') as f:
            json.dump(current_coverage, f)
    
    return delta
```

### 7.2 Linting Pipeline

**FR-VERIFY-010:** **Multi-Linter Execution**
```python
from dataclasses import dataclass
from typing import List, Dict
import subprocess
import json

@dataclass
class Violation:
    file: str
    line: int
    code: str
    message: str
    severity: str  # error | warning

@dataclass
class LintResult:
    passed: bool
    ruff_violations: List[Violation]
    mypy_errors: List[Violation]
    bandit_issues: List[Violation]
    new_violations: List[Violation]  # Only new issues

class LinterRunner:
    """Execute linters and collect violations."""
    
    def run_linters(self, changed_files: List[Path]) -> LintResult:
        """
        Run ruff, mypy, bandit on changed files.
        
        Strategy: Only fail on NEW violations (not pre-existing)
        """
        
        results = {
            "ruff": self._run_ruff(changed_files),
            "mypy": self._run_mypy(changed_files),
            "bandit": self._run_bandit(changed_files)
        }
        
        # Load baseline
        baseline = self._load_baseline()
        
        # Filter new violations
        new_violations = self._filter_new(results, baseline)
        
        # Save new baseline if no new violations
        if not new_violations:
            self._save_baseline(results)
        
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
        
        if not result.stdout:
            return []
        
        violations_data = json.loads(result.stdout)
        
        return [
            Violation(
                file=v["filename"],
                line=v["location"]["row"],
                code=v["code"],
                message=v["message"],
                severity="error" if v["code"].startswith("E") else "warning"
            )
            for v in violations_data
        ]
    
    def _run_mypy(self, files: List[Path]) -> List[Violation]:
        """Run mypy type checker."""
        result = subprocess.run(
            ["mypy", "--show-error-codes", "--json", *files],
            capture_output=True,
            text=True
        )
        
        # Parse mypy JSON output
        violations = []
        for line in result.stdout.splitlines():
            if not line:
                continue
            try:
                data = json.loads(line)
                violations.append(
                    Violation(
                        file=data["file"],
                        line=data["line"],
                        code=data.get("code", "mypy"),
                        message=data["message"],
                        severity="error"
                    )
                )
            except json.JSONDecodeError:
                continue
        
        return violations
    
    def _run_bandit(self, files: List[Path]) -> List[Violation]:
        """Run bandit security linter."""
        result = subprocess.run(
            ["bandit", "-f", "json", "-r", *files],
            capture_output=True,
            text=True
        )
        
        if not result.stdout:
            return []
        
        data = json.loads(result.stdout)
        
        return [
            Violation(
                file=issue["filename"],
                line=issue["line_number"],
                code=issue["test_id"],
                message=issue["issue_text"],
                severity=issue["issue_severity"].lower()
            )
            for issue in data.get("results", [])
        ]
```

---

## 8. GitHub Integration Requirements

### 8.1 Pull Request Creation

**FR-GITHUB-001:** **PR Creator**
```python
from github import Github, GithubException
from typing import List, Optional

class PRCreator:
    """Creates pull requests using GitHub API."""
    
    def __init__(self, token: str, repo_name: str):
        self.github = Github(token)
        self.repo = self.github.get_repo(repo_name)
    
    def create_pr(
        self,
        branch_name: str,
        finding: Finding,
        plan: RefactoringPlan,
        verification: VerificationResult
    ) -> int:
        """
        Create pull request with detailed description.
        
        Returns:
            PR number
        """
        
        title = self._generate_title(finding, plan)
        body = self._generate_body(finding, plan, verification)
        labels = self._get_labels(finding, plan)
        
        try:
            pr = self.repo.create_pull(
                title=title,
                body=body,
                head=branch_name,
                base="main",
                draft=(plan.confidence_score < 7)  # Draft if low confidence
            )
            
            # Add labels
            pr.add_to_labels(*labels)
            
            # Add reviewers (from config)
            if self.config.reviewers:
                pr.create_review_request(reviewers=self.config.reviewers)
            
            return pr.number
            
        except GithubException as e:
            raise GitHubAPIError(f"Failed to create PR: {e}")
    
    def _generate_title(self, finding: Finding, plan: RefactoringPlan) -> str:
        """Generate PR title (max 72 chars)."""
        emoji = {
            "deprecated_api": "🔄",
            "todo_comment": "📝",
            "code_smell": "🧹",
            "security": "🔒",
            "type_coverage": "🏷️"
        }.get(finding.type, "🔧")
        
        title = f"{emoji} {plan.summary}"
        return title[:72]
    
    def _generate_body(
        self, 
        finding: Finding, 
        plan: RefactoringPlan,
        verification: VerificationResult
    ) -> str:
        """Generate detailed PR description."""
        
        return f"""
## 🎯 Summary

{plan.summary}

## 🔍 Finding

- **Type:** {finding.type}
- **Severity:** {finding.severity}
- **File:** {finding.file}:{finding.line}
- **Priority Score:** {finding.priority_score:.1f}/200

**Description:**
{finding.description}

## 🤖 AI Reasoning

{plan.ai_reasoning}

## 📝 Changes

{self._format_changes(plan.changes)}

## ⚠️ Risks

{self._format_risks(plan.risks)}

## ✅ Verification

### Tests
- **Status:** {'✅ Passed' if verification.passed else '❌ Failed'}
- **Tests Run:** {verification.tests_run}
- **Passed:** {verification.tests_passed}
- **Failed:** {verification.tests_failed}
- **Duration:** {verification.duration:.1f}s

### Coverage
- **Overall:** {verification.coverage_overall:.1f}%
- **Delta:** {'+' if verification.coverage_delta >= 0 else ''}{verification.coverage_delta:.2f}%

### Linting
- **Ruff:** {len(verification.lint_result.ruff_violations)} issues
- **Mypy:** {len(verification.lint_result.mypy_errors)} errors
- **Bandit:** {len(verification.lint_result.bandit_issues)} security issues

## 📊 Confidence

**Score:** {plan.confidence_score}/10

**Factors:**
- Has tests: {'✅' if plan.confidence_factors.get('has_tests') else '❌'}
- Changes signature: {'❌' if plan.confidence_factors.get('changes_signature') else '✅'}
- Multi-file: {'❌' if plan.confidence_factors.get('multi_file') else '✅'}
- Logic complexity: {plan.confidence_factors.get('logic_complexity', 'unknown')}

---

🤖 *This PR was automatically created by [CodeCustodian](https://github.com/codecustodian/codecustodian)*
"""
```

### 8.2 Issue Creation (TODOs)

**FR-GITHUB-010:** **Automated Issue Creation**
```python
def create_issue_from_todo(
    self,
    finding: Finding,
    context: CodeContext
) -> int:
    """
    Create GitHub Issue for old TODO comment.
    
    Returns:
        Issue number
    """
    
    title = f"TODO Cleanup: {finding.metadata['todo_text'][:50]}"
    
    body = f"""
## 📝 TODO Comment Found

**Location:** `{finding.file}:{finding.line}`

**TODO Comment:**
```python
{finding.metadata['todo_text']}
```

**Context:**
```python
{context.code}
```

## 📊 Details

- **Author:** @{finding.metadata.get('author', 'unknown')}
- **Age:** {finding.metadata['age_days']} days ({finding.metadata['age_days'] // 30} months)
- **Last modified:** {context.last_modified.strftime('%Y-%m-%d')}

## 🎯 Suggested Action

{finding.suggestion}

---

🤖 *This issue was automatically created by CodeCustodian*
"""
    
    issue = self.repo.create_issue(
        title=title,
        body=body,
        labels=["tech-debt", "todo-cleanup"],
        assignees=[finding.metadata.get('author')] if finding.metadata.get('author') else []
    )
    
    return issue.number
```

---

## 9. Configuration System Requirements

**FR-CONFIG-001:** **Configuration Schema (Pydantic)**

```python
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional, Literal

class ScannerConfig(BaseModel):
    enabled: bool = True
    severity: Literal["critical", "high", "medium", "low"] = "high"

class DeprecatedAPIConfig(ScannerConfig):
    libraries: List[str] = Field(default_factory=lambda: ["pandas", "numpy"])
    custom_patterns: List[Dict[str, str]] = Field(default_factory=list)
    exclude: List[str] = Field(default_factory=list)

class TODOConfig(ScannerConfig):
    max_age_days: int = 90
    patterns: List[str] = Field(default_factory=lambda: ["TODO", "FIXME", "HACK"])
    auto_issue: bool = True
    notify_authors: bool = True

class CodeSmellConfig(ScannerConfig):
    thresholds: Dict[str, int] = Field(
        default_factory=lambda: {
            "cyclomatic_complexity": 10,
            "function_length": 50,
            "parameters": 5,
            "nesting_depth": 4
        }
    )

class ScannersConfig(BaseModel):
    deprecated_apis: DeprecatedAPIConfig = Field(default_factory=DeprecatedAPIConfig)
    todo_comments: TODOConfig = Field(default_factory=TODOConfig)
    code_smells: CodeSmellConfig = Field(default_factory=CodeSmellConfig)

class BehaviorConfig(BaseModel):
    max_prs_per_run: int = 5
    require_human_review: bool = True
    auto_merge: bool = False
    draft_prs_for_complex: bool = True
    confidence_threshold: int = Field(default=7, ge=1, le=10)

class GitHubConfig(BaseModel):
    pr_labels: List[str] = Field(default_factory=lambda: ["tech-debt", "automated"])
    reviewers: List[str] = Field(default_factory=list)
    branch_prefix: str = "tech-debt"

class CopilotConfig(BaseModel):
    model_selection: Literal["auto", "fast", "balanced", "reasoning"] = "auto"
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    max_tokens: int = Field(default=4096, ge=512, le=8192)
    max_cost_per_run: float = 5.0

class CodeCustodianConfig(BaseModel):
    version: str = "1.0"
    scanners: ScannersConfig = Field(default_factory=ScannersConfig)
    behavior: BehaviorConfig = Field(default_factory=BehaviorConfig)
    github: GitHubConfig = Field(default_factory=GitHubConfig)
    copilot: CopilotConfig = Field(default_factory=CopilotConfig)
    exclude_paths: List[str] = Field(
        default_factory=lambda: ["vendor/**", "node_modules/**", ".venv/**"]
    )
    
    @classmethod
    def from_yaml(cls, path: str) -> "CodeCustodianConfig":
        """Load config from YAML file."""
        import yaml
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return cls(**data)
```

---

## 10. CLI Requirements

**FR-CLI-001:** **CLI Interface (Typer)**

```python
import typer
from rich.console import Console
from rich.table import Table
from pathlib import Path

app = typer.Typer(
    name="codecustodian",
    help="Autonomous AI agent for technical debt management"
)
console = Console()

@app.command()
def run(
    repo_path: Path = typer.Option(".", help="Path to repository"),
    config: Path = typer.Option(".codecustodian.yml", help="Config file path"),
    max_prs: int = typer.Option(5, help="Max PRs per run"),
    scan_type: Optional[str] = typer.Option(None, help="Scanner filter"),
    dry_run: bool = typer.Option(False, help="Preview without creating PRs"),
    verbose: bool = typer.Option(False, "-v", help="Verbose logging"),
    debug: bool = typer.Option(False, help="Debug mode")
):
    """Run CodeCustodian scan and refactoring."""
    
    # Initialize
    custodian = CodeCustodian(
        repo_path=repo_path,
        config=Config.from_yaml(config)
    )
    
    # Scan
    console.print("[bold blue]🔍 Scanning codebase...[/bold blue]")
    findings = custodian.scan(filter_type=scan_type)
    console.print(f"[green]✓ Found {len(findings)} issues[/green]")
    
    # Process findings
    prs_created = 0
    for finding in findings[:max_prs]:
        console.print(f"\n[bold]Processing: {finding.description}[/bold]")
        
        # Plan
        plan = custodian.plan(finding)
        console.print(f"Confidence: {plan.confidence_score}/10")
        
        if dry_run:
            console.print("[yellow]Dry run: skipping execution[/yellow]")
            continue
        
        # Execute
        result = custodian.execute(plan)
        
        # Verify
        verification = custodian.verify(result)
        
        if verification.passed:
            # Create PR
            pr_num = custodian.create_pr(result, verification)
            console.print(f"[green]✓ Created PR #{pr_num}[/green]")
            prs_created += 1
        else:
            console.print(f"[red]✗ Verification failed[/red]")
    
    # Summary
    console.print(f"\n[bold green]✓ Created {prs_created} pull requests[/bold green]")

@app.command()
def init():
    """Initialize CodeCustodian in repository."""
    # Create .codecustodian.yml
    # Create .github/workflows/codecustodian.yml
    pass

@app.command()
def validate():
    """Validate configuration file."""
    pass
```

---

## 11. API Requirements (Future - Q2 2026)

**FR-API-001:** **REST API Server (FastAPI)**

```python
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List

app = FastAPI(title="CodeCustodian API")

class ScanRequest(BaseModel):
    repo_url: str
    branch: str = "main"

class FindingResponse(BaseModel):
    id: str
    type: str
    severity: str
    file: str
    line: int
    description: str

@app.post("/scan")
async def trigger_scan(request: ScanRequest):
    """Trigger manual scan."""
    pass

@app.get("/repositories/{repo_id}/findings")
async def get_findings(repo_id: str) -> List[FindingResponse]:
    """Get findings for repository."""
    pass
```

---

## 12. Testing & Quality Requirements

**FR-TEST-001:** **Test Coverage Target**
- Minimum 80% code coverage for all modules
- 90%+ for critical paths (executor, verifier)
- Use pytest + pytest-cov

**FR-TEST-002:** **Test Categories**
```
tests/
├── unit/
│   ├── test_scanners.py
│   ├── test_planner.py
│   ├── test_executor.py
│   └── test_verifier.py
├── integration/
│   ├── test_pipeline.py
│   └── test_github_api.py
├── e2e/
│   └── test_full_workflow.py
└── fixtures/
    ├── sample_repos/
    └── mock_responses/
```

**FR-TEST-003:** **Mocking Strategy**
- Mock GitHub Copilot SDK responses
- Mock GitHub API calls
- Use VCR.py for recording API interactions
- Fixture repositories for scanning tests

---

## 13. Security & Compliance Requirements

**FR-SEC-001:** **Secrets Management**
- Never log tokens or secrets
- Use environment variables for sensitive data
- Validate token permissions before operation
- Rotate tokens every 90 days

**FR-SEC-002:** **Code Execution Safety**
- Run in isolated environment (GitHub Actions runner)
- No arbitrary code execution
- Validate all file paths (prevent path traversal)
- Limit file size for processing (max 10MB per file)

**FR-SEC-003:** **Audit Trail**
```json
{
  "timestamp": "2026-02-11T17:00:00Z",
  "finding_id": "uuid",
  "action": "refactor_applied",
  "user": "github-actions[bot]",
  "file": "src/utils.py",
  "changes": {
    "lines_added": 5,
    "lines_removed": 3
  },
  "verification": {
    "tests_passed": true,
    "linting_passed": true
  },
  "pr_number": 123
}
```

---

## 14. Performance & Scalability Requirements

**FR-PERF-001:** **Performance Targets**
- Scan 1000 files in < 30 seconds
- Plan refactoring in < 10 seconds (per finding)
- Execute changes in < 5 seconds
- Verify with tests in < 2 minutes
- Total time per PR: < 5 minutes

**FR-PERF-002:** **Parallelization**
- Scan files in parallel (4 workers)
- Process independent findings in parallel
- Batch API calls to GitHub

**FR-PERF-003:** **Cost Optimization**
- Use token caching for Copilot SDK
- Select cheapest model that meets confidence threshold
- Rate limiting: max 20 requests/minute to Copilot

---

## 15. Observability & Logging Requirements

**FR-OBS-001:** **Structured Logging**
```python
import logging
import json

logger = logging.getLogger("codecustodian")
logger.setLevel(logging.INFO)

# JSON formatter
class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage(),
            "extra": getattr(record, "extra", {})
        })

# Usage
logger.info("Scan completed", extra={
    "findings_count": 20,
    "duration": 15.3
})
```

**FR-OBS-002:** **Metrics to Track**
- Findings per scan
- PRs created per run
- Confidence score distribution
- Verification pass rate
- Average cost per refactoring
- Time per stage (scan, plan, execute, verify)

---

## 16. Future Extensibility Requirements

### Q2 2026

**FR-EXT-001:** **Model Context Protocol (MCP) Integration**
- Implement MCP server for CodeCustodian tools
- Expose scanners as MCP resources
- Allow external MCP clients to query findings

**FR-EXT-002:** **Multi-Language Support**
- JavaScript/TypeScript scanner plugins
- Java scanner plugins (leveraging existing AST libraries)

**FR-EXT-003:** **Dashboard (Web UI)**
- Next.js dashboard for analytics
- Multi-repository overview
- Real-time scan status

### Q3 2026

**FR-EXT-004:** **Plugin Marketplace**
- Custom scanner SDK
- Community-contributed scanners
- Verified scanner badges

**FR-EXT-005:** **Advanced AI Features**
- RAG for codebase-specific patterns
- Learning from past refactorings
- Personalized confidence scoring

---

## Appendix A: Technology Stack

| Component | Technology | Version | Justification |
|-----------|-----------|---------|---------------|
| Language | Python | 3.11+ | GitHub Copilot SDK support, rich ecosystem |
| AI Engine | GitHub Copilot SDK | 0.1.0+ | Native GitHub integration, cost-effective |
| Git Operations | GitPython | 3.1.40+ | Mature, well-documented |
| GitHub API | PyGithub | 2.1.1+ | Complete GitHub API wrapper |
| CLI Framework | Typer | 0.9.0+ | Modern, type-safe CLI builder |
| Config Validation | Pydantic | 2.5.0+ | Runtime validation, type safety |
| Testing | pytest | 7.4.3+ | Industry standard |
| Linting | ruff | 0.1.7+ | Fast, modern linter |
| Security Scan | bandit | 1.7.5+ | Python security linter |
| Complexity | radon | 6.0.1+ | Cyclomatic complexity analysis |
| Coverage | pytest-cov | 4.1.0+ | Coverage integration with pytest |

---

## Appendix B: Competitive Feature Matrix

| Feature | CodeCustodian | Byteable | AutoCodeRover | Moderne | Dependabot |
|---------|---------------|----------|---------------|---------|------------|
| **Open Source** | ✅ | ❌ | ✅ | ❌ | ❌ |
| **CI/CD Native** | ✅ | ✅ | ⚠️ | ✅ | ✅ |
| **AI-Powered** | ✅ Copilot SDK | ✅ Multi-agent | ✅ Claude/GPT | ❌ Rule-based | ❌ |
| **Tech Debt Focus** | ✅ | ✅ | ⚠️ Bug fixing | ⚠️ Migrations | ❌ Deps only |
| **Confidence Scoring** | ✅ 1-10 | ✅ | ⚠️ Success rate | ❌ | ❌ |
| **Multi-turn AI** | ✅ | ✅ | ✅ | ❌ | ❌ |
| **Cost per Task** | < $0.50 | Unknown | $0.43 | Fixed price | Free |
| **Python Support** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **JS/TS Support** | Q2 2026 | ✅ | ❌ | ✅ | ✅ |
| **Security Scanning** | ✅ | ✅ | ❌ | ⚠️ Limited | ✅ |
| **Compliance Reports** | ✅ | ✅ SOC 2 | ❌ | ❌ | ❌ |
| **Dashboard** | Q2 2026 | ✅ | ❌ | ✅ | ✅ |

---

## Appendix C: Implementation Roadmap

### Phase 1: MVP (6 weeks)

**Week 1-2: Core Architecture**
- BaseScanner interface
- Pipeline architecture
- Configuration system
- CLI framework

**Week 3-4: Scanner Modules**
- Deprecated API scanner
- TODO comment scanner
- Code smell scanner (radon integration)

**Week 5: Copilot SDK Integration**
- Planner module
- Custom tools
- Prompt engineering
- Confidence scoring

**Week 6: Executor + Verifier**
- Safe file operations
- Git workflow manager
- Test runner
- Linter integration

### Phase 2: GitHub Integration (2 weeks)

**Week 7: GitHub API**
- PR creation
- Issue creation
- Comment automation

**Week 8: Testing + Polish**
- Unit tests (80%+ coverage)
- Integration tests
- Documentation
- Example repository

### Phase 3: Beta Launch (2 weeks)

**Week 9: Security + Compliance**
- Security hardening
- Audit logging
- SOC 2 preparation

**Week 10: Public Beta**
- GitHub Marketplace listing
- Community feedback
- Bug fixes

---

## Appendix D: Success Criteria

### Technical Metrics
- ✅ 80%+ test coverage
- ✅ < 5 minutes per PR creation
- ✅ < $0.50 per refactoring
- ✅ 95%+ test pass rate after refactoring
- ✅ 25-35% issue resolution rate (tech debt)

### Adoption Metrics
- ✅ 1000+ repositories in 6 months
- ✅ 100+ GitHub stars in 3 months
- ✅ 10+ community contributors
- ✅ 50+ custom scanners in marketplace (Q3 2026)

### Business Metrics
- ✅ 100+ Pro subscribers ($19/month) by Q3 2026
- ✅ 5+ Enterprise customers by Q4 2026
- ✅ 4.5+ stars on GitHub Marketplace

---

## Document Changelog

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2026-02-11 | 1.0 | Initial comprehensive requirements | AI + User |

---

**END OF DOCUMENT**

Total Pages: 35 | Total Requirements: 150+ | Target Audience: GitHub Copilot Agents