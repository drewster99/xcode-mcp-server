#!/usr/bin/env python3
"""get_xcode_projects tool - Find Xcode projects and workspaces"""

import os
import sys
import subprocess

from xcode_mcp_server.server import mcp
from xcode_mcp_server.security import ALLOWED_FOLDERS, is_path_allowed
from xcode_mcp_server.exceptions import AccessDeniedError, InvalidParameterError
from xcode_mcp_server.utils.applescript import show_access_denied_notification, show_error_notification, show_result_notification, show_warning_notification


@mcp.tool()
def get_xcode_projects(search_path: str = "") -> str:
    """
    Search the given search_path to find .xcodeproj (Xcode project) and
     .xcworkspace (Xcode workspace) paths. If the search_path is empty,
     all paths to which this tool has been granted access are searched.
     Searching all paths to which this tool has been granted access
     uses `mdfind` (Spotlight indexing) to find the relevant files, and
     so will only return .xcodeproj and .xcworkspace folders that are
     indexed.

    Args:
        search_path: Path to search. If empty, searches all allowed folders.

    Returns:
        A string which is a newline-separated list of .xcodeproj and
        .xcworkspace paths found. If none are found, returns an empty string.
    """
    # Determine paths to search
    paths_to_search = []

    if not search_path or search_path.strip() == "":
        # Search all allowed folders
        paths_to_search = list(ALLOWED_FOLDERS)
    else:
        # Search specific path
        project_path = search_path.strip()

        # Security check
        if not is_path_allowed(project_path):
            show_access_denied_notification(f"Access denied: {project_path}")
            raise AccessDeniedError(f"Access to path '{project_path}' is not allowed. Set XCODEMCP_ALLOWED_FOLDERS environment variable.")

        # Check if the path exists
        if not os.path.exists(project_path):
            show_error_notification(f"Path not found: {project_path}")
            raise InvalidParameterError(f"Project path does not exist: {project_path}")

        paths_to_search = [project_path]

    # Search for projects in all paths
    all_results = []
    for path in paths_to_search:
        try:
            # Use mdfind to search for Xcode projects
            mdfindResult = subprocess.run(['mdfind', '-onlyin', path,
                                         'kMDItemFSName == "*.xcodeproj" || kMDItemFSName == "*.xcworkspace"'],
                                         capture_output=True, text=True, check=True)
            result = mdfindResult.stdout.strip()
            if result:
                all_results.extend(result.split('\n'))
        except Exception as e:
            show_warning_notification(f"mdfind failed for {os.path.basename(path)}", str(e))
            print(f"Warning: Error searching in {path}: {str(e)}", file=sys.stderr)
            continue

    # Remove duplicates and sort
    unique_results = sorted(set(all_results))

    # Show result notification
    if unique_results:
        count = len(unique_results)
        # Get first 3 project names for notification
        sample_names = [os.path.basename(p) for p in unique_results[:3]]
        if count <= 3:
            details = "\n".join(f"• {name}" for name in sample_names)
        else:
            details = "\n".join(f"• {name}" for name in sample_names) + f"\n• +{count - 3} more"
        show_result_notification(f"Found {count} project{'s' if count != 1 else ''}", details)
    else:
        show_result_notification("No projects found")

    result = '\n'.join(unique_results) if unique_results else ""
    if result:
        result += "\n\nTo build a project, use `get_project_schemes` to see available build schemes, then call `build_project`."
    return result
