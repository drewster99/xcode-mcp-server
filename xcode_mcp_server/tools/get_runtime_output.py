#!/usr/bin/env python3
"""get_runtime_output tool - Get console output from last run"""

import sys
from typing import Optional

from xcode_mcp_server.server import mcp
from xcode_mcp_server.security import validate_and_normalize_project_path
from xcode_mcp_server.exceptions import InvalidParameterError, XCodeMCPError
from xcode_mcp_server.utils.xcresult import find_xcresult_for_project, extract_console_logs_from_xcresult


@mcp.tool()
def get_runtime_output(project_path: str,
                      max_lines: int = 25,
                      regex_filter: Optional[str] = None) -> str:
    """
    Get the runtime output from the console for the last COMPLETED run of the specified Xcode project.
    Output from currently running apps does not become available until a few seconds after the app has terminated.

    Args:
        project_path: Path to an Xcode project/workspace directory.
        max_lines: Maximum number of lines to retrieve. Defaults to 25.
        regex_filter: Optional regex pattern to filter console output lines.

    Returns:
        Console output as a string
    """
    # Validate other parameters
    if max_lines < 1:
        raise InvalidParameterError("max_lines must be at least 1")

    # Validate and normalize path
    project_path = validate_and_normalize_project_path(project_path, "Getting runtime output for")

    # Find the most recent xcresult file for this project
    xcresult_path = find_xcresult_for_project(project_path)

    if not xcresult_path:
        return "No xcresult file found. The project may not have been run recently, or the DerivedData may have been cleaned."

    print(f"Found xcresult: {xcresult_path}", file=sys.stderr)

    # Extract console logs
    success, console_output = extract_console_logs_from_xcresult(xcresult_path, max_lines, regex_filter)

    if not success:
        raise XCodeMCPError(f"Failed to extract runtime output: {console_output}")

    if not console_output:
        return "No console output found in the most recent run (or filtered out by regex)."

    # Return the console output with a header
    output_lines = console_output.splitlines()
    header = f"Console output from most recent run ({len(output_lines)} lines):\n"
    header += "=" * 60 + "\n"

    return header + console_output
