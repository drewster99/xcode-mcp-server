"""Xcode MCP Server - Model Context Protocol server for Xcode integration"""

__version__ = "1.2.1"

def main():
    """Entry point for the xcode-mcp-server command"""
    import sys
    import os
    import argparse
    import subprocess
    from . import __main__
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Xcode MCP Server")
    parser.add_argument("--version", action="version", version=f"xcode-mcp-server {__version__}")
    parser.add_argument("--allowed", action="append", help="Add an allowed folder path (can be used multiple times)")
    parser.add_argument("--show-notifications", action="store_true", help="Enable notifications for tool invocations")
    parser.add_argument("--hide-notifications", action="store_true", help="Disable notifications for tool invocations")
    parser.add_argument("--no-build-warnings", action="store_true", help="Exclude warnings from build output")
    parser.add_argument("--always-include-build-warnings", action="store_true", help="Always include warnings in build output")
    args = parser.parse_args()
    
    # Handle notification settings
    if args.show_notifications and args.hide_notifications:
        print("Error: Cannot use both --show-notifications and --hide-notifications", file=sys.stderr)
        sys.exit(1)
    elif args.show_notifications:
        __main__.NOTIFICATIONS_ENABLED = True
        print("Notifications enabled", file=sys.stderr)
    elif args.hide_notifications:
        __main__.NOTIFICATIONS_ENABLED = False
        print("Notifications disabled", file=sys.stderr)

    # Handle build warning settings
    if args.no_build_warnings and args.always_include_build_warnings:
        print("Error: Cannot use both --no-build-warnings and --always-include-build-warnings", file=sys.stderr)
        sys.exit(1)
    elif args.no_build_warnings:
        __main__.BUILD_WARNINGS_ENABLED = False
        __main__.BUILD_WARNINGS_FORCED = False
        print("Build warnings forcibly disabled", file=sys.stderr)
    elif args.always_include_build_warnings:
        __main__.BUILD_WARNINGS_ENABLED = True
        __main__.BUILD_WARNINGS_FORCED = True
        print("Build warnings forcibly enabled", file=sys.stderr)
    
    # Initialize allowed folders from environment and command line
    __main__.ALLOWED_FOLDERS = __main__.get_allowed_folders(args.allowed)
    
    # Check if we have any allowed folders
    if not __main__.ALLOWED_FOLDERS:
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
                          'display alert "Xcode MCP Server Error" message "No valid allowed folders found. Check your configuration."'], 
                          capture_output=True)
        except:
            pass  # Ignore notification errors
        
        sys.exit(1)
    
    # Debug info
    print(f"Total allowed folders: {__main__.ALLOWED_FOLDERS}", file=sys.stderr)
    
    # Run the server
    __main__.mcp.run()

__all__ = ["main", "__version__"]