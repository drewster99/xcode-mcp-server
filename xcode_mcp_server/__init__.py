"""Xcode MCP Server - Model Context Protocol server for Xcode integration"""

__version__ = "1.3.0b7"


def main():
    """Entry point that delegates to CLI"""
    from xcode_mcp_server.cli import initialize_server
    return initialize_server()


__all__ = ["main", "__version__"]
