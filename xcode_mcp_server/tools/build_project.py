#!/usr/bin/env python3
"""build_project tool - Build an Xcode project"""

import json
import os
import re
import sys
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
from xcode_mcp_server.utils.build_log_parser import (
    find_derived_data_for_project,
    aggregate_warnings_since_clean
)


def _supplement_with_xcactivitylog_warnings(
    errors_json: str,
    project_path: str,
    include_warnings: Optional[bool],
    regex_filter: Optional[str],
    max_lines: int
) -> str:
    """
    Supplement build results with comprehensive warnings from xcactivitylog files.

    The AppleScript build log only contains warnings for files recompiled in the
    current build. xcactivitylog files contain warnings from all builds since the
    last clean, providing comprehensive coverage across incremental builds.

    xcactivitylog is the primary source. Any errors or warnings from the AppleScript
    build log not already present in xcactivitylog are preserved as supplements.
    """
    from xcode_mcp_server.utils.xcresult import BUILD_WARNINGS_FORCED, BUILD_WARNINGS_ENABLED

    if BUILD_WARNINGS_FORCED is not None:
        show_warnings = BUILD_WARNINGS_FORCED
    else:
        show_warnings = include_warnings if include_warnings is not None else BUILD_WARNINGS_ENABLED

    if not show_warnings:
        return errors_json

    try:
        derived_data_path = find_derived_data_for_project(project_path)
        if not derived_data_path:
            return errors_json

        logs_dir = os.path.join(derived_data_path, "Logs", "Build")
        manifest_path = os.path.join(logs_dir, "LogStoreManifest.plist")

        if not os.path.exists(manifest_path):
            return errors_json

        xcactivity_result = aggregate_warnings_since_clean(manifest_path, logs_dir)
        xcactivity_items = xcactivity_result.get('aggregated_warnings', [])

        if not xcactivity_items:
            return errors_json

        # Apply regex_filter to xcactivitylog items if provided
        if regex_filter and regex_filter.strip():
            filter_re = re.compile(regex_filter)
            xcactivity_items = [
                w for w in xcactivity_items
                if filter_re.search(
                    f"{w['file']}:{w['line']}:{w['column']}: {w['type']}: {w['message']}"
                )
            ]
            if not xcactivity_items:
                return errors_json

        result = json.loads(errors_json)
        existing_text = result.get('errors_and_warnings', '')
        build_failed = result.get('summary', {}).get('build_failed', False)

        # Parse error/warning lines from existing AppleScript result
        error_re = re.compile(
            r'(:\d+:\d+: error:)|(^error\s*:)|(:\s+error:)', re.IGNORECASE
        )
        warning_re = re.compile(
            r'(:\d+:\d+: warning:)|(^warning\s*:)|(:\s+warning:)', re.IGNORECASE
        )
        flc_re = re.compile(r'(.+?):(\d+):(\d+): (?:warning|error):')

        existing_lines = existing_text.split('\n')
        applescript_error_lines = [l for l in existing_lines if error_re.search(l)]
        applescript_warning_lines = [l for l in existing_lines if warning_re.search(l)]

        # Build dedup set from xcactivitylog entries
        xcact_keys = set()
        for w in xcactivity_items:
            xcact_keys.add((w['file'], w['line'], w['column']))

        # Separate xcactivitylog items into error and warning text lines
        xcact_error_lines = []
        xcact_warning_lines = []
        for w in xcactivity_items:
            line = f"{w['file']}:{w['line']}:{w['column']}: {w['type']}: {w['message']}"
            if w['type'] == 'error':
                xcact_error_lines.append(line)
            else:
                xcact_warning_lines.append(line)

        # Find AppleScript lines not already in xcactivitylog
        extra_errors = []
        for line in applescript_error_lines:
            m = flc_re.match(line)
            if m:
                key = (m.group(1), int(m.group(2)), int(m.group(3)))
                if key not in xcact_keys:
                    extra_errors.append(line)
            else:
                extra_errors.append(line)

        extra_warnings = []
        for line in applescript_warning_lines:
            m = flc_re.match(line)
            if m:
                key = (m.group(1), int(m.group(2)), int(m.group(3)))
                if key not in xcact_keys:
                    extra_warnings.append(line)
            else:
                extra_warnings.append(line)

        # Combine: errors first (xcactivitylog + extras), then warnings
        all_error_lines = xcact_error_lines + extra_errors
        all_warning_lines = xcact_warning_lines + extra_warnings
        total_errors = len(all_error_lines)
        total_warnings = len(all_warning_lines)

        # Apply max_lines with errors prioritized
        combined = all_error_lines + all_warning_lines
        displayed_errors = min(total_errors, max_lines)
        displayed_warnings = max(0, min(total_warnings, max_lines - displayed_errors))
        if len(combined) > max_lines:
            combined = combined[:max_lines]

        # Build count message
        if build_failed:
            if total_errors > 0 and total_warnings > 0:
                count_msg = (
                    f"Build failed with {total_errors} error{'s' if total_errors != 1 else ''}"
                    f" and {total_warnings} warning{'s' if total_warnings != 1 else ''}."
                )
            elif total_errors > 0:
                count_msg = f"Build failed with {total_errors} error{'s' if total_errors != 1 else ''}."
            elif total_warnings > 0:
                count_msg = (
                    f"Build failed with 0 recognized errors"
                    f" and {total_warnings} warning{'s' if total_warnings != 1 else ''}."
                    f" See full log for failure details."
                )
            else:
                return errors_json
        else:
            if total_warnings > 0 and total_errors > 0:
                count_msg = (
                    f"Build succeeded with {total_errors} error{'s' if total_errors != 1 else ''}"
                    f" and {total_warnings} warning{'s' if total_warnings != 1 else ''}."
                )
            elif total_warnings > 0:
                count_msg = f"Build succeeded with {total_warnings} warning{'s' if total_warnings != 1 else ''}."
            else:
                return errors_json

        if total_errors + total_warnings > max_lines:
            count_msg += f" Showing first {len(combined)} of {total_errors + total_warnings}."

        important_list = "\n".join(combined)
        output_text = f"{count_msg}\n{important_list}" if combined else count_msg

        result['summary']['total_errors'] = total_errors
        result['summary']['total_warnings'] = total_warnings
        result['summary']['showing_errors'] = displayed_errors
        result['summary']['showing_warnings'] = displayed_warnings
        result['errors_and_warnings'] = output_text

        return json.dumps(result)

    except Exception as e:
        print(f"Debug: xcactivitylog supplement failed: {e}", file=sys.stderr)
        return errors_json


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
        Always returns JSON with format:
        {
            "full_log_path": "/tmp/xcode-mcp-server/logs/build-{hash}.txt",
            "summary": {"total_errors": N, "total_warnings": M, "showing_errors": X, "showing_warnings": Y},
            "errors_and_warnings": "Build failed with N errors...\nerror: ...\n..."
        }
        The errors_and_warnings field contains a summary message followed by the actual errors/warnings.
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

        -- 7. Return status prefix + build log (always, to capture warnings even on success)
        set buildStatus to "unknown"
        try
                set buildStatus to status of actionResult as string
        end try
        return "BUILD_STATUS:" & buildStatus & "
