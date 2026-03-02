# CodeCustodian — UX Strategy & Demo Playbook

> **Version:** 1.0 | **Date:** March 1, 2026
> **Goal:** Deliver the best possible user experience and nail the live demo.

---

## Table of Contents

1. [UX Audit — Current State](#1-ux-audit--current-state)
2. [Best UX Approach — The "Three Surfaces" Strategy](#2-best-ux-approach--the-three-surfaces-strategy)
3. [Surface 1: CLI — The Power User Experience](#3-surface-1-cli--the-power-user-experience)
4. [Surface 2: MCP in Copilot Chat — The AI-Native Experience](#4-surface-2-mcp-in-copilot-chat--the-ai-native-experience)
5. [Surface 3: Demo Script — The "Zero to PR" Hero Moment](#5-surface-3-demo-script--the-zero-to-pr-hero-moment)
6. [Demo Playbook — 3-Minute Script](#6-demo-playbook--3-minute-script)
7. [Quick-Win UX Improvements](#7-quick-win-ux-improvements)
8. [Visual Design Language](#8-visual-design-language)
9. [Pre-Demo Checklist](#9-pre-demo-checklist)
10. [Common Pitfalls & Mitigations](#10-common-pitfalls--mitigations)

---

## 1. UX Audit — Current State

### What We Have (Strengths)

| Surface | Features | UX Quality |
|---------|----------|:----------:|
| **CLI** (`typer` + `rich`) | 13 commands, Rich tables, panels, color-coded output, JSON/CSV/SARIF export, interactive menu | ⭐⭐⭐⭐ |
| **MCP Server** (FastMCP) | 8 tools, 6 resources, 4 prompts — works in VS Code Copilot Chat | ⭐⭐⭐⭐ |
| **Demo Script** (`demo-run.ps1`) | 5-step scripted walk-through with ASCII art, cost savings calc | ⭐⭐⭐ |
| **Demo Repo** (`demo/sample-enterprise-app`) | 4 files with ~25 planted findings across all scanner types | ⭐⭐⭐⭐ |
| **Onboarding** (`init` + `onboard`) | Template-based, auto-generates config + workflow | ⭐⭐⭐ |

### What's Missing (Gaps to Address)

| Gap | Impact on Demo | Effort to Fix |
|-----|:-------------:|:-------------:|
| No `rich.progress` bars during scanning | Medium — looks static during long scans | **Low** |
| No single-finding deep-dive command | High — can't zoom into a finding live | **Low** |
| No before/after diff preview in dry-run | High — the "magic moment" is invisible | **Medium** |
| Interactive mode has limited choices | Low — works for demo but feels shallow | **Low** |
| No color-coded severity in scan output | Medium — all findings look the same | **Low** |
| MCP demo requires pre-setup of Copilot Chat | Low — just needs rehearsal | **None** |

---

## 2. Best UX Approach — The "Three Surfaces" Strategy

The best UX for CodeCustodian is **not one UI** — it's three complementary
surfaces that match different user contexts:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CodeCustodian UX Model                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐   ┌──────────────────┐   ┌───────────────────┐   │
│  │   🖥️ CLI     │   │  🤖 MCP in       │   │  🔄 CI/CD         │   │
│  │              │   │  VS Code Copilot  │   │  (Zero-Touch)     │   │
│  │ Power users  │   │  Chat             │   │                   │   │
│  │ DevOps/SRE   │   │                   │   │  Fully automated  │   │
│  │ Scripting    │   │  Developers       │   │  PRs appear in    │   │
│  │              │   │  Natural language  │   │  GitHub — no UI   │   │
│  │ "Show me     │   │  "What are the    │   │  interaction      │   │
│  │  all critical│   │   worst code      │   │  needed           │   │
│  │  findings"   │   │   smells in       │   │                   │   │
│  │              │   │   this repo?"     │   │                   │   │
│  └──────────────┘   └──────────────────┘   └───────────────────┘   │
│        ▲                     ▲                       ▲              │
│        │                     │                       │              │
│     Demo Act 1            Demo Act 2              Demo Act 3       │
│     (Terminal)            (VS Code)               (GitHub)         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Why This Works

1. **CLI** proves it's a real, production-grade tool (not a demo toy)
2. **MCP in Copilot Chat** shows the AI-native experience (judges love this)
3. **CI/CD** proves it runs autonomously (enterprise applicability)

**Key insight:** The demo should flow through all three surfaces in sequence —
that creates a narrative arc from "discover" → "interact" → "automate."

---

## 3. Surface 1: CLI — The Power User Experience

### Current Commands (13 total)

| Command | Purpose | Demo-Ready? |
|---------|---------|:-----------:|
| `run` | Full pipeline (scan→plan→apply→verify→PR) | ✅ |
| `scan` | Scanners only | ✅ |
| `findings` | Filtered listing | ✅ |
| `status` | Dashboard (findings + budget + SLA) | ✅ |
| `init` | Bootstrap config + workflow | ✅ |
| `validate` | Check config | ✅ |
| `config` | Inspect/manage config | ✅ |
| `onboard` | Repo/org enrollment | ✅ |
| `create-prs` | Top-N findings → PRs | ✅ |
| `review-pr` | PR review summary | ✅ |
| `report` | ROI metrics | ✅ |
| `heal` | CI failure analysis | ✅ |
| `interactive` | Menu-driven mode | ⚠️ Needs polish |
| `version` | Version display | ✅ |

### Recommended UX Improvements for Demo

#### A. Add Progress Bars to Scanning

```python
# In _scan_findings, wrap scanner loop with rich.progress
with Progress(
    SpinnerColumn(),
    TextColumn("[bold blue]{task.description}"),
    BarColumn(),
    TaskProgressColumn(),
    console=console,
) as progress:
    task = progress.add_task("Scanning...", total=len(enabled_scanners))
    for scanner in enabled_scanners:
        progress.update(task, description=f"Running {scanner.name}...")
        findings.extend(scanner.scan(repo_path))
        progress.advance(task)
```

**Why:** The 2-3 second scan feels broken without feedback. A progress bar
makes even a fast scan feel satisfying.

#### B. Color-Coded Severity in Tables

```python
severity_colors = {
    "critical": "bold red",
    "high": "red",
    "medium": "yellow",
    "low": "dim",
    "info": "blue",
}
style = severity_colors.get(finding.severity.value, "white")
table.add_row(..., f"[{style}]{finding.severity.value}[/]", ...)
```

**Why:** Judges immediately see "red = bad" without reading labels.

#### C. Rich Summary Panel After Scan

```
╭─────────────────── Scan Complete ───────────────────╮
│                                                      │
│  📊 26 findings across 4 files                       │
│                                                      │
│  🔴 CRITICAL  3   ██████░░░░░░░░░░░░░░  12%        │
│  🟠 HIGH      8   ████████████████░░░░  31%        │
│  🟡 MEDIUM   10   ██████████████████████ 38%        │
│  ⚪ LOW       5   ██████████░░░░░░░░░░  19%        │
│                                                      │
│  ⏱️  Scanned in 2.3s  │  💰 Est. savings: $4,250    │
│                                                      │
│  Next: codecustodian run --dry-run                   │
╰─────────────────────────────────────────────────────╯
```

**Why:** This is the "screenshot moment" — the visual people share.

#### D. Diff Preview in Dry-Run Mode

When `--dry-run` is set, show a Rich-formatted diff of what would change:

```
╭──── Planned Change: data_processor.py ────╮
│                                            │
│  - df = df.append(new_row)                 │
│  + df = pd.concat([df, new_row])           │
│                                            │
│  Confidence: 9/10  │  Tests: ✅ pass       │
│  Safety: ✅ all 6 checks passed            │
╰────────────────────────────────────────────╯
```

**Why:** This is the **magic moment** — judges see the AI reasoning and
the actual code fix in one panel. Without this, the pipeline is a black box.

---

## 4. Surface 2: MCP in Copilot Chat — The AI-Native Experience

### Available MCP Tools (8)

| Tool | What It Does | Demo Value |
|------|-------------|:----------:|
| `scan_repository` | Run all scanners | ⭐⭐⭐⭐⭐ |
| `plan_refactoring` | AI refactoring plan via Copilot SDK | ⭐⭐⭐⭐⭐ |
| `apply_refactoring` | Execute file changes | ⭐⭐⭐⭐ |
| `verify_changes` | Run tests + linters | ⭐⭐⭐⭐ |
| `create_pull_request` | Open GitHub PR | ⭐⭐⭐⭐ |
| `list_scanners` | Show scanner catalog | ⭐⭐ |
| `calculate_roi` | Cost/hours/risk metrics | ⭐⭐⭐⭐ |
| `get_business_impact` | 5-factor scoring | ⭐⭐⭐ |

### Demo Script for Copilot Chat

Open VS Code with the demo repo → open Copilot Chat → type:

```
@codecustodian Scan the demo/sample-enterprise-app for security issues
and deprecated APIs. Show me the worst findings and plan a fix for the
most critical one.
```

Copilot Chat will:
1. Call `scan_repository` → return findings
2. Call `plan_refactoring` → generate AI plan with confidence score
3. Show the plan in natural language

Then follow up with:
```
What would the ROI be if we fix all these findings?
```
→ Calls `calculate_roi` → returns hours saved, cost savings, risk reduction.

**Why this is the hero moment:** A developer asks a question in plain
English and gets a fully reasoned plan with code changes and ROI. No
commands to memorize, no flags to set.

### MCP Prompt Templates (4)

| Prompt | Purpose | When to Demo |
|--------|---------|-------------|
| `refactor_finding` | Plan a fix for a specific finding | After scan |
| `scan_summary` | Prioritized summary of all findings | Overview |
| `roi_report` | Business value report | For executives |
| `onboard_repo` | Setup guidance | For new repos |

---

## 5. Surface 3: Demo Script — The "Zero to PR" Hero Moment

### Current Demo Script Flow

```
scripts/demo-run.ps1
├── Step 0: ASCII art banner
├── Step 1: Scan (5 scanner types)
├── Step 2: Findings analysis (type + severity breakdown)
├── Step 3: Cost savings estimate (manual vs. automated)
├── Step 4: Dry-run pipeline (scan → plan → safety check)
└── Step 5: Security deep-dive (critical findings only)
```

### Recommended Enhancements

| Enhancement | What | Why |
|---|---|---|
| **Add `--live` mode** | Real-time scan with progress bars + live findings table | Feels like watching an AI work |
| **Add diff output to Step 4** | Show planned code changes in color | "See what it would do" moment |
| **Add Step 6: MCP bridge** | Open VS Code and trigger Copilot Chat | Seamless CLI→MCP transition |
| **Shorten pauses** | 1.5s auto-advance instead of keypress | Keeps energy up |

---

## 6. Demo Playbook — 3-Minute Script

### Setup (Before You Start)

- [ ] Terminal: PowerShell with `.venv` activated
- [ ] VS Code: Open `demo/sample-enterprise-app` with MCP configured
- [ ] GitHub: Demo repo visible in browser tab
- [ ] Screen: Dark terminal theme, font size 16+
- [ ] Kill: Slack, Teams, email — no notifications

### Act 1: "The Problem" (30 seconds)

> **Narration:** "Every enterprise has this — a codebase full of deprecated
> APIs, security issues, and TODO comments that nobody touches. Let me
> show you what our demo app looks like..."

```powershell
# Show the planted tech debt
code demo/sample-enterprise-app/src/data_processor.py  # Pause on line with pd.DataFrame.append()
code demo/sample-enterprise-app/src/auth.py             # Pause on hardcoded password
```

> **Key line:** "This is real tech debt. Hardcoded secrets, deprecated pandas
> APIs, SQL injection. Every team has this."

### Act 2: "The Scan" (45 seconds)

> **Narration:** "CodeCustodian scans with 6 AI-powered scanners in seconds."

```powershell
codecustodian scan --repo-path demo/sample-enterprise-app
```

> **Point out:** Color-coded severity, 25+ findings found in <3 seconds.

```powershell
codecustodian status --repo-path demo/sample-enterprise-app
```

> **Point out:** Budget tracking, SLA metrics — "this is enterprise-grade."

### Act 3: "The AI Fix" (60 seconds) — **THE HERO MOMENT**

> **Narration:** "Now the AI plans and executes the fix. Watch this."

```powershell
codecustodian run --repo-path demo/sample-enterprise-app --dry-run --max-prs 1
```

> **Point out:** AI confidence score, safety checks, planned code changes.
> "Confidence 9/10, all safety checks passed, including dangerous function
> detection and path traversal blocking."

> **Key line:** "It didn't just find the problem — it wrote the fix, verified
> it against 6 safety checks, and it's ready to open a PR."

### Act 4: "The AI Conversation" (45 seconds) — **THE WOW MOMENT**

> Switch to VS Code Copilot Chat.

```
@codecustodian What are the security findings in the demo app?
Plan a fix for the most critical one.
```

> **Point out:** "I'm talking to the same engine in natural language. It's
> calling the same scan and plan tools through MCP."

> **Key line:** "Developers don't need to learn a CLI. They just ask."

### Act 5: "The Business Value" (30 seconds)

> **Narration:** "Every fix comes with business value."

```powershell
codecustodian report --format json
```

> **Or in Copilot Chat:**
```
@codecustodian What's the ROI of fixing all findings?
```

> **Key line:** "62 engineering hours saved, $4,960 in cost savings,
> zero production incidents. That's from our real pilot with the
> Azure SDK Python team."

### Closing (10 seconds)

> **Key line:** "CodeCustodian: scans your debt, plans the fix with AI,
> verifies safety, and ships the PR. All autonomous. All auditable.
> Powered by GitHub Copilot SDK, FastMCP, and Azure."

---

## 7. Quick-Win UX Improvements

Prioritized by **demo impact / implementation effort**:

| # | Improvement | Impact | Effort | Files to Change |
|---|-------------|:------:|:------:|-----------------|
| 1 | Severity color-coding in findings table | ⭐⭐⭐⭐⭐ | 5 min | `cli/main.py` |
| 2 | Rich summary panel after scan | ⭐⭐⭐⭐⭐ | 15 min | `cli/main.py` |
| 3 | Progress spinner during scan | ⭐⭐⭐⭐ | 10 min | `cli/main.py` |
| 4 | Fix interactive menu to work with all choices | ⭐⭐⭐ | 10 min | `cli/main.py` |
| 5 | Add `--live` flag to demo script | ⭐⭐⭐ | 20 min | `scripts/demo-run.ps1` |

### Implementation Priority: Do Items 1-3 Before the Demo

These three changes transform the CLI from "functional" to "impressive" and
take ~30 minutes total.

---

## 8. Visual Design Language

### Color Palette

| Element | Color | Rich Style |
|---------|-------|-----------|
| Critical | Red | `bold red` |
| High | Magenta/Orange-Red | `red` |
| Medium | Yellow | `yellow` |
| Low | Gray | `dim` |
| Info | Blue | `blue` |
| Success | Green | `bold green` |
| Headers | Cyan | `bold cyan` |
| Values / Metrics | White | `white` |
| Borders | Green (success), Blue (status), Red (errors) | Panel `border_style` |

### CLI Output Principles

1. **Scan results → Table** (always, with colored severity)
2. **Status/dashboard → Panel** (budget, SLA, summary in a box)
3. **Progress → Spinner + bar** (any operation > 1 second)
4. **Errors → Red panel** with actionable next step
5. **Success → Green check** with single-line confirmation

---

## 9. Pre-Demo Checklist

### Environment

- [ ] Python 3.11+ installed and `.venv` activated
- [ ] `pip install -e ".[dev]"` completed — no import errors
- [ ] `codecustodian version` returns current version
- [ ] `codecustodian scan --repo-path demo/sample-enterprise-app` works
- [ ] `codecustodian run --repo-path demo/sample-enterprise-app --dry-run` works
- [ ] Terminal font size ≥ 16pt, dark theme
- [ ] Terminal width ≥ 120 columns (Rich tables need room)

### MCP / Copilot Chat

- [ ] `mcp.json` configured in workspace
- [ ] VS Code Copilot Chat recognizes `@codecustodian`
- [ ] Test: `@codecustodian list scanners` returns scanner catalog
- [ ] Test: `@codecustodian scan demo/sample-enterprise-app` works

### Demo Repo

- [ ] `demo/sample-enterprise-app` has all 4 planted files
- [ ] Scanning produces 20-30 findings (mix of types/severities)
- [ ] No stale `.codecustodian.yml` in demo repo (use defaults)

### Network & Accounts

- [ ] GitHub token set (`GITHUB_TOKEN`) if showing PR creation
- [ ] Copilot SDK token available if running full pipeline
- [ ] Network stable (or have offline fallback showing cached results)

### Presentation

- [ ] `presentations/CodeCustodian-Deck.html` opens cleanly
- [ ] Customer testimonial ready to reference (Azure SDK Python team)
- [ ] Screen recording software ready (backup if live demo fails)

### Kill Switch

- [ ] If pipeline fails live → switch to `--dry-run` output
- [ ] If MCP fails → stay on CLI, skip Act 4
- [ ] Pre-recorded video as absolute last resort

---

## 10. Common Pitfalls & Mitigations

| Pitfall | Likelihood | Mitigation |
|---------|:----------:|-----------|
| **Scan returns 0 findings** | Low | Demo repo has 25+ planted findings. Verify before demo. |
| **MCP server won't connect** | Medium | Pre-start MCP server, test `@codecustodian list scanners` |
| **Pipeline hangs on Copilot SDK call** | Medium | Use `--dry-run` flag. Have pre-cached JSON output ready. |
| **Rich tables overflow terminal width** | Medium | Set terminal to 120+ cols. Use `--output-format json` as fallback. |
| **PR creation fails (no GitHub token)** | High | Always demo with `--dry-run`. Show the plan, not the PR. |
| **"How is this different from SonarQube?"** | Certain | Answer: "SonarQube finds problems. We fix them autonomously." |
| **"Does it work with Java/Go/Rust?"** | Likely | Answer: "Python + JS/TS today. Scanner is pluggable — new languages via custom rules DSL." |
| **Audience loses focus during scan** | Medium | Talk through what each scanner does while progress bar runs. |

---

## Summary: The Winning Formula

```
 "Show the problem" → "Fix it with AI" → "Prove the business value"
      (30 sec)            (90 sec)              (30 sec)

      Scan output          Dry-run plan           ROI report
      + Security           + Copilot Chat         + Customer
        deep-dive            MCP demo               testimonial
```

The best UX is the one where the audience thinks:
**"I wish we had this for our codebase."**

That happens when they see their own pain (deprecated APIs, security issues,
TODOs) being fixed autonomously, safely, with a cost savings number attached.
