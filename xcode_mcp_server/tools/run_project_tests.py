#!/usr/bin/env python3
"""run_project_tests tool - Run Xcode project tests"""

import os
import sys
import time
import json
from typing import Optional, List

from xcode_mcp_server.server import mcp
from xcode_mcp_server.config_manager import apply_config
from xcode_mcp_server.security import validate_and_normalize_project_path
from xcode_mcp_server.exceptions import InvalidParameterError
from xcode_mcp_server.utils.applescript import (
    escape_applescript_string,
    run_applescript,
    show_notification,
    show_result_notification,
    show_error_notification,
    show_warning_notification
)
from xcode_mcp_server.utils.xcresult import find_xcresult_bundle, extract_test_results_from_xcresult


# TODO: Implement selective test execution with xcodebuild
# AppleScript's 'test' command doesn't support -only-testing: flags, so we need
# to use xcodebuild directly for running specific tests. However, xcodebuild also
# requires specifying a run destination (-destination flag), which we need to
# extract from Xcode's active run destination before implementing this feature.
#
# def _get_active_scheme(project_path: str) -> str:
#     """Get the active scheme for a project using AppleScript"""
#     escaped_path = escape_applescript_string(project_path)
#     script = f'''
# tell application "Xcode"
#     open "{escaped_path}"
#     delay 1
#     set workspaceDoc to first workspace document whose path is "{escaped_path}"
#     set activeScheme to active scheme of workspaceDoc
#     return name of activeScheme
# end tell
#     '''
#     success, output = run_applescript(script)
#     if success:
#         return output.strip()
#     raise InvalidParameterError(f"Could not determine active scheme: {output}")
#
#
# def _run_tests_with_xcodebuild(project_path: str, tests_to_run: List[str],
#                                 scheme: Optional[str], max_wait_seconds: int) -> str:
#     """Run specific tests using xcodebuild (AppleScript doesn't support -only-testing:)"""
#
#     # Determine if this is a workspace or project
#     is_workspace = project_path.endswith('.xcworkspace')
#     project_flag = '-workspace' if is_workspace else '-project'
#
#     # Get scheme if not provided
#     if not scheme:
#         scheme = _get_active_scheme(project_path)
#
#     # Build xcodebuild command
#     cmd = [
#         'xcodebuild',
#         'test',
#         project_flag,
#         project_path,
#         '-scheme',
#         scheme
#     ]
#
#     # Add -only-testing: arguments
#     for test_id in tests_to_run:
#         cmd.extend(['-only-testing', test_id])
#
#     print(f"DEBUG: Running xcodebuild command: {' '.join(cmd)}", file=sys.stderr)
#
#     # Run xcodebuild
#     if max_wait_seconds == 0:
#         # Start in background and return immediately
#         subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
#         return "✅ Tests have been started. Use get_latest_test_results to check results later."
#
#     # Run and wait for completion
#     try:
#         result = subprocess.run(
#             cmd,
#             capture_output=True,
#             text=True,
#             timeout=max_wait_seconds
#         )
#
#         # Wait a moment for xcresult to be written
#         time.sleep(2)
#
#         # Get results from xcresult bundle
#         xcresult_path = find_xcresult_bundle(project_path)
#
#         if xcresult_path:
#             print(f"DEBUG: Found xcresult bundle at {xcresult_path}", file=sys.stderr)
#
#             try:
#                 xcresult = subprocess.run(
#                     ['xcrun', 'xcresulttool', 'get', 'test-results', 'tests', '--path', xcresult_path],
#                     capture_output=True,
#                     text=True,
#                     timeout=10
#                 )
#
#                 if xcresult.returncode == 0:
#                     # Parse to show notification
#                     try:
#                         test_data = json.loads(xcresult.stdout)
#                         failure_count = 0
#                         if 'tests' in test_data and '_values' in test_data['tests']:
#                             for test in test_data['tests']['_values']:
#                                 if test.get('testStatus', '') == 'Failure':
#                                     failure_count += 1
#
#                         if failure_count == 0:
#                             show_result_notification("All tests PASSED")
#                         else:
#                             show_error_notification(f"{failure_count} test{'s' if failure_count != 1 else ''} FAILED")
#                     except:
#                         pass
#
#                     return xcresult.stdout
#             except Exception as e:
#                 print(f"DEBUG: Exception getting xcresult data: {e}", file=sys.stderr)
#
#         # Fallback to xcodebuild output
#         if result.returncode == 0:
#             show_result_notification("Tests PASSED")
#             return "✅ Tests passed"
#         else:
#             show_error_notification("Tests FAILED")
#             # Return last 50 lines of output
#             lines = result.stdout.split('\n')
#             return "❌ Tests failed\n\n" + '\n'.join(lines[-50:])
#
#     except subprocess.TimeoutExpired:
#         show_result_notification(f"Tests timeout ({max_wait_seconds}s)")
#         return f"⏳ Tests did not complete within {max_wait_seconds} seconds"


