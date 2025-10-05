#!/usr/bin/env python3
"""get_runtime_output tool - Get console output from last run"""

import sys
import json
from typing import Optional

from xcode_mcp_server.server import mcp
from xcode_mcp_server.config_manager import apply_config
from xcode_mcp_server.security import validate_and_normalize_project_path
from xcode_mcp_server.exceptions import InvalidParameterError, XCodeMCPError
from xcode_mcp_server.utils.xcresult import find_xcresult_for_project, extract_console_logs_from_xcresult
from xcode_mcp_server.utils.applescript import show_error_notification, show_warning_notification, show_result_notification


@mcp.tool()
@apply_config
def get_runtime_output(project_path: str,
                      regex_filter: Optional[str] = None,
                      max_lines: int = 20) -> str:
    """
    Fetches and returns the most relevant runtime console output from the project's
    most recent run.

    Output becomes available 2 seconds after the app terminates.

    Args:
        project_path: Path to an Xcode project (`*.xcproject`) or workspace (`*.xcworkspace`)
        regex_filter: Optional regex pattern to find matching lines in the output
        max_lines: Maximum number of matching lines to return (default 20)

    Returns:
        JSON string with structured console output including errors, warnings, context,
        and full_log_path pointing to the complete unfiltered plaintext log file.
    """
    # Validate and normalize path
    project_path = validate_and_normalize_project_path(project_path, "Getting runtime output for")

    # Find the most recent xcresult file for this project
    xcresult_path = find_xcresult_for_project(project_path)

    if not xcresult_path:
        show_warning_notification("No runtime output", "No xcresult found - project may not have been run recently")
        return "No xcresult file found. The project may not have been run recently, or the DerivedData may have been cleaned."

    print(f"Found xcresult: {xcresult_path}", file=sys.stderr)

    # Extract console logs (returns JSON)
    success, console_output = extract_console_logs_from_xcresult(xcresult_path, regex_filter, max_lines)

    if not success:
        show_error_notification("Failed to extract runtime output", console_output)
        raise XCodeMCPError(f"Failed to extract runtime output: {console_output}")

    if not console_output:
        if regex_filter:
            show_result_notification("No console output matched filter")
            return json.dumps({
                "summary": {"total_lines": 0},
                "note": f"No console output matched filter: {regex_filter}"
            })
        else:
            show_result_notification("No console output")
            return json.dumps({
                "summary": {"total_lines": 0},
                "note": "No console output in xcresult"
            })

    # Parse the JSON to show notification with summary
    try:
        output_data = json.loads(console_output)
        summary = output_data.get("summary", {})
        total = summary.get("total_lines", 0)
        errors = summary.get("errors_and_faults", 0)

        if errors > 0:
            show_error_notification("Runtime output", f"{errors} errors/faults in {total} lines")
        else:
            show_result_notification(f"Runtime output ({total} lines)")
    except json.JSONDecodeError:
        show_result_notification("Runtime output retrieved")

    return console_output
