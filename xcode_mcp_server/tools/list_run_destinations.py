#!/usr/bin/env python3
"""list_run_destinations tool - List available run destinations for a scheme"""

import json
import os
import re
import subprocess
from typing import Optional

from xcode_mcp_server.server import mcp
from xcode_mcp_server.config_manager import apply_config
from xcode_mcp_server.security import validate_and_normalize_project_path
from xcode_mcp_server.exceptions import XCodeMCPError
from xcode_mcp_server.utils.applescript import (
    show_notification,
    show_result_notification,
)


def _get_first_scheme_via_xcodebuild(project_path: str, project_flag: str) -> Optional[str]:
    """Get the first scheme name using xcodebuild -list (no Xcode side effects)."""
    try:
        result = subprocess.run(
            ['xcodebuild', '-list', project_flag, project_path],
            capture_output=True, text=True, timeout=15,
        )
        # Parse "Schemes:" section from output
        in_schemes = False
        for line in result.stdout.split('\n'):
            stripped = line.strip()
            if stripped == 'Schemes:':
                in_schemes = True
                continue
            if in_schemes:
                if stripped == '' or stripped.endswith(':'):
                    break
                return stripped
    except Exception:
        pass
    return None


def _parse_destination_line(line: str) -> Optional[dict]:
    """
    Parse a single xcodebuild destination line.
    Format: { platform:iOS Simulator, arch:arm64, id:ABC123, OS:26.4, name:iPhone 17 Pro }
    """
    line = line.strip()
    if not line.startswith('{') or not line.endswith('}'):
        return None

    inner = line[1:-1].strip()
    if not inner:
        return None

    # Parse key:value pairs — keys are simple words, values run until next ", key:" or end
    result = {}
    pattern = r'(\w+):(.+?)(?=, \w+:|$)'
    for match in re.finditer(pattern, inner):
        key = match.group(1).strip()
        value = match.group(2).strip()
        result[key] = value

    if not result.get('name') or not result.get('id'):
        return None

    return result


@mcp.tool()
@apply_config
def list_run_destinations(
    project_path: str,
    scheme: Optional[str] = None,
) -> str:
    """
    List available run destinations (devices and simulators) for a project scheme.

    Returns destinations filtered to what's compatible with the given scheme.
    For example, an iOS scheme will show iOS simulators and devices but not Mac
    destinations (unless the app supports Mac Catalyst).

    Use the 'id' field from the results with set_run_destination to change
    which device Xcode builds and runs for.

    Args:
        project_path: Path to an Xcode project (.xcodeproj) or workspace (.xcworkspace).
        scheme: Scheme name to list destinations for. If not provided, uses the
            first scheme found via xcodebuild.

    Returns:
        JSON array of destinations, each with: name, platform, id, and optionally
        arch, OS, and variant fields.
    """
    normalized_path = validate_and_normalize_project_path(project_path, "Listing destinations for")
    project_name = os.path.basename(normalized_path)

    # Determine the xcodebuild flag based on project type
    if normalized_path.endswith('.xcworkspace'):
        project_flag = '-workspace'
    else:
        project_flag = '-project'

    # Get scheme name if not provided
    if not scheme:
        scheme = _get_first_scheme_via_xcodebuild(normalized_path, project_flag)
        if not scheme:
            raise XCodeMCPError(
                f"Could not determine scheme for {project_name}. "
                "Please provide a scheme name."
            )

    show_notification("Listing Destinations", project_name, f"Scheme: {scheme}")

    try:
        result = subprocess.run(
            ['xcodebuild', '-showdestinations', project_flag, normalized_path, '-scheme', scheme],
            capture_output=True, text=True, timeout=30,
        )
        output = result.stdout + result.stderr
        if result.returncode != 0:
            # Look for a clear error message from xcodebuild
            for err_line in result.stderr.split('\n'):
                if 'error:' in err_line:
                    raise XCodeMCPError(err_line.strip())
            raise XCodeMCPError(f"xcodebuild failed for scheme '{scheme}'")
    except subprocess.TimeoutExpired:
        raise XCodeMCPError("xcodebuild -showdestinations timed out after 30 seconds")
    except XCodeMCPError:
        raise
    except Exception as e:
        raise XCodeMCPError(f"Failed to run xcodebuild: {e}")

    # Parse destination lines
    destinations = []
    for line in output.split('\n'):
        line = line.strip()
        if line.startswith('{') and line.endswith('}'):
            parsed = _parse_destination_line(line)
            if parsed:
                # Skip generic placeholder destinations
                if 'placeholder' in parsed.get('id', ''):
                    continue
                destinations.append(parsed)

    if destinations:
        count = len(destinations)
        show_result_notification(
            f"{count} destination{'s' if count != 1 else ''} for {scheme}",
            f"Scheme: {scheme}",
        )
    else:
        show_result_notification("No destinations found", f"Scheme: {scheme}")

    return json.dumps(destinations, indent=2)
