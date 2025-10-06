#!/usr/bin/env python3
"""run_project_until_terminated tool - Run app until it terminates or times out"""

import os
import sys
import time
import datetime
from typing import Optional

from xcode_mcp_server.server import mcp
from xcode_mcp_server.config_manager import apply_config
from xcode_mcp_server.security import validate_and_normalize_project_path
from xcode_mcp_server.exceptions import XCodeMCPError
from xcode_mcp_server.utils.applescript import (
    escape_applescript_string,
    run_applescript,
    show_notification,
    show_result_notification,
    show_error_notification,
    show_warning_notification
)
from xcode_mcp_server.utils.xcresult import (
    wait_for_xcresult_after_timestamp,
    extract_console_logs_from_xcresult
)


@mcp.tool()
@apply_config
def run_project_until_terminated(project_path: str,
                                  scheme: Optional[str] = None,
                                  regex_filter: Optional[str] = None,
                                  max_lines: int = 20) -> str:
    """
    Run the app and wait for it to terminate naturally (up to 10 minutes).

    The app will run in Xcode/Simulator. If it doesn't terminate within 10 minutes,
    it will be force-stopped and runtime logs will be extracted.

    No user interaction required - fully automated.

    Perfect for: Automated tests, CLI tools, apps with defined exit points

    Args:
        project_path: Path to an Xcode project/workspace directory
        scheme: Optional scheme to run. If not provided, uses the active scheme.
        regex_filter: Optional regex pattern to find matching lines in the output
        max_lines: Maximum number of matching lines to return (default 20)

    Returns:
        JSON string with structured console output
    """
    # Validate and normalize path
    scheme_desc = scheme if scheme else "active scheme"
    normalized_path = validate_and_normalize_project_path(project_path, f"Running {scheme_desc} in")
    escaped_path = escape_applescript_string(normalized_path)

    # Show running notification
    project_name = os.path.basename(normalized_path)
    scheme_name = scheme if scheme else "active scheme"
    show_notification("Drew's Xcode MCP", subtitle=scheme_name, message=f"Running {project_name}")

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
            set actionResult to run workspaceDoc

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
            set actionResult to run workspaceDoc

            return "launched"
        end tell
        '''

    print(f"Launching app...", file=sys.stderr)

    # Capture start time BEFORE running the script
    start_time = time.time()
    start_datetime = datetime.datetime.fromtimestamp(start_time)
    print(f"Run start time: {start_datetime.strftime('%Y-%m-%d %H:%M:%S.%f')}", file=sys.stderr)

    success, output = run_applescript(script)

    if not success:
        show_error_notification("Failed to launch app", project_name)
        raise XCodeMCPError(f"Launch failed: {output}")

    print(f"App launched, polling for termination (up to 10 minutes)...", file=sys.stderr)

    # Poll every 2 seconds for up to 10 minutes (600 seconds)
    timeout = 600
    elapsed = 0
    app_terminated = False

    while elapsed < timeout:
        # Check if app terminated
        check_script = f'''
        tell application "Xcode"
            set workspaceDoc to first workspace document whose path is "{escaped_path}"
            set lastAction to last scheme action result of workspaceDoc
            return completed of lastAction as string
        end tell
        '''

        success, completed_str = run_applescript(check_script)
        if success and completed_str.strip().lower() == "true":
            print(f"App terminated naturally after {elapsed} seconds", file=sys.stderr)
            app_terminated = True
            break

        time.sleep(2)
        elapsed += 2

    # If still running after timeout, force-stop
    if not app_terminated:
        print(f"App did not terminate within 10 minutes, force-stopping...", file=sys.stderr)
        show_warning_notification("App timeout (10 min)", "Force-stopping app")

        stop_script = f'''
        tell application "Xcode"
            set workspaceDoc to first workspace document whose path is "{escaped_path}"
            stop workspaceDoc
        end tell
        '''
        run_applescript(stop_script)

        # Wait and verify it stopped (up to 20 seconds)
        for _ in range(10):
            check_script = f'''
            tell application "Xcode"
                set workspaceDoc to first workspace document whose path is "{escaped_path}"
                set lastAction to last scheme action result of workspaceDoc
                return completed of lastAction as string
            end tell
            '''
            success, completed_str = run_applescript(check_script)
            if success and completed_str.strip().lower() == "true":
                print(f"App stopped successfully", file=sys.stderr)
                break
            time.sleep(2)

    # Wait for xcresult to finalize
    print(f"Waiting for runtime logs to become available...", file=sys.stderr)
    time.sleep(2)

    # Wait for an xcresult file that was modified at or after our start time
    xcresult_timeout = 10
    xcresult_path = wait_for_xcresult_after_timestamp(normalized_path, start_time, xcresult_timeout)

    if not xcresult_path:
        show_error_notification("Run completed but logs unavailable", "Could not find xcresult")
        return "Run completed. Could not find xcresult file to extract console logs."

    print(f"Using xcresult: {xcresult_path}", file=sys.stderr)

    # Extract console logs (returns JSON)
    success, console_output = extract_console_logs_from_xcresult(xcresult_path, regex_filter, max_lines)

    if not success:
        show_error_notification("Failed to extract logs", console_output)
        return f"Run completed. {console_output}"

    if not console_output:
        show_result_notification(f"Run completed")
        return "Run completed. No console output found (or filtered out)."

    # Show result notification with error count
    import json
    try:
        output_data = json.loads(console_output)
        summary = output_data.get("summary", {})
        errors = summary.get("errors_and_faults", 0)
        if errors > 0:
            show_error_notification(f"Run completed", f"{errors} errors/faults")
        else:
            show_result_notification(f"Run completed")
    except json.JSONDecodeError:
        show_result_notification(f"Run completed")

    return console_output
