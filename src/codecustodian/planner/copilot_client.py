"""GitHub Copilot SDK client wrapper.

Wraps ``github-copilot-sdk`` (``copilot`` package, v0.1.29+) for
multi-turn AI planning sessions with tool calling, model routing,
streaming responses, cost tracking, and session hooks.

Auth order: ``github_token`` from config → ``GITHUB_TOKEN`` env var →
``gh`` CLI auth (``use_logged_in_user``).

Send API: hybrid — ``send_and_wait()`` for plan-generation turns,
``send()`` + event loop for tool-call turns.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from codecustodian.exceptions import BudgetExceededError, PlannerError
from codecustodian.logging import get_logger

if TYPE_CHECKING:
    from copilot.types import CopilotClientOptions

    from codecustodian.config.schema import CopilotConfig

logger = get_logger("planner.copilot_client")


# ── Cost tracking ──────────────────────────────────────────────────────────


@dataclass
class UsageAccumulator:
    """Tracks token usage and cost across a pipeline run."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_cost: float = 0.0
    requests: int = 0

    def record(self, input_toks: int, output_toks: int, cost: float) -> None:
        self.input_tokens += input_toks
        self.output_tokens += output_toks
        self.total_cost += cost
        self.requests += 1


@dataclass
class ToolAuditEntry:
    """A single tool-call audit record."""

    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    result_summary: str = ""
    session_id: str = ""


# ── Client wrapper ─────────────────────────────────────────────────────────


