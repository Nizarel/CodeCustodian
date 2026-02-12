"""FastMCP server for CodeCustodian.

Thin entry point: initialises the ``FastMCP`` instance and wires in
tools, resources, and prompts from their dedicated modules.

Exposes scanning, planning, execution, and configuration as MCP-native
primitives consumable by Copilot Chat, VS Code, Claude Desktop, and
other MCP clients.
"""

from __future__ import annotations

import sys

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from codecustodian import __version__

from .prompts import register_prompts
from .resources import register_resources
from .tools import register_tools

# ── Server initialisation ──────────────────────────────────────────────────

mcp = FastMCP(
    name="CodeCustodian",
    instructions="Autonomous AI agent for technical debt management",
    version=__version__,
    on_duplicate_tools="error",
)

# Wire modular registrations
register_tools(mcp)
register_resources(mcp)
register_prompts(mcp)


# ── Health check (Azure Container Apps / load-balancer probes) ─────────────


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Lightweight health probe for HTTP deployments."""
    return JSONResponse({"status": "ok", "version": __version__})


# ── Entry point ────────────────────────────────────────────────────────────


def main() -> None:
    """Entry point for the ``codecustodian-mcp`` console script.

    Accepts an optional ``--transport`` flag:

    * ``stdio``  (default) — for Claude Desktop / VS Code / CLI
    * ``streamable-http`` — for remote / Azure Container Apps deployment
    """
    transport = "stdio"
    if "--transport" in sys.argv:
        idx = sys.argv.index("--transport")
        if idx + 1 < len(sys.argv):
            transport = sys.argv[idx + 1]

    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
