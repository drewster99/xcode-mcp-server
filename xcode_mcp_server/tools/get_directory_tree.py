#!/usr/bin/env python3
"""get_directory_tree tool - Visual directory tree"""

import os
from typing import List

from xcode_mcp_server.server import mcp, TOOL_READONLY
from xcode_mcp_server.config_manager import apply_config
from xcode_mcp_server.security import validate_and_normalize_directory_path
from xcode_mcp_server.exceptions import InvalidParameterError, XCodeMCPError
from xcode_mcp_server.utils.applescript import show_error_notification

# Directories whose contents we never expand in the tree view. These are
# typically large build/dependency caches that bloat the output without
# adding information the LLM needs.
SKIP_DIR_NAMES = frozenset([
    '.build',
    'build',
    'DerivedData',
    'node_modules',
    'venv',
    '.venv',
    '__pycache__',
    'Pods',
    '.cocoapods',
    '.swiftpm',
    'Carthage',
])

# Hard ceiling on lines returned. Past this we truncate with a note so the
# response can't blow up token usage on pathological repos.
MAX_TREE_LINES = 5000


@mcp.tool(annotations=TOOL_READONLY)
@apply_config
def get_directory_tree(directory_path: str, max_depth: int = 4) -> str:
    """
    Get a visual tree of directories (folders only) in the specified path.

    Shows the folder structure as a tree diagram with box-drawing characters.
    Does not include individual files - use get_directory_listing for file details.

    Special behavior: If directory_path ends with .xcodeproj or .xcworkspace,
    the tree will show the parent directory structure (since these are typically
    at the root of a project folder).

    Args:
        directory_path: Path to directory to scan. Can also be a .xcodeproj or
                       .xcworkspace path (will scan parent directory in that case).
        max_depth: Maximum recursion depth (default 4, prevents excessive output).
                  Depth 1 = immediate subdirectories only, Depth 4 = up to 4 levels deep.

    Returns:
        A visual tree representation showing only directories/folders, with a note
        about using get_directory_listing for file-level details.

        Example:
        /Users/you/Projects/MyApp/
        ├── Sources/
        │   ├── Models/
        │   └── Views/
        ├── Tests/
        └── Resources/
    """
    # Validate max_depth
    if max_depth < 1:
        raise InvalidParameterError("max_depth must be at least 1")

    directory_path = validate_and_normalize_directory_path(directory_path)

    # Determine which directory to scan
    # If path ends with .xcodeproj or .xcworkspace, scan the parent directory
    if directory_path.endswith('.xcodeproj') or directory_path.endswith('.xcworkspace'):
        scan_dir = os.path.dirname(directory_path)
    else:
        scan_dir = directory_path

    # Verify scan_dir is a directory
    if not os.path.isdir(scan_dir):
        error_msg = f"Not a directory: {scan_dir}"
        show_error_notification(error_msg)
        raise InvalidParameterError(f"Path is not a directory: {scan_dir}")

    # Build the hierarchy (directories only)
    def build_hierarchy(path: str, prefix: str = "", is_last: bool = True, base_path: str = "", current_depth: int = 0) -> List[str]:
        """Recursively build a visual hierarchy of directories only"""
        lines = []

        if not base_path:
            base_path = path

        # Add current item (only if it's a directory and not the base)
        if path != base_path:
            connector = "└── " if is_last else "├── "
            name = os.path.basename(path) + "/"
            lines.append(prefix + connector + name)

            # Update prefix for children
            extension = "    " if is_last else "│   "
            prefix = prefix + extension

        # Check if we've reached max depth
        if current_depth >= max_depth:
            return lines

        # If it's a directory, recurse into it (with restrictions)
        if os.path.isdir(path):
            # Skip certain directories
            if os.path.basename(path) in SKIP_DIR_NAMES:
                return lines

            # Don't recurse into .xcodeproj or .xcworkspace directories
            if path.endswith('.xcodeproj') or path.endswith('.xcworkspace'):
                return lines

            try:
                items = sorted(os.listdir(path))
                # Filter to directories only, exclude hidden except for important ones
                dir_items = []
                for item in items:
                    item_path = os.path.join(path, item)
                    if os.path.isdir(item_path):
                        # Include if not hidden, or if it's an important hidden dir
                        if not item.startswith('.') or item in ['.git']:
                            dir_items.append(item)

                for i, item in enumerate(dir_items):
                    item_path = os.path.join(path, item)
                    is_last_item = (i == len(dir_items) - 1)
                    lines.extend(build_hierarchy(item_path, prefix, is_last_item, base_path, current_depth + 1))
            except PermissionError:
                pass

        return lines

    # Build hierarchy starting from scan directory
    hierarchy_lines = [scan_dir + "/"]

    try:
        items = sorted(os.listdir(scan_dir))
        # Filter to directories only
        dir_items = []
        for item in items:
            item_path = os.path.join(scan_dir, item)
            if os.path.isdir(item_path):
                if not item.startswith('.') or item in ['.git']:
                    dir_items.append(item)

        for i, item in enumerate(dir_items):
            item_path = os.path.join(scan_dir, item)
            is_last_item = (i == len(dir_items) - 1)
            hierarchy_lines.extend(build_hierarchy(item_path, "", is_last_item, scan_dir, 1))

    except Exception as e:
        raise XCodeMCPError(f"Error building directory tree for {directory_path}: {str(e)}")

    truncation_note = ""
    if len(hierarchy_lines) > MAX_TREE_LINES:
        original = len(hierarchy_lines)
        hierarchy_lines = hierarchy_lines[:MAX_TREE_LINES]
        truncation_note = (
            f"\n\n[Truncated: showing {MAX_TREE_LINES} of {original} lines. "
            f"Lower max_depth or call get_directory_listing on a subdirectory.]"
        )

    tree_output = '\n'.join(hierarchy_lines)
    return tree_output + truncation_note + "\n\nUse `get_directory_listing` to see files and details for a specific directory."
