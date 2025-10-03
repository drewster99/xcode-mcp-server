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
    show_error_notification
)
from xcode_mcp_server.utils.xcresult import extract_build_errors_and_warnings


@mcp.tool()
@apply_config
def build_project(project_path: str,
                 scheme: Optional[str] = None,
                 include_warnings: Optional[bool] = None) -> str:
    """
    Build the specified Xcode project or workspace.

    Args:
        project_path: Path to an Xcode project or workspace directory.
        scheme: Name of the scheme to build. If not provided, uses the active scheme.
        include_warnings: Include warnings in build output. If not provided, uses global setting.

    Returns:
        On success, returns "Build succeeded with 0 errors."
        On failure, returns the first (up to) 25 error/warning lines from the build log.
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
    show_notification("Xcode MCP", f"Building {project_name}", subtitle=scheme_name)

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

        -- 6. Wait for completion
        repeat
                if completed of actionResult is true then exit repeat
                delay 0.5
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

        -- 5. Wait for completion
        repeat
                if completed of actionResult is true then exit repeat
                delay 0.5
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
            show_result_notification(f"Build succeeded", project_name)
            return "Build succeeded with 0 errors.\n\nUse `run_project` to launch the app, or `run_project_tests` to run tests."
        else:
            # Use the shared helper to extract and format errors/warnings
            errors_output = extract_build_errors_and_warnings(output, include_warnings)
            # Count errors for notification
            error_count = errors_output.count("error:")
            show_error_notification(f"Build failed", f"{error_count} error{'s' if error_count != 1 else ''}")
            return errors_output
    else:
        show_error_notification("Build failed to start")
        raise XCodeMCPError(f"Build failed to start for scheme {scheme} in project {project_path}: {output}")
