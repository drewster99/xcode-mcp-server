# Notification Usage Across Xcode MCP Server

This document catalogs all notification usage in the codebase, showing where notifications are displayed, their titles, and messages.

## Build Operations

build_project.py:50 - build_project - before starting a build
  title: "Xcode MCP"
  message: "Building {project_name}" with subtitle showing scheme_name

build_project.py:143 - build_project - after successful build completion
  title: "Xcode MCP"
  message: "Build succeeded" with subtitle showing project_name

build_project.py:150 - build_project - after build failure
  title: "Xcode MCP"
  message: "Build failed" with subtitle showing error count (e.g., "3 errors")

build_project.py:153 - build_project - when build fails to start
  title: "Xcode MCP"
  message: "Build failed to start"

## Run Operations

run_project.py:65 - run_project - before starting a run
  title: "Xcode MCP"
  message: "Running {project_name}" with subtitle showing scheme_name

run_project.py:181 - run_project - when run fails
  title: "Xcode MCP"
  message: "Run failed: {final_status}"

run_project.py:185 - run_project - when run completes successfully without console output
  title: "Xcode MCP"
  message: "Run completed: {final_status}"

run_project.py:189 - run_project - when run completes successfully with console output
  title: "Xcode MCP"
  message: "Run completed: {final_status}"

## Test Operations

run_project_tests.py:164 - run_project_tests - before starting tests
  title: "Xcode MCP"
  message: "Running tests" with subtitle showing basename of project_path

run_project_tests.py:340 - run_project_tests - when tests timeout
  title: "Xcode MCP"
  message: "Tests timeout ({max_wait_seconds}s)"

run_project_tests.py:372 - run_project_tests - when all tests pass
  title: "Xcode MCP"
  message: "All tests PASSED"

run_project_tests.py:374 - run_project_tests - when some tests fail
  title: "Xcode MCP"
  message: "{failure_count} test{'s' if failure_count != 1 else ''} FAILED"

run_project_tests.py:389 - run_project_tests - when all tests pass (fallback path)
  title: "Xcode MCP"
  message: "All tests PASSED"

run_project_tests.py:392 - run_project_tests - when tests fail (fallback path)
  title: "Xcode MCP"
  message: "Tests FAILED"

run_project_tests.py:395 - run_project_tests - on other test status (fallback path)
  title: "Xcode MCP"
  message: "Tests: {status}"

get_latest_test_results.py:71 - get_latest_test_results - when all tests passed (from xcresult)
  title: "Xcode MCP"
  message: "All tests PASSED"

get_latest_test_results.py:73 - get_latest_test_results - when some tests failed (from xcresult)
  title: "Xcode MCP"
  message: "{failed_count} test{'s' if failed_count != 1 else ''} FAILED"

get_latest_test_results.py:127 - get_latest_test_results - when no test results available (from AppleScript)
  title: "Xcode MCP"
  message: "No test results"

get_latest_test_results.py:129 - get_latest_test_results - when tests succeeded (from AppleScript)
  title: "Xcode MCP"
  message: "All tests PASSED"

get_latest_test_results.py:131 - get_latest_test_results - when tests failed (from AppleScript)
  title: "Xcode MCP"
  message: "Tests FAILED"

get_latest_test_results.py:134 - get_latest_test_results - when no test results available (fallback)
  title: "Xcode MCP"
  message: "No test results"

## Project Discovery

get_xcode_projects.py:45 - get_xcode_projects - when access is denied to a path
  title: "Xcode MCP"
  message: "Access denied: {project_path}"

get_xcode_projects.py:51 - get_xcode_projects - when path is not found
  title: "Xcode MCP"
  message: "Path not found: {project_path}"

get_xcode_projects.py:83 - get_xcode_projects - when projects are found
  title: "Xcode MCP"
  message: "Found {count} project{'s' if count != 1 else ''}" with subtitle showing first 3 project names

get_xcode_projects.py:85 - get_xcode_projects - when no projects are found
  title: "Xcode MCP"
  message: "No projects found"

## Screenshot Operations

### Simulator Screenshots

take_simulator_screenshot.py:58 - take_simulator_screenshot - when no booted simulators exist
  title: "Xcode MCP"
  message: "No booted simulators"

take_simulator_screenshot.py:98 - take_simulator_screenshot - when screenshot file is not created
  title: "Xcode MCP"
  message: "Screenshot failed" with subtitle "File not created"

take_simulator_screenshot.py:102 - take_simulator_screenshot - after successful screenshot
  title: "Xcode MCP"
  message: "SCREENSHOT - Simulator"

take_simulator_screenshot.py:107 - take_simulator_screenshot - on screenshot timeout
  title: "Xcode MCP"
  message: "Screenshot timeout"

take_simulator_screenshot.py:112 - take_simulator_screenshot - on screenshot failure (non-"not found" errors)
  title: "Xcode MCP"
  message: "Screenshot failed" with subtitle showing exception message

