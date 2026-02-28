# GitHub Copilot SDK v0.1.29 — Deep Analysis & Feedback

**Upgraded from:** v0.1.23 → **v0.1.29** | **Analyzed in:** CodeCustodian (Python 3.11+, async pipeline)

---

### Breaking Changes Impact on Our Codebase

| Change | SDK Version | Impact on CodeCustodian | Action Needed |
|---|---|---|---|
| `CopilotClient.stop()` now raises `ExceptionGroup[StopError]` instead of returning a list | v0.1.29 | **HIGH** — Our pipeline.py calls `await client.stop()` in a bare `finally` block with no `ExceptionGroup` handling. If sessions fail to destroy, we'll get an unhandled `ExceptionGroup`. | Wrap in `try/except*` or catch `ExceptionGroup` |
| `on_permission_request` handler **required** on `create_session()` / `resume_session()` (deny-all by default) | v0.1.28 | **CRITICAL** — Our copilot_client.py `create_session()` **does NOT pass `on_permission_request`** in the session config. The SDK will raise `ValueError` immediately. | Must add `"on_permission_request": PermissionHandler.approve_all` to session config |
| `typing-extensions` dropped from dependencies | v0.1.29 | Low — We don't depend on it transitively through the SDK | None |
| Min Python bumped to 3.11 | v0.1.28 | None — We already target 3.11+ | None |
| 30s hardcoded timeout removed from `JsonRpcClient.request()` | v0.1.28 | **Positive** — Our long-running planning turns won't hit an unexpected 30s wall anymore. `send_and_wait()` default is now 60s and configurable | Monitor for hangs |

---

### Bugs Found in the SDK

1. **`__version__` stuck at `"0.1.0"`** — copilot/\_\_init\_\_.py line 43 hardcodes `__version__ = "0.1.0"` instead of `"0.1.29"`. This means `copilot.__version__` is misleading. The *package metadata* correctly reports 0.1.29 (`pip show`), but the runtime attribute is wrong. **Recommendation:** Auto-generate `__version__` from package metadata or update during release.

2. **`_on_post_tool_use` hook return type mismatch** — The SDK `PostToolUseHandler` type signature expects `PostToolUseHookOutput | None`, but the hook invocation in client.py doesn't validate returns. Our wrapper returns `None` which works, but the type contract is inconsistent with the actual handler dispatch.

3. **`SessionRpc` has zero public methods** — The generated `SessionRpc` class exposes no typed methods. Only `ServerRpc.ping()` exists. All other RPC calls (`session.create`, `session.send`, etc.) go through raw `_client.request()` strings. This defeats the purpose of the codegen layer.

4. **TCP mode `_connect_via_tcp` lacks `sessions_lock`** — The TCP notification handler accesses `self._sessions.get(session_id)` without acquiring `self._sessions_lock`, unlike the stdio handler which correctly uses the lock. Race condition potential.

5. **`PermissionHandler.approve_all` type annotation is `Any -> dict`** — The static method is typed with `Any` for both params and returns a plain `dict` instead of `PermissionRequestResult`. This breaks type checking for consumers.

---

### Documentation Issues

1. **No migration guide for v0.1.23 → v0.1.29** — Six versions shipped with two breaking changes, but there's no consolidated Python-specific migration doc. The release notes are cross-SDK and noisy.

2. **`create_session` docstring doesn't mention `on_permission_request` is mandatory** — The docstring says "Optional configuration" but the implementation raises `ValueError` if the handler is missing. The example in the docstring also omits it in some code paths.

3. **No documentation on `SessionEvent` type discrimination** — The generated events use `SessionEventType` enum, but there's no guide showing how to match event types to their data shapes. Users have to read auto-generated code to discover `event.data` fields.

4. **`send_and_wait` timeout semantics unclear** — Docs say "does not abort in-flight agent work" but don't explain what happens to the session after timeout. Is it still processing? Can you send again?

5. **PyPI package description says "Python SDK for GitHub Copilot CLI"** — The Summary field is generic. Should mention version capabilities like hooks, permissions, infinite sessions.

6. **`hooks` API undiscoverable** — `SessionHooks` is a `TypedDict` with 6 hook types, but there's no high-level doc explaining the hook lifecycle or when each fires. Only type comments exist.

---

### New Feature Requests

1. **Async context manager for `CopilotClient`** — Currently must manually call `start()`/`stop()`. Should support `async with CopilotClient() as client:`. The `__aenter__`/`__aexit__` pattern is standard Python async and would prevent resource leaks. (`CopilotSession` has this, but `CopilotClient` doesn't.)

2. **Cost/usage tracking built into the SDK** — We had to build `UsageAccumulator` ourselves by parsing `assistant.usage` events. The SDK knows about `ModelBilling.multiplier` but doesn't expose cumulative session cost. A `session.total_usage` property would be invaluable.

3. **`define_tool` should support returning async generators for streaming tool results** — Currently tools must return the full result synchronously. For our file-scanning tools that process large codebases, streaming partial results via `tool.execution_partial_result` events would be useful.

4. **Retry/backoff configuration on `CopilotClientOptions`** — When `auto_restart` is True, there's no configuration for backoff strategy, max retries, or circuit-breaking. Our production deployment needs this for resilience.

5. **Model capability querying helper** — `list_models()` returns `ModelInfo` with nested `capabilities.supports.reasoning_effort`, but there's no `client.get_model(id)` or `client.supports_reasoning(model_id)` convenience method. We had to build `_pick_available()` ourselves.

6. **Session-level structured logging integration** — The SDK prints handler errors to stdout via `print(f"Error in session event handler: {e}")` in `_dispatch_event()`. Should integrate with Python `logging` module or allow a logger to be injected.

7. **`ExceptionGroup` catch pattern needs `except*` (Python 3.11+)** — Since the SDK now requires 3.11+, good. But document the recommended `except*` pattern clearly since many teams aren't familiar with PEP 654.

---

### What's Working Well

- **`define_tool` with Pydantic** — Decorator-based tool definition with auto JSON schema from Pydantic models is excellent. Clean DX.
- **Permission handler architecture** — Deny-by-default is the right security posture. `PermissionHandler.approve_all` convenience is practical for dev/CI.
- **Infinite sessions with compaction** — `InfiniteSessionConfig` with configurable thresholds is well-designed for long-running planning.
- **Bundled CLI binary** — Platform wheels with embedded `copilot.exe` eliminate the "where's my CLI" problem.
- **New event types** — `subagent.selected/completed/failed`, `session.compaction_*`, `skill.invoked` give great observability for agent orchestration.
- **Session lifecycle events on `CopilotClient.on()`** — Can now observe session creation/deletion at the client level.
- **`force_stop()`** — Essential for production — when graceful stop hangs, we need a kill switch.

---

### Summary Metrics

| Metric | Value |
|---|---|
| Public API surface (CopilotClient) | 14 methods + 1 property |
| Public API surface (CopilotSession) | 5 methods + 2 properties |
| Session event types | 47 enum values |
| Hook types | 6 (pre/post tool, prompt, session start/end, error) |
| Dependencies | 2 runtime (pydantic, python-dateutil) |
| Lines of Python source | ~2,800 across 8 modules |
| Breaking changes since v0.1.23 | 2 (permission handler required, stop() ExceptionGroup) |