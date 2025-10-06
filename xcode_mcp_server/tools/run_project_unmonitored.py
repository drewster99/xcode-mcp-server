#!/usr/bin/env python3
"""run_project_unmonitored tool - Launch app and return immediately"""

import os
from typing import Optional

from xcode_mcp_server.server import mcp
from xcode_mcp_server.config_manager import apply_config
from xcode_mcp_server.security import validate_and_normalize_project_path
from xcode_mcp_server.exceptions import XCodeMCPError
from xcode_mcp_server.utils.applescript import (
    escape_applescript_string,
    run_applescript,
    show_notification,
    show_error_notification
)


@mcp.tool()
@apply_config
def run_project_unmonitored(project_path: str,
                             scheme: Optional[str] = None) -> str:
    """
    Launch the app in Xcode and return immediately without waiting.

    The app will continue running until you stop it manually in Xcode.
    No monitoring, no automatic termination, no log extraction.

    Use get_runtime_output later (after manual termination) to retrieve logs.

    Perfect for: Long-running apps, servers, apps needing extended manual testing

    Args:
        project_path: Path to an Xcode project/workspace directory
        scheme: Optional scheme to run. If not provided, uses the active scheme.

    Returns:
        Success message indicating the app has been launched
    """
    # Validate and normalize path
    scheme_desc = scheme if scheme else "active scheme"
    normalized_path = validate_and_normalize_project_path(project_path, f"Launching {scheme_desc} in")
    escaped_path = escape_applescript_string(normalized_path)

    # Show launching notification
    project_name = os.path.basename(normalized_path)
    scheme_name = scheme if scheme else "active scheme"
    show_notification("Drew's Xcode MCP", subtitle=scheme_name, message=f"Launching {project_name}")

    # Build the AppleScript to launch the app
    if scheme:
        escaped_scheme = escape_applescript_string(scheme)
        script = f'''
        tell application "Xcode"
            open "{escaped_path}"

            -- Get the workspace document
            set workspaceDoc to first workspace document whose path is "{escaped_path}"

            -- Wait for it to load
            repeat 60 times
                if loaded of workspaceDoc is true then exit repeat
                delay 0.5
            end repeat

            if loaded of workspaceDoc is false then
                error "Xcode workspace did not load in time."
            end if

            -- Set the active scheme
            set active scheme of workspaceDoc to (first scheme of workspaceDoc whose name is "{escaped_scheme}")

            -- Run
            run workspaceDoc

            return "launched"
        end tell
        '''
    else:
        script = f'''
        tell application "Xcode"
            open "{escaped_path}"

            -- Get the workspace document
            set workspaceDoc to first workspace document whose path is "{escaped_path}"

            -- Wait for it to load
            repeat 60 times
                if loaded of workspaceDoc is true then exit repeat
                delay 0.5
            end repeat

            if loaded of workspaceDoc is false then
                error "Xcode workspace did not load in time."
            end if

            -- Run with active scheme
            run workspaceDoc

            return "launched"
        end tell
        '''

    success, output = run_applescript(script)

    if not success:
        show_error_notification("Failed to launch app", project_name)
        raise XCodeMCPError(f"Launch failed: {output}")

    # Show success notification with sound to get attention
    show_notification(
        "Drew's Xcode MCP",
        subtitle=project_name,
        message="🚀 App launched (running until manually stopped)",
        sound=True
    )

    return f"App '{project_name}' launched successfully in Xcode.\n\nThe app is now running and will continue until you stop it manually in Xcode.\n\nUse get_runtime_output after termination to retrieve console logs."
