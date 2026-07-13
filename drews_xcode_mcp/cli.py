#!/usr/bin/env python3
"""Command-line interface and server initialization"""

import os
import sys
import subprocess
import argparse
import time

from drews_xcode_mcp import __version__
from drews_xcode_mcp.server import mcp, LEGACY_PACKAGE_NAME
from drews_xcode_mcp.security import get_allowed_folders, set_allowed_folders
from drews_xcode_mcp.utils.applescript import set_notifications_enabled, show_notification
from drews_xcode_mcp.utils.xcresult import set_build_warnings_enabled, freeze_build_warnings_settings

_LEGACY_RENAME_NOTIFICATION_INTERVAL_SECONDS = 24 * 60 * 60


def _show_legacy_rename_notification_if_needed():
    """Show a macOS notification about the package rename, at most once a day.

    This pop-up is the migration channel the user sees directly; the LLM-facing
    channels (server instructions, version tool, migration prompt) live in
    server.py. Throttled via a marker file because MCP clients start a fresh
    server process per session, which could otherwise nag on every restart.
    """
    if not LEGACY_PACKAGE_NAME:
        return

    # Constructing the ConfigManager first lets it migrate ~/.xcode-mcp-server
    # to ~/.drews-xcode-mcp; touching the marker path directly here would create
    # the new directory prematurely and strand the old settings.
    from drews_xcode_mcp.config_manager import ConfigManager
    try:
        marker = ConfigManager()._config_dir / "legacy-rename-notified"
        if marker.exists() and time.time() - marker.stat().st_mtime < _LEGACY_RENAME_NOTIFICATION_INTERVAL_SECONDS:
            return
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
    except OSError:
        # A notification is never worth failing startup over.
        return

    show_notification(
        "Xcode MCP Server renamed",
        subtitle=f"'{LEGACY_PACKAGE_NAME}' is now 'drews-xcode-mcp'",
        message="Your current setup still works. When convenient, update your MCP config to run 'drews-xcode-mcp'.",
    )


def initialize_server():
    """Entry point for the drews-xcode-mcp command"""
    # Debug
    print(f"Drew's Xcode MCP Server (drews-xcode-mcp) v{__version__}", file=sys.stderr)

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Drew's Xcode MCP Server")
    parser.add_argument("--version", action="version", version=f"drews-xcode-mcp {__version__}")
    parser.add_argument("--configure", action="store_true", help="Launch configuration UI")
    parser.add_argument("--allowed", action="append", help="Add an allowed folder path (can be used multiple times)")
    parser.add_argument("--show-notifications", action="store_true", help="Enable notifications for tool invocations")
    parser.add_argument("--hide-notifications", action="store_true", help="Disable notifications for tool invocations")
    parser.add_argument("--no-build-warnings", action="store_true", help="Exclude warnings from build output")
    parser.add_argument("--always-include-build-warnings", action="store_true", help="Always include warnings in build output")
    args = parser.parse_args()

    # Handle --configure flag
    if args.configure:
        from drews_xcode_mcp.config_ui import run_configuration_ui
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

    # Construct the ConfigManager up front so the one-time migration of
    # ~/.xcode-mcp-server to ~/.drews-xcode-mcp happens at startup, where its
    # stderr note lands in the launch log, rather than lazily inside the first
    # tool call. This also protects any future startup code that touches the
    # config directory from stranding the legacy settings.
    from drews_xcode_mcp.config_manager import ConfigManager
    try:
        ConfigManager()
    except OSError as e:
        # An unusable config directory is not worth failing startup over;
        # before this eager construction the same failure surfaced at the
        # first tool call, and it still will (the singleton is only cached
        # on successful construction).
        print(f"Warning: could not initialize config directory: {e}", file=sys.stderr)

    # After notification settings are applied, so --hide-notifications is honored
    _show_legacy_rename_notification_if_needed()

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
   drews-xcode-mcp --allowed /path/to/folder1 --allowed /path/to/folder2

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
        except Exception:
            pass

        sys.exit(1)

    # Debug info
    print(f"Total allowed folders: {allowed_folders}", file=sys.stderr)
    cwd = os.getcwd()
    print(f"Working directory: {cwd}", file=sys.stderr)

    # Import all tools to register them with the MCP server
    # This must be done before mcp.run()
    from drews_xcode_mcp import tools

    # Show startup notification
    from drews_xcode_mcp.utils.applescript import show_notification

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

    # Lock startup-only globals so any later mutation surfaces as a
    # RuntimeError instead of silently racing concurrent tool readers.
    freeze_build_warnings_settings()

    # Run the server
    mcp.run()
