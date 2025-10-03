#!/usr/bin/env python3
"""FastMCP server instance for Xcode MCP Server"""

from mcp.server.fastmcp import FastMCP

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
