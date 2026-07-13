#!/usr/bin/env python3
"""run_project_unmonitored tool - Launch app and return immediately"""

import os
from typing import Optional

from drews_xcode_mcp.server import mcp, TOOL_BUILD
from drews_xcode_mcp.config_manager import apply_config
from drews_xcode_mcp.security import validate_and_normalize_project_path
from drews_xcode_mcp.exceptions import XCodeMCPError
from drews_xcode_mcp.utils.applescript import (
    build_open_and_wait_applescript,
    escape_applescript_string,
    run_applescript,
    show_notification,
    show_error_notification,
)


@mcp.tool(annotations=TOOL_BUILD)
@apply_config
def run_project_unmonitored(project_path: str,
                             scheme: Optional[str] = None) -> str:
    """
    Launch the app in Xcode and return immediately without waiting.

    The app will continue running until you stop it manually in Xcode.
    No monitoring, no automatic termination, no log extraction.

    Use get_runtime_output later (after manual termination) to retrieve logs.

    Perfect for: Long-running apps, servers, apps needing extended manual testing

    Note: unlike the monitored run/test tools this is deliberately NOT wrapped
    in @exclusive_per_project. It is fire-and-forget — it returns as soon as the
    launch is dispatched while the app keeps running — so the guard would
    release its per-project key immediately and provide no real protection
    (it would only block two launches dispatched in the same instant, not a
    launch that collides with an already-running app). It also does no
    .xcresult snapshotting, so it has none of the result-isolation the guard
    exists to protect. Callers are responsible for not launching the same
    project repeatedly without stopping it.

    Args:
        project_path: Path to an Xcode project/workspace directory
        scheme: Optional scheme to run. If not provided, uses the active scheme.

    Returns:
        Success message indicating the app has been launched
    """
    # Validate and normalize path
    scheme_desc = scheme if scheme else "active scheme"
    normalized_path = validate_and_normalize_project_path(project_path, f"Launching {scheme_desc} in")
    escaped_path = escape_applescript_string(normalized_path)

    # Show launching notification
    project_name = os.path.basename(normalized_path)
    scheme_name = scheme if scheme else "active scheme"
    show_notification("Drew's Xcode MCP", subtitle=scheme_name, message=f"Launching {project_name}")

    escaped_scheme = escape_applescript_string(scheme) if scheme else None
    script = (
        build_open_and_wait_applescript(escaped_path, escaped_scheme)
        + '    run workspaceDoc\n'
        + '    return "launched"\n'
        + 'end tell\n'
    )

    success, output = run_applescript(script)

    if not success:
        show_error_notification("Failed to launch app", project_name)
        raise XCodeMCPError(f"Launch failed: {output}")

    # Show success notification with sound to get attention
    show_notification(
        "Drew's Xcode MCP",
        subtitle=project_name,
        message="🚀 App launched (running until manually stopped)",
        sound=True
    )

    return f"App '{project_name}' launched successfully in Xcode.\n\nThe app is now running and will continue until you stop it manually in Xcode.\n\nUse get_runtime_output after termination to retrieve console logs."
