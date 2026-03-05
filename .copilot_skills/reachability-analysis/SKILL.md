---
name: reachability-analysis
description: >
  Code reachability and entry-point analysis using import graphs, call-chain
  tracing, and framework-aware detection for Flask, FastAPI, Django, and Lambda.
---

# Reachability Analysis Skill

## Entry Point Detection

### Supported Frameworks
| Framework  | Entry Pattern              | Detection Heuristic                        |
|-----------|----------------------------|--------------------------------------------|
| Flask     | `@app.route("/path")`      | Route decorator on `Flask()` app           |
| FastAPI   | `@router.get("/path")`     | HTTP method decorators on APIRouter/app    |
| Django    | `class MyView(View)`       | Subclasses of `View`, `APIView`, `ViewSet` |
| Lambda    | `def handler(event, ctx)`  | Two-param function named `handler`/`lambda_handler` |
| CLI/Main  | `if __name__ == "__main__"` | Standard Python entry guard               |

### Custom Entry Points
Beyond frameworks, consider these as entry points:
- Celery tasks: `@app.task`, `@shared_task`
- Click/Typer CLI commands: `@cli.command()`
- Management commands in Django: `BaseCommand` subclasses
- Webhook handlers: functions registered to receive external HTTP callbacks
- Cron jobs / scheduled tasks: code invoked on a schedule

## Call Graph Interpretation

### Reachability Tags
- **`entry-point`** — The finding is in a direct entry point module (highest exposure)
- **`reachable`** — There exists at least one call chain from an entry point to the finding
- **`internal-only`** — No entry-point path found; only used internally
- **`test-only`** — Used exclusively in test modules

### Priority Adjustment Based on Reachability
- Entry-point findings: **escalate** severity by one level
- Reachable findings: **keep** existing severity
- Internal-only findings: **may de-prioritize** if no external exposure
- Test-only findings: **informational** unless they mask production issues

### Understanding Call Chains
A call chain like `[app.main, app.routes, app.services.payment, app.utils.crypto]`
means:
1. `app.main` is the entry point
2. It imports `app.routes` which imports `app.services.payment`
3. Payment service imports `app.utils.crypto` — the module containing the finding
4. This is a **4-hop chain** — the finding is reachable from the entry point

Shorter chains = higher exposure. A 1-hop chain means the finding is directly in
an entry point.

## Attack Surface Analysis

### Security-Sensitive Reachability
For security findings (deprecated crypto, insecure defaults, injection risks):
1. Check if the finding is reachable from **any** HTTP/event entry point
2. Count the number of distinct entry points that can reach it
3. Higher fan-in (more entry points reaching the code) = higher blast radius
4. If reachable from authentication or payment entry points, escalate to CRITICAL

### Remediation Prioritization
When multiple findings are reachable:
1. Fix entry-point findings first (they're directly exposed)
2. Then fix findings reachable from security-sensitive entry points
3. Then fix other reachable findings by shortest chain length
4. Internal-only findings can wait for lower-priority sprints

## Import Graph Patterns

### Circular Imports
If the import graph contains cycles:
- Reachability may be understated (BFS terminates at visited nodes)
- Consider all modules in a cycle as mutually reachable
- Suggest breaking the cycle as a separate refactoring task

### Dynamic Imports
`importlib.import_module()` and `__import__()` are not captured by static
analysis. Flag modules using dynamic imports as potentially reachable even if
the static graph shows them as internal-only.
