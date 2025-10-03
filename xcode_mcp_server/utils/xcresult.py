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
                                      max_lines: int = 100,
                                      regex_filter: Optional[str] = None) -> Tuple[bool, str]:
    """
    Extract console logs from an xcresult file.

    Args:
        xcresult_path: Path to the .xcresult file
        max_lines: Maximum number of lines to return
        regex_filter: Optional regex pattern to filter output lines

    Returns:
        Tuple of (success, output_or_error_message)
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

        # Extract console content from items
        console_lines = []
        for item in log_data.get('items', []):
            content = item.get('content', '').strip()
            if content:
                # Apply regex filter if provided and not empty
                if regex_filter and regex_filter.strip():
                    try:
                        if re.search(regex_filter, content):
                            console_lines.append(content)
                    except re.error as e:
                        raise InvalidParameterError(f"Invalid regex pattern: {e}")
                else:
                    console_lines.append(content)

        # Limit to max_lines (take the first N lines)
        if len(console_lines) > max_lines:
            console_lines = console_lines[:max_lines]

        if not console_lines:
            return True, ""  # No output is not an error

        return True, "\n".join(console_lines)

    except json.JSONDecodeError as e:
        return False, f"Failed to parse console logs: {e}"
    except Exception as e:
        return False, f"Error processing console logs: {e}"


def extract_build_errors_and_warnings(build_log: str,
                                     include_warnings: Optional[bool] = None) -> str:
    """
    Extract and format errors and warnings from a build log.

    Args:
        build_log: The raw build log output from Xcode
        include_warnings: Include warnings in output. If not provided, uses global setting.

    Returns:
        Formatted string with errors/warnings, limited to 25 lines
    """
    # Determine whether to include warnings
    # Command-line flags override function parameter (user control > LLM control)
    if BUILD_WARNINGS_FORCED is not None:
        # User explicitly set a command-line flag to force behavior
        show_warnings = BUILD_WARNINGS_FORCED
    else:
        # No forcing, use function parameter or default
        show_warnings = include_warnings if include_warnings is not None else BUILD_WARNINGS_ENABLED

    output_lines = build_log.split("\n")
    error_lines = []
    warning_lines = []

    # Single iteration through output lines
    for line in output_lines:
        line_lower = line.lower()
        if "error" in line_lower:
            error_lines.append(line)
        elif show_warnings and "warning" in line_lower:
            warning_lines.append(line)

    # Store total counts
    total_errors = len(error_lines)
    total_warnings = len(warning_lines)

    # Combine errors first, then warnings
    important_lines = error_lines + warning_lines

    # Calculate what we're actually showing
    displayed_errors = min(total_errors, 25)
    displayed_warnings = 0 if total_errors >= 25 else min(total_warnings, 25 - total_errors)

    # Limit to first 25 important lines
    if len(important_lines) > 25:
        important_lines = important_lines[:25]

    important_list = "\n".join(important_lines)

    # Build appropriate message based on what we found
    if error_lines and warning_lines:
        # Build detailed count message
        count_msg = f"Build failed with {total_errors} error(s) and {total_warnings} warning(s)."
        if total_errors + total_warnings > 25:
            if displayed_warnings == 0:
                count_msg += f" Showing first {displayed_errors} errors."
            else:
                count_msg += f" Showing {displayed_errors} error(s) and first {displayed_warnings} warning(s)."
        return f"{count_msg}\n{important_list}"
    elif error_lines:
        count_msg = f"Build failed with {total_errors} error(s)."
        if total_errors > 25:
            count_msg += f" Showing first 25 errors."
        return f"{count_msg}\n{important_list}"
    elif warning_lines:
        count_msg = f"Build completed with {total_warnings} warning(s)."
        if total_warnings > 25:
            count_msg += f" Showing first 25 warnings."
        return f"{count_msg}\n{important_list}"
    else:
        return "Build failed (no specific errors or warnings found in output)"


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