" & build log of actionResult
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

        -- 6. Return status prefix + build log (always, to capture warnings even on success)
        set buildStatus to "unknown"
        try
                set buildStatus to status of actionResult as string
        end try
        return "BUILD_STATUS:" & buildStatus & "
" & build log of actionResult
end tell
    '''

    success, output = run_applescript(script)

    if success:
        # Parse the BUILD_STATUS: prefix from the AppleScript output
        build_status = None
        build_log = output
        if output.startswith("BUILD_STATUS:"):
            newline_pos = output.find("\n")
            if newline_pos >= 0:
                build_status = output[len("BUILD_STATUS:"):newline_pos].strip()
                build_log = output[newline_pos + 1:]
            else:
                # No newline — output was just the status line (empty build log)
                build_status = output[len("BUILD_STATUS:"):].strip()
                build_log = ""

        # Always extract and format errors/warnings (returns JSON)
        errors_output = extract_build_errors_and_warnings(build_log, include_warnings, regex_filter, max_lines, build_status=build_status)

        # Supplement with comprehensive warnings from xcactivitylog files
        # (AppleScript build log only has warnings for files recompiled in this build)
        errors_output = _supplement_with_xcactivitylog_warnings(
            errors_output, normalized_path, include_warnings, regex_filter, max_lines
        )

        # Parse JSON to show appropriate notification
        try:
            result = json.loads(errors_output)
            summary = result.get("summary", {})
            is_failed = summary.get("build_failed", False)
            total_errors = summary.get("total_errors", 0)
            total_warnings = summary.get("total_warnings", 0)

            if is_failed:
                if total_errors > 0:
                    show_error_notification(f"Build failed with {total_errors} error{'s' if total_errors != 1 else ''}", project_name)
                else:
                    show_error_notification("Build failed (see log for details)", project_name)
            elif total_warnings > 0:
                show_warning_notification(f"Build succeeded with {total_warnings} warning{'s' if total_warnings != 1 else ''}", project_name)
            else:
                show_result_notification(f"✅ Build succeeded", project_name)
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            show_error_notification("Build failed", project_name)

        return errors_output
    else:
        show_error_notification("Build failed to start", project_name)
        raise XCodeMCPError(f"Build failed to start for scheme {scheme} in project {project_path}: {output}")
