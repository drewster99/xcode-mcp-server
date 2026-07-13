"""Compatibility shim: the xcode-mcp-server package is now drews-xcode-mcp.

Installing this package pulls in drews-xcode-mcp and forwards the old
`xcode-mcp-server` command to it, so existing MCP client configurations keep
working unchanged. New configurations should invoke `drews-xcode-mcp` directly.
"""

import os
import sys

# Read by the renamed server so it can surface migration guidance to the
# client when it was launched through this legacy package name.
LEGACY_PACKAGE_ENVIRONMENT_VARIABLE = "XCODE_MCP_LEGACY_PACKAGE_NAME"


def main():
    """Forward the legacy xcode-mcp-server command to drews-xcode-mcp."""
    os.environ[LEGACY_PACKAGE_ENVIRONMENT_VARIABLE] = "xcode-mcp-server"
    # stderr only: stdout carries the MCP protocol stream and must stay clean.
    print(
        "NOTE: The 'xcode-mcp-server' package has been renamed to 'drews-xcode-mcp'.\n"
        "      This compatibility package keeps existing configurations working,\n"
        "      but please update your MCP configuration to run 'drews-xcode-mcp'.\n"
        "      Details: https://github.com/drewster99/drews-xcode-mcp",
        file=sys.stderr,
    )
    from drews_xcode_mcp import main as run_renamed_server
    return run_renamed_server()


def __getattr__(name):
    # __version__ is resolved lazily (PEP 562) rather than imported at module
    # scope: importing this shim must never pull in drews_xcode_mcp before
    # main() has set the legacy environment variable, because server.py reads
    # that variable at import time.
    if name == "__version__":
        from drews_xcode_mcp import __version__
        return __version__
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["main", "__version__"]
