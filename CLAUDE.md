# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the Xcode MCP Server - a Model Context Protocol (MCP) server that enables AI assistants to interact with Xcode projects. It provides tools for building, running, and managing Xcode projects/workspaces programmatically through AppleScript.

## Development Commands

### Local Development
```bash
# Quick start with dev script (sets up conda env and runs MCP Inspector)
./dev.sh

# Manual setup: Test the server locally with MCP Inspector
export XCODEMCP_ALLOWED_FOLDERS=/Users/username/Projects
mcp dev xcode_mcp_server/__main__.py

# Run the server directly
python -m xcode_mcp_server
```

### Testing
```bash
# Run tests using the test runner framework
python tests/test_basic.py      # Basic functionality tests
python tests/test_build.py      # Build operation tests
python tests/test_runner.py     # Test infrastructure

# Tests automatically:
# - Set up isolated working directory (test_projects/working/)
# - Copy template projects from test_projects/templates/
# - Configure ALLOWED_FOLDERS to working directory
# - Clean up after execution
```

### Build and Deploy
```bash
# Deploy to PyPI (increments version, builds, and uploads)
./deploy.sh

# Manual version increment
hatch version patch  # 1.2.0 -> 1.2.1
hatch version minor  # 1.2.0 -> 1.3.0
hatch version major  # 1.2.0 -> 2.0.0

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

2. **MCP Server Implementation** (`xcode_mcp_server/server.py` and `xcode_mcp_server/tools/`)
   - Built with FastMCP framework
   - Implements 24 MCP tools for Xcode interaction:
     - **Project discovery**: `version`, `get_xcode_projects`
     - **File system**: `get_directory_tree`, `get_directory_listing`
     - **Build operations**: `get_project_schemes`, `build_project`, `clean_project`, `stop_project`, `get_build_errors`
     - **Runtime**: `run_project_with_user_interaction`, `run_project_until_terminated`, `run_project_unmonitored`, `get_runtime_output`
     - **Testing**: `list_project_tests`, `run_project_tests`, `get_latest_test_results`
     - **Screenshots**: `take_xcode_screenshot`, `take_simulator_screenshot`, `take_window_screenshot`, `take_app_screenshot`
     - **System info**: `list_booted_simulators`, `list_running_mac_apps`, `list_mac_app_windows`
     - **Debug**: `debug_list_notification_history`

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

Version is stored in `xcode_mcp_server/__init__.py` and managed by hatch. The `deploy.sh` script automatically increments the patch version, but you can manually control it with:
```bash
hatch version patch  # Increment patch version
hatch version minor  # Increment minor version
hatch version major  # Increment major version
```

## Important Implementation Details

### Internal Helper Functions
- **`get_frontmost_project()`**: Not exposed as MCP tool; retrieves the currently open Xcode project path from frontmost window
- **`extract_console_logs_from_xcresult()`**: Parses .xcresult bundles to extract runtime console output as structured JSON
- **`extract_build_errors_and_warnings()`**: Filters build logs to show only errors/warnings as structured JSON (configurable via `include_warnings` parameter)
- **`extract_test_results_from_xcresult()`**: Parses .xcresult test bundles to extract concise test results with failure details
- **`wait_for_xcresult_after_timestamp()`**: Polls for new .xcresult files after a run starts, with timeout
- **`find_xcresult_for_project()`**: Locates the most recent .xcresult bundle for a project (runtime logs)
- **`find_xcresult_bundle()`**: Locates the most recent .xcresult bundle for a project (test logs)
- **`validate_and_normalize_project_path()`**: Ensures paths are absolute, exist, and are allowed by security policy
- **`escape_applescript_string()`**: Properly escapes strings for safe AppleScript execution

### Operational Behavior
- **Scheme Selection**: When no scheme is specified in `build_project`, the active scheme is used automatically
- **Debug Output**: Server prints debug information to stderr for troubleshooting
- **Workspace Loading**: All operations wait for Xcode workspace to fully load before proceeding (60-second timeout)
- **Build Log Filtering**: Build failures return structured JSON with errors/warnings (up to 25 lines) and full log path
- **Test Result Filtering**: Test results return structured JSON with summary and only failed test details; passing tests are counted but not detailed
- **Warning Control**: Global `BUILD_WARNINGS_ENABLED` and `BUILD_WARNINGS_FORCED` flags control warning display; can be overridden per-tool with `include_warnings` parameter
- **Notifications**: Optional macOS notifications via `osascript` (controlled by `NOTIFICATIONS_ENABLED` global flag)

### xcresult Management
The server relies heavily on Xcode's .xcresult bundles for extracting build, runtime, and test information:
- **Runtime logs**: Located in `~/Library/Developer/Xcode/DerivedData/*/Logs/Launch/`
- **Test results**: Located in `~/Library/Developer/Xcode/DerivedData/*/Logs/Test/`
- Parsed using `xcrun xcresulttool` with appropriate subcommands
- Timestamped checking prevents reading stale results
- **Runtime output**: Console logs extracted from `actionsInvocationRecord` → `actions` → `actionResult` → `logRef` paths, returned as structured JSON with errors/warnings prioritized
- **Test results**: Test tree parsed recursively to extract pass/fail counts and failure details, returned as concise structured JSON (10-50x smaller than raw xcresult output)
- **Build errors**: Filtered using regex patterns, returned as structured JSON with full log path for deep analysis