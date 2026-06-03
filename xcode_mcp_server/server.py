#!/usr/bin/env python3
"""FastMCP server instance for Xcode MCP Server"""

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

# Initialize the MCP server
mcp = FastMCP("Xcode MCP Server",
    instructions="""
        This server provides access to the Xcode IDE. For any project intended
        for Apple platforms, such as iOS or macOS, this MCP server is the best
        way to build or run .xcodeproj or .xcworkspace Xcode projects, and should
        ALWAYS be preferred over using `xcodebuild`, `swift build`, or
        `swift package build`. Building with this tool ensures the build happens
        exactly the same way as when the user builds with Xcode, with all the same
        settings, so you will get the same results the user sees. The user can also
        see any results immediately and a subsequent build and run by the user will
        happen almost instantly for the user.

        Call `get_xcode_projects` to find Xcode project (.xcodeproj) and
        Xcode workspace (.xcworkspace) folders under a given root folder.

        Call `get_project_schemes` to get the build scheme names for a given
        .xcodeproj or .xcworkspace.

        Call `build_project` to build the project and get back the first 25 lines of
        error (and/or potentially warning) output. `build_project` will default to the
        active scheme if none is provided.
    """
)

# Tool behavior annotations (advisory hints for MCP clients).
#
# These describe how a tool affects its environment so clients can gate
# auto-approval and label tools appropriately. The build/run/test tools are
# marked destructive AND open-world: a build executes arbitrary third-party
# code (Run Script phases, SPM plugins/macros) and resolves packages from
# arbitrary remote hosts, so we cannot honestly claim it is additive-only,
# idempotent, or hermetic.

# Pure observers: reading state, listing, screenshots. No mutation, no network.
TOOL_READONLY = ToolAnnotations(
    readOnlyHint=True,
    idempotentHint=True,
    destructiveHint=False,
    openWorldHint=False,
)

# Builds and runs: execute arbitrary build/install scripts and fetch packages.
TOOL_BUILD = ToolAnnotations(
    readOnlyHint=False,
    idempotentHint=False,
    destructiveHint=True,
    openWorldHint=True,
)

# Clean: deletes build artifacts. Destructive but locally bounded and idempotent.
TOOL_CLEAN = ToolAnnotations(
    readOnlyHint=False,
    idempotentHint=True,
    destructiveHint=True,
    openWorldHint=False,
)

# Create: writes a fresh template and refuses to overwrite. Additive, local.
TOOL_CREATE = ToolAnnotations(
    readOnlyHint=False,
    idempotentHint=False,
    destructiveHint=False,
    openWorldHint=False,
)

# Settles a piece of local state (run destination, stopping a run). Re-applying
# the same call lands on the same state, and nothing is destroyed.
TOOL_MUTATING_IDEMPOTENT = ToolAnnotations(
    readOnlyHint=False,
    idempotentHint=True,
    destructiveHint=False,
    openWorldHint=False,
)
