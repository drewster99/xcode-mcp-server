#!/usr/bin/env python3
"""run_project tool - Run an Xcode project"""

import os
import sys
import time
import datetime
from typing import Optional

from xcode_mcp_server.server import mcp
from xcode_mcp_server.config_manager import apply_config
from xcode_mcp_server.security import validate_and_normalize_project_path
from xcode_mcp_server.exceptions import InvalidParameterError, XCodeMCPError
from xcode_mcp_server.utils.applescript import (
    escape_applescript_string,
    run_applescript,
    show_notification,
    show_result_notification,
    show_error_notification
)
from xcode_mcp_server.utils.xcresult import (
    wait_for_xcresult_after_timestamp,
    extract_console_logs_from_xcresult
)


@mcp.tool()
@apply_config
def run_project(project_path: str,
               wait_seconds: int,
               scheme: Optional[str] = None,
               regex_filter: Optional[str] = None,
               max_lines: int = 20) -> str:
    """
    Run the specified Xcode project or workspace and wait for completion.
    Returns structured JSON with runtime output if the run completes within wait_seconds.

    Set wait_seconds to 0 to launch and return immediately, then use get_runtime_output to retrieve logs, which become available 2 seconds after execution terminates.

    Args:
        project_path: Path to an Xcode project/workspace directory
        wait_seconds: Maximum seconds to wait for completion. Set to 0 to launch and return immediately.
        scheme: Optional scheme to run. If not provided, uses the active scheme.
        regex_filter: Optional regex pattern to find matching lines in the output
        max_lines: Maximum number of matching lines to return (default 20)

    Returns:
        JSON string with structured console output, or status message if still running
    """
    # Validate other parameters
    if wait_seconds < 0:
        raise InvalidParameterError("wait_seconds must be non-negative")

    # Validate and normalize path
    scheme_desc = scheme if scheme else "active scheme"
    normalized_path = validate_and_normalize_project_path(project_path, f"Running {scheme_desc} in")
    escaped_path = escape_applescript_string(normalized_path)

    # Show running notification
    project_name = os.path.basename(normalized_path)
    scheme_name = scheme if scheme else "active scheme"
    show_notification("Drew's Xcode MCP", subtitle=scheme_name, message=f"Running {project_name}")

    # Build the AppleScript that runs and polls in one script
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
            set actionResult to run workspaceDoc

            -- Wait for completion
            repeat {wait_seconds} times
                if completed of actionresult is true then
                    return "done|" & (status of actionResult as text)
                end if
                delay 1
            end repeat

            -- Final return
            return "FAIL|" & (actionResult as text)
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
            set actionResult to run workspaceDoc

            -- Wait for completion
            repeat {wait_seconds} times
                if completed of actionresult is true then
                    return "done|" & (status of actionResult as text)
                end if
                delay 1
            end repeat

            -- Final return
            return "FAIL|" & (actionResult as text)
        end tell
        '''

    print(f"Running and waiting up to {wait_seconds} seconds for completion...", file=sys.stderr)

    # Capture start time BEFORE running the script
    start_time = time.time()
    start_datetime = datetime.datetime.fromtimestamp(start_time)
    print(f"Run start time: {start_datetime.strftime('%Y-%m-%d %H:%M:%S.%f')}", file=sys.stderr)

    success, output = run_applescript(script)

    if not success:
        show_error_notification("Failed to run project", project_name)
        raise XCodeMCPError(f"Run failed: {output}")

    # Parse the result
    print(f"Raw output: '{output}'", file=sys.stderr)
    parts = output.split("|")

    if len(parts) != 2:
        show_error_notification("Unexpected run output format", project_name)
        raise XCodeMCPError(f"Unexpected output format: {output}")

    completed = parts[0].strip().lower() == "true"
    final_status = parts[1].strip()

    print(f"Run completed={completed}, status={final_status}", file=sys.stderr)

    # Wait for an xcresult file that was modified at or after our start time
    # This prevents us from accidentally using results from a previous run
    # We'll wait up to 10 seconds for the xcresult file to appear/update
    xcresult_timeout = wait_seconds + 1
    xcresult_path = wait_for_xcresult_after_timestamp(normalized_path, start_time, xcresult_timeout)

    if not xcresult_path:
        if completed:
            show_error_notification("Run completed but logs unavailable", f"Status: {final_status}")
            return f"Run completed with status: {final_status}. Could not find xcresult file (modified after start time) to extract console logs."
        else:
            # No notification for still-running case
            return f"Still running after {wait_seconds} seconds (status: {final_status}). Try `get_runtime_output` after process exits."

    print(f"Using xcresult: {xcresult_path}", file=sys.stderr)

    # Extract console logs (returns JSON)
    success, console_output = extract_console_logs_from_xcresult(xcresult_path, regex_filter, max_lines)

    if not success:
        show_error_notification("Failed to extract logs", f"Status: {final_status}")
        return f"Run completed with status: {final_status}. {console_output}"

    if not console_output:
        show_result_notification(f"Run completed: {final_status}")
        return f"Run completed with status: {final_status}. No console output found (or filtered out)."

    # Show result notification with error count
    import json
    try:
        output_data = json.loads(console_output)
        summary = output_data.get("summary", {})
        errors = summary.get("errors_and_faults", 0)
        if errors > 0:
            show_error_notification(f"Run completed: {final_status}", f"{errors} errors/faults")
        else:
            show_result_notification(f"Run completed: {final_status}")
    except json.JSONDecodeError:
        show_result_notification(f"Run completed: {final_status}")

    return console_output
