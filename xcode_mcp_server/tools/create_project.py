#!/usr/bin/env python3
"""create_project tool - Create a new Xcode project from a built-in template"""

import json
import os
from typing import Optional

from xcode_mcp_server.server import mcp
from xcode_mcp_server.config_manager import apply_config
from xcode_mcp_server.security import validate_parent_for_new_project
from xcode_mcp_server.exceptions import InvalidParameterError
from xcode_mcp_server.utils.applescript import (
    show_notification,
    show_result_notification,
)
from xcode_mcp_server.utils.project_templates import (
    generate_project,
    sanitize_to_identifier,
)
from xcode_mcp_server.tools.get_xcode_projects import register_created_project


SUPPORTED_PLATFORMS = {"ios", "macos"}


@mcp.tool()
@apply_config
def create_project(
    parent_directory: str,
    project_name: str,
    platform: str = "ios",
    bundle_identifier: str = "",
    deployment_target: str = "",
) -> str:
    """
    Create a new Xcode project with a SwiftUI app template.

    Creates a complete, buildable Xcode project with a SwiftUI app entry point,
    ContentView, and asset catalog. The project uses the modern Xcode 16+ format
    (objectVersion 77) with automatic file discovery.

    Args:
        parent_directory: Directory where the project folder will be created.
            Must be within the allowed folders configured for this server.
        project_name: Name of the project (e.g. "MyApp"). Used for the folder
            name, target name, and scheme name.
        platform: Target platform - "ios" or "macos" (case-insensitive).
            Defaults to "ios".
        bundle_identifier: Bundle identifier (e.g. "com.mycompany.MyApp").
            Defaults to "com.example.{ProjectName}".
        deployment_target: Minimum deployment target version (e.g. "26.0").
            Defaults to "26.0".

    Returns:
        JSON string with project_path, project_directory, platform,
        bundle_identifier, and files_created.
    """
    # Validate platform
    platform = platform.lower().strip()
    if platform not in SUPPORTED_PLATFORMS:
        raise InvalidParameterError(
            f"platform must be one of: {', '.join(sorted(SUPPORTED_PLATFORMS))}. "
            f"Got: '{platform}'"
        )

    # Validate parent directory and project name
    parent_directory = validate_parent_for_new_project(parent_directory, project_name)

    show_notification(
        "Creating Project",
        project_name,
        f"Platform: {platform}",
    )

    # Generate the project
    result = generate_project(
        parent_dir=parent_directory,
        project_name=project_name,
        platform=platform,
        bundle_identifier=bundle_identifier or None,
        deployment_target=deployment_target or None,
    )

    # Register so get_xcode_projects finds it before Spotlight indexes it
    register_created_project(result["project_path"])

    show_result_notification(
        f"Created: {project_name}",
        f"Platform: {platform}",
    )

    # Compute the actual bundle identifier used
    if not bundle_identifier:
        identifier = sanitize_to_identifier(project_name)
        bundle_identifier = f"com.example.{identifier}"

    result["platform"] = platform
    result["bundle_identifier"] = bundle_identifier

    return json.dumps(result, indent=2)
