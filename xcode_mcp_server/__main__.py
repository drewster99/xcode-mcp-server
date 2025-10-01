#!/usr/bin/env python3
import os
import sys
import subprocess
import json
import argparse
import time
import re
from typing import Optional, Dict, List, Any, Tuple, Set

from mcp.server.fastmcp import FastMCP, Context

# Global variables for allowed folders
ALLOWED_FOLDERS: Set[str] = set()
NOTIFICATIONS_ENABLED = True  # No type annotation to avoid global declaration issues
BUILD_WARNINGS_ENABLED = True  # No type annotation to avoid global declaration issues
BUILD_WARNINGS_FORCED = None  # True if forced on, False if forced off, None if not forced

class XCodeMCPError(Exception):
    def __init__(self, message, code=None):
        self.message = message
        self.code = code
        super().__init__(self.message)

class AccessDeniedError(XCodeMCPError):
    pass

class InvalidParameterError(XCodeMCPError):
    pass

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
    # Basic validation
    if not project_path or project_path.strip() == "":
        raise InvalidParameterError("project_path cannot be empty")

    project_path = project_path.strip()

    # Verify path ends with .xcodeproj or .xcworkspace
    if not (project_path.endswith('.xcodeproj') or project_path.endswith('.xcworkspace')):
        raise InvalidParameterError("project_path must end with '.xcodeproj' or '.xcworkspace'")

    # Show notification
    show_notification("Xcode MCP", f"{function_name} {os.path.basename(project_path)}")

    # Security check
    if not is_path_allowed(project_path):
        raise AccessDeniedError(f"Access to path '{project_path}' is not allowed. Set XCODEMCP_ALLOWED_FOLDERS environment variable.")

    # Check if the path exists
    if not os.path.exists(project_path):
        raise InvalidParameterError(f"Project path does not exist: {project_path}")

    # Normalize the path to resolve symlinks
    return os.path.realpath(project_path)

