#!/usr/bin/env python3
"""build_project tool - Build an Xcode project"""

import os
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
    show_error_notification,
    show_warning_notification
)
from xcode_mcp_server.utils.xcresult import extract_build_errors_and_warnings


@mcp.tool()
@apply_config
def build_project(project_path: str,
                 scheme: Optional[str] = None,
                 include_warnings: Optional[bool] = None,
                 regex_filter: Optional[str] = None,
                 max_lines: int = 25) -> str:
    """
    Build the specified Xcode project or workspace.

    Builds will run for up to 10 minutes before timing out. This timeout is hardcoded
    to prevent issues with builds hanging indefinitely.

    Args:
        project_path: Path to an Xcode project or workspace directory.
        scheme: Name of the scheme to build. If not provided, uses the active scheme.
        include_warnings: Include warnings in build output. If not provided, uses global setting.
        regex_filter: Optional regex to filter error/warning lines
        max_lines: Maximum number of error/warning lines to show (default 25)

    Returns:
        On success, returns "Build succeeded with 0 errors."
        On failure, returns JSON with format:
        {
            "full_log_path": "/tmp/xcode-mcp-server/logs/build-{hash}.txt",
            "summary": {"total_errors": N, "total_warnings": M, "showing_errors": X, "showing_warnings": Y},
            "errors_and_warnings": "Build failed with N errors...\nerror: ...\n..."
        }
        Errors are prioritized over warnings - errors are shown first, then warnings fill remaining slots.
    """
    # Validate include_warnings parameter
    if include_warnings is not None and not isinstance(include_warnings, bool):
        raise InvalidParameterError("include_warnings must be a boolean value")

    # Validate and normalize path
    scheme_desc = scheme if scheme else "active scheme"
    normalized_path = validate_and_normalize_project_path(project_path, f"Building {scheme_desc} in")
    escaped_path = escape_applescript_string(normalized_path)

    # Show building notification
    project_name = os.path.basename(normalized_path)
    scheme_name = scheme if scheme else "active scheme"
    show_notification("Drew's Xcode MCP", subtitle=project_name, message=f"Building {scheme_name}")

    # Build the AppleScript
    if scheme:
        # Use provided scheme
        escaped_scheme = escape_applescript_string(scheme)
        script = f'''
set projectPath to "{escaped_path}"
set schemeName to "{escaped_scheme}"

tell application "Xcode"
        -- 1. Open the project file
        open projectPath

        -- 2. Get the workspace document
        set workspaceDoc to first workspace document whose path is projectPath

        -- 3. Wait for it to load (timeout after ~30 seconds)
        repeat 60 times
                if loaded of workspaceDoc is true then exit repeat
                delay 0.5
        end repeat

        if loaded of workspaceDoc is false then
                error "Xcode workspace did not load in time."
        end if

        -- 4. Set the active scheme
        set active scheme of workspaceDoc to (first scheme of workspaceDoc whose name is schemeName)

        -- 5. Build
        set actionResult to build workspaceDoc

        -- 6. Wait for completion (with 10 minute timeout)
        set buildWaitTime to 0
        repeat
                if completed of actionResult is true then exit repeat
                if buildWaitTime >= 600 then
                        error "Build timed out after 10 minutes"
                end if
                delay 0.5
                set buildWaitTime to buildWaitTime + 0.5
        end repeat

        -- 7. Check result
        set buildStatus to status of actionResult
        if buildStatus is succeeded then
                return "Build succeeded."
        else
                return build log of actionResult
        end if
end tell
    '''
    else:
        # Use active scheme
        script = f'''
set projectPath to "{escaped_path}"

tell application "Xcode"
        -- 1. Open the project file
        open projectPath

        -- 2. Get the workspace document
        set workspaceDoc to first workspace document whose path is projectPath

        -- 3. Wait for it to load (timeout after ~30 seconds)
        repeat 60 times
                if loaded of workspaceDoc is true then exit repeat
                delay 0.5
        end repeat

        if loaded of workspaceDoc is false then
                error "Xcode workspace did not load in time."
        end if

        -- 4. Build with current active scheme
        set actionResult to build workspaceDoc

        -- 5. Wait for completion (with 10 minute timeout)
        set buildWaitTime to 0
        repeat
                if completed of actionResult is true then exit repeat
                if buildWaitTime >= 600 then
                        error "Build timed out after 10 minutes"
                end if
                delay 0.5
                set buildWaitTime to buildWaitTime + 0.5
        end repeat

        -- 6. Check result
        set buildStatus to status of actionResult
        if buildStatus is succeeded then
                return "Build succeeded."
        else
                return build log of actionResult
        end if
end tell
    '''

    success, output = run_applescript(script)

    if success:
        if output == "Build succeeded.":
            show_result_notification(f"✅ Build succeeded", project_name)
            return "Build succeeded with 0 errors.\n\nUse `run_project` to launch the app, or `run_project_tests` to run tests."
        else:
            # Use the shared helper to extract and format errors/warnings (returns JSON)
            errors_output = extract_build_errors_and_warnings(output, include_warnings, regex_filter, max_lines)

            # Parse JSON to show appropriate notification
            import json
            try:
                result = json.loads(errors_output)
                summary = result.get("summary", {})
                total_errors = summary.get("total_errors", 0)
                total_warnings = summary.get("total_warnings", 0)

                if total_errors == 0 and total_warnings > 0:
                    # Warnings only - build succeeded
                    show_warning_notification(f"Build succeeded with {total_warnings} warning{'s' if total_warnings != 1 else ''}", project_name)
                elif total_errors > 0:
                    # Has errors - build failed
                    show_error_notification(f"Build failed with {total_errors} error{'s' if total_errors != 1 else ''}", project_name)
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                show_error_notification("Build failed", project_name)

            return errors_output
    else:
        show_error_notification("Build failed to start", project_name)
        raise XCodeMCPError(f"Build failed to start for scheme {scheme} in project {project_path}: {output}")
