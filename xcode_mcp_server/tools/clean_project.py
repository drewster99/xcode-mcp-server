#!/usr/bin/env python3
"""clean_project tool - Clean an Xcode project"""

import os

from xcode_mcp_server.server import mcp
from xcode_mcp_server.config_manager import apply_config
from xcode_mcp_server.security import validate_and_normalize_project_path
from xcode_mcp_server.exceptions import XCodeMCPError
from xcode_mcp_server.utils.applescript import escape_applescript_string, run_applescript, show_result_notification, show_error_notification


@mcp.tool()
@apply_config
def clean_project(project_path: str) -> str:
    """
    Clean the specified Xcode project or workspace.

    Args:
        project_path: Path to an Xcode project/workspace directory.

    Returns:
        Output message
    """
    # Validate and normalize path
    normalized_path = validate_and_normalize_project_path(project_path, "Cleaning")
    escaped_path = escape_applescript_string(normalized_path)

    # AppleScript to clean the project
    script = f'''
    tell application "Xcode"
        open "{escaped_path}"

        -- Get the workspace document
        set workspaceDoc to first workspace document whose path is "{escaped_path}"

        -- Wait for it to load (timeout after ~30 seconds)
        repeat 60 times
            if loaded of workspaceDoc is true then exit repeat
            delay 0.5
        end repeat

        if loaded of workspaceDoc is false then
            error "Xcode workspace did not load in time."
        end if

        -- Clean the workspace
        clean workspaceDoc

        return "Clean completed successfully"
    end tell
    '''

    success, output = run_applescript(script)

    project_name = os.path.basename(normalized_path)

    if success:
        show_result_notification("Clean completed", project_name)
        return output
    else:
        show_error_notification("Clean failed", project_name)
        raise XCodeMCPError(f"Clean failed: {output}")
