#!/usr/bin/env python3
"""Security and path validation utilities for Xcode MCP Server"""

import os
import re
import sys
from typing import Optional, List, Set

from drews_xcode_mcp.exceptions import AccessDeniedError, InvalidParameterError

# Global allowed folders set - initialized by CLI
ALLOWED_FOLDERS: Set[str] = set()


def set_allowed_folders(folders: Set[str]):
    """Set the global allowed folders.

    Paths are resolved through realpath so the stored values always represent
    the real on-disk target. is_path_allowed assumes ALLOWED_FOLDERS contains
    resolved paths, so callers that bypass get_allowed_folders still produce
    correct comparisons.
    """
    global ALLOWED_FOLDERS
    resolved = set()
    for f in folders:
        if not f:
            continue
        real = os.path.realpath(f)
        # `realpath("/").rstrip("/")` is "", and an empty allowed entry makes the
        # `startswith(entry + "/")` test in is_path_allowed match every absolute
        # path — i.e. a silent allow-everything. Root isn't a permitted allowed
        # folder (get_allowed_folders drops it too), so skip it here rather than
        # store a value that defeats the allow-list.
        if real == "/":
            print("Warning: refusing to use '/' as an allowed folder", file=sys.stderr)
            continue
        resolved.add(real.rstrip("/"))
    ALLOWED_FOLDERS = resolved


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

        # Resolve symlinks so subsequent prefix checks compare real paths to real paths.
        # Otherwise a symlink inside an allowed folder pointing outside it would silently
        # pass validation and let downstream tools operate on the target.
        resolved = os.path.realpath(folder).rstrip("/")

        allowed_folders.add(resolved)
        if resolved != folder:
            print(f"Added allowed folder: {folder} (resolved: {resolved})", file=sys.stderr)
        else:
            print(f"Added allowed folder: {folder}", file=sys.stderr)

    return allowed_folders


def is_path_allowed(project_path: str) -> bool:
    """
    Check if a project path is allowed based on the allowed folders list.
    Path must be a subfolder or direct match of an allowed folder.

    Symlinks are resolved before comparison so that a symlink inside an allowed
    folder pointing outside it does not bypass validation.
    """
    if not project_path:
        return False

    if not ALLOWED_FOLDERS:
        return False

    # Resolve symlinks in both the path and (already resolved at registration)
    # the allowed folders. realpath also normalizes and makes absolute, and works
    # on non-existent paths by resolving only the parents that do exist.
    resolved = os.path.realpath(project_path).rstrip("/")

    for allowed_folder in ALLOWED_FOLDERS:
        # Defensively ignore an empty entry; matching against "" + "/" would
        # accept every absolute path. set_allowed_folders should never store one.
        if not allowed_folder:
            continue
        if resolved == allowed_folder:
            return True
        if resolved.startswith(allowed_folder + "/"):
            return True

    return False


def validate_and_normalize_project_path(project_path: str, function_name: str) -> str:
    """
    Validate and normalize a project path for Xcode operations.

    Args:
        project_path: The project path to validate
        function_name: Name of calling function for error messages

    Returns:
        Normalized project path (symlinks resolved)

    Raises:
        InvalidParameterError: If validation fails
        AccessDeniedError: If path access is denied
    """
    # Import here to avoid circular dependency
    from drews_xcode_mcp.utils.applescript import show_access_denied_notification, show_error_notification

    if not project_path or project_path.strip() == "":
        raise InvalidParameterError("project_path cannot be empty")

    project_path = project_path.strip()

    if not (project_path.endswith('.xcodeproj') or project_path.endswith('.xcworkspace')):
        raise InvalidParameterError("project_path must end with '.xcodeproj' or '.xcworkspace'")

    # is_path_allowed resolves symlinks internally so the check is against the
    # real target, not the symlink alias.
    if not is_path_allowed(project_path):
        show_access_denied_notification(f"Access denied: {os.path.basename(project_path)}")
        raise AccessDeniedError(f"Access to path '{project_path}' is not allowed. Set XCODEMCP_ALLOWED_FOLDERS environment variable.")

    if not os.path.exists(project_path):
        show_error_notification(f"Path not found: {os.path.basename(project_path)}")
        raise InvalidParameterError(f"Project path does not exist: {project_path}")

    return os.path.realpath(project_path)


def validate_and_normalize_directory_path(directory_path: str) -> str:
    """
    Validate and normalize a directory path against the allowed-folders policy.

    Symlinks are resolved before the allow-list check (handled by is_path_allowed).

    Args:
        directory_path: The directory path to validate

    Returns:
        Normalized directory path (symlinks resolved, no trailing slash)

    Raises:
        InvalidParameterError: If validation fails or path is not a directory
        AccessDeniedError: If path access is denied
    """
    from drews_xcode_mcp.utils.applescript import show_access_denied_notification, show_error_notification

    if not directory_path or directory_path.strip() == "":
        raise InvalidParameterError("directory_path cannot be empty")

    directory_path = directory_path.strip()

    if not is_path_allowed(directory_path):
        show_access_denied_notification(f"Access denied: {directory_path}")
        raise AccessDeniedError(
            f"Access to path '{directory_path}' is not allowed. "
            "Set XCODEMCP_ALLOWED_FOLDERS environment variable."
        )

    if not os.path.exists(directory_path):
        show_error_notification(f"Path not found: {directory_path}")
        raise InvalidParameterError(f"Path does not exist: {directory_path}")

    resolved = os.path.realpath(directory_path).rstrip("/")

    if not os.path.isdir(resolved) and not (
        resolved.endswith('.xcodeproj') or resolved.endswith('.xcworkspace')
    ):
        show_error_notification(f"Not a directory: {resolved}")
        raise InvalidParameterError(f"Path is not a directory: {resolved}")

    return resolved


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
    from drews_xcode_mcp.utils.applescript import show_access_denied_notification, show_error_notification

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

    # Disallow spaces (and other punctuation): the name is interpolated unquoted
    # into project.pbxproj fields (path/name/productName), where a space
    # terminates the token and yields a syntactically invalid OpenStep plist that
    # Xcode refuses to open. Quoting in the template would be an alternative, but
    # bare-identifier names keep the generated pbxproj simplest and safest.
    if not re.match(r'^[A-Za-z0-9][A-Za-z0-9_-]*$', project_name):
        raise InvalidParameterError(
            "project_name must start with a letter or digit and contain only "
            "letters, digits, hyphens, or underscores (no spaces)"
        )

    # Prevent overwriting existing projects
    project_dir = os.path.join(parent_path, project_name)
    if os.path.exists(project_dir):
        raise InvalidParameterError(
            f"A file or directory already exists at: {project_dir}"
        )

    return os.path.realpath(parent_path)
