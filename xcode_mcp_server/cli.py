#!/usr/bin/env python3
"""Command-line interface and server initialization"""

import os
import sys
import subprocess
import argparse

from xcode_mcp_server import __version__
from xcode_mcp_server.server import mcp
from xcode_mcp_server.security import get_allowed_folders, set_allowed_folders
from xcode_mcp_server.utils.applescript import set_notifications_enabled
from xcode_mcp_server.utils.xcresult import set_build_warnings_enabled


def initialize_server():
    """Entry point for the xcode-mcp-server command"""
    # Debug
    print(f"Drew's Xcode MCP Server (xcode-mcp-server) v{__version__}", file=sys.stderr)

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Drew's Xcode MCP Server")
    parser.add_argument("--version", action="version", version=f"xcode-mcp-server {__version__}")
    parser.add_argument("--configure", action="store_true", help="Launch configuration UI")
    parser.add_argument("--allowed", action="append", help="Add an allowed folder path (can be used multiple times)")
    parser.add_argument("--show-notifications", action="store_true", help="Enable notifications for tool invocations")
    parser.add_argument("--hide-notifications", action="store_true", help="Disable notifications for tool invocations")
    parser.add_argument("--no-build-warnings", action="store_true", help="Exclude warnings from build output")
    parser.add_argument("--always-include-build-warnings", action="store_true", help="Always include warnings in build output")
    args = parser.parse_args()

    # Handle --configure flag
    if args.configure:
        from xcode_mcp_server.config_ui import run_configuration_ui
        run_configuration_ui()
        sys.exit(0)

    # Handle notification settings
    if args.show_notifications and args.hide_notifications:
        print("Error: Cannot use both --show-notifications and --hide-notifications", file=sys.stderr)
        sys.exit(1)
    elif args.show_notifications:
        set_notifications_enabled(True)
        print("Notifications enabled", file=sys.stderr)
    elif args.hide_notifications:
        set_notifications_enabled(False)
        print("Notifications disabled", file=sys.stderr)

    # Handle build warning settings
    if args.no_build_warnings and args.always_include_build_warnings:
        print("Error: Cannot use both --no-build-warnings and --always-include-build-warnings", file=sys.stderr)
        sys.exit(1)
    elif args.no_build_warnings:
        set_build_warnings_enabled(False, forced=True)
        print("Build warnings forcibly disabled", file=sys.stderr)
    elif args.always_include_build_warnings:
        set_build_warnings_enabled(True, forced=True)
        print("Build warnings forcibly enabled", file=sys.stderr)

    # Initialize allowed folders from environment and command line
    allowed_folders = get_allowed_folders(args.allowed)
    set_allowed_folders(allowed_folders)

    # Check if we have any allowed folders
    if not allowed_folders:
        error_msg = """
========================================================================
ERROR: Xcode MCP Server cannot start - No valid allowed folders!
========================================================================

No valid folders were found to allow access to.

To fix this, you can either:

1. Set the XCODEMCP_ALLOWED_FOLDERS environment variable:
   export XCODEMCP_ALLOWED_FOLDERS="/path/to/folder1:/path/to/folder2"

2. Use the --allowed command line option:
   xcode-mcp-server --allowed /path/to/folder1 --allowed /path/to/folder2

3. Ensure your $HOME directory exists and is accessible

All specified folders must:
- Be absolute paths
- Exist on the filesystem
- Be directories (not files)
- Not contain '..' components

========================================================================
"""
        print(error_msg, file=sys.stderr)

        # Show macOS notification
        try:
            subprocess.run(['osascript', '-e',
                          'display alert "Drew\'s Xcode MCP Server Error" message "No valid allowed folders found. Check your configuration."'],
                          capture_output=True)
        except:
            pass  # Ignore notification errors

        sys.exit(1)

    # Debug info
    print(f"Total allowed folders: {allowed_folders}", file=sys.stderr)
    cwd = os.getcwd()
    print(f"Working directory: {cwd}", file=sys.stderr)

    # Import all tools to register them with the MCP server
    # This must be done before mcp.run()
    from xcode_mcp_server import tools

    # Show startup notification
    from xcode_mcp_server.utils.applescript import show_notification

    # Format the working directory relative to home if possible
    home = os.path.expanduser("~")
    if cwd.startswith(home):
        # Make it relative to home with ~ prefix
        display_cwd = "~" + cwd[len(home):]
    else:
        display_cwd = cwd

    show_notification(
        f"Drew's Xcode MCP Server - v{__version__}",

        message="Working dir: " + display_cwd,
        subtitle="✅ Server started"
    )

    # Run the server
    mcp.run()
