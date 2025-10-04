#!/usr/bin/env python3
"""version tool - Get server version"""

from xcode_mcp_server import __version__
from xcode_mcp_server.server import mcp
from xcode_mcp_server.config_manager import apply_config
from xcode_mcp_server.utils.applescript import show_result_notification


@mcp.tool()
@apply_config
def version() -> str:
    """
    Get the current version of the Xcode MCP Server.

    Returns:
        The version string of the server
    """
    show_result_notification(f"Version {__version__}")
    return f"Xcode MCP Server version {__version__}"
