#!/usr/bin/env python3
"""xcresult and build log utilities"""

import os
import sys
import subprocess
import json
import re
import time
import datetime
from typing import Optional, Tuple

from xcode_mcp_server.exceptions import InvalidParameterError

# Global build warning settings - initialized by CLI
BUILD_WARNINGS_ENABLED = True
BUILD_WARNINGS_FORCED = None  # True if forced on, False if forced off, None if not forced


def set_build_warnings_enabled(enabled: bool, forced: bool = False):
    """Set the global build warnings setting"""
    global BUILD_WARNINGS_ENABLED, BUILD_WARNINGS_FORCED
    BUILD_WARNINGS_ENABLED = enabled
    BUILD_WARNINGS_FORCED = enabled if forced else None


def extract_console_logs_from_xcresult(xcresult_path: str,
                                      regex_filter: Optional[str] = None,
                                      max_lines: int = 20) -> Tuple[bool, str]:
    """
    Extract console logs from xcresult bundle and return structured JSON.

    Args:
        xcresult_path: Path to the .xcresult file
        regex_filter: Optional regex pattern to find matching lines
        max_lines: Maximum matching lines to return (default 20)

    Returns:
        Tuple of (success, json_output_or_error_message)
    """
    # The xcresult file may still be finalizing, so retry a few times
    max_retries = 7
    retry_delay = 1

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                print(f"Retry attempt {attempt + 1}/{max_retries} after {retry_delay}s delay...", file=sys.stderr)
                time.sleep(retry_delay)

            result = subprocess.run(
                ['xcrun', 'xcresulttool', 'get', 'log',
                 '--path', xcresult_path,
                 '--type', 'console'],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                if "root ID is missing" in result.stderr and attempt < max_retries - 1:
                    print(f"xcresult not ready yet: {result.stderr.strip()}", file=sys.stderr)
                    continue
                return False, f"Failed to extract console logs: {result.stderr}"

            # Success - break out of retry loop
            break

        except subprocess.TimeoutExpired:
            if attempt < max_retries - 1:
                continue
            return False, "Timeout extracting console logs"
        except Exception as e:
            if attempt < max_retries - 1:
                continue
            return False, f"Error extracting console logs: {e}"

    # Parse the JSON output
    try:
        log_data = json.loads(result.stdout)

        # Extract ALL log entries (no filtering at this stage)
        all_logs = []
        for idx, item in enumerate(log_data.get('items', []), start=1):
            content = item.get('content', '').strip()
            if not content:
                continue

            # Extract structured fields
            log_entry = {
                'line': idx,
                'kind': item.get('kind', 'unknown'),
                'content': content
            }

            # Add optional fields if present
            log_data_obj = item.get('logData', {})
            if log_data_obj:
                if 'subsystem' in log_data_obj and log_data_obj['subsystem']:
                    log_entry['subsystem'] = log_data_obj['subsystem']
                if 'category' in log_data_obj and log_data_obj['category']:
                    log_entry['category'] = log_data_obj['category']

            all_logs.append(log_entry)

        if not all_logs:
            return True, json.dumps({"summary": {"total_lines": 0}, "full_log_path": None})

        # Format the output using helper function
        output = _format_structured_logs(all_logs, xcresult_path, regex_filter, max_lines)
        return True, output

    except json.JSONDecodeError as e:
        return False, f"Failed to parse console logs: {e}"
    except InvalidParameterError:
        raise
    except Exception as e:
        return False, f"Error processing console logs: {e}"


def _format_structured_logs(all_logs: list, xcresult_path: str,
                           regex_filter: Optional[str], max_lines: int) -> str:
    """
    Format structured logs into JSON with priority-based selection and write full unfiltered log file.

    Strategy:
    - Write ALL logs to unfiltered plaintext file
    - First 2 errors/faults (3 lines before, 2 after each) - from unfiltered logs
    - Last 3 errors/faults (5 lines before, 4 after each) - from unfiltered logs
    - First 2 warnings (2 lines before, 1 after each) - from unfiltered logs
    - Last 10 info/debug lines - from unfiltered logs
    - If regex_filter: Up to max_lines matching lines

    Args:
        all_logs: Complete list of all log entries (unfiltered)
        xcresult_path: Path to xcresult bundle (used for temp file naming)
        regex_filter: Optional regex to find matching lines
        max_lines: Maximum matching lines to include in response

    Returns:
        JSON string with formatted output including full_log_path
    """
    import hashlib

    # Categorize logs by severity
    errors_and_faults = []
    warnings = []
    others = []

    for log in all_logs:
        kind = log.get('kind', 'unknown')
        if kind in ['error', 'fault', 'osLogDefaultErrorFault']:
            errors_and_faults.append(log)
        elif kind in ['warning']:
            warnings.append(log)
        else:
            others.append(log)

    # Write complete UNFILTERED plaintext log to temp file
    log_dir = "/tmp/xcode-mcp-server/logs"
    os.makedirs(log_dir, exist_ok=True)

    xcresult_hash = hashlib.md5(xcresult_path.encode()).hexdigest()[:8]
    temp_log_path = os.path.join(log_dir, f"runtime-{xcresult_hash}.txt")

    try:
        with open(temp_log_path, 'w') as f:
            for log in all_logs:
                f.write(f"{log['content']}\n")
    except Exception as e:
        print(f"Warning: Failed to write full log to {temp_log_path}: {e}", file=sys.stderr)
        temp_log_path = None

    # Build summary
    summary = {
        "total_lines": len(all_logs),
        "errors_and_faults": len(errors_and_faults),
        "warnings": len(warnings),
        "info_debug": len(others)
    }

    # Find matching lines if regex_filter is provided
    matching_lines = []
    total_matching = 0
    if regex_filter and regex_filter.strip():
        try:
            for log in all_logs:
                if re.search(regex_filter, log['content']):
                    total_matching += 1
                    if len(matching_lines) < max_lines:
                        matching_lines.append({
                            'line': log['line'],
                            'content': log['content'],
                            'kind': log['kind'],
                            'subsystem': log.get('subsystem'),
                            'category': log.get('category')
                        })
            summary['matching_lines'] = total_matching
        except re.error as e:
            raise InvalidParameterError(f"Invalid regex pattern: {e}")

    # Helper function to get context lines from ALL logs (unfiltered)
    def get_context(log_list, target_log, lines_before, lines_after):
        """Get context lines around a target log entry."""
        target_line = target_log['line']
        context_before = []
        context_after = []

        for log in log_list:
            line_num = log['line']
            if target_line - lines_before <= line_num < target_line:
                context_before.append({
                    'line': line_num,
                    'content': log['content']
                })
            elif target_line < line_num <= target_line + lines_after:
                context_after.append({
                    'line': line_num,
                    'content': log['content']
                })

        return context_before, context_after

    # Select errors/faults with context (from ALL unfiltered logs)
    selected_errors = []
    if errors_and_faults:
        # First 2 errors (3 before, 2 after)
        for err in errors_and_faults[:2]:
            before, after = get_context(all_logs, err, 3, 2)
            selected_errors.append({
                'line': err['line'],
                'content': err['content'],
                'kind': err['kind'],
                'subsystem': err.get('subsystem'),
                'category': err.get('category'),
                'context_before': before,
                'context_after': after
            })

        # Last 3 errors (5 before, 4 after) - avoid duplicates if < 8 total
        if len(errors_and_faults) > 5:
            for err in errors_and_faults[-3:]:
                before, after = get_context(all_logs, err, 5, 4)
                selected_errors.append({
                    'line': err['line'],
                    'content': err['content'],
                    'kind': err['kind'],
                    'subsystem': err.get('subsystem'),
                    'category': err.get('category'),
                    'context_before': before,
                    'context_after': after
                })
        elif len(errors_and_faults) > 2:
            # If 3-5 total, just add the remaining ones with context
            for err in errors_and_faults[2:]:
                before, after = get_context(all_logs, err, 5, 4)
                selected_errors.append({
                    'line': err['line'],
                    'content': err['content'],
                    'kind': err['kind'],
                    'subsystem': err.get('subsystem'),
                    'category': err.get('category'),
                    'context_before': before,
                    'context_after': after
                })

    # Select warnings with context (from ALL unfiltered logs)
    selected_warnings = []
    for warn in warnings[:2]:
        before, after = get_context(all_logs, warn, 2, 1)
        selected_warnings.append({
            'line': warn['line'],
            'content': warn['content'],
            'kind': warn['kind'],
            'subsystem': warn.get('subsystem'),
            'category': warn.get('category'),
            'context_before': before,
            'context_after': after
        })

    # Get last 10 info/debug lines (from ALL unfiltered logs)
    trailing_info = []
    for log in others[-10:]:
        trailing_info.append({
            'line': log['line'],
            'content': log['content'],
            'kind': log.get('kind', 'unknown')
        })

    # Build output
    output = {
        "full_log_path": temp_log_path,
        "summary": summary
    }

    if selected_errors:
        output["errors_and_faults"] = selected_errors
        if len(errors_and_faults) > len(selected_errors):
            output["errors_note"] = f"Showing {len(selected_errors)} of {len(errors_and_faults)} errors/faults (first 2 and last 3). Use Read tool with full_log_path for complete log."

    if selected_warnings:
        output["warnings"] = selected_warnings
        if len(warnings) > len(selected_warnings):
            output["warnings_note"] = f"Showing {len(selected_warnings)} of {len(warnings)} warnings (first 2). Use Read tool with full_log_path for complete log."

    if matching_lines:
        output["matching_lines"] = matching_lines
        if len(matching_lines) < summary.get('matching_lines', 0):
            output["matching_note"] = f"Showing first {len(matching_lines)} of {summary['matching_lines']} matching lines. Use Read tool with full_log_path and grep for more."

    if trailing_info:
        output["trailing_info"] = trailing_info

    return json.dumps(output, indent=2)


def extract_build_errors_and_warnings(build_log: str,
                                     include_warnings: Optional[bool] = None,
                                     regex_filter: Optional[str] = None,
                                     max_lines: int = 25) -> str:
    """
    Extract and format errors and warnings from a build log using regex pattern matching.

    Uses word-boundary regex patterns (\\berror\\s*: and \\bwarning\\s*:) to match compiler
    errors and warnings while avoiding false positives from phrases like "error-free" or
    "no errors detected".

    Writes the complete unfiltered build log to /tmp/xcode-mcp-server/logs/build-{hash}.txt
    for full analysis.

    Prioritizes errors over warnings: shows up to max_lines total with errors first, then
    warnings to fill remaining slots. Optional regex_filter can further filter the error/warning
    lines before limiting.

    Args:
        build_log: The raw build log output from Xcode
        include_warnings: Include warnings in output. If not provided, uses global setting.
                         Note: Command-line flags override this parameter if set.
        regex_filter: Optional regex to further filter error/warning lines
        max_lines: Maximum number of error/warning lines to include (default 25)

    Returns:
        JSON string with format:
        {
            "full_log_path": "/tmp/xcode-mcp-server/logs/build-{hash}.txt",
            "summary": {
                "total_errors": N,
                "total_warnings": M,
                "showing_errors": X,
                "showing_warnings": Y
            },
            "errors_and_warnings": "Build failed with N errors...\nerror: ...\n..."
        }
    """
    import hashlib

    # Determine whether to include warnings
    # Command-line flags override function parameter (user control > LLM control)
    if BUILD_WARNINGS_FORCED is not None:
        # User explicitly set a command-line flag to force behavior
        show_warnings = BUILD_WARNINGS_FORCED
    else:
        # No forcing, use function parameter or default
        show_warnings = include_warnings if include_warnings is not None else BUILD_WARNINGS_ENABLED

    # Write complete UNFILTERED build log to temp file
    log_dir = "/tmp/xcode-mcp-server/logs"
    os.makedirs(log_dir, exist_ok=True)

    build_hash = hashlib.md5(build_log.encode()).hexdigest()[:8]
    temp_log_path = os.path.join(log_dir, f"build-{build_hash}.txt")

    try:
        with open(temp_log_path, 'w') as f:
            f.write(build_log)
    except Exception as e:
        print(f"Warning: Failed to write full log to {temp_log_path}: {e}", file=sys.stderr)
        temp_log_path = None

    output_lines = build_log.split("\n")
    error_lines = []
    warning_lines = []

    # Pattern for compiler errors/warnings: matches "error:" or "warning:" at word boundaries
    # This avoids false positives from phrases like "error-free" or "no errors"
    error_pattern = re.compile(r'\berror\s*:', re.IGNORECASE)
    warning_pattern = re.compile(r'\bwarning\s*:', re.IGNORECASE)

    # Single iteration through output lines to extract errors/warnings
    for line in output_lines:
        if error_pattern.search(line):
            error_lines.append(line)
        elif show_warnings and warning_pattern.search(line):
            warning_lines.append(line)

    # Store total counts before filtering
    total_errors = len(error_lines)
    total_warnings = len(warning_lines)

    # Apply regex filter if provided
    if regex_filter and regex_filter.strip():
        try:
            filter_pattern = re.compile(regex_filter)
            error_lines = [line for line in error_lines if filter_pattern.search(line)]
            warning_lines = [line for line in warning_lines if filter_pattern.search(line)]
        except re.error as e:
            raise InvalidParameterError(f"Invalid regex pattern: {e}")

    # Combine errors first, then warnings
    important_lines = error_lines + warning_lines

    # Calculate what we're actually showing
    displayed_errors = min(len(error_lines), max_lines)
    displayed_warnings = 0 if len(error_lines) >= max_lines else min(len(warning_lines), max_lines - len(error_lines))

    # Limit to max_lines
    if len(important_lines) > max_lines:
        important_lines = important_lines[:max_lines]

    important_list = "\n".join(important_lines)

    # Build appropriate message based on what we found
    if error_lines and warning_lines:
        # Build detailed count message
        count_msg = f"Build failed with {total_errors} error{'s' if total_errors != 1 else ''} and {total_warnings} warning{'s' if total_warnings != 1 else ''}."
        if total_errors + total_warnings > max_lines:
            if displayed_warnings == 0:
                # Showing only errors, warnings excluded
                count_msg += f" Showing first {displayed_errors} of {total_errors} errors."
            else:
                # Showing errors and warnings, but some may be truncated
                error_part = f"all {displayed_errors} error{'s' if displayed_errors != 1 else ''}" if displayed_errors == len(error_lines) else f"first {displayed_errors} of {len(error_lines)} errors"
                warning_part = f"first {displayed_warnings} of {len(warning_lines)} warnings"
                count_msg += f" Showing {error_part} and {warning_part}."
        output_text = f"{count_msg}\n{important_list}"
    elif error_lines:
        count_msg = f"Build failed with {total_errors} error{'s' if total_errors != 1 else ''}."
        if len(error_lines) > max_lines:
            count_msg += f" Showing first {max_lines} of {total_errors} errors."
        output_text = f"{count_msg}\n{important_list}"
    elif warning_lines:
        count_msg = f"Build completed with {total_warnings} warning{'s' if total_warnings != 1 else ''}."
        if len(warning_lines) > max_lines:
            count_msg += f" Showing first {max_lines} of {total_warnings} warnings."
        output_text = f"{count_msg}\n{important_list}"
    else:
        output_text = "Build failed (no specific errors or warnings found in output)"

    # Build JSON output
    result = {
        "full_log_path": temp_log_path,
        "summary": {
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "showing_errors": displayed_errors,
            "showing_warnings": displayed_warnings
        },
        "errors_and_warnings": output_text
    }

    return json.dumps(result, indent=2)


def find_xcresult_for_project(project_path: str) -> Optional[str]:
    """
    Find the most recent xcresult file for a given project.

    Args:
        project_path: Path to the .xcodeproj or .xcworkspace

    Returns:
        Path to the most recent xcresult file, or None if not found
    """
    # Normalize and get project name
    normalized_path = os.path.realpath(project_path)
    project_name = os.path.basename(normalized_path).replace('.xcworkspace', '').replace('.xcodeproj', '')

    # Find the most recent xcresult file in DerivedData
    derived_data_base = os.path.expanduser("~/Library/Developer/Xcode/DerivedData")

    # Look for directories matching the project name
    # DerivedData directories typically have format: ProjectName-randomhash
    try:
        for derived_dir in os.listdir(derived_data_base):
            # More precise matching: must start with project name followed by a dash
            if derived_dir.startswith(project_name + "-"):
                logs_dir = os.path.join(derived_data_base, derived_dir, "Logs", "Launch")
                if os.path.exists(logs_dir):
                    # Find the most recent .xcresult file
                    xcresult_files = []
                    for f in os.listdir(logs_dir):
                        if f.endswith('.xcresult'):
                            full_path = os.path.join(logs_dir, f)
                            xcresult_files.append((os.path.getmtime(full_path), full_path))

                    if xcresult_files:
                        xcresult_files.sort(reverse=True)
                        return xcresult_files[0][1]
    except Exception as e:
        print(f"Error searching for xcresult: {e}", file=sys.stderr)

    return None


def wait_for_xcresult_after_timestamp(project_path: str, start_timestamp: float, timeout_seconds: int) -> Optional[str]:
    """
    Wait for an xcresult file that was created AND modified at or after the given timestamp.

    This ensures we don't accidentally get results from a previous run by only
    accepting xcresult files where BOTH the creation time and modification time
    are at or after our operation started.

    Args:
        project_path: Path to the .xcodeproj or .xcworkspace
        start_timestamp: Unix timestamp (from time.time()) when the operation started
        timeout_seconds: Maximum seconds to wait for a valid xcresult file

    Returns:
        Path to the xcresult file if found, or None if timeout expires or no valid file found
    """
    start_datetime = datetime.datetime.fromtimestamp(start_timestamp)
    print(f"Waiting for xcresult modified at or after: {start_datetime.strftime('%Y-%m-%d %H:%M:%S.%f')}", file=sys.stderr)

    end_time = time.time() + timeout_seconds

    while time.time() < end_time:
        # Try to find an xcresult file
        xcresult_path = find_xcresult_for_project(project_path)

        if xcresult_path and os.path.exists(xcresult_path):
            mod_time = os.path.getmtime(xcresult_path)
            create_time = os.path.getctime(xcresult_path)

            mod_datetime = datetime.datetime.fromtimestamp(mod_time)
            create_datetime = datetime.datetime.fromtimestamp(create_time)

            print(f"Found xcresult - created: {create_datetime.strftime('%Y-%m-%d %H:%M:%S.%f')}, modified: {mod_datetime.strftime('%Y-%m-%d %H:%M:%S.%f')} ({xcresult_path})", file=sys.stderr)

            # Check if BOTH creation time AND modification time are at or after our start time
            if create_time >= start_timestamp and mod_time >= start_timestamp:
                print(f"xcresult creation and modification times are both newer than start time - accepting it", file=sys.stderr)
                return xcresult_path
            else:
                if create_time < start_timestamp:
                    time_diff = start_timestamp - create_time
                    print(f"xcresult creation time is {time_diff:.2f} seconds older than start time - waiting for newer file...", file=sys.stderr)
                if mod_time < start_timestamp:
                    time_diff = start_timestamp - mod_time
                    print(f"xcresult modification time is {time_diff:.2f} seconds older than start time - waiting for newer file...", file=sys.stderr)
        else:
            print(f"No xcresult file found yet - waiting...", file=sys.stderr)

        # Wait a bit before checking again
        time.sleep(1)

    return None


def format_test_identifier(bundle: str, class_name: str = None, method: str = None) -> str:
    """
    Format test identifier in standard format.
    Returns: "Bundle/Class/method" or "Bundle/Class" or "Bundle"
    """
    if method and class_name:
        return f"{bundle}/{class_name}/{method}"
    elif class_name:
        return f"{bundle}/{class_name}"
    else:
        return bundle


def find_xcresult_bundle(project_path: str, wait_seconds: int = 10) -> Optional[str]:
    """
    Find the most recent .xcresult bundle for the project.

    Args:
        project_path: Path to the Xcode project
        wait_seconds: Maximum seconds to wait for xcresult to appear (not currently used,
                      but kept for API compatibility)

    Returns:
        Path to the most recent xcresult bundle or None if not found
    """
    # Normalize and get project name
    normalized_path = os.path.realpath(project_path)
    project_name = os.path.basename(normalized_path).replace('.xcworkspace', '').replace('.xcodeproj', '')

    # Find the most recent xcresult file in DerivedData
    derived_data_base = os.path.expanduser("~/Library/Developer/Xcode/DerivedData")

    # Look for directories matching the project name
    # DerivedData directories typically have format: ProjectName-randomhash
    try:
        for derived_dir in os.listdir(derived_data_base):
            # More precise matching: must start with project name followed by a dash
            if derived_dir.startswith(project_name + "-"):
                logs_dir = os.path.join(derived_data_base, derived_dir, "Logs", "Test")
                if os.path.exists(logs_dir):
                    # Find the most recent .xcresult file
                    xcresult_files = []
                    for f in os.listdir(logs_dir):
                        if f.endswith('.xcresult'):
                            full_path = os.path.join(logs_dir, f)
                            xcresult_files.append((os.path.getmtime(full_path), full_path))

                    if xcresult_files:
                        xcresult_files.sort(reverse=True)
                        most_recent = xcresult_files[0][1]
                        print(f"DEBUG: Found xcresult bundle at {most_recent}", file=sys.stderr)
                        return most_recent
    except Exception as e:
        print(f"Error searching for xcresult: {e}", file=sys.stderr)

    return None


def extract_test_results_from_xcresult(xcresult_path: str) -> Tuple[bool, str]:
    """
    Extract and parse test results from xcresult bundle.

    Args:
        xcresult_path: Path to the .xcresult bundle

    Returns:
        Tuple of (success, json_output_or_error_message)
        JSON format:
        {
            "xcresult_path": "...",
            "summary": {
                "total_tests": N,
                "passed": M,
                "failed": K,
                "skipped": L
            },
            "failed_tests": [
                {
                    "test_name": "Bundle/Class/method",
                    "duration": "0.5s",
                    "failure_message": "...",
                    "file": "...",
                    "line": 42
                }
            ]
        }
    """
    try:
        # Extract test results from xcresult bundle
        result = subprocess.run(
            ['xcrun', 'xcresulttool', 'get', 'test-results', 'tests', '--path', xcresult_path],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return False, f"Failed to extract test results: {result.stderr}"

        # Parse the JSON
        test_data = json.loads(result.stdout)

    except subprocess.TimeoutExpired:
        return False, "Timeout extracting test results"
    except json.JSONDecodeError as e:
        return False, f"Failed to parse test results JSON: {e}"
    except Exception as e:
        return False, f"Error extracting test results: {e}"

    # Recursively walk the test tree to find all test cases
    def walk_test_nodes(node, parent_path=""):
        """Recursively walk test nodes and collect test case results."""
        test_cases = []

        node_type = node.get('nodeType', '')
        node_name = node.get('name', '')

        # Build the path for this node
        if node_type in ['Unit test bundle', 'Test Suite']:
            current_path = f"{parent_path}/{node_name}" if parent_path else node_name
        else:
            current_path = parent_path

        # If this is a test case, record it
        if node_type == 'Test Case':
            test_info = {
                'name': f"{current_path}/{node_name}",
                'result': node.get('result', 'Unknown'),
                'duration': node.get('duration', '0s')
            }

            # Extract failure details if test failed
            if test_info['result'] in ['Failed', 'Failure']:
                failures = []

                # Get failure messages from the node
                if 'failureMessages' in node:
                    for failure in node['failureMessages']:
                        failure_info = {
                            'message': failure.get('message', 'Unknown failure')
                        }

                        # Extract file location if available
                        if 'location' in failure:
                            location = failure['location']
                            if 'file' in location:
                                failure_info['file'] = location['file']
                            if 'line' in location:
                                failure_info['line'] = location['line']

                        failures.append(failure_info)

                test_info['failures'] = failures

            test_cases.append(test_info)

        # Recursively process children
        if 'children' in node:
            for child in node['children']:
                test_cases.extend(walk_test_nodes(child, current_path))

        return test_cases

    # Walk the test tree starting from testNodes
    all_tests = []
    for test_node in test_data.get('testNodes', []):
        all_tests.extend(walk_test_nodes(test_node))

    # Categorize tests
    passed_tests = [t for t in all_tests if t['result'] in ['Passed', 'Success']]
    failed_tests = [t for t in all_tests if t['result'] in ['Failed', 'Failure']]
    skipped_tests = [t for t in all_tests if t['result'] in ['Skipped']]

    # Build summary
    summary = {
        'total_tests': len(all_tests),
        'passed': len(passed_tests),
        'failed': len(failed_tests),
        'skipped': len(skipped_tests)
    }

    # Format failed tests for output
    failed_test_details = []
    for test in failed_tests:
        test_detail = {
            'test_name': test['name'],
            'duration': test['duration']
        }

        # Add failure details
        if 'failures' in test and test['failures']:
            # Combine all failure messages
            messages = []
            for failure in test['failures']:
                messages.append(failure['message'])

                # Add file/line info if available
                if 'file' in failure:
                    test_detail['file'] = failure['file']
                if 'line' in failure:
                    test_detail['line'] = failure['line']

            test_detail['failure_message'] = '\n'.join(messages)
        else:
            test_detail['failure_message'] = 'Test failed (no failure message available)'

        failed_test_details.append(test_detail)

    # Build output JSON
    output = {
        'xcresult_path': xcresult_path,
        'summary': summary
    }

    if failed_test_details:
        output['failed_tests'] = failed_test_details

    return True, json.dumps(output, indent=2)
