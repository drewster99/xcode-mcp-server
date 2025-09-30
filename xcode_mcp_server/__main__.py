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
NOTIFICATIONS_ENABLED = False  # No type annotation to avoid global declaration issues
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
        always be preferred over using `xcodebuild`, `swift build`, or
        `swift package build`. Building with this tool ensures the build happens
        exactly the same way as when the user builds with Xcode, with all the same
        settings, so you will get the same results the user sees. The user can also
        see any results immediately and a subsequent build and run by the user will
        happen almost instantly for the user.

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
    max_retries = 3
    retry_delay = 2

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
    Get the hierarchy of the specified Xcode project or workspace.

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

    Args:
        project_path: Path to an Xcode project/workspace directory.
        wait_seconds: Maximum number of seconds to wait for the run to complete.
        scheme: Optional scheme to run. If not provided, uses the active scheme.
        max_lines: Maximum number of console log lines to return. Defaults to 100.
        regex_filter: Optional regex pattern to filter console output lines.

    Returns:
        Console output from the run, or status message if still running
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
    Get the runtime output from the console for the specified Xcode project.

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