@mcp.tool()
@apply_config
def run_project_tests(project_path: str,
                     scheme: Optional[str] = None) -> str:
    """
    Run tests for the specified Xcode project or workspace.

    Tests will run for up to 10 minutes before timing out. This timeout is hardcoded
    to prevent issues with test runs hanging indefinitely.

    Args:
        project_path: Path to Xcode project/workspace directory
        scheme: Optional scheme to test (uses active scheme if not specified)

    Returns:
        JSON with test results if tests complete, otherwise plain text status message.
        Success format:
        {
            "xcresult_path": "...",
            "summary": {"total_tests": N, "passed": M, "failed": K, "skipped": L},
            "failed_tests": [{"test_name": "...", "failure_message": "...", ...}]
        }
        Timeout: Plain text message indicating timeout
    """
    # Validate and normalize the project path
    project_path = validate_and_normalize_project_path(project_path, "run_project_tests")

    # Show notification
    show_notification("Drew's Xcode MCP", subtitle=os.path.basename(project_path), message="Running tests")

    # TODO: Selective test execution - commented out until we can get active run destination
    # # Handle various forms of empty/invalid tests_to_run parameter
    # # This works around MCP client issues with optional list parameters
    # if tests_to_run is not None:
    #     # Handle string inputs that might come from the client
    #     if isinstance(tests_to_run, str):
    #         tests_to_run = tests_to_run.strip()
    #         if not tests_to_run or tests_to_run in ['[]', 'null', 'undefined', '']:
    #             tests_to_run = None
    #         else:
    #             # Try to parse as a comma-separated list
    #             tests_to_run = [t.strip() for t in tests_to_run.split(',') if t.strip()]
    #     elif not tests_to_run:  # Empty list or other falsy value
    #         tests_to_run = None
    #
    # # If specific tests are requested, use xcodebuild (AppleScript doesn't support -only-testing:)
    # if tests_to_run:
    #     return _run_tests_with_xcodebuild(project_path, tests_to_run, scheme, max_wait_seconds)

    # For running all tests, use AppleScript
    escaped_path = escape_applescript_string(project_path)
    test_command = 'test workspaceDoc'

    # Build the wait section with 10 minute (600 second) timeout
    wait_section = f'''set waitTime to 0
    repeat while waitTime < 600
        if completed of testResult is true then
            exit repeat
        end if
        delay 1
        set waitTime to waitTime + 1
    end repeat

    -- Get results
    set testStatus to status of testResult as string
    set testCompleted to completed of testResult

    -- Get failures if any with full details
    set failureMessages to ""
    set failureCount to 0
    try
        set failures to test failures of testResult
        set failureCount to count of failures
        if failureCount > 0 then
            repeat with failure in failures
                set failureMsg to ""
                set failurePath to ""
                set failureLine to ""

                try
                    set failureMsg to message of failure
                on error
                    set failureMsg to "Unknown test failure"
                end try

                try
                    set failurePath to file path of failure
                end try

                try
                    set failureLine to starting line number of failure as string
                end try

                set failureMessages to failureMessages & "FAILURE: " & failureMsg & "\\n"
                if failurePath is not "" and failurePath is not missing value then
                    set failureMessages to failureMessages & "FILE: " & failurePath & "\\n"
                end if
                if failureLine is not "" and failureLine is not "missing value" then
                    set failureMessages to failureMessages & "LINE: " & failureLine & "\\n"
                end if
                set failureMessages to failureMessages & "---\\n"
            end repeat
        else
            -- No test failures in collection, but status might still be failed
            -- This happens when tests fail but the failures collection is empty
            -- We'll parse the build log later to extract actual failure details
            if testStatus is "failed" or testStatus contains "fail" then
                set failureMessages to "PARSE_FROM_LOG" & "\\n"
            end if
        end if
    on error errMsg
        -- Could not access test failures
        if testStatus is "failed" or testStatus contains "fail" then
            set failureMessages to "PARSE_FROM_LOG" & "\\n"
        end if
    end try

    -- Get build log for statistics
    set buildLog to ""
    try
        set buildLog to build log of testResult
    end try

    return "Status: " & testStatus & "\\n" & ¬
           "Completed: " & testCompleted & "\\n" & ¬
           "FailureCount: " & (failureCount as string) & "\\n" & ¬
           "Failures:\\n" & failureMessages & "\\n" & ¬
           "---LOG---\\n" & buildLog'''

    script = f'''
set projectPath to "{escaped_path}"

tell application "Xcode"
    -- Wait for any modal dialogs to be dismissed
    delay 0.5

    -- Open and get the workspace document
    open projectPath
    delay 2

    -- Get the workspace document
    set workspaceDoc to first workspace document whose path is projectPath

    -- Wait for workspace to load
    set loadWaitTime to 0
    repeat while loadWaitTime < 60
        if loaded of workspaceDoc is true then
            exit repeat
        end if
        delay 0.5
        set loadWaitTime to loadWaitTime + 0.5
    end repeat

    if loaded of workspaceDoc is false then
        error "Workspace failed to load within timeout"
    end if

    -- Set scheme if specified
    {f'set active scheme of workspaceDoc to scheme "{escape_applescript_string(scheme)}" of workspaceDoc' if scheme else ''}

    -- Start the test
    set testResult to {test_command}

    -- Wait for completion (up to 10 minutes)
    {wait_section}
end tell
    '''

    success, output = run_applescript(script)

    if not success:
        show_error_notification("Failed to run tests", os.path.basename(project_path))
        return f"Failed to run tests: {output}"

    # Debug: Log raw output to see what we're getting
    if os.environ.get('XCODE_MCP_DEBUG'):
        print(f"DEBUG: Raw test output:\n{output}\n", file=sys.stderr)

    # Parse the AppleScript output to get test status
    lines = output.split('\n')
    status = ""
    completed = False

    for line in lines:
        if line.startswith("Status: "):
            status = line.replace("Status: ", "").strip()
        elif line.startswith("Completed: "):
            completed = line.replace("Completed: ", "").strip().lower() == "true"

    # Format the output
    output_lines = []

    if not completed:
        output_lines.append(f"⏳ Tests did not complete within 10 minutes")
        output_lines.append(f"Status: {status}")
        show_warning_notification(f"Tests timeout (10 min)")
        return '\n'.join(output_lines)

    # If tests completed, get detailed results from xcresult
    # Wait a moment for xcresult to be written
    time.sleep(2)
    xcresult_path = find_xcresult_bundle(project_path)

    if xcresult_path:
        print(f"DEBUG: Found xcresult bundle at {xcresult_path}", file=sys.stderr)

        # Extract and parse test results
        success, test_results = extract_test_results_from_xcresult(xcresult_path)

        if success:
            # Parse JSON to show notification
            try:
                result_data = json.loads(test_results)
                summary = result_data.get('summary', {})
                failed = summary.get('failed', 0)

                if failed == 0:
                    show_result_notification("All tests PASSED")
                else:
                    show_error_notification(f"{failed} test{'s' if failed != 1 else ''} FAILED")
            except:
                pass

            # Return the parsed JSON
            return test_results
        else:
            print(f"DEBUG: Failed to parse xcresult data: {test_results}", file=sys.stderr)

    # Fallback if we couldn't get xcresult data
    print(f"DEBUG: No xcresult bundle found for {project_path}", file=sys.stderr)

    if status == "succeeded":
        show_result_notification("All tests PASSED")
        return "✅ All tests passed"
    elif status == "failed":
        show_error_notification("Tests FAILED")
        return "❌ Tests failed\n\nNo detailed test results available - xcresult bundle not found"
    else:
        show_warning_notification(f"Tests: {status}")
        return f"Test run status: {status}"
