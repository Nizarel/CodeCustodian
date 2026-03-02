"""FastMCP server for Model Context Protocol integration.

Public API::

    from codecustodian.mcp import mcp, main
    from codecustodian.mcp import register_tools, register_resources, register_prompts
"""

from codecustodian.mcp.prompts import register_prompts
from codecustodian.mcp.resources import register_resources
from codecustodian.mcp.server import main, mcp
from codecustodian.mcp.tools import register_tools

__all__ = [
    "main",
    "mcp",
    "register_prompts",
    "register_resources",
    "register_tools",
]
