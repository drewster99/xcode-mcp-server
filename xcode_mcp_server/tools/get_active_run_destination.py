#!/usr/bin/env python3
"""get_active_run_destination tool - Get the currently active run destination"""

import glob
import json
import os
import subprocess

from xcode_mcp_server.server import mcp
from xcode_mcp_server.config_manager import apply_config
from xcode_mcp_server.security import validate_and_normalize_project_path
from xcode_mcp_server.exceptions import XCodeMCPError
from xcode_mcp_server.utils.applescript import show_result_notification


def _find_xcuserstate(project_path: str) -> str:
    """Find the UserInterfaceState.xcuserstate file for a project."""
    if project_path.endswith('.xcodeproj'):
        workspace_dir = os.path.join(project_path, "project.xcworkspace")
    else:
        workspace_dir = project_path

    pattern = os.path.join(workspace_dir, "xcuserdata", "*", "UserInterfaceState.xcuserstate")
    matches = glob.glob(pattern)
    if not matches:
        return ""

    return max(matches, key=os.path.getmtime)


def _decode_active_destinations(xcuserstate_path: str) -> dict:
    """
    Run the Swift decoder script to extract active destination per scheme.
    Returns dict like {"SchemeName": "UDID_platform_arch"}
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    swift_script = os.path.join(os.path.dirname(script_dir), 'utils', 'decode_active_destination.swift')

    if not os.path.exists(swift_script):
        return {}

    try:
        result = subprocess.run(
            ['swift', swift_script, xcuserstate_path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout.strip())
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
        pass

    return {}


def _get_active_scheme_from_xcuserstate(project_path: str) -> str:
    """Get the active scheme name from xcschememanagement.plist (no Xcode side effects)."""
    # Look in xcuserdata for scheme management plist
    pattern = os.path.join(project_path, "xcuserdata", "*", "xcschemes", "xcschememanagement.plist")
    matches = glob.glob(pattern)
    if not matches:
        return ""

    plist_path = max(matches, key=os.path.getmtime)
    try:
        result = subprocess.run(
            ['plutil', '-convert', 'json', '-o', '-', plist_path],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            scheme_state = data.get("SchemeUserState", {})
            # Keys look like "SchemeName.xcscheme_^#shared#^_" or "SchemeName.xcscheme"
            # Find the one with lowest orderHint (or just return the first)
            best_scheme = ""
            best_order = float('inf')
            for key, value in scheme_state.items():
                # Strip the suffix to get scheme name
                scheme_name = key.split('.xcscheme')[0]
                order = value.get('orderHint', 999)
                if order < best_order:
                    best_order = order
                    best_scheme = scheme_name
            return best_scheme
    except Exception:
        pass
    return ""


def _lookup_simulator_info(udid: str) -> tuple:
    """
    Look up a simulator name and OS version by UDID using xcrun simctl.
    Returns (name, os_version) or ("", "").
    """
    try:
        result = subprocess.run(
            ['xcrun', 'simctl', 'list', 'devices', udid],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            current_os = ""
            for line in result.stdout.split('\n'):
                stripped = line.strip()
                # Track OS version from section headers like "-- iOS 26.4 --"
                if stripped.startswith('-- ') and stripped.endswith(' --'):
                    current_os = stripped[3:-3]  # e.g. "iOS 26.4"
                elif udid in stripped:
                    paren_idx = stripped.find('(')
                    if paren_idx > 0:
                        name = stripped[:paren_idx].strip()
                        return (name, current_os)
    except Exception:
        pass
    return ("", "")


@mcp.tool()
@apply_config
def get_active_run_destination(
    project_path: str,
) -> str:
    """
    Get the currently active run destination for a project.

    Returns the device or simulator that Xcode will use for the next build or
    run operation. This reads from Xcode's workspace state file without opening
    the project in Xcode.

    Note: After calling set_run_destination, Xcode may take several seconds to
    flush its state to disk. If called immediately after set_run_destination,
    this may return the previous destination.

    Args:
        project_path: Path to an Xcode project (.xcodeproj) or workspace (.xcworkspace).

    Returns:
        JSON with the active destination's name, platform, architecture, and id.
        Returns an error message if the active destination cannot be determined
        (e.g. the project has never been opened in Xcode).
    """
    normalized_path = validate_and_normalize_project_path(project_path, "Getting active destination for")
    project_name = os.path.basename(normalized_path)

    # Find the xcuserstate file
    xcuserstate = _find_xcuserstate(normalized_path)
    if not xcuserstate:
        raise XCodeMCPError(
            "No workspace state file found. The project may not have been "
            "opened in Xcode yet."
        )

    # Decode the active destinations per scheme
    scheme_destinations = _decode_active_destinations(xcuserstate)
    if not scheme_destinations:
        raise XCodeMCPError(
            "Could not determine active run destination. The project may not "
            "have been built or run yet."
        )

    # Determine which scheme's destination to report
    active_scheme = _get_active_scheme_from_xcuserstate(normalized_path)

    dest_string = None
    if active_scheme and active_scheme in scheme_destinations:
        dest_string = scheme_destinations[active_scheme]
    elif scheme_destinations:
        # Fall back to first scheme's destination
        active_scheme = next(iter(scheme_destinations))
        dest_string = scheme_destinations[active_scheme]

    if not dest_string:
        raise XCodeMCPError("No active run destination found in workspace state.")

    # Parse the destination string (format: "UDID_platform_arch")
    parts = dest_string.split('_')
    if len(parts) < 3:
        raise XCodeMCPError(f"Unexpected destination format: {dest_string}")

    target_udid = parts[0]
    platform = parts[1]
    architecture = parts[2]

    # Try to get a friendly name and OS version
    name, os_version = _lookup_simulator_info(target_udid)
    if not name:
        name = target_udid

    result = {
        "name": name,
        "platform": platform,
        "architecture": architecture,
        "id": target_udid,
    }
    if os_version:
        result["os"] = os_version
    if active_scheme:
        result["scheme"] = active_scheme

    show_result_notification(f"Active: {name}", project_name)
    return json.dumps(result, indent=2)