take_simulator_screenshot.py:115 - take_simulator_screenshot - on general screenshot error
  title: "Xcode MCP"
  message: "Screenshot failed" with subtitle showing exception message

### Xcode Window Screenshots

take_xcode_screenshot.py:101 - take_xcode_screenshot - when screenshot file is not created
  title: "Xcode MCP"
  message: "Screenshot failed" with subtitle "File not created"

take_xcode_screenshot.py:105 - take_xcode_screenshot - after successful Xcode screenshot
  title: "Xcode MCP"
  message: "SCREENSHOT - Xcode ({workspace_name})"

take_xcode_screenshot.py:110 - take_xcode_screenshot - on screenshot timeout
  title: "Xcode MCP"
  message: "Screenshot timeout"

take_xcode_screenshot.py:115 - take_xcode_screenshot - on screenshot failure (non-"not found" errors)
  title: "Xcode MCP"
  message: "Screenshot failed" with subtitle showing exception message

take_xcode_screenshot.py:118 - take_xcode_screenshot - on general screenshot error
  title: "Xcode MCP"
  message: "Screenshot failed" with subtitle showing exception message

### Window Screenshots

take_window_screenshot.py:61 - take_window_screenshot - when no matching window is found
  title: "Xcode MCP"
  message: "Window not found: {window_id_or_name}"

take_window_screenshot.py:95 - take_window_screenshot - when screenshot file is not created
  title: "Xcode MCP"
  message: "Screenshot failed" with subtitle "Window {window_id}"

take_window_screenshot.py:103 - take_window_screenshot - after successful single window screenshot
  title: "Xcode MCP"
  message: "SCREENSHOT - {window_title}"

take_window_screenshot.py:105 - take_window_screenshot - after successful multiple window screenshots
  title: "Xcode MCP"
  message: "SCREENSHOT - {len(matches)} windows"

take_window_screenshot.py:112 - take_window_screenshot - on screenshot failure (non-"not found" errors)
  title: "Xcode MCP"
  message: "Screenshot failed" with subtitle showing exception message

take_window_screenshot.py:115 - take_window_screenshot - on general screenshot error
  title: "Xcode MCP"
  message: "Screenshot failed" with subtitle showing exception message

### App Screenshots

take_app_screenshot.py:47 - take_app_screenshot - when no matching app is found
  title: "Xcode MCP"
  message: "App not found: {app_name}"

take_app_screenshot.py:106 - take_app_screenshot - when screenshot file is not created for a window
  title: "Xcode MCP"
  message: "Screenshot failed" with subtitle "Window {window['id']}"

take_app_screenshot.py:112 - take_app_screenshot - after successful app screenshots
  title: "Xcode MCP"
  message: "SCREENSHOT - {app_matched}"

take_app_screenshot.py:119 - take_app_screenshot - on screenshot failure (non-"not found", non-"Multiple apps" errors)
  title: "Xcode MCP"
  message: "Screenshot failed" with subtitle showing exception message

take_app_screenshot.py:122 - take_app_screenshot - on general screenshot error
  title: "Xcode MCP"
  message: "Screenshot failed" with subtitle showing exception message

## Simulator Management

list_booted_simulators.py:25 - list_booted_simulators - when no booted simulators exist
  title: "Xcode MCP"
  message: "No booted simulators"

list_booted_simulators.py:32 - list_booted_simulators - when exactly one simulator is found
  title: "Xcode MCP"
  message: "Found {first_sim}"

list_booted_simulators.py:37 - list_booted_simulators - when multiple simulators are found
  title: "Xcode MCP"
  message: "Found {count} simulators" with subtitle showing first simulator name and "+N more"

list_booted_simulators.py:52 - list_booted_simulators - on timeout while listing simulators
  title: "Xcode MCP"
  message: "Timeout listing simulators"

list_booted_simulators.py:58 - list_booted_simulators - on general error while listing simulators
  title: "Xcode MCP"
  message: "Error listing simulators" with subtitle showing exception message

## Directory Operations

get_directory_tree.py:56 - get_directory_tree - when access is denied to a path
  title: "Xcode MCP"
  message: "Access denied: {directory_path}"

get_directory_tree.py:62 - get_directory_tree - when path is not found
  title: "Xcode MCP"
  message: "Path not found: {directory_path}"

get_directory_tree.py:78 - get_directory_tree - when path is not a directory
  title: "Xcode MCP"
  message: "Not a directory: {scan_dir}"

get_directory_listing.py:55 - get_directory_listing - when access is denied to a path
  title: "Xcode MCP"
  message: "Access denied: {directory_path}"

get_directory_listing.py:63 - get_directory_listing - when path is not found
  title: "Xcode MCP"
  message: "Path not found: {directory_path}"

get_directory_listing.py:68 - get_directory_listing - when path is not a directory
  title: "Xcode MCP"
  message: "Not a directory: {directory_path}"

## System Information

version.py:17 - version - when version tool is called
  title: "Xcode MCP"
  message: "XcodeMCP v{__version__}"

