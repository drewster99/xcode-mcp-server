#!/usr/bin/env python3
"""run_project_with_user_interaction tool - Run app with user interaction"""

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
    show_persistent_alert
)
from xcode_mcp_server.utils.xcresult import (
    wait_for_xcresult_after_timestamp,
    extract_console_logs_from_xcresult
)


@mcp.tool()
@apply_config
def run_project_with_user_interaction(project_path: str,
                                       scheme: Optional[str] = None,
                                       regex_filter: Optional[str] = None,
                                       max_lines: int = 20) -> str:
    """
    Run the app and display an alert dialog for you to interact with it.

    The app will run in Xcode/Simulator. Once confirmed running, an alert dialog
    will appear with a "Finish" button.

    - Click "Finish" when you're done testing → app will be force-stopped
    - If the app terminates on its own → no force-stop needed

    In either case, runtime logs are extracted and returned after a 2-second wait.

    Perfect for: Interactive testing, manual QA, debugging UI flows

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

    print(f"App launched, waiting for it to start running...", file=sys.stderr)

    # Poll for a few seconds to verify the app is actually running
    time.sleep(3)

    # Show the persistent alert with "Finish" button
    alert_process = show_persistent_alert(
        f"{project_name} is running",
        f"{project_name} is now running in Xcode/Simulator.\\n\\nInteract with the app as needed, then click Finish when you're done testing.",
        button_text="Finish"
    )

    print(f"Alert shown. Polling for app termination or user finish click...", file=sys.stderr)

    # Now poll to check if:
    # 1. App terminated naturally (check via AppleScript)
    # 2. User clicked Finish (alert process exited)

    app_terminated = False
    user_clicked_finish = False

    while True:
        # Check if user clicked Finish
        if alert_process and alert_process.poll() is not None:
            print(f"User clicked Finish", file=sys.stderr)
            user_clicked_finish = True
            break

        # Check if app terminated naturally
        check_script = f'''
        tell application "Xcode"
            set workspaceDoc to first workspace document whose path is "{escaped_path}"
            set lastAction to last scheme action result of workspaceDoc
            return completed of lastAction as string
        end tell
        '''

        success, completed_str = run_applescript(check_script)
        if success and completed_str.strip().lower() == "true":
            print(f"App terminated naturally", file=sys.stderr)
            app_terminated = True
            # Kill the alert since app is done
            if alert_process:
                try:
                    alert_process.terminate()
                except:
                    pass
            break

        # Poll every 2 seconds
        time.sleep(2)

    # If user clicked finish, we need to stop the app
    if user_clicked_finish and not app_terminated:
        print(f"Force-stopping app...", file=sys.stderr)
        stop_script = f'''
        tell application "Xcode"
            set workspaceDoc to first workspace document whose path is "{escaped_path}"
            stop workspaceDoc
        end tell
        '''
        run_applescript(stop_script)

        # Wait and verify it stopped
        for _ in range(10):  # Wait up to 20 seconds
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
