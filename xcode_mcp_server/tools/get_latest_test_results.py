#!/usr/bin/env python3
"""get_latest_test_results tool - Get test results from last run"""

import os
import subprocess
import json
import datetime

from xcode_mcp_server.server import mcp
from xcode_mcp_server.security import validate_and_normalize_project_path
from xcode_mcp_server.utils.applescript import (
    escape_applescript_string,
    run_applescript,
    show_result_notification,
    show_error_notification
)
from xcode_mcp_server.utils.xcresult import find_xcresult_bundle


@mcp.tool()
def get_latest_test_results(project_path: str) -> str:
    """
    Get the test results from the most recent test run.

    Args:
        project_path: Path to Xcode project/workspace directory

    Returns:
        Latest test results or "No test results available"
    """
    # Validate and normalize the project path
    project_path = validate_and_normalize_project_path(project_path, "get_latest_test_results")

    # Try to find the most recent xcresult bundle
    xcresult_path = find_xcresult_bundle(project_path)

    if xcresult_path and os.path.exists(xcresult_path):
        # Extract test results from xcresult bundle
        try:
            # Get test summary
            result = subprocess.run(
                ['xcrun', 'xcresulttool', 'get', '--path', xcresult_path, '--format', 'json'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)

                    # Parse the JSON to extract test information
                    output_lines = ["Test Results from xcresult bundle:", ""]

                    # Try to extract metrics
                    failed_count = 0
                    if 'metrics' in data:
                        metrics = data['metrics']
                        if 'testsCount' in metrics:
                            output_lines.append(f"Total tests: {metrics.get('testsCount', {}).get('_value', 'N/A')}")
                        if 'testsFailedCount' in metrics:
                            failed_count = metrics.get('testsFailedCount', {}).get('_value', 0)
                            output_lines.append(f"Failed tests: {failed_count}")

                    # Get modification time of xcresult
                    mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(xcresult_path))
                    output_lines.append(f"Test run: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")

                    # Show notification
                    if failed_count == 0:
                        show_result_notification("All tests PASSED")
                    else:
                        show_error_notification(f"{failed_count} test{'s' if failed_count != 1 else ''} FAILED")

                    return '\n'.join(output_lines)
                except:
                    pass
        except:
            pass

    # Fallback: Try to get from Xcode via AppleScript
    escaped_path = escape_applescript_string(project_path)

    script = f'''
set projectPath to "{escaped_path}"

tell application "Xcode"
    try
        -- Try to get the workspace document if it's already open
        set workspaceDoc to first workspace document whose path is projectPath

        -- Try to get last scheme action result
        set lastResult to last scheme action result of workspaceDoc

        set resultStatus to status of lastResult as string
        set resultCompleted to completed of lastResult

        -- Check if it was a test action by looking for test failures
        set isTestResult to false
        set failureMessages to ""
        try
            set failures to test failures of lastResult
            set isTestResult to true
            repeat with failure in failures
                set failureMessages to failureMessages & (message of failure) & "\\n"
            end repeat
        end try

        if isTestResult then
            return "Last test status: " & resultStatus & "\\n" & ¬
                   "Completed: " & resultCompleted & "\\n" & ¬
                   "Test failures:\\n" & failureMessages
        else
            return "No test results available (last action was not a test)"
        end if
    on error
        return "No test results available"
    end try
end tell
    '''

    success, output = run_applescript(script)

    if success:
        # Parse output to show notification
        if "No test results available" in output:
            show_result_notification("No test results")
        elif "succeeded" in output.lower():
            show_result_notification("All tests PASSED")
        elif "failed" in output.lower():
            show_error_notification("Tests FAILED")
        return output
    else:
        show_result_notification("No test results")
        return "No test results available"
