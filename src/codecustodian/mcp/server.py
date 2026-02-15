"""FastMCP server for CodeCustodian.

Thin entry point: initialises the ``FastMCP`` instance and wires in
tools, resources, and prompts from their dedicated modules.

Exposes scanning, planning, execution, and configuration as MCP-native
primitives consumable by Copilot Chat, VS Code, Claude Desktop, and
other MCP clients.
"""

from __future__ import annotations

import argparse
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
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--transport", default="stdio")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args, _ = parser.parse_known_args(sys.argv[1:])

    if args.transport == "streamable-http":
        mcp.run(transport=args.transport, host=args.host, port=args.port)
        return

    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
