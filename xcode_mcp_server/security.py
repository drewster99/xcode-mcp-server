#!/usr/bin/env python3
"""Security and path validation utilities for Xcode MCP Server"""

import os
import re
import sys
from typing import Optional, List, Set

from xcode_mcp_server.exceptions import AccessDeniedError, InvalidParameterError

# Global allowed folders set - initialized by CLI
ALLOWED_FOLDERS: Set[str] = set()


def set_allowed_folders(folders: Set[str]):
    """Set the global allowed folders"""
    global ALLOWED_FOLDERS
    ALLOWED_FOLDERS = folders


def get_allowed_folders(command_line_folders: Optional[List[str]] = None) -> Set[str]:
    """
    Get the allowed folders from environment variable and command line.
    Validates that paths are absolute, exist, and are directories.

    Args:
        command_line_folders: List of folders provided via command line

    Returns:
        Set of validated folder paths
    """
    allowed_folders = set()
    folders_to_process = []

    # Get from environment variable
    folder_list_str = os.environ.get("XCODEMCP_ALLOWED_FOLDERS")

    if folder_list_str:
        print(f"Using allowed folders from environment: {folder_list_str}", file=sys.stderr)
        folders_to_process.extend(folder_list_str.split(":"))

    # Add command line folders
    if command_line_folders:
        print(f"Adding {len(command_line_folders)} folder(s) from command line", file=sys.stderr)
        folders_to_process.extend(command_line_folders)

    # If no folders specified, use $HOME
    if not folders_to_process:
        print("Warning: No allowed folders specified via environment or command line.", file=sys.stderr)
        print("Set XCODEMCP_ALLOWED_FOLDERS environment variable or use --allowed flag.", file=sys.stderr)
        home = os.environ.get("HOME", "/")
        print(f"Using default: $HOME = {home}", file=sys.stderr)
        folders_to_process = [home]

    # Process all folders
    for folder in folders_to_process:
        folder = folder.rstrip("/")  # Normalize by removing trailing slash

        # Skip empty entries
        if not folder:
            print(f"Warning: Skipping empty folder entry", file=sys.stderr)
            continue

        # Check if path is absolute
        if not os.path.isabs(folder):
            print(f"Warning: Skipping non-absolute path: {folder}", file=sys.stderr)
            continue

        # Check if path contains ".." components
        if ".." in folder:
            print(f"Warning: Skipping path with '..' components: {folder}", file=sys.stderr)
            continue

        # Check if path exists and is a directory
        if not os.path.exists(folder):
            print(f"Warning: Skipping non-existent path: {folder}", file=sys.stderr)
            continue

        if not os.path.isdir(folder):
            print(f"Warning: Skipping non-directory path: {folder}", file=sys.stderr)
            continue

        # Add to allowed folders
        allowed_folders.add(folder)
        print(f"Added allowed folder: {folder}", file=sys.stderr)

    return allowed_folders


def is_path_allowed(project_path: str) -> bool:
    """
    Check if a project path is allowed based on the allowed folders list.
    Path must be a subfolder or direct match of an allowed folder.
    """
    if not project_path:
        print(f"Debug: Empty project_path provided", file=sys.stderr)
        return False

    # If no allowed folders are specified, nothing is allowed
    if not ALLOWED_FOLDERS:
        print(f"Debug: ALLOWED_FOLDERS is empty, denying access", file=sys.stderr)
        return False

    # Normalize the path
    project_path = os.path.abspath(project_path).rstrip("/")

    # Check if path is in allowed folders
    print(f"Debug: Checking normalized project_path: {project_path}", file=sys.stderr)
    for allowed_folder in ALLOWED_FOLDERS:
        # Direct match
        if project_path == allowed_folder:
            print(f"Debug: Direct match to {allowed_folder}", file=sys.stderr)
            return True

        # Path is a subfolder
        if project_path.startswith(allowed_folder + "/"):
            print(f"Debug: Subfolder match to {allowed_folder}", file=sys.stderr)
            return True
    print(f"Debug: No match found for {project_path}", file=sys.stderr)
    return False


def validate_and_normalize_project_path(project_path: str, function_name: str) -> str:
    """
    Validate and normalize a project path for Xcode operations.

    Args:
        project_path: The project path to validate
        function_name: Name of calling function for error messages

    Returns:
        Normalized project path

    Raises:
        InvalidParameterError: If validation fails
        AccessDeniedError: If path access is denied
    """
    # Import here to avoid circular dependency
    from xcode_mcp_server.utils.applescript import show_access_denied_notification, show_error_notification

    # Basic validation
    if not project_path or project_path.strip() == "":
        raise InvalidParameterError("project_path cannot be empty")

    project_path = project_path.strip()

    # Verify path ends with .xcodeproj or .xcworkspace
    if not (project_path.endswith('.xcodeproj') or project_path.endswith('.xcworkspace')):
        raise InvalidParameterError("project_path must end with '.xcodeproj' or '.xcworkspace'")

    # Security check
    if not is_path_allowed(project_path):
        show_access_denied_notification(f"Access denied: {os.path.basename(project_path)}")
        raise AccessDeniedError(f"Access to path '{project_path}' is not allowed. Set XCODEMCP_ALLOWED_FOLDERS environment variable.")

    # Check if the path exists
    if not os.path.exists(project_path):
        show_error_notification(f"Path not found: {os.path.basename(project_path)}")
        raise InvalidParameterError(f"Project path does not exist: {project_path}")

    # Normalize the path to resolve symlinks
    return os.path.realpath(project_path)


def validate_parent_for_new_project(parent_path: str, project_name: str) -> str:
    """
    Validate that a parent directory is allowed and a project name is safe
    for creating a new Xcode project.

    Args:
        parent_path: Directory where the project folder will be created
        project_name: Name of the new project

    Returns:
        Normalized parent path

    Raises:
        InvalidParameterError: If validation fails
        AccessDeniedError: If path access is denied
    """
    from xcode_mcp_server.utils.applescript import show_access_denied_notification, show_error_notification

    if not parent_path or parent_path.strip() == "":
        raise InvalidParameterError("parent_directory cannot be empty")

    if not project_name or project_name.strip() == "":
        raise InvalidParameterError("project_name cannot be empty")

    parent_path = parent_path.strip().rstrip("/")
    project_name = project_name.strip()

    if not os.path.isabs(parent_path):
        raise InvalidParameterError("parent_directory must be an absolute path")

    if ".." in parent_path:
        raise InvalidParameterError("parent_directory must not contain '..' components")

    if not os.path.exists(parent_path):
        show_error_notification(f"Path not found: {parent_path}")
        raise InvalidParameterError(f"parent_directory does not exist: {parent_path}")

    if not os.path.isdir(parent_path):
        raise InvalidParameterError(f"parent_directory is not a directory: {parent_path}")

    if not is_path_allowed(parent_path):
        show_access_denied_notification(f"Access denied: {parent_path}")
        raise AccessDeniedError(
            f"Access to path '{parent_path}' is not allowed. "
            "Set XCODEMCP_ALLOWED_FOLDERS environment variable."
        )

    # Validate project name contains only safe characters
    if not re.match(r'^[A-Za-z0-9][A-Za-z0-9 _-]*$', project_name):
        raise InvalidParameterError(
            "project_name must start with a letter or digit and contain only "
            "letters, digits, spaces, hyphens, or underscores"
        )

    # Prevent overwriting existing projects
    project_dir = os.path.join(parent_path, project_name)
    if os.path.exists(project_dir):
        raise InvalidParameterError(
            f"A file or directory already exists at: {project_dir}"
        )

    return os.path.realpath(parent_path)