class CopilotPlannerClient:
    """Wrapper around the GitHub Copilot SDK for refactoring planning.

    Lifecycle::

        client = CopilotPlannerClient(config)
        await client.start()
        models = await client.list_available_models()
        session = await client.create_session(model=..., tools=...)
        ...
        await client.stop()
    """

    def __init__(self, config: CopilotConfig) -> None:
        self.config = config
        self._client: Any = None
        self._available_models: list[Any] | None = None
        self.usage = UsageAccumulator()
        self.tool_audit_log: list[ToolAuditEntry] = []

    # ── Lifecycle ──────────────────────────────────────────────────────

    def _resolve_token(self) -> str:
        """Resolve GitHub token: config → env → empty (gh CLI fallback)."""
        return self.config.github_token or os.environ.get("GITHUB_TOKEN", "")

    async def start(self) -> None:
        """Initialize and start the Copilot SDK client."""
        try:
            from copilot import CopilotClient  # type: ignore[import-untyped]
        except ImportError as exc:
            raise PlannerError(
                "github-copilot-sdk is not installed. "
                "Install with: pip install github-copilot-sdk"
            ) from exc

        token = self._resolve_token()
        client_opts: dict[str, Any] = {
            "auto_start": True,
            "auto_restart": True,
            "log_level": "warning",
        }
        if token:
            client_opts["github_token"] = token
        else:
            # Fall back to gh CLI authentication
            client_opts["use_logged_in_user"] = True
            logger.info("No github_token — falling back to gh CLI auth")

        self._client = CopilotClient(cast("CopilotClientOptions", client_opts))
        await self._client.start()
        logger.info("Copilot SDK client started")

    async def stop(self) -> None:
        """Stop the Copilot SDK client gracefully.

        SDK v0.1.29 changed ``CopilotClient.stop()`` to raise
        ``ExceptionGroup[StopError]`` when cleanup has partial failures.
        We log and continue shutdown so pipeline cleanup remains resilient.
        """
        if self._client is not None:
            try:
                await self._client.stop()
            except ExceptionGroup as exc_group:
                for stop_err in exc_group.exceptions:
                    logger.warning("Copilot SDK stop cleanup error: %s", stop_err)
            self._client = None
            logger.info(
                "Copilot SDK client stopped — total cost=$%.4f, tokens=%d/%d",
                self.usage.total_cost,
                self.usage.input_tokens,
                self.usage.output_tokens,
            )

    # ── Model discovery ────────────────────────────────────────────────

    async def list_available_models(self) -> list[Any]:
        """Query available models from the SDK and cache the result."""
        self._ensure_client()
        if self._available_models is None:
            models = await self._client.list_models()
            self._available_models = models
            logger.info("Discovered %d available models", len(models))
        return self._available_models if self._available_models is not None else []

    def select_model(self, finding: Any) -> str:
        """Route to the appropriate model based on strategy + finding.

        Strategies:
        - ``auto``:  severity critical/high → best available, else mini
        - ``fast``:  fastest available model
        - ``balanced``:  mid-tier model
        - ``reasoning``: reasoning-capable model with high effort

        When ``list_available_models()`` has been called, validates
        the chosen model exists. Otherwise uses sensible defaults.
        """
        strategy = self.config.model_selection

        # Fixed strategies — models queried via list_models() 2026-02
        preferred: dict[str, list[str]] = {
            "fast": ["gpt-5-mini", "gpt-4.1", "gpt-5.1-codex-mini"],
            "balanced": ["gpt-5.1-codex", "gpt-5.1", "claude-sonnet-4"],
            "reasoning": [
                "gpt-5.2-codex", "gpt-5.1-codex-max",
                "gpt-5.2", "gpt-5.1-codex",
            ],
        }

        if strategy != "auto":
            candidates = preferred.get(strategy, ["gpt-5.1"])
            return self._pick_available(candidates)

        # Auto-route by severity
        severity = getattr(finding, "severity", None)
        sev_value = severity.value if severity else "medium"
        if sev_value in ("critical", "high"):
            return self._pick_available(
                ["gpt-5.2-codex", "gpt-5.1-codex", "gpt-5.1"]
            )
        return self._pick_available(
            ["gpt-5-mini", "gpt-5.1-codex-mini", "gpt-4.1"]
        )

    def _pick_available(self, candidates: list[str]) -> str:
        """Return the first candidate in the available models list.

        If models were not fetched yet, return the first candidate.
        """
        if not self._available_models:
            return candidates[0]

        model_ids = {
            getattr(m, "id", str(m)) for m in self._available_models
        }
        for c in candidates:
            if c in model_ids:
                return c
        # Fallback: first available or first candidate
        return candidates[0]

    # ── Session creation ───────────────────────────────────────────────

    async def create_session(
        self,
        *,
        model: str,
        tools: list[Any] | None = None,
        system_prompt: str = "",
    ) -> Any:
        """Create a multi-turn Copilot session for refactoring planning.

        Args:
            model: Model identifier (e.g. ``"gpt-5.1-codex"``).
            tools: List of ``@define_tool``-decorated tool objects.
            system_prompt: System prompt text (appended to SDK defaults).

        Returns:
            A ``CopilotSession`` object.
        """
        self._ensure_client()
        from copilot import PermissionHandler  # type: ignore[import-untyped]

        session_config: dict[str, Any] = {
            "model": model,
            "streaming": self.config.streaming,
            "tools": tools or [],
            # Required by SDK v0.1.28+: permissions are deny-by-default.
            "on_permission_request": PermissionHandler.approve_all,
            "system_message": {
                "mode": "append",
                "content": system_prompt,
            },
            "infinite_sessions": {"enabled": False},
            "hooks": {
                "on_pre_tool_use": self._on_pre_tool_use,
                "on_post_tool_use": self._on_post_tool_use,
                "on_error_occurred": self._on_error_occurred,
            },
        }

        # Azure OpenAI BYOK provider
        if self.config.azure_openai_provider is not None:
            prov = self.config.azure_openai_provider
            session_config["provider"] = {
                "type": "azure",
                "base_url": prov.base_url,
                "api_key": prov.api_key,
                "azure": {"api_version": prov.api_version},
            }

        # Reasoning effort for capable models (all GPT-5.x support it)
        if self.config.reasoning_effort and model in {
            "gpt-5.2-codex", "gpt-5.2", "gpt-5.1-codex-max",
            "gpt-5.1-codex", "gpt-5.1", "gpt-5.1-codex-mini", "gpt-5-mini",
        }:
            session_config["reasoning_effort"] = self.config.reasoning_effort

        session = await self._client.create_session(session_config)
        logger.info("Created planning session model=%s", model)
        return session

    # ── Send helpers (hybrid approach) ─────────────────────────────────

    async def send_and_wait(
        self,
        session: Any,
        prompt: str,
        *,
        timeout: int | None = None,
    ) -> str:
        """Send a prompt and wait for the full response (Turn 2 pattern).

        Uses ``session.send_and_wait()`` for synchronous plan generation.
        Tracks cost via ``assistant.usage`` events.
        """
        effective_timeout = timeout or self.config.timeout
        response = await session.send_and_wait(
            {"prompt": prompt}, timeout=effective_timeout
        )

        # Extract content from response
        content = self._extract_content(response)

        # Track usage if available
        self._track_usage_from_response(response)

        return content

    async def send_streaming(
        self,
        session: Any,
        prompt: str,
    ) -> str:
        """Send a prompt and accumulate streamed response (Turn 1 pattern).

        Uses ``session.send()`` + ``session.on()`` event loop.
        Waits for ``session.idle`` event indicating the turn is complete
        (all tool calls resolved).
        """
        done = asyncio.Event()
        chunks: list[str] = []
        final_content: list[str] = []

        def on_event(event: Any) -> None:
            event_type = getattr(event.type, "value", str(event.type))
            if event_type == "assistant.message_delta":
                delta = getattr(event.data, "delta_content", None) or ""
                chunks.append(delta)
            elif event_type == "assistant.message":
                content = getattr(event.data, "content", None) or ""
                final_content.append(content)
            elif event_type == "assistant.usage":
                self._track_usage_from_event(event)
            elif event_type == "session.idle":
                done.set()

        session.on(on_event)
        await session.send({"prompt": prompt})

        try:
            await asyncio.wait_for(done.wait(), timeout=self.config.timeout)
        except TimeoutError:
            logger.warning("Streaming turn timed out after %ds", self.config.timeout)

        # Prefer final assembled content, fallback to joined deltas
        return final_content[0] if final_content else "".join(chunks)

    # ── Session hooks ──────────────────────────────────────────────────

    async def _on_pre_tool_use(
        self, input_data: dict[str, Any], invocation: dict[str, Any]
    ) -> dict[str, str]:
        """Log tool calls and always allow (our tools are safe)."""
        tool_name = input_data.get("toolName", "unknown")
        args = input_data.get("toolArgs", {})
        session_id = invocation.get("session_id", "")

        logger.info("Copilot calling tool: %s args=%s", tool_name, args)
        self.tool_audit_log.append(
            ToolAuditEntry(
                tool_name=tool_name,
                arguments=args,
                session_id=session_id,
            )
        )
        return {"permissionDecision": "allow"}

    async def _on_post_tool_use(
        self, input_data: dict[str, Any], invocation: dict[str, Any]
    ) -> None:
        """Log tool result summary after execution."""
        tool_name = input_data.get("toolName", "unknown")
        result = input_data.get("result", "")
        result_summary = str(result)[:200] if result else ""

        logger.debug("Tool %s completed: %s", tool_name, result_summary)

        # Update last audit entry with result
        if self.tool_audit_log:
            self.tool_audit_log[-1].result_summary = result_summary

    async def _on_error_occurred(
        self, input_data: dict[str, Any], invocation: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle errors — retry recoverable, abort otherwise."""
        error_ctx = input_data.get("errorContext", "unknown")
        error = input_data.get("error", "unknown error")
        recoverable = input_data.get("recoverable", False)

        logger.error(
            "Error in %s: %s (recoverable=%s)", error_ctx, error, recoverable
        )

        if recoverable:
            return {"errorHandling": "retry", "retryCount": 2}
        return {"errorHandling": "abort"}

    # ── Cost tracking internals ────────────────────────────────────────

    def _track_usage_from_response(self, response: Any) -> None:
        """Extract and track usage from a send_and_wait response."""
        data = getattr(response, "data", response)
        input_toks = getattr(data, "input_tokens", 0) or 0
        output_toks = getattr(data, "output_tokens", 0) or 0
        cost = getattr(data, "cost", 0.0) or 0.0
        if input_toks or output_toks:
            self.usage.record(input_toks, output_toks, cost)
            self._check_budget()

    def _track_usage_from_event(self, event: Any) -> None:
        """Extract and track usage from an assistant.usage event."""
        data = getattr(event, "data", None)
        if data is None:
            return
        input_toks = getattr(data, "input_tokens", 0) or 0
        output_toks = getattr(data, "output_tokens", 0) or 0
        cost = getattr(data, "cost", 0.0) or 0.0
        if input_toks or output_toks:
            self.usage.record(input_toks, output_toks, cost)
            self._check_budget()

    def _check_budget(self) -> None:
        """Raise BudgetExceededError if cost exceeds max_cost_per_run."""
        limit = self.config.max_cost_per_run
        if limit > 0 and self.usage.total_cost > limit:
            raise BudgetExceededError(
                f"AI cost ${self.usage.total_cost:.4f} exceeds "
                f"max_cost_per_run ${limit:.2f}",
                current_cost=self.usage.total_cost,
                budget_limit=limit,
            )

    # ── Helpers ────────────────────────────────────────────────────────

    def _ensure_client(self) -> None:
        """Assert the client has been started."""
        if self._client is None:
            raise PlannerError(
                "CopilotPlannerClient not started. "
                "Call await client.start() first."
            )

    @staticmethod
    def _extract_content(response: Any) -> str:
        """Extract text content from a send_and_wait response."""
        if isinstance(response, str):
            return response
        data = getattr(response, "data", response)
        content = getattr(data, "content", None)
        if content:
            return str(content)
        if isinstance(data, dict):
            return data.get("content", str(data))
        return str(response)
