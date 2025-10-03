#!/usr/bin/env python3
"""run_project_tests tool - Run Xcode project tests"""

import os
import sys
import time
import subprocess
import json
from typing import Optional, List

from xcode_mcp_server.server import mcp
from xcode_mcp_server.security import validate_and_normalize_project_path
from xcode_mcp_server.exceptions import InvalidParameterError
from xcode_mcp_server.utils.applescript import (
    escape_applescript_string,
    run_applescript,
    show_notification,
    show_result_notification,
    show_error_notification
)
from xcode_mcp_server.utils.xcresult import find_xcresult_bundle


@mcp.tool()
def run_project_tests(project_path: str,
                     tests_to_run: Optional[List[str]] = None,
                     scheme: Optional[str] = None,
                     max_wait_seconds: int = 300) -> str:
    """
    Run tests for the specified Xcode project or workspace.

    Args:
        project_path: Path to Xcode project/workspace directory
        tests_to_run: Optional list of test identifiers to run.
                     If None or empty list, runs ALL tests.
                     Format: ["BundleName/ClassName/testMethod", ...]
        scheme: Optional scheme to test (uses active scheme if not specified)
        max_wait_seconds: Maximum seconds to wait for completion (default 300).
                         Set to 0 to start tests and return immediately.

    Returns:
        Test results if max_wait_seconds > 0, otherwise confirmation message
    """
    # Validate and normalize the project path
    project_path = validate_and_normalize_project_path(project_path, "run_project_tests")

    # Show starting notification for long-running operation
    show_notification("Xcode MCP", f"Running tests", subtitle=os.path.basename(project_path))

    # Validate wait time
    if max_wait_seconds < 0:
        raise InvalidParameterError("max_wait_seconds must be >= 0")

    # Handle various forms of empty/invalid tests_to_run parameter
    # This works around MCP client issues with optional list parameters
    if tests_to_run is not None:
        # Handle string inputs that might come from the client
        if isinstance(tests_to_run, str):
            tests_to_run = tests_to_run.strip()
            if not tests_to_run or tests_to_run in ['[]', 'null', 'undefined', '']:
                tests_to_run = None
            else:
                # Try to parse as a comma-separated list
                tests_to_run = [t.strip() for t in tests_to_run.split(',') if t.strip()]
        elif not tests_to_run:  # Empty list or other falsy value
            tests_to_run = None

    # Escape for AppleScript
    escaped_path = escape_applescript_string(project_path)

    # Build test arguments
    test_args = []
    if tests_to_run:  # If list is provided and not empty
        for test_id in tests_to_run:
            # Add -only-testing: prefix for each test
            test_args.append(f'-only-testing:{test_id}')
    # If tests_to_run is None or [], we run all tests (no arguments needed)

    # Build the AppleScript
    if test_args:
        # Format arguments for AppleScript list
        args_list = ', '.join([f'"{escape_applescript_string(arg)}"' for arg in test_args])
        test_command = f'test workspaceDoc with command line arguments {{{args_list}}}'
    else:
        # Run all tests
        test_command = 'test workspaceDoc'

    # Build the script differently based on max_wait_seconds
    if max_wait_seconds > 0:
        wait_section = f'''set waitTime to 0
    repeat while waitTime < {max_wait_seconds}
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
    else:
        wait_section = 'return "Tests started successfully"'

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

    {'-- Wait for completion' if max_wait_seconds > 0 else '-- Return immediately'}
    {wait_section}
end tell
    '''

    success, output = run_applescript(script)

    if not success:
        return f"Failed to run tests: {output}"

    if max_wait_seconds == 0:
        return "✅ Tests have been started. Use get_latest_test_results to check results later."

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
        output_lines.append(f"⏳ Tests did not complete within {max_wait_seconds} seconds")
        output_lines.append(f"Status: {status}")
        show_result_notification(f"Tests timeout ({max_wait_seconds}s)")
        return '\n'.join(output_lines)

    # If tests completed, get detailed results from xcresult
    # Wait a moment for xcresult to be written
    time.sleep(2)
    xcresult_path = find_xcresult_bundle(project_path)

    if xcresult_path:
        print(f"DEBUG: Found xcresult bundle at {xcresult_path}", file=sys.stderr)

        # Get the raw JSON from xcresulttool and return it
        try:
            result = subprocess.run(
                ['xcrun', 'xcresulttool', 'get', 'test-results', 'tests', '--path', xcresult_path],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                # Parse to show notification
                try:
                    test_data = json.loads(result.stdout)
                    # Count failures
                    failure_count = 0
                    if 'tests' in test_data and '_values' in test_data['tests']:
                        for test in test_data['tests']['_values']:
                            if test.get('testStatus', '') == 'Failure':
                                failure_count += 1

                    if failure_count == 0:
                        show_result_notification("All tests PASSED")
                    else:
                        show_error_notification(f"{failure_count} test{'s' if failure_count != 1 else ''} FAILED")
                except:
                    pass

                # Return the raw JSON - let the LLM parse it
                return result.stdout
            else:
                print(f"DEBUG: Failed to get xcresult data: {result.stderr}", file=sys.stderr)
        except Exception as e:
            print(f"DEBUG: Exception getting xcresult data: {e}", file=sys.stderr)

    # Fallback if we couldn't get xcresult data
    print(f"DEBUG: No xcresult bundle found for {project_path}", file=sys.stderr)

    if status == "succeeded":
        show_result_notification("All tests PASSED")
        return "✅ All tests passed"
    elif status == "failed":
        show_error_notification("Tests FAILED")
        return "❌ Tests failed\n\nNo detailed test results available - xcresult bundle not found"
    else:
        show_result_notification(f"Tests: {status}")
        return f"Test run status: {status}"
