# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the Xcode MCP Server - a Model Context Protocol (MCP) server that enables AI assistants to interact with Xcode projects. It provides tools for building, running, and managing Xcode projects/workspaces programmatically through AppleScript.

## Development Commands

### Local Development
```bash
# Test the server locally with MCP Inspector
export XCODEMCP_ALLOWED_FOLDERS=/Users/username/Projects
mcp dev xcode_mcp_server/__main__.py

# Run the server directly
python -m xcode_mcp_server
```

### Build and Deploy
```bash
# Deploy to PyPI (increments version, builds, and uploads)
./deploy.sh

# Build distribution manually
python -m build

# Install locally for testing
pip install -e .
```

### Testing with uvx
```bash
# Run the published version
uvx xcode-mcp-server

# Run with specific allowed folders
XCODEMCP_ALLOWED_FOLDERS=/path/to/projects uvx xcode-mcp-server
```

## Architecture

### Core Components

1. **Main Entry Point** (`xcode_mcp_server/__init__.py`)
   - Handles command-line argument parsing
   - Manages allowed folder configuration from environment and CLI args
   - Validates security settings before server startup

2. **MCP Server Implementation** (`xcode_mcp_server/__main__.py`)
   - Built with FastMCP framework
   - Implements 20 MCP tools for Xcode interaction:
     - **Project discovery**: `version`, `get_xcode_projects`
     - **File system**: `get_directory_tree`, `get_directory_listing`
     - **Build operations**: `get_project_schemes`, `build_project`, `clean_project`, `stop_project`, `get_build_errors`
     - **Runtime**: `run_project`, `get_runtime_output`
     - **Testing**: `list_project_tests`, `run_project_tests`, `get_latest_test_results`
     - **Screenshots**: `take_xcode_screenshot`, `take_simulator_screenshot`, `take_window_screenshot`, `take_app_screenshot`
     - **System info**: `list_booted_simulators`, `list_running_mac_apps`, `list_mac_app_windows`

### Security Model

The server implements path-based security:
- **ALLOWED_FOLDERS**: Set of validated absolute paths where access is permitted
- Paths are validated for: absolute paths, existence, directory type, no '..' components
- Default to $HOME if no folders specified
- Every tool call validates the project path against allowed folders

### AppleScript Integration

All Xcode interactions use AppleScript via `osascript`:
- Opens projects/workspaces in Xcode
- Waits for workspace loading (60-second timeout)
- Handles build/run/clean operations
- Extracts build errors from Xcode's UI

### Error Handling

Custom exception hierarchy:
- `XCodeMCPError`: Base exception class
- `AccessDeniedError`: Path access violations
- `InvalidParameterError`: Invalid input parameters

## Key Implementation Details

- **Notifications**: Optional macOS notifications for tool invocations (--show-notifications flag)
- **Scheme Handling**: Active scheme detection with fallback to scheme list
- **Build Output**: Captures first 25 lines of build errors for concise feedback
- **Path Normalization**: Removes trailing slashes, validates absolute paths
- **Spotlight Integration**: Uses `mdfind` for efficient project discovery across allowed folders

## Version Management

Version is stored in `xcode_mcp_server/__init__.py` and managed by hatch:
```bash
hatch version patch  # Increment patch version
hatch version minor  # Increment minor version
hatch version major  # Increment major version
```

## Important Notes

- **get_frontmost_project**: Internal helper function (not exposed as MCP tool) that retrieves the currently open Xcode project path
- **Scheme Selection**: When no scheme is specified in `build_project`, the active scheme is used automatically
- **Debug Output**: Server prints debug information to stderr for troubleshooting
- **Workspace Loading**: All operations wait for Xcode workspace to fully load before proceeding (60-second timeout)
- **Build Log Filtering**: Build failures return only error lines (up to 25) from the full build log for clarity