#!/usr/bin/env python3
"""stop_project tool - Stop build/run operations"""

import os

from xcode_mcp_server.server import mcp
from xcode_mcp_server.config_manager import apply_config
from xcode_mcp_server.security import validate_and_normalize_project_path
from xcode_mcp_server.exceptions import InvalidParameterError, XCodeMCPError
from xcode_mcp_server.utils.applescript import escape_applescript_string, run_applescript, show_result_notification, show_error_notification


@mcp.tool()
@apply_config
def stop_project(project_path: str) -> str:
    """
    Stop the currently running build or run operation for the specified Xcode project or workspace.

    Args:
        project_path: Path to an Xcode project/workspace directory, which must
        end in '.xcodeproj' or '.xcworkspace' and must exist.

    Returns:
        A message indicating whether the stop was successful
    """
    # Validate and normalize path
    normalized_path = validate_and_normalize_project_path(project_path, "Stopping build/run for")
    escaped_path = escape_applescript_string(normalized_path)

    # AppleScript to stop the current build or run operation
    script = f'''
    tell application "Xcode"
        -- Try to get the workspace document
        try
            set workspaceDoc to first workspace document whose path is "{escaped_path}"
        on error
            return "ERROR: No open workspace found for path: {escaped_path}"
        end try

        -- Stop the current action (build or run)
        try
            stop workspaceDoc
            return "Successfully stopped the current build/run operation"
        on error errMsg
            return "ERROR: " & errMsg
        end try
    end tell
    '''

    success, output = run_applescript(script)

    project_name = os.path.basename(normalized_path)

    if success:
        if output.startswith("ERROR:"):
            # Extract the error message
            error_msg = output[6:].strip()
            if "No open workspace found" in error_msg:
                show_error_notification("Project not open in Xcode", project_name)
                raise InvalidParameterError(f"Project is not currently open in Xcode: {project_path}")
            else:
                show_error_notification("Failed to stop", error_msg)
                raise XCodeMCPError(f"Failed to stop build/run: {error_msg}")
        else:
            show_result_notification("Stopped", project_name)
            return output
    else:
        show_error_notification("Failed to stop", project_name)
        raise XCodeMCPError(f"Failed to stop build/run for {project_path}: {output}")
