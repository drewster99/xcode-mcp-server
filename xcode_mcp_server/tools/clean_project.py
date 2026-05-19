#!/usr/bin/env python3
"""clean_project tool - Clean an Xcode project"""

import os

from xcode_mcp_server.server import mcp
from xcode_mcp_server.config_manager import apply_config
from xcode_mcp_server.security import validate_and_normalize_project_path
from xcode_mcp_server.exceptions import XCodeMCPError
from xcode_mcp_server.utils.applescript import (
    BUILD_TIMEOUT_SECONDS,
    build_open_and_wait_applescript,
    escape_applescript_string,
    run_applescript,
    show_result_notification,
    show_error_notification,
)


@mcp.tool()
@apply_config
def clean_project(project_path: str) -> str:
    """
    Clean the specified Xcode project or workspace.

    Args:
        project_path: Path to an Xcode project/workspace directory.

    Returns:
        Output message
    """
    # Validate and normalize path
    normalized_path = validate_and_normalize_project_path(project_path, "Cleaning")
    escaped_path = escape_applescript_string(normalized_path)

    script = build_open_and_wait_applescript(escaped_path) + (
        '    clean workspaceDoc\n'
        '    return "Clean completed successfully"\n'
        'end tell\n'
    )

    # Clean is synchronous in AppleScript and can take minutes on large projects;
    # use the same budget as build/test rather than the short default.
    success, output = run_applescript(script, timeout=BUILD_TIMEOUT_SECONDS + 60)

    project_name = os.path.basename(normalized_path)

    if success:
        show_result_notification("Clean completed", project_name)
        return output
    else:
        show_error_notification("Clean failed", project_name)
        raise XCodeMCPError(f"Clean failed: {output}")
