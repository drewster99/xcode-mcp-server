#!/usr/bin/env python3
"""get_build_errors tool - Get build errors from last build"""

from typing import Optional

from xcode_mcp_server.server import mcp
from xcode_mcp_server.config_manager import apply_config
from xcode_mcp_server.security import validate_and_normalize_project_path
from xcode_mcp_server.exceptions import InvalidParameterError, XCodeMCPError
from xcode_mcp_server.utils.applescript import escape_applescript_string, run_applescript
from xcode_mcp_server.utils.xcresult import extract_build_errors_and_warnings


@mcp.tool()
@apply_config
def get_build_errors(project_path: str,
                    include_warnings: Optional[bool] = None,
                    regex_filter: Optional[str] = None,
                    max_lines: int = 25) -> str:
    """
    Get the build errors from the last build for the specified Xcode project or workspace.

    Args:
        project_path: Path to an Xcode project or workspace directory.
        include_warnings: Include warnings in output. If not provided, uses global setting.
        regex_filter: Optional regex to filter error/warning lines
        max_lines: Maximum number of error/warning lines to show (default 25)

    Returns:
        If no build has been performed: Returns plain text message.
        Otherwise, returns JSON string with format:
        {
            "full_log_path": "/tmp/xcode-mcp-server/logs/build-{hash}.txt",
            "summary": {"total_errors": N, "total_warnings": M, "showing_errors": X, "showing_warnings": Y},
            "errors_and_warnings": "Build succeeded/failed with N errors...\nerror: ...\n..."
        }
        Output is filtered using regex patterns to match compiler errors/warnings, with errors
        prioritized over warnings. Includes full unfiltered log file for complete analysis.
    """
    # Validate include_warnings parameter
    if include_warnings is not None and not isinstance(include_warnings, bool):
        raise InvalidParameterError("include_warnings must be a boolean value")

    # Validate and normalize path
    normalized_path = validate_and_normalize_project_path(project_path, "Getting build errors for")
    escaped_path = escape_applescript_string(normalized_path)

    # Get the last build log from the workspace
    script = f'''
    set projectPath to "{escaped_path}"

    tell application "Xcode"
        open projectPath

        -- Get the workspace document
        set workspaceDoc to first workspace document whose path is projectPath

        -- Wait for it to load (timeout after ~30 seconds)
        repeat 60 times
            if loaded of workspaceDoc is true then exit repeat
            delay 0.5
        end repeat

        if loaded of workspaceDoc is false then
            error "Xcode workspace did not load in time."
        end if

        -- Try to get the last build log
        try
            -- Get the most recent scheme action result
            set lastBuildResult to last scheme action result of workspaceDoc

            -- Always return the build log to capture warnings even on success
            return build log of lastBuildResult
        on error
            -- No build has been performed yet
            return ""
        end try
    end tell
    '''

    success, output = run_applescript(script)

    if success:
        if output == "":
            return "No build has been performed yet for this project."
        else:
            # Always extract and format errors/warnings (returns JSON)
            return extract_build_errors_and_warnings(output, include_warnings, regex_filter, max_lines)
    else:
        raise XCodeMCPError(f"Failed to retrieve build errors: {output}")