def escape_applescript_string(s: str) -> str:
    """
    Escape a string for safe use in AppleScript.

    Args:
        s: String to escape

    Returns:
        Escaped string safe for AppleScript
    """
    # Escape backslashes first, then quotes
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    return s

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
        
        Available tools:
        - get_xcode_projects: Find Xcode project (.xcodeproj) and workspace (.xcworkspace) files
        - get_project_hierarchy: Get the file structure of a project
        - get_project_schemes: List available build schemes for a project
        - build_project: Build the project (defaults to active scheme if none specified)
        - run_project: Run the project and capture console output
        - get_build_errors: Get errors from the last build
        - clean_project: Clean build artifacts
        - stop_project: Stop any currently running build or run operation
        - get_runtime_output: Get console output from the most recent run
        - list_booted_simulators: List all currently booted iOS simulators
        - take_screenshot_xcode: Take a screenshot of the Xcode window for a project
        - take_simulator_screenshot: Take a screenshot of a booted simulator
    """
)

def run_applescript(script: str) -> Tuple[bool, str]:
    """Run an AppleScript and return success status and output"""
    try:
        result = subprocess.run(['osascript', '-e', script],
                               capture_output=True, text=True, check=True)
        return True, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return False, e.stderr.strip()

def extract_console_logs_from_xcresult(xcresult_path: str,
                                      max_lines: int = 100,
                                      regex_filter: Optional[str] = None) -> Tuple[bool, str]:
    """
    Extract console logs from an xcresult file.

    Args:
        xcresult_path: Path to the .xcresult file
        max_lines: Maximum number of lines to return
        regex_filter: Optional regex pattern to filter output lines

    Returns:
        Tuple of (success, output_or_error_message)
    """
    # The xcresult file may still be finalizing, so retry a few times
    max_retries = 7
    retry_delay = 1

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                print(f"Retry attempt {attempt + 1}/{max_retries} after {retry_delay}s delay...", file=sys.stderr)
                time.sleep(retry_delay)

            result = subprocess.run(
                ['xcrun', 'xcresulttool', 'get', 'log',
                 '--path', xcresult_path,
                 '--type', 'console'],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                if "root ID is missing" in result.stderr and attempt < max_retries - 1:
                    print(f"xcresult not ready yet: {result.stderr.strip()}", file=sys.stderr)
                    continue
                return False, f"Failed to extract console logs: {result.stderr}"

            # Success - break out of retry loop
            break

        except subprocess.TimeoutExpired:
            if attempt < max_retries - 1:
                continue
            return False, "Timeout extracting console logs"
        except Exception as e:
            if attempt < max_retries - 1:
                continue
            return False, f"Error extracting console logs: {e}"

    # Parse the JSON output
    try:
        log_data = json.loads(result.stdout)

        # Extract console content from items
        console_lines = []
        for item in log_data.get('items', []):
            content = item.get('content', '').strip()
            if content:
                # Apply regex filter if provided and not empty
                if regex_filter and regex_filter.strip():
                    try:
                        if re.search(regex_filter, content):
                            console_lines.append(content)
                    except re.error as e:
                        raise InvalidParameterError(f"Invalid regex pattern: {e}")
                else:
                    console_lines.append(content)

        # Limit to max_lines (take the last N lines)
        if len(console_lines) > max_lines:
            console_lines = console_lines[-max_lines:]

        if not console_lines:
            return True, ""  # No output is not an error

        return True, "\n".join(console_lines)

    except json.JSONDecodeError as e:
        return False, f"Failed to parse console logs: {e}"
    except Exception as e:
        return False, f"Error processing console logs: {e}"

def extract_build_errors_and_warnings(build_log: str,
                                     include_warnings: Optional[bool] = None) -> str:
    """
    Extract and format errors and warnings from a build log.

    Args:
        build_log: The raw build log output from Xcode
        include_warnings: Include warnings in output. If not provided, uses global setting.

    Returns:
        Formatted string with errors/warnings, limited to 25 lines
    """
    # Determine whether to include warnings
    # Command-line flags override function parameter (user control > LLM control)
    if BUILD_WARNINGS_FORCED is not None:
        # User explicitly set a command-line flag to force behavior
        show_warnings = BUILD_WARNINGS_FORCED
    else:
        # No forcing, use function parameter or default
        show_warnings = include_warnings if include_warnings is not None else BUILD_WARNINGS_ENABLED

    output_lines = build_log.split("\n")
    error_lines = []
    warning_lines = []

    # Single iteration through output lines
    for line in output_lines:
        line_lower = line.lower()
        if "error" in line_lower:
            error_lines.append(line)
        elif show_warnings and "warning" in line_lower:
            warning_lines.append(line)

    # Store total counts
    total_errors = len(error_lines)
    total_warnings = len(warning_lines)

    # Combine errors first, then warnings
    important_lines = error_lines + warning_lines

    # Calculate what we're actually showing
    displayed_errors = min(total_errors, 25)
    displayed_warnings = 0 if total_errors >= 25 else min(total_warnings, 25 - total_errors)

    # Limit to first 25 important lines
    if len(important_lines) > 25:
        important_lines = important_lines[:25]

    important_list = "\n".join(important_lines)

    # Build appropriate message based on what we found
    if error_lines and warning_lines:
        # Build detailed count message
        count_msg = f"Build failed with {total_errors} error(s) and {total_warnings} warning(s)."
        if total_errors + total_warnings > 25:
            if displayed_warnings == 0:
                count_msg += f" Showing first {displayed_errors} errors."
            else:
                count_msg += f" Showing {displayed_errors} error(s) and first {displayed_warnings} warning(s)."
        return f"{count_msg}\n{important_list}"
    elif error_lines:
        count_msg = f"Build failed with {total_errors} error(s)."
        if total_errors > 25:
            count_msg += f" Showing first 25 errors."
        return f"{count_msg}\n{important_list}"
    elif warning_lines:
        count_msg = f"Build completed with {total_warnings} warning(s)."
        if total_warnings > 25:
            count_msg += f" Showing first 25 warnings."
        return f"{count_msg}\n{important_list}"
    else:
        return "Build failed (no specific errors or warnings found in output)"

def find_xcresult_for_project(project_path: str) -> Optional[str]:
    """
    Find the most recent xcresult file for a given project.

    Args:
        project_path: Path to the .xcodeproj or .xcworkspace

    Returns:
        Path to the most recent xcresult file, or None if not found
    """
    # Normalize and get project name
    normalized_path = os.path.realpath(project_path)
    project_name = os.path.basename(normalized_path).replace('.xcworkspace', '').replace('.xcodeproj', '')

    # Find the most recent xcresult file in DerivedData
    derived_data_base = os.path.expanduser("~/Library/Developer/Xcode/DerivedData")

    # Look for directories matching the project name
    # DerivedData directories typically have format: ProjectName-randomhash
    try:
        for derived_dir in os.listdir(derived_data_base):
            # More precise matching: must start with project name followed by a dash
            if derived_dir.startswith(project_name + "-"):
                logs_dir = os.path.join(derived_data_base, derived_dir, "Logs", "Launch")
                if os.path.exists(logs_dir):
                    # Find the most recent .xcresult file
                    xcresult_files = []
                    for f in os.listdir(logs_dir):
                        if f.endswith('.xcresult'):
                            full_path = os.path.join(logs_dir, f)
                            xcresult_files.append((os.path.getmtime(full_path), full_path))

                    if xcresult_files:
                        xcresult_files.sort(reverse=True)
                        return xcresult_files[0][1]
    except Exception as e:
        print(f"Error searching for xcresult: {e}", file=sys.stderr)

    return None

def show_notification(title: str, message: str):
    """Show a macOS notification if notifications are enabled"""
    if NOTIFICATIONS_ENABLED:
        try:
            subprocess.run(['osascript', '-e', 
                          f'display notification "{message}" with title "{title}"'], 
                          capture_output=True)
        except:
            pass  # Ignore notification errors

# MCP Tools for Xcode

@mcp.tool()
def version() -> str:
    """
    Get the current version of the Xcode MCP Server.
    
    Returns:
        The version string of the server
    """
    show_notification("Xcode MCP", "Getting server version")
    return f"Xcode MCP Server version {__import__('xcode_mcp_server').__version__}"


@mcp.tool()
def get_xcode_projects(search_path: str = "") -> str:
    """
    Search the given search_path to find .xcodeproj (Xcode project) and
     .xcworkspace (Xcode workspace) paths. If the search_path is empty,
     all paths to which this tool has been granted access are searched.
     Searching all paths to which this tool has been granted access can
     uses `mdfind` (Spotlight indexing) to find the relevant files, and
     so will only return .xcodeproj and .xcworkspace folders that are
     indexed.
    
    Args:
        search_path: Path to search. If empty, searches all allowed folders.
        
    Returns:
        A string which is a newline-separated list of .xcodeproj and
        .xcworkspace paths found. If none are found, returns an empty string.
    """
    global ALLOWED_FOLDERS
    
    # Determine paths to search
    paths_to_search = []
    
    if not search_path or search_path.strip() == "":
        # Search all allowed folders
        show_notification("Xcode MCP", f"Searching all {len(ALLOWED_FOLDERS)} allowed folders for Xcode projects")
        paths_to_search = list(ALLOWED_FOLDERS)
    else:
        # Search specific path
        project_path = search_path.strip()
        
        # Security check
        if not is_path_allowed(project_path):
            raise AccessDeniedError(f"Access to path '{project_path}' is not allowed. Set XCODEMCP_ALLOWED_FOLDERS environment variable.")
        
        # Check if the path exists
        if not os.path.exists(project_path):
            raise InvalidParameterError(f"Project path does not exist: {project_path}")
            
        show_notification("Xcode MCP", f"Searching {project_path} for Xcode projects")
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
            print(f"Warning: Error searching in {path}: {str(e)}", file=sys.stderr)
            continue
    
    # Remove duplicates and sort
    unique_results = sorted(set(all_results))
    
    return '\n'.join(unique_results) if unique_results else ""


@mcp.tool()
def get_project_hierarchy(project_path: str) -> str:
    """
    Get a recursive directory tree for the specified Xcode project or workspace.

    Args:
        project_path: Path to an Xcode project/workspace directory, which must
        end in '.xcodeproj' or '.xcworkspace' and must exist.

    Returns:
        A string representation of the project hierarchy
    """
    # Validate and normalize path
    project_path = validate_and_normalize_project_path(project_path, "Getting hierarchy for")
    
    # Get the parent directory to scan
    parent_dir = os.path.dirname(project_path)
    project_name = os.path.basename(project_path)
    
    # Build the hierarchy
    def build_hierarchy(path: str, prefix: str = "", is_last: bool = True, base_path: str = "") -> List[str]:
        """Recursively build a visual hierarchy of files and folders"""
        lines = []

        if not base_path:
            base_path = path

        # Add current item
        if path != base_path:
            connector = "└── " if is_last else "├── "
            name = os.path.basename(path)
            if os.path.isdir(path):
                name += "/"
            lines.append(prefix + connector + name)
            
            # Update prefix for children
            extension = "    " if is_last else "│   "
            prefix = prefix + extension
        
        # If it's a directory, recurse into it (with restrictions)
        if os.path.isdir(path):
            # Skip certain directories
            if os.path.basename(path) in ['.build', 'build']:
                return lines
                
            # Don't recurse into .xcodeproj or .xcworkspace directories
            if path.endswith('.xcodeproj') or path.endswith('.xcworkspace'):
                return lines
            
            try:
                items = sorted(os.listdir(path))
                # Filter out hidden files except for important ones
                items = [item for item in items if not item.startswith('.') or item in ['.gitignore', '.swift-version']]
                
                for i, item in enumerate(items):
                    item_path = os.path.join(path, item)
                    is_last_item = (i == len(items) - 1)
                    lines.extend(build_hierarchy(item_path, prefix, is_last_item, base_path))
            except PermissionError:
                pass
                
        return lines
    
    # Build hierarchy starting from parent directory
    hierarchy_lines = [parent_dir + "/"]
    
    try:
        items = sorted(os.listdir(parent_dir))
        # Filter out hidden files and build directories
        items = [item for item in items if not item.startswith('.') or item in ['.gitignore', '.swift-version']]
        
        for i, item in enumerate(items):
            item_path = os.path.join(parent_dir, item)
            is_last_item = (i == len(items) - 1)
            hierarchy_lines.extend(build_hierarchy(item_path, "", is_last_item, parent_dir))
            
    except Exception as e:
        raise XCodeMCPError(f"Error building hierarchy for {project_path}: {str(e)}")
    
    return '\n'.join(hierarchy_lines)

@mcp.tool()
def get_project_schemes(project_path: str) -> str:
    """
    Get the available build schemes for the specified Xcode project or workspace.

    Args:
        project_path: Path to an Xcode project/workspace directory, which must
        end in '.xcodeproj' or '.xcworkspace' and must exist.

    Returns:
        A newline-separated list of scheme names, with the active scheme listed first.
        If no schemes are found, returns an empty string.
    """
    # Validate and normalize path
    normalized_path = validate_and_normalize_project_path(project_path, "Getting schemes for")
    escaped_path = escape_applescript_string(normalized_path)

    script = f'''
    tell application "Xcode"
        open "{escaped_path}"

        set workspaceDoc to first workspace document whose path is "{escaped_path}"
        
        -- Wait for it to load
        repeat 60 times
            if loaded of workspaceDoc is true then exit repeat
            delay 0.5
        end repeat
        
        if loaded of workspaceDoc is false then
            error "Xcode workspace did not load in time."
        end if
        
        -- Try to get active scheme name, but don't fail if we can't
        set activeScheme to ""
        try
            set activeScheme to name of active scheme of workspaceDoc
        on error
            -- If we can't get active scheme (e.g., Xcode is busy), continue without it
        end try
        
        -- Get all scheme names
        set schemeNames to {{}}
        repeat with aScheme in schemes of workspaceDoc
            set end of schemeNames to name of aScheme
        end repeat
        
        -- Format output
        set output to ""
        if activeScheme is not "" then
            -- If we have an active scheme, list it first with annotation
            set output to activeScheme & " (active)"
            repeat with schemeName in schemeNames
                if schemeName as string is not equal to activeScheme then
                    set output to output & "\\n" & schemeName
                end if
            end repeat
        else
            -- If no active scheme available, just list all schemes
            set AppleScript's text item delimiters to "\\n"
            set output to schemeNames as string
            set AppleScript's text item delimiters to ""
        end if
        
        return output
    end tell
    '''
    
    success, output = run_applescript(script)
    
    if success:
        return output
    else:
        raise XCodeMCPError(f"Failed to get schemes for {project_path}: {output}")

@mcp.tool()
def build_project(project_path: str,
                 scheme: Optional[str] = None,
                 include_warnings: Optional[bool] = None) -> str:
    """
    Build the specified Xcode project or workspace.

    Args:
        project_path: Path to an Xcode project or workspace directory.
        scheme: Name of the scheme to build. If not provided, uses the active scheme.
        include_warnings: Include warnings in build output. If not provided, uses global setting.

    Returns:
        On success, returns "Build succeeded with 0 errors."
        On failure, returns the first (up to) 25 error/warning lines from the build log.
    """
    # Validate include_warnings parameter
    if include_warnings is not None and not isinstance(include_warnings, bool):
        raise InvalidParameterError("include_warnings must be a boolean value")

    # Validate and normalize path
    scheme_desc = scheme if scheme else "active scheme"
    normalized_path = validate_and_normalize_project_path(project_path, f"Building {scheme_desc} in")
    escaped_path = escape_applescript_string(normalized_path)

    # Build the AppleScript
    if scheme:
        # Use provided scheme
        escaped_scheme = escape_applescript_string(scheme)
        script = f'''
set projectPath to "{escaped_path}"
set schemeName to "{escaped_scheme}"

tell application "Xcode"
        -- 1. Open the project file
        open projectPath

        -- 2. Get the workspace document
        set workspaceDoc to first workspace document whose path is projectPath

        -- 3. Wait for it to load (timeout after ~30 seconds)
        repeat 60 times
                if loaded of workspaceDoc is true then exit repeat
                delay 0.5
        end repeat

        if loaded of workspaceDoc is false then
                error "Xcode workspace did not load in time."
        end if

        -- 4. Set the active scheme
        set active scheme of workspaceDoc to (first scheme of workspaceDoc whose name is schemeName)

        -- 5. Build
        set actionResult to build workspaceDoc

        -- 6. Wait for completion
        repeat
                if completed of actionResult is true then exit repeat
                delay 0.5
        end repeat

        -- 7. Check result
        set buildStatus to status of actionResult
        if buildStatus is succeeded then
                return "Build succeeded." 
        else
                return build log of actionResult
        end if
end tell
    '''
    else:
        # Use active scheme
        script = f'''
set projectPath to "{escaped_path}"

tell application "Xcode"
        -- 1. Open the project file
        open projectPath

        -- 2. Get the workspace document
        set workspaceDoc to first workspace document whose path is projectPath

        -- 3. Wait for it to load (timeout after ~30 seconds)
        repeat 60 times
                if loaded of workspaceDoc is true then exit repeat
                delay 0.5
        end repeat

        if loaded of workspaceDoc is false then
                error "Xcode workspace did not load in time."
        end if

        -- 4. Build with current active scheme
        set actionResult to build workspaceDoc

        -- 5. Wait for completion
        repeat
                if completed of actionResult is true then exit repeat
                delay 0.5
        end repeat

        -- 6. Check result
        set buildStatus to status of actionResult
        if buildStatus is succeeded then
                return "Build succeeded." 
        else
                return build log of actionResult
        end if
end tell
    '''
    
    success, output = run_applescript(script)
    
    if success:
        if output == "Build succeeded.":
            return "Build succeeded with 0 errors."
        else:
            # Use the shared helper to extract and format errors/warnings
            return extract_build_errors_and_warnings(output, include_warnings)
    else:
        raise XCodeMCPError(f"Build failed to start for scheme {scheme} in project {project_path}: {output}")

@mcp.tool()
def run_project(project_path: str,
               wait_seconds: int,
               scheme: Optional[str] = None,
               max_lines: int = 100,
               regex_filter: Optional[str] = None) -> str:
    """
    Run the specified Xcode project or workspace and wait for completion.
    If the project run has completed by the time `wait_seconds` have passed,
    this function will return filtered runtime output.
    
    Alternatively, you can call this with `0` for `wait_seconds` and get the
    filtered runtime output later by calling `get_runtime_output`.

    Args:
        project_path: Path to an Xcode project/workspace directory.
        wait_seconds: Maximum number of seconds to wait for the run to complete. If given a value of zero (0), this function returns as soon as the project is launched.
        scheme: Optional scheme to run. If not provided, uses the active scheme.
        max_lines: Maximum number of console log lines to return. Defaults to 100.
        regex_filter: Optional regex pattern to filter console output lines.

    Returns:
        Console output from the run, or status message if still running.
    """
    # Validate other parameters
    if wait_seconds < 0:
        raise InvalidParameterError("wait_seconds must be non-negative")

    if max_lines < 1:
        raise InvalidParameterError("max_lines must be at least 1")

    # Validate and normalize path
    scheme_desc = scheme if scheme else "active scheme"
    normalized_path = validate_and_normalize_project_path(project_path, f"Running {scheme_desc} in")
    escaped_path = escape_applescript_string(normalized_path)

    # Build the AppleScript that runs and polls in one script
    if scheme:
        escaped_scheme = escape_applescript_string(scheme)
        script = f'''
        tell application "Xcode"
            open "{escaped_path}"

            -- Get the workspace document
            set workspaceDoc to first workspace document whose path is "{escaped_path}"

            -- Wait for it to load
            repeat 60 times
                if loaded of workspaceDoc is true then exit repeat
                delay 0.5
            end repeat

            if loaded of workspaceDoc is false then
                error "Xcode workspace did not load in time."
            end if

            -- Set the active scheme
            set active scheme of workspaceDoc to (first scheme of workspaceDoc whose name is "{escaped_scheme}")

            -- Run
            set actionResult to run workspaceDoc

            -- Poll for completion
            repeat {wait_seconds} times
                if completed of actionResult is true then
                    exit repeat
                end if
                delay 1
            end repeat

            -- Return completion status and status
            if completed of actionResult is true then
                return "true|" & (status of actionResult as text)
            else
                return "false|" & (status of actionResult as text)
            end if
        end tell
        '''
    else:
        script = f'''
        tell application "Xcode"
            open "{escaped_path}"

            -- Get the workspace document
            set workspaceDoc to first workspace document whose path is "{escaped_path}"

            -- Wait for it to load
            repeat 60 times
                if loaded of workspaceDoc is true then exit repeat
                delay 0.5
            end repeat

            if loaded of workspaceDoc is false then
                error "Xcode workspace did not load in time."
            end if

            -- Run with active scheme
            set actionResult to run workspaceDoc

            -- Poll for completion
            repeat {wait_seconds} times
                if completed of actionResult is true then
                    exit repeat
                end if
                delay 1
            end repeat

            -- Return completion status and status
            if completed of actionResult is true then
                return "true|" & (status of actionResult as text)
            else
                return "false|" & (status of actionResult as text)
            end if
        end tell
        '''

    print(f"Running and waiting up to {wait_seconds} seconds for completion...", file=sys.stderr)
    success, output = run_applescript(script)

    if not success:
        raise XCodeMCPError(f"Run failed: {output}")

    # Parse the result
    print(f"Raw output: '{output}'", file=sys.stderr)
    parts = output.split("|")

    if len(parts) != 2:
        raise XCodeMCPError(f"Unexpected output format: {output}")

    completed = parts[0].strip().lower() == "true"
    final_status = parts[1].strip()

    print(f"Run completed={completed}, status={final_status}", file=sys.stderr)

    # Find the most recent xcresult file for this project
    xcresult_path = find_xcresult_for_project(project_path)

    if not xcresult_path:
        if completed:
            return f"Run completed with status: {final_status}. Could not find xcresult file to extract console logs."
        else:
            return f"Run did not complete within {wait_seconds} seconds (status: {final_status}). Could not extract console logs."

    print(f"Found xcresult: {xcresult_path}", file=sys.stderr)

    # Extract console logs
    success, console_output = extract_console_logs_from_xcresult(xcresult_path, max_lines, regex_filter)

    if not success:
        return f"Run completed with status: {final_status}. {console_output}"

    if not console_output:
        return f"Run completed with status: {final_status}. No console output found (or filtered out)."

    output_summary = f"Run completed with status: {final_status}\n"
    output_summary += f"Console output ({len(console_output.splitlines())} lines):\n"
    output_summary += "=" * 60 + "\n"
    output_summary += console_output

    return output_summary

@mcp.tool()
def get_build_errors(project_path: str,
                    include_warnings: Optional[bool] = None) -> str:
    """
    Get the build errors from the last build for the specified Xcode project or workspace.

    Args:
        project_path: Path to an Xcode project or workspace directory.
        include_warnings: Include warnings in output. If not provided, uses global setting.

    Returns:
        A string containing the build errors/warnings or a message if there are none
    """
    # Validate include_warnings parameter
    if include_warnings is not None and not isinstance(include_warnings, bool):
        raise InvalidParameterError("include_warnings must be a boolean value")

    # Validate and normalize path
    normalized_path = validate_and_normalize_project_path(project_path, "Getting build errors for")
    escaped_path = escape_applescript_string(normalized_path)

    # Get the last build log from the workspace
    script = f'''
    tell application "Xcode"
        open "{escaped_path}"

        -- Get the workspace document
        set workspaceDoc to first workspace document whose path is "{escaped_path}"

        -- Wait for it to load (timeout after ~30 seconds)
        repeat 60 times
            if loaded of workspaceDoc is true then exit repeat
            delay 0.5
        end repeat

        if loaded of workspaceDoc is false then
            error "Xcode workspace did not load in time."
        end if

        -- Try to get the last build log
        try
            -- Get the most recent build action result
            set lastBuildResult to last build action result of workspaceDoc

            -- Get its build log
            return build log of lastBuildResult
        on error
            -- No build has been performed yet
            return ""
        end try
    end tell
    '''

    success, output = run_applescript(script)

    if success:
        if output == "":
            return "No build has been performed yet for this project."
        else:
            # Use the shared helper to extract and format errors/warnings
            return extract_build_errors_and_warnings(output, include_warnings)
    else:
        raise XCodeMCPError(f"Failed to retrieve build errors: {output}")

@mcp.tool()
def clean_project(project_path: str) -> str:
    """
    Clean the specified Xcode project or workspace.

    Args:
        project_path: Path to an Xcode project/workspace directory.

    Returns:
        Output message
    """
    # Validate and normalize path
    normalized_path = validate_and_normalize_project_path(project_path, "Cleaning")
    escaped_path = escape_applescript_string(normalized_path)

    # AppleScript to clean the project
    script = f'''
    tell application "Xcode"
        open "{escaped_path}"

        -- Get the workspace document
        set workspaceDoc to first workspace document whose path is "{escaped_path}"

        -- Wait for it to load (timeout after ~30 seconds)
        repeat 60 times
            if loaded of workspaceDoc is true then exit repeat
            delay 0.5
        end repeat

        if loaded of workspaceDoc is false then
            error "Xcode workspace did not load in time."
        end if

        -- Clean the workspace
        clean workspaceDoc

        return "Clean completed successfully"
    end tell
    '''

    success, output = run_applescript(script)

    if success:
        return output
    else:
        raise XCodeMCPError(f"Clean failed: {output}")

@mcp.tool()
def stop_project(project_path: str) -> str:
    """
    Stop the currently running build or run operation for the specified Xcode project or workspace.

    Args:
        project_path: Path to an Xcode project/workspace directory, which must
        end in '.xcodeproj' or '.xcworkspace' and must exist.

    Returns:
        A message indicating whether the stop was successful
    """
    # Validate and normalize path
    normalized_path = validate_and_normalize_project_path(project_path, "Stopping build/run for")
    escaped_path = escape_applescript_string(normalized_path)

    # AppleScript to stop the current build or run operation
    script = f'''
    tell application "Xcode"
        -- Try to get the workspace document
        try
            set workspaceDoc to first workspace document whose path is "{escaped_path}"
        on error
            return "ERROR: No open workspace found for path: {escaped_path}"
        end try

        -- Stop the current action (build or run)
        try
            stop workspaceDoc
            return "Successfully stopped the current build/run operation"
        on error errMsg
            return "ERROR: " & errMsg
        end try
    end tell
    '''

    success, output = run_applescript(script)

    if success:
        if output.startswith("ERROR:"):
            # Extract the error message
            error_msg = output[6:].strip()
            if "No open workspace found" in error_msg:
                raise InvalidParameterError(f"Project is not currently open in Xcode: {project_path}")
            else:
                raise XCodeMCPError(f"Failed to stop build/run: {error_msg}")
        else:
            return output
    else:
        raise XCodeMCPError(f"Failed to stop build/run for {project_path}: {output}")

@mcp.tool()
def get_runtime_output(project_path: str,
                      max_lines: int = 25,
                      regex_filter: Optional[str] = None) -> str:
    """
    Get the runtime output from the console for the last COMPLETED run of the specified Xcode project.
    Output from currently running apps does not become available until a few seconds after the app has terminated.

    Args:
        project_path: Path to an Xcode project/workspace directory.
        max_lines: Maximum number of lines to retrieve. Defaults to 25.
        regex_filter: Optional regex pattern to filter console output lines.

    Returns:
        Console output as a string
    """
    # Validate other parameters
    if max_lines < 1:
        raise InvalidParameterError("max_lines must be at least 1")

    # Validate and normalize path
    project_path = validate_and_normalize_project_path(project_path, "Getting runtime output for")

    # Find the most recent xcresult file for this project
    xcresult_path = find_xcresult_for_project(project_path)

    if not xcresult_path:
        return "No xcresult file found. The project may not have been run recently, or the DerivedData may have been cleaned."

    print(f"Found xcresult: {xcresult_path}", file=sys.stderr)

    # Extract console logs
    success, console_output = extract_console_logs_from_xcresult(xcresult_path, max_lines, regex_filter)

    if not success:
        raise XCodeMCPError(f"Failed to extract runtime output: {console_output}")

    if not console_output:
        return "No console output found in the most recent run (or filtered out by regex)."

    # Return the console output with a header
    output_lines = console_output.splitlines()
    header = f"Console output from most recent run ({len(output_lines)} lines):\n"
    header += "=" * 60 + "\n"

    return header + console_output

def _get_booted_simulators():
    """
    Internal helper to get list of booted simulators using text parsing.
    Returns a list of dicts with 'name', 'udid', and 'os' keys.
    """
    result = subprocess.run(
        ['xcrun', 'simctl', 'list', 'devices', 'booted'],
        capture_output=True,
        text=True,
        timeout=10
    )

    if result.returncode != 0:
        raise XCodeMCPError(f"Failed to list simulators: {result.stderr}")

    lines = result.stdout.strip().split('\n')
    booted_simulators = []
    current_os = None

    for line in lines:
        line = line.strip()
        # Check for OS version headers like "-- iOS 26.0 --"
        if line.startswith('-- ') and line.endswith(' --'):
            current_os = line[3:-3].strip()
        # Check for booted device lines
        elif '(Booted)' in line and current_os:
            # Parse device info from line like: "iPad (A16) (D89C8520-3426-49B2-9CF5-09DCA506DC66) (Booted)"
            import re
            match = re.match(r'(.+?)\s+\(([A-F0-9-]+)\)\s+\(Booted\)', line)
            if match:
                device_name = match.group(1).strip()
                device_udid = match.group(2).strip()
                booted_simulators.append({
                    'name': device_name,
                    'udid': device_udid,
                    'os': current_os
                })

    return booted_simulators

@mcp.tool()
def list_booted_simulators() -> str:
    """
    List all currently booted iOS, iPadOS, tvOS, and watchOS simulators.

    Returns:
        A formatted list of booted simulators with their names, UDIDs, and OS versions.
        Returns "No booted simulators found" if none are running.
    """
    show_notification("Xcode MCP", "Listing booted simulators")

    try:
        booted_simulators = _get_booted_simulators()

        if not booted_simulators:
            return "No booted simulators found"

        # Format output
        output_lines = [f"Found {len(booted_simulators)} booted simulator(s):", ""]

        for sim in booted_simulators:
            output_lines.append(f"• {sim['name']}")
            output_lines.append(f"  UDID: {sim['udid']}")
            output_lines.append(f"  OS: {sim['os']}")
            output_lines.append("")

        return "\n".join(output_lines)

    except subprocess.TimeoutExpired:
        raise XCodeMCPError("Timeout while listing simulators")
    except Exception as e:
        if isinstance(e, XCodeMCPError):
            raise
        raise XCodeMCPError(f"Error listing simulators: {e}")

@mcp.tool()
def take_xcode_screenshot(project_path: str) -> str:
    """
    Take a screenshot of the Xcode window for the specified project.

    Args:
        project_path: Path to an Xcode project/workspace directory.

    Returns:
        The file path to the saved screenshot.

    Raises:
        XCodeMCPError: If Xcode window is not found or screenshot fails.
    """
    # Validate and normalize path
    normalized_path = validate_and_normalize_project_path(project_path, "Taking Xcode screenshot for")
    escaped_path = escape_applescript_string(normalized_path)

    try:
        # Get the workspace name (used as window title in Xcode)
        workspace_name = os.path.basename(normalized_path)
        escaped_workspace_name = escape_applescript_string(workspace_name)

        # Get the window ID via AppleScript
        script = f'''
        tell application "Xcode"
            -- First, try to find the window by exact path match
            repeat with w in windows
                try
                    if path of document of w is "{escaped_path}" then
                        return id of w
                    end if
                end try
            end repeat

            -- If not found by path, try by name (less reliable but fallback)
            try
                return id of window "{escaped_workspace_name}"
            on error
                error "No Xcode window found for project: {escaped_workspace_name}"
            end try
        end tell
        '''

        success, window_id = run_applescript(script)
        if not success:
            raise XCodeMCPError(f"Failed to get Xcode window: {window_id}")

        window_id = window_id.strip()
        if not window_id:
            raise XCodeMCPError(f"No Xcode window found for project: {workspace_name}")

        print(f"Found Xcode window with ID: {window_id}", file=sys.stderr)

        # Create screenshot directory
        screenshot_dir = "/tmp/xcode-mcp-server/screenshots"
        os.makedirs(screenshot_dir, exist_ok=True)

        # Generate filename with timestamp
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', workspace_name)
        filename = f"xcode_{safe_name}_{timestamp}.png"
        screenshot_path = os.path.join(screenshot_dir, filename)

        print(f"Taking screenshot of Xcode window for '{workspace_name}'", file=sys.stderr)

        # Capture the screenshot using screencapture
        result = subprocess.run(
            ["screencapture", "-l", window_id, "-x", "-o", screenshot_path],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            raise XCodeMCPError(f"Failed to capture screenshot: {result.stderr}")

        # Verify the file was created
        if not os.path.exists(screenshot_path):
            raise XCodeMCPError("Screenshot file was not created")

        print(f"Screenshot saved to: {screenshot_path}", file=sys.stderr)
        return screenshot_path

    except subprocess.TimeoutExpired:
        raise XCodeMCPError("Timeout while taking screenshot")
    except Exception as e:
        if isinstance(e, XCodeMCPError):
            raise
        raise XCodeMCPError(f"Error taking Xcode screenshot: {e}")

@mcp.tool()
def take_simulator_screenshot(udid: Optional[str] = None) -> str:
    """
    Take a screenshot of a booted iOS simulator.

    Args:
        udid: Optional UDID (device identifier) of the simulator to screenshot.
              If not provided or empty, the first booted simulator found is used.
              A list of running simulators can be found with `list_booted_simulators`.

    Returns:
        The file path to the saved screenshot.

    Raises:
        XCodeMCPError: If no booted simulators found or screenshot fails.
    """
    show_notification("Xcode MCP", "Taking simulator screenshot")

    try:
        target_udid = None
        target_name = "Unknown"

        if udid and udid.strip():
            # User specified a UDID - use it directly without checking booted list
            # xcrun simctl will fail appropriately if it's not booted
            target_udid = udid.strip()

            # Try to get the name for better logging (optional)
            try:
                booted_simulators = _get_booted_simulators()
                for sim in booted_simulators:
                    if sim['udid'] == target_udid:
                        target_name = sim['name']
                        break
            except:
                # If we can't get the name, continue anyway
                pass
        else:
            # No UDID specified - find first booted simulator
            booted_simulators = _get_booted_simulators()

            if not booted_simulators:
                raise XCodeMCPError("No booted simulators found")

            # Use first booted simulator
            target_udid = booted_simulators[0]['udid']
            target_name = booted_simulators[0]['name']

        # Create screenshot directory
        screenshot_dir = "/tmp/xcode-mcp-server/screenshots"
        os.makedirs(screenshot_dir, exist_ok=True)

        # Generate filename with timestamp
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', target_name)
        filename = f"simulator_{safe_name}_{timestamp}.png"
        screenshot_path = os.path.join(screenshot_dir, filename)

        print(f"Taking screenshot of '{target_name}' (UDID: {target_udid})", file=sys.stderr)

        # Take the screenshot
        result = subprocess.run(
            ['xcrun', 'simctl', 'io', target_udid, 'screenshot', screenshot_path],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip()
            # Provide more helpful error messages
            if 'Invalid device' in error_msg:
                raise XCodeMCPError(f"Simulator with UDID '{target_udid}' does not exist")
            elif 'not booted' in error_msg.lower():
                raise XCodeMCPError(f"Simulator with UDID '{target_udid}' is not booted")
            else:
                raise XCodeMCPError(f"Failed to take screenshot: {error_msg}")

        # Verify the file was created
        if not os.path.exists(screenshot_path):
            raise XCodeMCPError("Screenshot file was not created")

        print(f"Screenshot saved to: {screenshot_path}", file=sys.stderr)
        return screenshot_path

    except subprocess.TimeoutExpired:
        raise XCodeMCPError("Timeout while taking screenshot")
    except Exception as e:
        if isinstance(e, XCodeMCPError):
            raise
        raise XCodeMCPError(f"Error taking screenshot: {e}")

@mcp.tool()
def list_running_mac_apps() -> str:
    """
    List all currently running macOS applications.

    Returns:
        A formatted list of running applications with their name, bundle ID,
        and status flags (frontmost/visible/hidden).
    """
    show_notification("Xcode MCP", "Listing running macOS applications")

    try:
        # Use AppleScript to get running applications
        script = '''
        tell application "System Events"
            set appList to {}
            set runningApps to every application process

            repeat with anApp in runningApps
                set appName to name of anApp
                set appBundleID to bundle identifier of anApp
                set appPID to unix id of anApp
                set appFrontmost to frontmost of anApp
                set appVisible to visible of anApp
                set appHidden to not appVisible

                -- Format as tab-separated values for easy parsing
                set appInfo to appName & tab & appBundleID & tab & appPID & tab & appFrontmost & tab & appVisible
                set end of appList to appInfo
            end repeat

            return appList
        end tell
        '''

        success, output = run_applescript(script)

        if not success:
            raise XCodeMCPError(f"Failed to list running apps: {output}")

        # Parse the output
        apps = []
        lines = output.strip().split(', ')

        for line in lines:
            if not line.strip():
                continue

            parts = line.split('\t')
            if len(parts) >= 5:
                app_name = parts[0]
                bundle_id = parts[1] if parts[1] != 'missing value' else 'N/A'
                pid = parts[2]
                is_frontmost = parts[3] == 'true'
                is_visible = parts[4] == 'true'

                apps.append({
                    'name': app_name,
                    'bundle_id': bundle_id,
                    'pid': pid,
                    'is_frontmost': is_frontmost,
                    'is_visible': is_visible,
                    'is_hidden': not is_visible
                })

        # Sort by name for consistent output
        apps.sort(key=lambda x: x['name'].lower())

        if not apps:
            return "No running applications found"

        # Format output
        output_lines = [f"Found {len(apps)} running application(s):", ""]

        for app in apps:
            status_flags = []
            if app['is_frontmost']:
                status_flags.append("FRONTMOST")
            if app['is_visible']:
                status_flags.append("VISIBLE")
            if app['is_hidden']:
                status_flags.append("HIDDEN")
            status = f" [{', '.join(status_flags)}]" if status_flags else ""

            output_lines.append(f"• {app['name']}{status}")
            output_lines.append(f"  Bundle ID: {app['bundle_id']}")
            output_lines.append(f"  PID: {app['pid']}")
            output_lines.append("")

        return "\n".join(output_lines)

    except Exception as e:
        if isinstance(e, XCodeMCPError):
            raise
        raise XCodeMCPError(f"Error listing applications: {e}")

@mcp.tool()
def list_mac_app_windows() -> str:
    """
    List all on-screen macOS application windows with their CGWindow IDs.
    These window IDs can be used to capture screenshots of a given window
    or app with `take_app_screenshot` or `take_window_screenshot`.

    Returns:
        A formatted list of windows grouped by application, including window IDs
        that can be used with `take_window_screenshot`.
    """
    show_notification("Xcode MCP", "Listing macOS application windows")

    try:
        # Use Swift to get window information via CoreGraphics
        swift_code = '''
import Cocoa
import CoreGraphics

// Get all on-screen windows
let options: CGWindowListOption = [.optionOnScreenOnly, .excludeDesktopElements]
guard let windowList = CGWindowListCopyWindowInfo(options, kCGNullWindowID) as? [[String: Any]] else {
    print("ERROR: Failed to get window list")
    exit(1)
}

// Group windows by app and filter out system UI elements
var appWindows: [String: [(id: Int, title: String, pid: Int)]] = [:]

for window in windowList {
    let windowID = window[kCGWindowNumber as String] as? Int ?? 0
    let appName = window[kCGWindowOwnerName as String] as? String ?? "Unknown"
    let windowTitle = window[kCGWindowName as String] as? String ?? ""
    let windowLayer = window[kCGWindowLayer as String] as? Int ?? 0
    let ownerPID = window[kCGWindowOwnerPID as String] as? Int ?? 0

    // Skip menu bar items and system UI (layer 0 is normal windows)
    // Also skip windows without titles
    if windowLayer == 0 && !windowTitle.isEmpty {
        if appWindows[appName] == nil {
            appWindows[appName] = []
        }
        appWindows[appName]?.append((id: windowID, title: windowTitle, pid: ownerPID))
    }
}

// Output as structured format for parsing
for (app, windows) in appWindows.sorted(by: { $0.key < $1.key }) {
    print("APP:\\(app)")
    for window in windows {
        print("WINDOW:\\(window.id)\\t\\(window.pid)\\t\\(window.title)")
    }
}
'''

        # Write Swift code to temporary file and execute
        import tempfile

        with tempfile.NamedTemporaryFile(mode='w', suffix='.swift', delete=False) as f:
            f.write(swift_code)
            temp_file = f.name

        try:
            # Run Swift code
            result = subprocess.run(
                ['swift', temp_file],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                raise XCodeMCPError(f"Failed to get window list: {result.stderr}")

            output = result.stdout

        finally:
            # Clean up temp file
            try:
                os.unlink(temp_file)
            except:
                pass

        # Check for error
        if output.startswith("ERROR:"):
            raise XCodeMCPError(output.replace("ERROR: ", ""))

        # Parse the output
        apps_with_windows = {}
        current_app = None

        for line in output.strip().split('\n'):
            if line.startswith('APP:'):
                current_app = line[4:]
                apps_with_windows[current_app] = []
            elif line.startswith('WINDOW:') and current_app:
                parts = line[7:].split('\t', 2)
                if len(parts) >= 3:
                    window_id = parts[0]
                    pid = parts[1]
                    title = parts[2]
                    apps_with_windows[current_app].append({
                        'id': window_id,
                        'pid': pid,
                        'title': title
                    })

        if not apps_with_windows:
            return "No visible windows found"

        # Format output - one line per window
        output_lines = []
        total_windows = sum(len(windows) for windows in apps_with_windows.values())
        output_lines.append(f"Found {total_windows} window(s) across {len(apps_with_windows)} application(s):")
        output_lines.append("")

        # Sort windows by app name for consistent output
        for app_name, windows in sorted(apps_with_windows.items()):
            for window in windows:
                output_lines.append(f"Window ID {window['id']} - \"{window['title']}\" - App PID {window['pid']} - \"{app_name}\"")

        output_lines.append("")
        output_lines.append("Use with `take_window_screenshot`.")

        return "\n".join(output_lines)

    except Exception as e:
        if isinstance(e, XCodeMCPError):
            raise
        raise XCodeMCPError(f"Error listing windows: {e}")

@mcp.tool()
def take_window_screenshot(window_id_or_name: str) -> str:
    """
    Take a screenshot of a window by ID or name (case-insensitive substring match).
    Window IDs can be obtained by calling `list_mac_app_windows`, or you can simply
    pass a partial (or complete) window title, like "News" for the News app.
    If multiple windows match the provided name, screenshots will be taken for up to
    the first 5 of them.
    
    Note: Only on-screen windows can be found by name.

    Args:
        window_id_or_name: Window ID number or partial window title to match.

    Returns:
        Path(s) to saved screenshot file(s), one per line if multiple matches.

    Raises:
        XCodeMCPError: If no matching windows found or screenshot fails.
    """
    show_notification("Xcode MCP", f"Taking screenshot of window: {window_id_or_name}")

    try:
        # First, get all windows
        windows_data = _get_all_windows()

        matches = []

        # Try to interpret as window ID first
        try:
            target_id = int(window_id_or_name)
            for app_name, windows in windows_data.items():
                for window in windows:
                    if window['id'] == target_id:
                        matches.append((window['id'], window['title'], app_name))
                        break
                if matches:
                    break
        except ValueError:
            # Not a number, search by title substring (case-insensitive)
            search_term = window_id_or_name.lower()
            for app_name, windows in windows_data.items():
                for window in windows:
                    if search_term in window['title'].lower():
                        matches.append((window['id'], window['title'], app_name))

        if not matches:
            raise XCodeMCPError(f"No windows found matching '{window_id_or_name}'")

        # Take screenshots
        import uuid
        screenshot_paths = []
        timestamp = time.strftime("%Y%m%d_%H%M%S")

        # Create screenshot directory
        screenshot_dir = "/tmp/xcode-mcp-server/screenshots"
        os.makedirs(screenshot_dir, exist_ok=True)

        for window_id, window_title, app_name in matches:
            # Sanitize window title for filename
            safe_title = "".join(c for c in window_title if c.isalnum() or c in (' ', '-', '_')).rstrip()[:50]
            safe_app = "".join(c for c in app_name if c.isalnum() or c in (' ', '-', '_')).rstrip()[:30]
            unique_id = uuid.uuid4().hex[:8]

            filename = f"window_{window_id}_{safe_app}_{safe_title}_{timestamp}_{unique_id}.png"
            screenshot_path = os.path.join(screenshot_dir, filename)

            # Take the screenshot using screencapture (-x flag disables sound)
            result = subprocess.run(
                ['screencapture', '-x', '-l', str(window_id), screenshot_path],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                raise XCodeMCPError(f"Failed to capture window {window_id}: {result.stderr}")

            # Verify file was created
            if not os.path.exists(screenshot_path):
                raise XCodeMCPError(f"Screenshot file was not created for window {window_id}")

            screenshot_paths.append(screenshot_path)

        return "\n".join(screenshot_paths)

    except Exception as e:
        if isinstance(e, XCodeMCPError):
            raise
        raise XCodeMCPError(f"Error taking window screenshot: {e}")

@mcp.tool()
def take_app_screenshot(app_name: str) -> str:
    """
    Take screenshots of all windows for an app (case-insensitive substring match).
    If the app has more than one window, screenshots will be taken for up to 5 of them.

    Note: Only apps with at least one on-screen window can be found by this tool.
    
    Args:
        app_name: Full or partial app name to match.

    Returns:
        Path(s) to saved screenshot file(s), one per line (max 5 windows).
        If multiple apps match, returns an error with the full window list.

    Raises:
        XCodeMCPError: If no matching app found, multiple apps match, or screenshot fails.
    """
    show_notification("Xcode MCP", f"Taking screenshots for app: {app_name}")

    try:
        # Get all windows
        windows_data = _get_all_windows()

        # Find matching apps (case-insensitive substring match)
        search_term = app_name.lower()
        matching_apps = {}

        for app, windows in windows_data.items():
            if search_term in app.lower():
                matching_apps[app] = windows

        if not matching_apps:
            raise XCodeMCPError(f"No apps found matching '{app_name}'")

        # If multiple apps match, return error with window list
        if len(matching_apps) > 1:
            output_lines = [f"Multiple apps match '{app_name}'. Please be more specific:"]
            output_lines.append("")

            total_windows = sum(len(windows) for windows in matching_apps.values())
            output_lines.append(f"Found {total_windows} window(s) across {len(matching_apps)} matching application(s):")
            output_lines.append("")

            for app, windows in sorted(matching_apps.items()):
                for window in windows:
                    output_lines.append(f"Window ID {window['id']} - \"{window['title']}\" - App PID {window['pid']} - \"{app}\"")

            raise XCodeMCPError("\n".join(output_lines))

        # Single app matched - take screenshots of all its windows (max 5)
        app_matched = list(matching_apps.keys())[0]
        windows = matching_apps[app_matched]

        if not windows:
            raise XCodeMCPError(f"App '{app_matched}' has no visible windows")

        # Limit to 5 windows
        windows = windows[:5]

        # Take screenshots
        import uuid
        screenshot_paths = []
        timestamp = time.strftime("%Y%m%d_%H%M%S")

        # Create screenshot directory
        screenshot_dir = "/tmp/xcode-mcp-server/screenshots"
        os.makedirs(screenshot_dir, exist_ok=True)

        for window in windows:
            # Sanitize names for filename
            safe_title = "".join(c for c in window['title'] if c.isalnum() or c in (' ', '-', '_')).rstrip()[:50]
            safe_app = "".join(c for c in app_matched if c.isalnum() or c in (' ', '-', '_')).rstrip()[:30]
            unique_id = uuid.uuid4().hex[:8]

            filename = f"app_{safe_app}_window_{window['id']}_{safe_title}_{timestamp}_{unique_id}.png"
            screenshot_path = os.path.join(screenshot_dir, filename)

            # Take the screenshot using screencapture (-x flag disables sound)
            result = subprocess.run(
                ['screencapture', '-x', '-l', str(window['id']), screenshot_path],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                raise XCodeMCPError(f"Failed to capture window {window['id']}: {result.stderr}")

            # Verify file was created
            if not os.path.exists(screenshot_path):
                raise XCodeMCPError(f"Screenshot file was not created for window {window['id']}")

            screenshot_paths.append(screenshot_path)

        return "\n".join(screenshot_paths)

    except Exception as e:
        if isinstance(e, XCodeMCPError):
            raise
        raise XCodeMCPError(f"Error taking app screenshot: {e}")

def _get_all_windows():
    """
    Internal helper to get all windows grouped by app.
    Returns a dict of {app_name: [window_info, ...]}
    """
    # Use Swift to get window information via CoreGraphics
    swift_code = '''
import Cocoa
import CoreGraphics

// Get all on-screen windows
let options: CGWindowListOption = [.optionOnScreenOnly, .excludeDesktopElements]
guard let windowList = CGWindowListCopyWindowInfo(options, kCGNullWindowID) as? [[String: Any]] else {
    print("ERROR: Failed to get window list")
    exit(1)
}

// Group windows by app and filter out system UI elements
var appWindows: [String: [(id: Int, title: String, pid: Int)]] = [:]

for window in windowList {
    let windowID = window[kCGWindowNumber as String] as? Int ?? 0
    let appName = window[kCGWindowOwnerName as String] as? String ?? "Unknown"
    let windowTitle = window[kCGWindowName as String] as? String ?? ""
    let windowLayer = window[kCGWindowLayer as String] as? Int ?? 0
    let ownerPID = window[kCGWindowOwnerPID as String] as? Int ?? 0

    // Skip menu bar items and system UI (layer 0 is normal windows)
    // Also skip windows without titles
    if windowLayer == 0 && !windowTitle.isEmpty {
        if appWindows[appName] == nil {
            appWindows[appName] = []
        }
        appWindows[appName]?.append((id: windowID, title: windowTitle, pid: ownerPID))
    }
}

// Output as structured format for parsing
for (app, windows) in appWindows.sorted(by: { $0.key < $1.key }) {
    print("APP:\\(app)")
    for window in windows {
        print("WINDOW:\\(window.id)\\t\\(window.pid)\\t\\(window.title)")
    }
}
'''

    # Write Swift code to temporary file and execute
    import tempfile

    with tempfile.NamedTemporaryFile(mode='w', suffix='.swift', delete=False) as f:
        f.write(swift_code)
        temp_file = f.name

    try:
        # Run Swift code
        result = subprocess.run(
            ['swift', temp_file],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            raise XCodeMCPError(f"Failed to get window list: {result.stderr}")

        output = result.stdout

    finally:
        # Clean up temp file
        try:
            os.unlink(temp_file)
        except:
            pass

    # Check for error
    if output.startswith("ERROR:"):
        raise XCodeMCPError(output.replace("ERROR: ", ""))

    # Parse the output
    apps_with_windows = {}
    current_app = None

    for line in output.strip().split('\n'):
        if line.startswith('APP:'):
            current_app = line[4:]
            apps_with_windows[current_app] = []
        elif line.startswith('WINDOW:') and current_app:
            parts = line[7:].split('\t', 2)
            if len(parts) >= 3:
                window_id = int(parts[0])
                pid = parts[1]
                title = parts[2]
                apps_with_windows[current_app].append({
                    'id': window_id,
                    'pid': pid,
                    'title': title
                })

    return apps_with_windows

# =============================================================================
# Test-related helper functions
# =============================================================================

def format_test_identifier(bundle: str, class_name: str = None, method: str = None) -> str:
    """
    Format test identifier in standard format.
    Returns: "Bundle/Class/method" or "Bundle/Class" or "Bundle"
    """
    if method and class_name:
        return f"{bundle}/{class_name}/{method}"
    elif class_name:
        return f"{bundle}/{class_name}"
    else:
        return bundle

def parse_test_failures(failures_text: str) -> List[Dict[str, str]]:
    """
    Parse test failure information from AppleScript result.
    Returns list of failure dictionaries with message, file_path, etc.
    Note: This is rarely used now since AppleScript test failures collection
    is often empty; we primarily rely on extract_test_failures_from_log() instead.
    """
    failures = []
    if not failures_text or failures_text == "missing value" or failures_text.strip() == "":
        return failures

    # Parse the structured format from AppleScript
    current_failure = {}
    for line in failures_text.strip().split('\n'):
        line = line.strip()
        if line.startswith("FAILURE: "):
            if current_failure:
                failures.append(current_failure)
            current_failure = {"message": line[9:], "file_path": "", "line_number": "", "test_class": "", "test_method": ""}
        elif line.startswith("FILE: "):
            if current_failure:
                current_failure["file_path"] = line[6:]
        elif line.startswith("LINE: "):
            if current_failure:
                current_failure["line_number"] = line[6:]
        elif line.startswith("ERROR: "):
            # Handle error message about failure retrieval
            if not failures:
                failures.append({"message": line[7:], "file_path": "", "line_number": "", "test_class": "", "test_method": ""})
        elif line == "---":
            if current_failure:
                failures.append(current_failure)
                current_failure = {}
        elif line and not line.startswith("---"):
            # Handle single line failure messages
            if not current_failure and line not in ["", "Failures:"]:
                failures.append({"message": line, "file_path": "", "line_number": "", "test_class": "", "test_method": ""})

    # Add last failure if exists
    if current_failure and current_failure.get("message"):
        failures.append(current_failure)

    return failures

def extract_test_statistics(build_log: str) -> Dict[str, Any]:
    """
    Extract test counts and timing from build log.
    """
    stats = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "duration": 0.0
    }

    if not build_log:
        return stats

    # Look for test summary lines in build log
    # Example: "Test Suite 'All tests' passed at 2024-01-01 12:00:00.000."
    # Example: "Executed 42 tests, with 2 failures (0 unexpected) in 12.500 (12.501) seconds"

    for line in build_log.split('\n'):
        # Check for test execution summary
        if "Executed" in line and "tests" in line:
            import re
            # Try to extract numbers
            executed_match = re.search(r'Executed (\d+) test', line)
            if executed_match:
                stats["total"] = int(executed_match.group(1))

            failures_match = re.search(r'(\d+) failure', line)
            if failures_match:
                stats["failed"] = int(failures_match.group(1))
                stats["passed"] = stats["total"] - stats["failed"]
            elif "0 failures" in line or "passed" in line.lower():
                stats["passed"] = stats["total"]

            # Extract duration
            duration_match = re.search(r'in ([\d.]+)', line)
            if duration_match:
                stats["duration"] = float(duration_match.group(1))

    return stats

def extract_test_failures_from_log(build_log: str) -> List[Dict[str, str]]:
    """
    Extract test failure details from the build log when the test failures
    collection from AppleScript is empty.
    """
    import re
    failures = []
    seen_failures = set()  # Track unique failures to avoid duplicates

    if not build_log:
        return failures

    lines = build_log.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]

        # Look for test failure patterns
        # Pattern 1: "Test Case '-[TestClass testMethod]' failed (x.xx seconds)"
        if "Test Case" in line and "failed" in line:
            match = re.search(r"Test Case '?-?\[(\w+)\s+(\w+)\]'?\s+failed", line)
            if match:
                test_class = match.group(1)
                test_method = match.group(2)

                # Extract failure message and location from surrounding lines
                failure_msg = ""
                file_path = ""
                line_num = ""

                # Look at next few lines for assertion details
                for j in range(i + 1, min(i + 5, len(lines))):
                    next_line = lines[j]

                    # Look for XCTAssert failures or error messages
                    if "XCTAssert" in next_line or "failed" in next_line.lower():
                        if not failure_msg:
                            failure_msg = next_line.strip()

                    # Look for file:line patterns
                    file_match = re.search(r'([\w/\-\.]+\.swift):(\d+)', next_line)
                    if file_match and not file_path:
                        file_path = file_match.group(1)
                        line_num = file_match.group(2)

                # Create a unique key to avoid duplicates
                failure_key = f"{test_class}.{test_method}:{file_path}:{line_num}"
                if failure_key not in seen_failures:
                    seen_failures.add(failure_key)
                    failures.append({
                        "test_class": test_class,
                        "test_method": test_method,
                        "message": failure_msg or f"Test {test_class}.{test_method} failed",
                        "file_path": file_path,
                        "line_number": line_num
                    })

        # Pattern 2: XCTest output format with file location
        # "	Executed 1 test, with 1 failure (0 unexpected) in 0.123 (0.456) seconds"
        # "/path/to/TestFile.swift:42: error: -[TestClass testMethod] : XCTAssertEqual failed..."
        elif ": error: -[" in line:
            match = re.search(r'([\w/\-\.]+\.swift):(\d+):\s*error:\s*-\[(\w+)\s+(\w+)\]\s*:\s*(.+)', line)
            if match:
                file_path = match.group(1)
                line_num = match.group(2)
                test_class = match.group(3)
                test_method = match.group(4)
                failure_msg = match.group(5)

                # Create a unique key to avoid duplicates
                failure_key = f"{test_class}.{test_method}:{file_path}:{line_num}"
                if failure_key not in seen_failures:
                    seen_failures.add(failure_key)
                    failures.append({
                        "test_class": test_class,
                        "test_method": test_method,
                        "message": failure_msg,
                        "file_path": file_path,
                        "line_number": line_num
                    })

        # Pattern 3: Xcode 15+ format with ❌ emoji
        # "❌ /path/to/file.swift:123: XCTAssertEqual failed: ("actual") is not equal to ("expected")"
        elif "❌" in line:
            # Try to extract file path, line, and message
            match = re.search(r'❌\s+([\w/\-\.]+\.swift):(\d+):\s*(.+)', line)
            if not match:
                # Try alternate format without file path
                match = re.search(r'❌\s+(.+)', line)
                if match:
                    failure_msg = match.group(1)
                    file_path = ""
                    line_num = ""
                else:
                    i += 1
                    continue
            else:
                file_path = match.group(1)
                line_num = match.group(2)
                failure_msg = match.group(3)

            # Try to extract test name from previous lines
            test_class = ""
            test_method = ""
            for j in range(max(0, i-5), i):
                if "Test Case" in lines[j] or "-[" in lines[j]:
                    name_match = re.search(r'-\[(\w+)\s+(\w+)\]', lines[j])
                    if name_match:
                        test_class = name_match.group(1)
                        test_method = name_match.group(2)
                        break

            # Create a unique key to avoid duplicates
            failure_key = f"{test_class or 'Unknown'}.{test_method or 'Unknown'}:{file_path}:{line_num}"
            if failure_key not in seen_failures:
                seen_failures.add(failure_key)
                failures.append({
                    "test_class": test_class or "Unknown",
                    "test_method": test_method or "Unknown",
                    "message": failure_msg,
                    "file_path": file_path,
                    "line_number": line_num
                })

        # Pattern 4: Test Suite failures
        # "Test Suite 'TestClassName' failed at 2024-01-01 12:00:00.000"
        elif "Test Suite" in line and "failed" in line:
            match = re.search(r"Test Suite '(\w+)' failed", line)
            if match:
                test_class = match.group(1)
                # Look for details in next lines
                failure_msg = f"Test suite {test_class} failed"
                for j in range(i + 1, min(i + 3, len(lines))):
                    if "Executed" in lines[j] and "failure" in lines[j]:
                        failure_msg = lines[j].strip()
                        break

                # For suite failures, we only track by test class name
                failure_key = f"{test_class}.Suite"
                if failure_key not in seen_failures:
                    seen_failures.add(failure_key)
                    failures.append({
                        "test_class": test_class,
                        "test_method": "Suite",
                        "message": failure_msg,
                        "file_path": "",
                        "line_number": ""
                    })

        # Pattern 5: Simple failure messages with test name context
        # "XCTAssertTrue failed - Some description"
        elif re.search(r'XCTAssert\w+\s+failed', line):
            failure_msg = line.strip()

            # Try to find test context from previous lines
            test_class = ""
            test_method = ""
            file_path = ""
            line_num = ""

            # Look back for test case info
            for j in range(max(0, i-10), i):
                if "Test Case" in lines[j]:
                    name_match = re.search(r'-\[(\w+)\s+(\w+)\]', lines[j])
                    if name_match:
                        test_class = name_match.group(1)
                        test_method = name_match.group(2)
                        break

            # Look for file location
            file_match = re.search(r'([\w/\-\.]+\.swift):(\d+)', line)
            if file_match:
                file_path = file_match.group(1)
                line_num = file_match.group(2)

            if test_class or test_method or failure_msg != line.strip():
                # Create a unique key to avoid duplicates
                failure_key = f"{test_class or 'Unknown'}.{test_method or 'Unknown'}:{file_path}:{line_num}:{failure_msg[:50]}"
                if failure_key not in seen_failures:
                    seen_failures.add(failure_key)
                    failures.append({
                        "test_class": test_class or "Unknown",
                        "test_method": test_method or "Unknown",
                        "message": failure_msg,
                        "file_path": file_path,
                        "line_number": line_num
                    })

        i += 1

    # If we still don't have specific failures but know tests failed,
    # try to extract any useful information
    if not failures and ("failed" in build_log.lower() or "❌" in build_log):
        # Look for summary lines
        for line in lines:
            if "Executed" in line and "failure" in line:
                match = re.search(r'Executed (\d+) tests?, with (\d+) failures?', line)
                if match:
                    test_count = match.group(1)
                    failure_count = match.group(2)
                    failures.append({
                        "test_class": "TestSuite",
                        "test_method": "Multiple",
                        "message": f"Executed {test_count} tests with {failure_count} failures (details not available in log)",
                        "file_path": "",
                        "line_number": ""
                    })
                    break

        # If still nothing, add generic failure
        if not failures:
            failures.append({
                "test_class": "Unknown",
                "test_method": "Unknown",
                "message": "Tests failed (specific details could not be extracted from log)",
                "file_path": "",
                "line_number": ""
            })

    return failures

def find_xcresult_bundle(project_path: str) -> Optional[str]:
    """
    Find the most recent .xcresult bundle for the project.
    """
    # Get project name for searching
    project_name = os.path.basename(project_path).replace('.xcodeproj', '').replace('.xcworkspace', '')

    # Common locations for xcresult bundles
    derived_data_paths = [
        os.path.expanduser(f"~/Library/Developer/Xcode/DerivedData"),
        "/tmp/XCBuildData"
    ]

    newest_xcresult = None
    newest_time = 0

    for base_path in derived_data_paths:
        if not os.path.exists(base_path):
            continue

        # Search for xcresult files
        try:
            result = subprocess.run(
                ['find', base_path, '-name', '*.xcresult', '-type', 'd'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and result.stdout:
                for path in result.stdout.strip().split('\n'):
                    if path and os.path.exists(path):
                        # Check if this is related to our project
                        if project_name.lower() in path.lower():
                            stat = os.stat(path)
                            if stat.st_mtime > newest_time:
                                newest_time = stat.st_mtime
                                newest_xcresult = path
        except:
            continue

    return newest_xcresult

# =============================================================================
# Test-related MCP tools
# =============================================================================

@mcp.tool()
def list_project_tests(project_path: str) -> str:
    """
    List all available tests in the specified Xcode project or workspace.

    Args:
        project_path: Path to Xcode project/workspace directory

    Returns:
        A list of all test identifiers in the format:
        BundleName/ClassName/testMethodName
    """
    show_notification("Xcode MCP", f"Listing tests for {os.path.basename(project_path)}")

    # Validate and normalize the project path
    project_path = validate_and_normalize_project_path(project_path, "list_project_tests")

    # Escape for AppleScript
    escaped_path = escape_applescript_string(project_path)

    # Note: There's no direct way to list all tests via AppleScript,
    # so we'll look for test files in the project directory

    # Try to find test files in the project
    try:
        # Find test files in the project directory
        project_dir = os.path.dirname(project_path)
        test_files = []

        result = subprocess.run(
            ['find', project_dir, '-name', '*Tests.swift', '-o', '-name', '*Test.swift'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0 and result.stdout:
            test_files = result.stdout.strip().split('\n')

            # Parse test files to extract test methods
            tests = []
            for file_path in test_files:
                if file_path and os.path.exists(file_path):
                    try:
                        with open(file_path, 'r') as f:
                            content = f.read()
                            # Extract test class name from filename
                            filename = os.path.basename(file_path)
                            class_name = filename.replace('.swift', '')

                            # Find test methods (simple regex)
                            import re
                            test_methods = re.findall(r'func\s+(test\w+)\s*\(', content)

                            for method in test_methods:
                                # Guess bundle name from path
                                if 'UITests' in file_path:
                                    bundle = f"{os.path.basename(project_path).replace('.xcodeproj', '').replace('.xcworkspace', '')}UITests"
                                else:
                                    bundle = f"{os.path.basename(project_path).replace('.xcodeproj', '').replace('.xcworkspace', '')}Tests"

                                tests.append(f"{bundle}/{class_name}/{method}")
                    except:
                        continue

            if tests:
                return "\n".join(sorted(tests))

        return f"Could not find test files for project: {os.path.basename(project_path)}\n" + \
               "Make sure your test files follow naming convention (*Test.swift or *Tests.swift)"

    except Exception as e:
        return f"Error listing tests: {str(e)}"

@mcp.tool()
def run_project_tests(project_path: str,
                     tests_to_run: Optional[List[str]] = None,
                     scheme: Optional[str] = None,
                     wait_for_completion: bool = True,
                     max_wait_seconds: int = 300) -> str:
    """
    Run tests for the specified Xcode project or workspace.

    Args:
        project_path: Path to Xcode project/workspace directory
        tests_to_run: Optional list of test identifiers to run.
                     If None or empty list, runs ALL tests.
                     Format: ["BundleName/ClassName/testMethod", ...]
        scheme: Optional scheme to test (uses active scheme if not specified)
        wait_for_completion: If True, waits for tests to complete and returns results.
                           If False, starts tests and returns immediately.
        max_wait_seconds: Maximum seconds to wait for completion (default 300)

    Returns:
        Test results if wait_for_completion is True, otherwise confirmation message
    """
    show_notification("Xcode MCP", f"Running tests for {os.path.basename(project_path)}")

    # Validate and normalize the project path
    project_path = validate_and_normalize_project_path(project_path, "run_project_tests")

    # Validate wait time
    if max_wait_seconds < 0:
        raise InvalidParameterError("max_wait_seconds must be >= 0")

    # Handle various forms of empty/invalid tests_to_run parameter
    # This works around MCP client issues with optional list parameters
    if tests_to_run is not None:
        # Handle string inputs that might come from the client
        if isinstance(tests_to_run, str):
            tests_to_run = tests_to_run.strip()
            if not tests_to_run or tests_to_run in ['[]', 'null', 'undefined', '']:
                tests_to_run = None
            else:
                # Try to parse as a comma-separated list
                tests_to_run = [t.strip() for t in tests_to_run.split(',') if t.strip()]
        elif not tests_to_run:  # Empty list or other falsy value
            tests_to_run = None

    # Escape for AppleScript
    escaped_path = escape_applescript_string(project_path)

    # Build test arguments
    test_args = []
    if tests_to_run:  # If list is provided and not empty
        for test_id in tests_to_run:
            # Add -only-testing: prefix for each test
            test_args.append(f'-only-testing:{test_id}')
    # If tests_to_run is None or [], we run all tests (no arguments needed)

    # Build the AppleScript
    if test_args:
        # Format arguments for AppleScript list
        args_list = ', '.join([f'"{escape_applescript_string(arg)}"' for arg in test_args])
        test_command = f'test workspaceDoc with command line arguments {{{args_list}}}'
    else:
        # Run all tests
        test_command = 'test workspaceDoc'

    # Build the script differently based on wait_for_completion
    if wait_for_completion:
        wait_section = f'''set waitTime to 0
    repeat while waitTime < {max_wait_seconds}
        if completed of testResult is true then
            exit repeat
        end if
        delay 1
        set waitTime to waitTime + 1
    end repeat

    -- Get results
    set testStatus to status of testResult as string
    set testCompleted to completed of testResult

    -- Get failures if any with full details
    set failureMessages to ""
    set failureCount to 0
    try
        set failures to test failures of testResult
        set failureCount to count of failures
        if failureCount > 0 then
            repeat with failure in failures
                set failureMsg to ""
                set failurePath to ""
                set failureLine to ""

                try
                    set failureMsg to message of failure
                on error
                    set failureMsg to "Unknown test failure"
                end try

                try
                    set failurePath to file path of failure
                end try

                try
                    set failureLine to starting line number of failure as string
                end try

                set failureMessages to failureMessages & "FAILURE: " & failureMsg & "\\n"
                if failurePath is not "" and failurePath is not missing value then
                    set failureMessages to failureMessages & "FILE: " & failurePath & "\\n"
                end if
                if failureLine is not "" and failureLine is not "missing value" then
                    set failureMessages to failureMessages & "LINE: " & failureLine & "\\n"
                end if
                set failureMessages to failureMessages & "---\\n"
            end repeat
        else
            -- No test failures in collection, but status might still be failed
            -- This happens when tests fail but the failures collection is empty
            -- We'll parse the build log later to extract actual failure details
            if testStatus is "failed" or testStatus contains "fail" then
                set failureMessages to "PARSE_FROM_LOG" & "\\n"
            end if
        end if
    on error errMsg
        -- Could not access test failures
        if testStatus is "failed" or testStatus contains "fail" then
            set failureMessages to "PARSE_FROM_LOG" & "\\n"
        end if
    end try

    -- Get build log for statistics
    set buildLog to ""
    try
        set buildLog to build log of testResult
    end try

    return "Status: " & testStatus & "\\n" & ¬
           "Completed: " & testCompleted & "\\n" & ¬
           "FailureCount: " & (failureCount as string) & "\\n" & ¬
           "Failures:\\n" & failureMessages & "\\n" & ¬
           "---LOG---\\n" & buildLog'''
    else:
        wait_section = 'return "Tests started successfully"'

    script = f'''
set projectPath to "{escaped_path}"

tell application "Xcode"
    -- Wait for any modal dialogs to be dismissed
    delay 0.5

    -- Open and get the workspace document
    open projectPath
    delay 2

    -- Get the workspace document
    set workspaceDoc to first workspace document whose path is projectPath

    -- Wait for workspace to load
    set loadWaitTime to 0
    repeat while loadWaitTime < 60
        if loaded of workspaceDoc is true then
            exit repeat
        end if
        delay 0.5
        set loadWaitTime to loadWaitTime + 0.5
    end repeat

    if loaded of workspaceDoc is false then
        error "Workspace failed to load within timeout"
    end if

    -- Set scheme if specified
    {f'set active scheme of workspaceDoc to scheme "{escape_applescript_string(scheme)}" of workspaceDoc' if scheme else ''}

    -- Start the test
    set testResult to {test_command}

    {'-- Wait for completion' if wait_for_completion else '-- Return immediately'}
    {wait_section}
end tell
    '''

    success, output = run_applescript(script)

    if not success:
        return f"Failed to run tests: {output}"

    if not wait_for_completion:
        return "✅ Tests have been started. Use get_latest_test_results to check results later."

    # Debug: Log raw output to see what we're getting
    print(f"DEBUG: Raw test output:\n{output}\n", file=sys.stderr)

    # Parse the results
    lines = output.split('\n')
    status = ""
    completed = False
    failure_count = 0
    failures_text = []
    build_log = []
    in_log = False
    in_failures = False

    for line in lines:
        if line.startswith("Status: "):
            status = line.replace("Status: ", "").strip()
        elif line.startswith("Completed: "):
            completed = line.replace("Completed: ", "").strip().lower() == "true"
        elif line.startswith("FailureCount: "):
            try:
                failure_count = int(line.replace("FailureCount: ", "").strip())
            except:
                failure_count = 0
        elif line.startswith("Failures:"):
            in_failures = True
            in_log = False
        elif line.startswith("---LOG---"):
            in_log = True
            in_failures = False
        elif in_failures and not line.startswith("---LOG"):
            failures_text.append(line)
        elif in_log:
            build_log.append(line)

    # Parse statistics from build log
    build_log_str = '\n'.join(build_log)
    stats = extract_test_statistics(build_log_str)

    # Save build log for debugging if environment variable is set
    if os.environ.get('XCODE_MCP_DEBUG_LOGS'):
        import tempfile
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = os.path.join(tempfile.gettempdir(), f"xcode_mcp_test_log_{timestamp}.txt")
        try:
            with open(log_path, 'w') as f:
                f.write(f"Test run at {timestamp}\n")
                f.write(f"Project: {project_path}\n")
                f.write(f"Status: {status}\n")
                f.write(f"Completed: {completed}\n")
                f.write(f"Failure count: {failure_count}\n")
                f.write("\n--- BUILD LOG ---\n")
                f.write(build_log_str)
                f.write("\n--- FAILURES TEXT ---\n")
                f.write('\n'.join(failures_text))
            print(f"DEBUG: Test log saved to {log_path}", file=sys.stderr)
        except Exception as e:
            print(f"DEBUG: Failed to save test log: {e}", file=sys.stderr)

    # Parse failures
    failures = []
    failures_str = '\n'.join(failures_text)

    # Check if we need to parse failures from the build log
    if "PARSE_FROM_LOG" in failures_str and build_log_str:
        # Debug: Log that we're parsing from log
        print(f"DEBUG: Parsing test failures from build log (AppleScript collection was empty)", file=sys.stderr)
        print(f"DEBUG: Build log length: {len(build_log_str)} chars", file=sys.stderr)

        # Extract test failures from build log
        failures = extract_test_failures_from_log(build_log_str)
        failure_count = len(failures)

        print(f"DEBUG: Found {len(failures)} failures from build log parsing", file=sys.stderr)
        for idx, failure in enumerate(failures):
            print(f"DEBUG: Failure {idx + 1}: {failure.get('test_class', 'Unknown')}.{failure.get('test_method', 'Unknown')} - {failure.get('message', 'No message')}", file=sys.stderr)
    else:
        # Parse from AppleScript output
        failures = parse_test_failures(failures_str)

    # Use failure count if we have it
    if failure_count > 0 and stats["failed"] == 0:
        stats["failed"] = failure_count

    # If we didn't get stats from build log, try to get from xcresult
    if stats["total"] == 0 and completed:
        # Wait a moment for xcresult to be written
        time.sleep(2)
        xcresult_path = find_xcresult_bundle(project_path)
        if xcresult_path:
            try:
                # Try to get test count from xcresult
                result = subprocess.run(
                    ['xcrun', 'xcresulttool', 'get', '--path', xcresult_path, '--format', 'json'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    import json
                    data = json.loads(result.stdout)
                    if 'metrics' in data:
                        metrics = data['metrics']
                        if 'testsCount' in metrics:
                            stats["total"] = metrics.get('testsCount', {}).get('_value', 0)
                        if 'testsFailedCount' in metrics:
                            stats["failed"] = metrics.get('testsFailedCount', {}).get('_value', 0)
                            stats["passed"] = stats["total"] - stats["failed"]
            except:
                pass

    # Format the output
    output_lines = []

    if not completed:
        output_lines.append(f"⏳ Tests did not complete within {max_wait_seconds} seconds")
        output_lines.append(f"Status: {status}")
        return '\n'.join(output_lines)

    # Determine overall result
    if status == "succeeded" or (stats["total"] > 0 and stats["failed"] == 0):
        output_lines.append("✅ All tests passed")
    elif status == "failed" or stats["failed"] > 0:
        output_lines.append("❌ Tests failed")
    else:
        output_lines.append(f"Status: {status}")

    output_lines.append("")
    output_lines.append("Summary:")
    if stats["total"] > 0:
        output_lines.append(f"- Total: {stats['total']} tests")
        output_lines.append(f"- Passed: {stats['passed']}")
        output_lines.append(f"- Failed: {stats['failed']}")
        if stats["skipped"] > 0:
            output_lines.append(f"- Skipped: {stats['skipped']}")
        if stats["duration"] > 0:
            output_lines.append(f"- Duration: {stats['duration']:.1f} seconds")
    else:
        output_lines.append("- No detailed test statistics available from Xcode")
        output_lines.append(f"- Test run status: {status}")
        if status == "succeeded":
            output_lines.append("- All tests in scheme passed successfully")

    if failures:
        output_lines.append("")
        output_lines.append(f"Failed Tests ({len(failures)}):")
        for i, failure in enumerate(failures, 1):
            # Format test identifier if available
            test_id = ""
            if failure.get('test_class') and failure['test_class'] != "Unknown":
                test_id = f"[{failure['test_class']}"
                if failure.get('test_method') and failure['test_method'] != "Unknown":
                    test_id += f".{failure['test_method']}"
                test_id += "] "

            output_lines.append(f"\n{i}. {test_id}{failure.get('message', 'Test failed')}")

            # Add location if available
            if failure.get('file_path') and failure['file_path'] not in ["", "missing value"]:
                location = failure['file_path']
                if failure.get('line_number') and failure['line_number'] not in ["", "missing value"]:
                    location += f":{failure['line_number']}"
                output_lines.append(f"   Location: {location}")

    return '\n'.join(output_lines)

@mcp.tool()
def get_latest_test_results(project_path: str) -> str:
    """
    Get the test results from the most recent test run.

    Args:
        project_path: Path to Xcode project/workspace directory

    Returns:
        Latest test results or "No test results available"
    """
    show_notification("Xcode MCP", f"Getting test results for {os.path.basename(project_path)}")

    # Validate and normalize the project path
    project_path = validate_and_normalize_project_path(project_path, "get_latest_test_results")

    # Try to find the most recent xcresult bundle
    xcresult_path = find_xcresult_bundle(project_path)

    if xcresult_path and os.path.exists(xcresult_path):
        # Extract test results from xcresult bundle
        try:
            # Get test summary
            result = subprocess.run(
                ['xcrun', 'xcresulttool', 'get', '--path', xcresult_path, '--format', 'json'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                import json
                try:
                    data = json.loads(result.stdout)

                    # Parse the JSON to extract test information
                    output_lines = ["Test Results from xcresult bundle:", ""]

                    # Try to extract metrics
                    if 'metrics' in data:
                        metrics = data['metrics']
                        if 'testsCount' in metrics:
                            output_lines.append(f"Total tests: {metrics.get('testsCount', {}).get('_value', 'N/A')}")
                        if 'testsFailedCount' in metrics:
                            output_lines.append(f"Failed tests: {metrics.get('testsFailedCount', {}).get('_value', 0)}")

                    # Get modification time of xcresult
                    import datetime
                    mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(xcresult_path))
                    output_lines.append(f"Test run: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")

                    return '\n'.join(output_lines)
                except:
                    pass
        except:
            pass

    # Fallback: Try to get from Xcode via AppleScript
    escaped_path = escape_applescript_string(project_path)

    script = f'''
set projectPath to "{escaped_path}"

tell application "Xcode"
    try
        -- Try to get the workspace document if it's already open
        set workspaceDoc to first workspace document whose path is projectPath

        -- Try to get last scheme action result
        set lastResult to last scheme action result of workspaceDoc

        set resultStatus to status of lastResult as string
        set resultCompleted to completed of lastResult

        -- Check if it was a test action by looking for test failures
        set isTestResult to false
        set failureMessages to ""
        try
            set failures to test failures of lastResult
            set isTestResult to true
            repeat with failure in failures
                set failureMessages to failureMessages & (message of failure) & "\\n"
            end repeat
        end try

        if isTestResult then
            return "Last test status: " & resultStatus & "\\n" & ¬
                   "Completed: " & resultCompleted & "\\n" & ¬
                   "Test failures:\\n" & failureMessages
        else
            return "No test results available (last action was not a test)"
        end if
    on error
        return "No test results available"
    end try
end tell
    '''

    success, output = run_applescript(script)

    if success:
        return output
    else:
        return "No test results available"

# Main entry point for the server
if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Xcode MCP Server")
    parser.add_argument("--version", action="version", version=f"xcode-mcp-server {__import__('xcode_mcp_server').__version__}")
    parser.add_argument("--allowed", action="append", help="Add an allowed folder path (can be used multiple times)")
    parser.add_argument("--show-notifications", action="store_true", help="Enable notifications for tool invocations")
    parser.add_argument("--hide-notifications", action="store_true", help="Disable notifications for tool invocations")
    parser.add_argument("--no-build-warnings", action="store_true", help="Exclude warnings from build output")
    parser.add_argument("--always-include-build-warnings", action="store_true", help="Always include warnings in build output")
    args = parser.parse_args()
    
    # Handle notification settings
    if args.show_notifications and args.hide_notifications:
        print("Error: Cannot use both --show-notifications and --hide-notifications", file=sys.stderr)
        sys.exit(1)
    elif args.show_notifications:
        NOTIFICATIONS_ENABLED = True
        print("Notifications enabled", file=sys.stderr)
    elif args.hide_notifications:
        NOTIFICATIONS_ENABLED = False
        print("Notifications disabled", file=sys.stderr)

    # Handle build warning settings
    if args.no_build_warnings and args.always_include_build_warnings:
        print("Error: Cannot use both --no-build-warnings and --always-include-build-warnings", file=sys.stderr)
        sys.exit(1)
    elif args.no_build_warnings:
        BUILD_WARNINGS_ENABLED = False
        BUILD_WARNINGS_FORCED = False
        print("Build warnings forcibly disabled", file=sys.stderr)
    elif args.always_include_build_warnings:
        BUILD_WARNINGS_ENABLED = True
        BUILD_WARNINGS_FORCED = True
        print("Build warnings forcibly enabled", file=sys.stderr)
    
    # Initialize allowed folders from environment and command line
    ALLOWED_FOLDERS = get_allowed_folders(args.allowed)
    
    # Check if we have any allowed folders
    if not ALLOWED_FOLDERS:
        error_msg = """
========================================================================
ERROR: Xcode MCP Server cannot start - No valid allowed folders!
========================================================================

No valid folders were found to allow access to.

To fix this, you can either:

1. Set the XCODEMCP_ALLOWED_FOLDERS environment variable:
   export XCODEMCP_ALLOWED_FOLDERS="/path/to/folder1:/path/to/folder2"

2. Use the --allowed command line option:
   xcode-mcp-server --allowed /path/to/folder1 --allowed /path/to/folder2

3. Ensure your $HOME directory exists and is accessible

All specified folders must:
- Be absolute paths
- Exist on the filesystem
- Be directories (not files)
- Not contain '..' components

========================================================================
"""
        print(error_msg, file=sys.stderr)
        
        # Show macOS notification
        try:
            subprocess.run(['osascript', '-e', 
                          'display alert "Xcode MCP Server Error" message "No valid allowed folders found. Check your configuration."'], 
                          capture_output=True)
        except:
            pass  # Ignore notification errors
        
        sys.exit(1)
    
    # Debug info
    print(f"Total allowed folders: {ALLOWED_FOLDERS}", file=sys.stderr)
    
    # Run the server
    mcp.run() 