list_running_mac_apps.py:19 - list_running_mac_apps - before listing running macOS applications
  title: "Xcode MCP"
  message: "Listing running macOS applications"

list_mac_app_windows.py:24 - list_mac_app_windows - before listing macOS application windows
  title: "Xcode MCP"
  message: "Listing macOS application windows"

## Security and Validation

security.py:153 - validate_and_normalize_project_path - when access is denied to a path
  title: "Xcode MCP"
  message: "Access denied: {os.path.basename(project_path)}"

security.py:159 - validate_and_normalize_project_path - when path is not found
  title: "Xcode MCP"
  message: "Path not found: {os.path.basename(project_path)}"

## Configuration Management

config_manager.py:422 - apply_config decorator - before calling any tool decorated with @apply_config
  title: "Xcode MCP"
  message: includes the function name (e.g., "build_project")

---

## Implementation Plan: Structured Notification System

### Overview
Create a centralized, typed notification system with unique identifiers for each notification type, allowing for future per-notification configuration control.

### Step 1: Create Notification Type Definitions
**File**: New `xcode_mcp_server/notification_types.py`

- Define string-based Enum with ~40-50 notification types (after consolidation)
- Create metadata dictionary mapping each notification type to:
  - `name`: Human-readable name for UI/configuration (e.g., "Build Start", "Build Success", "Build Failed")
  - `category`: Category string for grouping (e.g., "build", "test", "screenshot", "error", "info")

**Key consolidations**:
- Multiple "Access denied" notifications → single `ACCESS_DENIED` type
- Multiple "Path not found" notifications → single `PATH_NOT_FOUND` type
- Multiple "Screenshot failed" notifications → single `SCREENSHOT_FAILED` type with context in subtitle
- Multiple test result notifications → distinct types for each state

### Step 2: Update Notification Manager
**File**: `xcode_mcp_server/utils/applescript.py`

Add new function:
```python
def show_typed_notification(notification_type: NotificationType, message: str, subtitle: str = None):
    """Show a typed notification

    Args:
        notification_type: The type of notification (from NotificationType enum)
        message: The notification message
        subtitle: Optional subtitle for additional context
    """
    # Always uses "Drew's Xcode MCP" as title
    # Looks up notification metadata
    # Checks if notifications enabled (and later, if this specific type is enabled)
    # Calls osascript
```

**Note**: Existing `show_notification()`, `show_error_notification()`, and `show_result_notification()` will remain for now but are updated to use "Drew's Xcode MCP" ✓ (COMPLETED)

### Step 3: Update All Call Sites (~94 locations across 15 files)
Replace calls to existing notification functions with `show_typed_notification()`:

**Build Operations** (build_project.py - 6 calls):
- Line 50: `BUILD_START`
- Line 143: `BUILD_SUCCESS`
- Line 150: `BUILD_FAILED`
- Line 153: `BUILD_FAILED_TO_START`

**Run Operations** (run_project.py - 6 calls):
- Line 65: `RUN_START`
- Line 181: `RUN_FAILED`
- Line 185: `RUN_COMPLETED`
- Line 189: `RUN_COMPLETED`

**Test Operations** (run_project_tests.py - 14 calls):
- Line 164: `TEST_START`
- Line 340: `TEST_TIMEOUT`
- Lines 372, 389: `TEST_ALL_PASSED`
- Lines 374, 392: `TEST_SOME_FAILED`
- Line 395: `TEST_OTHER_STATUS`

**Test Results** (get_latest_test_results.py - 8 calls):
- Various: `TEST_ALL_PASSED`, `TEST_SOME_FAILED`, `TEST_NO_RESULTS`

**Project Discovery** (get_xcode_projects.py - 5 calls):
- Lines 45, 51: Consolidated error types
- Lines 83, 85: `PROJECTS_FOUND`, `PROJECTS_NOT_FOUND`

**Screenshot Operations**:
- take_simulator_screenshot.py (7 calls)
- take_xcode_screenshot.py (7 calls)
- take_window_screenshot.py (7 calls)
- take_app_screenshot.py (6 calls)
Total: Various screenshot-related types

**Simulator Management** (list_booted_simulators.py - 6 calls):
- Various simulator listing notifications

**Directory Operations**:
- get_directory_tree.py (4 calls)
- get_directory_listing.py (4 calls)

**System & Security**:
- version.py (2 calls)
- security.py (3 calls)
- list_running_mac_apps.py (1 call)
- list_mac_app_windows.py (1 call)
- config_manager.py (3 calls)
- config_ui.py (1 call)

### Step 4: Testing
- Verify all notifications still display correctly
- Confirm title shows "Drew's Xcode MCP" in all cases
- Test that NOTIFICATIONS_ENABLED global flag still works
- Prepare for future per-notification configuration

### Implementation Notes
- Title is now hardcoded to "Drew's Xcode MCP" in wrapper functions ✓ (COMPLETED)
- Each notification call site will provide: notification type ID, message, optional subtitle
- Category information stored in metadata, not provided by caller
- Configuration/filtering logic can be added later to `show_typed_notification()`
