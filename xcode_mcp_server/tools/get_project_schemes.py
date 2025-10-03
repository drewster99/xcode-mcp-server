#!/usr/bin/env python3
"""get_project_schemes tool - Get available build schemes"""

from xcode_mcp_server.server import mcp
from xcode_mcp_server.security import validate_and_normalize_project_path
from xcode_mcp_server.exceptions import XCodeMCPError
from xcode_mcp_server.utils.applescript import escape_applescript_string, run_applescript


@mcp.tool()
def get_project_schemes(project_path: str) -> str:
    """
    Get the available build schemes for the specified Xcode project or workspace.

    Args:
        project_path: Path to an Xcode project/workspace directory, which must
        end in '.xcodeproj' or '.xcworkspace' and must exist.

    Returns:
        A newline-separated list of scheme names, with the active scheme listed first.
        If no schemes are found, returns an empty string.
    """
    # Validate and normalize path
    normalized_path = validate_and_normalize_project_path(project_path, "Getting schemes for")
    escaped_path = escape_applescript_string(normalized_path)

    script = f'''
    tell application "Xcode"
        open "{escaped_path}"

        set workspaceDoc to first workspace document whose path is "{escaped_path}"

        -- Wait for it to load
        repeat 60 times
            if loaded of workspaceDoc is true then exit repeat
            delay 0.5
        end repeat

        if loaded of workspaceDoc is false then
            error "Xcode workspace did not load in time."
        end if

        -- Try to get active scheme name, but don't fail if we can't
        set activeScheme to ""
        try
            set activeScheme to name of active scheme of workspaceDoc
        on error
            -- If we can't get active scheme (e.g., Xcode is busy), continue without it
        end try

        -- Get all scheme names
        set schemeNames to {{}}
        repeat with aScheme in schemes of workspaceDoc
            set end of schemeNames to name of aScheme
        end repeat

        -- Format output
        set output to ""
        if activeScheme is not "" then
            -- If we have an active scheme, list it first with annotation
            set output to activeScheme & " (active)"
            repeat with schemeName in schemeNames
                if schemeName as string is not equal to activeScheme then
                    set output to output & "\\n" & schemeName
                end if
            end repeat
        else
            -- If no active scheme available, just list all schemes
            set AppleScript's text item delimiters to "\\n"
            set output to schemeNames as string
            set AppleScript's text item delimiters to ""
        end if

        return output
    end tell
    '''

    success, output = run_applescript(script)

    if success:
        if output:
            output += "\n\nUse `build_project` with a scheme name, or omit the scheme parameter to build the active scheme."
        return output
    else:
        raise XCodeMCPError(f"Failed to get schemes for {project_path}: {output}")
