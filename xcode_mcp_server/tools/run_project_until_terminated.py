#!/usr/bin/env python3
"""run_project_until_terminated tool - Run app until it terminates or times out"""

import os
import re
import sys
import time
import datetime
from typing import Optional

from xcode_mcp_server.server import mcp, TOOL_BUILD
from xcode_mcp_server.config_manager import apply_config
from xcode_mcp_server.security import validate_and_normalize_project_path
from xcode_mcp_server.exceptions import XCodeMCPError, InvalidParameterError
from xcode_mcp_server.utils.run_guard import exclusive_per_project
from xcode_mcp_server.utils.applescript import (
    resolve_build_timeout,
    format_timeout_duration,
    build_open_and_wait_applescript,
    escape_applescript_string,
    run_applescript,
    show_notification,
    show_result_notification,
    show_error_notification,
    show_warning_notification,
)
from xcode_mcp_server.utils.xcresult import (
    snapshot_xcresult_mtimes,
    wait_for_xcresult_after_timestamp,
    extract_console_logs_from_xcresult
)


@mcp.tool(annotations=TOOL_BUILD)
@apply_config
@exclusive_per_project
def run_project_until_terminated(project_path: str,
                                  scheme: Optional[str] = None,
                                  regex_filter: Optional[str] = None,
                                  max_lines: int = 20,
                                  timeout: Optional[int] = None) -> str:
    """
    Run the app and wait for it to terminate naturally (up to `timeout` seconds).

    The app will run in Xcode/Simulator. If it doesn't terminate within `timeout`
    seconds (default 600, i.e. 10 minutes), it will be force-stopped and runtime
    logs will be extracted.

    No user interaction required - fully automated.

    Perfect for: Automated tests, CLI tools, apps with defined exit points

    Args:
        project_path: Path to an Xcode project/workspace directory
        scheme: Optional scheme to run. If not provided, uses the active scheme.
        regex_filter: Optional regex pattern to find matching lines in the output
        max_lines: Maximum number of matching lines to return (default 20)
        timeout: Maximum seconds to wait for the app to terminate before
            force-stopping it. If not provided, defaults to 600. Must be a
            positive integer.

    Returns:
        JSON string with structured console output
    """
    # Validate and normalize path
    scheme_desc = scheme if scheme else "active scheme"
    normalized_path = validate_and_normalize_project_path(project_path, f"Running {scheme_desc} in")
    escaped_path = escape_applescript_string(normalized_path)
    effective_timeout = resolve_build_timeout(timeout)

    # Validate regex_filter up front so a bad pattern fails immediately rather
    # than after the (multi-minute) build+run, where it's otherwise only
    # compiled during log extraction.
    if regex_filter and regex_filter.strip():
        try:
            re.compile(regex_filter)
        except re.error as e:
            raise InvalidParameterError(f"Invalid regex_filter: {e}")

    # Show running notification
    project_name = os.path.basename(normalized_path)
    scheme_name = scheme if scheme else "active scheme"
    show_notification("Drew's Xcode MCP", subtitle=scheme_name, message=f"Running {project_name}")

    # The poll loop runs entirely inside AppleScript against the `actionResult`
    # reference returned by `run workspaceDoc`. This pins the wait to the action
    # this tool started — reading the workspace-global `last scheme action
    # result` (the prior approach) could observe a concurrent build/run/test on
    # the same workspace and report the wrong action's status. It also replaces
    # one osascript spawn every 2s with a single subprocess for the whole run.
    # Loops measure elapsed time with AppleScript's `(current date) - startDate`
    # (real wall-clock seconds) instead of summing fixed `delay` increments.
    # Counting `delay 1.0` ignores the per-iteration Apple Event round-trip, so
    # the old loop drifted longer than `effective_timeout` proportionally to the
    # timeout — which could push the run past the subprocess budget and get
    # osascript killed before its own `stop` ran. Wall-clock keeps the inner
    # bound honest regardless of IPC overhead.
    escaped_scheme = escape_applescript_string(scheme) if scheme else None
    script = (
        build_open_and_wait_applescript(escaped_path, escaped_scheme)
        + '    set actionResult to run workspaceDoc\n'
        + '    set runStartDate to (current date)\n'
        + '    set didTimeout to false\n'
        + '    repeat\n'
        + '        if completed of actionResult is true then exit repeat\n'
        + f'        if ((current date) - runStartDate) >= {effective_timeout} then\n'
        + '            set didTimeout to true\n'
        + '            exit repeat\n'
        + '        end if\n'
        + '        delay 1.0\n'
        + '    end repeat\n'
        + '    if didTimeout then\n'
        + '        stop workspaceDoc\n'
        + '        set stopStartDate to (current date)\n'
        + '        repeat\n'
        + '            if completed of actionResult is true then exit repeat\n'
        + '            if ((current date) - stopStartDate) >= 20 then exit repeat\n'
        + '            delay 1.0\n'
        + '        end repeat\n'
        + '        return "timeout"\n'
        + '    end if\n'
        + '    return "terminated"\n'
        + 'end tell\n'
    )

    print(f"Launching app and waiting for termination (up to {format_timeout_duration(effective_timeout)})...", file=sys.stderr)

    # Snapshot existing runtime xcresults BEFORE launching so we wait for a
    # genuinely new bundle rather than risk re-reading a prior run's logs.
    existing_xcresults = snapshot_xcresult_mtimes(normalized_path, logs_subdir="Launch")

    # Capture start time BEFORE running the script
    start_time = time.time()
    start_datetime = datetime.datetime.fromtimestamp(start_time)
    print(f"Run start time: {start_datetime.strftime('%Y-%m-%d %H:%M:%S.%f')}", file=sys.stderr)

    # The script polls inside AppleScript for up to effective_timeout (plus up
    # to 20s verifying a forced stop); the subprocess timeout must exceed that,
    # with a buffer for workspace load and IPC overhead. If the subprocess is
    # nonetheless killed (run_applescript raises), osascript dies mid-run and the
    # AppleScript's own `stop` never executes — so issue a best-effort stop with
    # a fresh short-lived osascript before propagating, rather than leaving the
    # app running.
    try:
        success, output = run_applescript(script, timeout=effective_timeout + 60)
    except XCodeMCPError:
        stop_script = (
            f'set projectPath to "{escaped_path}"\n'
            'tell application "Xcode"\n'
            '    set workspaceDoc to first workspace document whose path is projectPath\n'
            '    stop workspaceDoc\n'
            'end tell\n'
        )
        try:
            run_applescript(stop_script)
            print("Issued best-effort stop after run subprocess was killed.", file=sys.stderr)
        except XCodeMCPError:
            print("Best-effort stop after subprocess kill also failed; app may still be running.", file=sys.stderr)
        raise

    if not success:
        show_error_notification("Failed to launch app", project_name)
        raise XCodeMCPError(f"Launch failed: {output}")

    if output.strip() == "timeout":
        duration = format_timeout_duration(effective_timeout)
        print(f"App did not terminate within {duration}; force-stopped.", file=sys.stderr)
        show_warning_notification(f"App timeout ({duration})", "Force-stopped app")
    else:
        print(f"App terminated naturally.", file=sys.stderr)

    # Wait for xcresult to finalize
    print(f"Waiting for runtime logs to become available...", file=sys.stderr)
    time.sleep(2)

    # Wait for an xcresult file that was modified at or after our start time
    xcresult_timeout = 10
    xcresult_path = wait_for_xcresult_after_timestamp(normalized_path, start_time, xcresult_timeout, prior_mtimes=existing_xcresults)

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
