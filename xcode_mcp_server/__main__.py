#!/usr/bin/env python3
import os
import sys
import subprocess
import json
import argparse
from typing import Optional, Dict, List, Any, Tuple, Set
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP, Context

# Global variables for allowed folders
ALLOWED_FOLDERS: Set[str] = set()
NOTIFICATIONS_ENABLED = False  # No type annotation to avoid global declaration issues

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

    global ALLOWED_FOLDERS
    if not project_path:
        print(f"Warning: not project_path: {project_path}", file=sys.stderr)
        return False
    
    # If no allowed folders are specified, nothing is allowed
    if not ALLOWED_FOLDERS:
        print(f"Warning: ALLOWED_FOLDERS is empty, denying access", file=sys.stderr)
        return False
    
    # Normalize the path
    project_path = os.path.abspath(project_path).rstrip("/")
    
    # Check if path is in allowed folders
    print(f"Warning: Normalized project_path: {project_path}", file=sys.stderr)
    for allowed_folder in ALLOWED_FOLDERS:
        # Direct match
        if project_path == allowed_folder:
            print(f"direct match to {allowed_folder}", file=sys.stderr)
            return True
        
        # Path is a subfolder
        if project_path.startswith(allowed_folder + "/"):
            print(f"Match to startswith {allowed_folder}", file=sys.stderr)
            return True
        print(f"no match of {project_path} with allowed folder {allowed_folder}", file=sys.stderr)
    return False

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

        You might start with `get_frontmost_project` to see if the user currently
        has an Xcode project already open.

        You can call `get_xcode_projects` to find Xcode project (.xcodeproj) and
        Xcode workspace (.xcworkspace) folders under a given root folder.

        You can call `get_project_schemes` to get the build scheme names for a given
        .xcodeproj or .xcworkspace.

        Call build_project to build the project and get back the first 25 lines of
        error output. `build_project` will default to the active scheme if none is provided.
    """
)

# Helper functions for Xcode interaction
def get_frontmost_project() -> str:
    """
    Get the path to the frontmost Xcode project/workspace.
    Returns empty string if no project is open.
    """
    script = '''
    tell application "Xcode"
        if it is running then
            try
                tell application "System Events"
                    tell process "Xcode"
                        set frontWindow to name of front window
                    end tell
                end tell
                
                set docPath to ""
                try
                    set docPath to path of document 1
                end try
                
                return docPath
            on error errMsg
                return "ERROR: " & errMsg
            end try
        else
            return "ERROR: Xcode is not running"
        end if
    end tell
    '''
    try:
        result = subprocess.run(['osascript', '-e', script], 
                               capture_output=True, text=True, check=True)
        output = result.stdout.strip()
        
        # Check if we got an error message from our AppleScript
        if output.startswith("ERROR:"):
            print(f"AppleScript error: {output}")
            return ""
        
        return output
    except subprocess.CalledProcessError as e:
        print(f"Error executing AppleScript: {e.stderr}")
        return ""

def run_applescript(script: str) -> Tuple[bool, str]:
    """Run an AppleScript and return success status and output"""
    try:
        result = subprocess.run(['osascript', '-e', script], 
                               capture_output=True, text=True, check=True)
        return True, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return False, e.stderr.strip()

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
    # Validate input
    if not project_path or project_path.strip() == "":
        raise InvalidParameterError("project_path cannot be empty")
    
    project_path = project_path.strip()
    
    # Verify path ends with .xcodeproj or .xcworkspace
    if not (project_path.endswith('.xcodeproj') or project_path.endswith('.xcworkspace')):
        raise InvalidParameterError("project_path must end with '.xcodeproj' or '.xcworkspace'")
    
    show_notification("Xcode MCP", f"Getting hierarchy for {os.path.basename(project_path)}")
    
    # Security check
    if not is_path_allowed(project_path):
        raise AccessDeniedError(f"Access to path '{project_path}' is not allowed. Set XCODEMCP_ALLOWED_FOLDERS environment variable.")
    
    # Check if the path exists
    if not os.path.exists(project_path):
        raise InvalidParameterError(f"Project path does not exist: {project_path}")
    
    # Get the parent directory to scan
    parent_dir = os.path.dirname(project_path)
    project_name = os.path.basename(project_path)
    
    # Build the hierarchy
    def build_hierarchy(path: str, prefix: str = "", is_last: bool = True, base_path: str = "") -> List[str]:
        """Recursively build a visual hierarchy of files and folders"""
        lines = []
        
        if not base_path:
            base_path = path
            
        # Get relative path for display
        rel_path = os.path.relpath(path, os.path.dirname(base_path))
        
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
    # Validate input
    if not project_path or project_path.strip() == "":
        raise InvalidParameterError("project_path cannot be empty")
    
    project_path = project_path.strip()
    
    # Verify path ends with .xcodeproj or .xcworkspace
    if not (project_path.endswith('.xcodeproj') or project_path.endswith('.xcworkspace')):
        raise InvalidParameterError("project_path must end with '.xcodeproj' or '.xcworkspace'")
    
    show_notification("Xcode MCP", f"Getting schemes for {os.path.basename(project_path)}")
    
    # Security check
    if not is_path_allowed(project_path):
        raise AccessDeniedError(f"Access to path '{project_path}' is not allowed. Set XCODEMCP_ALLOWED_FOLDERS environment variable.")
    
    # Check if the path exists
    if not os.path.exists(project_path):
        raise InvalidParameterError(f"Project path does not exist: {project_path}")
    
    script = f'''
    tell application "Xcode"
        open "{project_path}"
        
        set workspaceDoc to first workspace document whose path is "{project_path}"
        
        -- Wait for it to load
        repeat 60 times
            if loaded of workspaceDoc is true then exit repeat
            delay 0.5
        end repeat
        
        if loaded of workspaceDoc is false then
            error "Xcode workspace did not load in time."
        end if
        
        -- Get active scheme name
        set activeScheme to name of active scheme of workspaceDoc
        
        -- Get all scheme names
        set schemeNames to {{}}
        repeat with aScheme in schemes of workspaceDoc
            set end of schemeNames to name of aScheme
        end repeat
        
        -- Format output with active scheme first
        set output to activeScheme & " (active)"
        repeat with schemeName in schemeNames
            if schemeName as string is not equal to activeScheme then
                set output to output & "\\n" & schemeName
            end if
        end repeat
        
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
                 scheme: Optional[str] = None) -> str:
    """
    Build the specified Xcode project or workspace.
    
    Args:
        project_path: Path to an Xcode project workspace or directory.
        scheme: Name of the scheme to build. If not provided, uses the active scheme.
        
    Returns:
        On success, returns "Build succeeded with 0 errors."
        On failure, returns the first (up to) 25 error lines from the build log.
    """
    # Validate input
    if not project_path or project_path.strip() == "":
        raise InvalidParameterError("project_path cannot be empty")
    
    project_path = project_path.strip()
    
    # Verify path ends with .xcodeproj or .xcworkspace
    if not (project_path.endswith('.xcodeproj') or project_path.endswith('.xcworkspace')):
        raise InvalidParameterError("project_path must end with '.xcodeproj' or '.xcworkspace'")
    
    scheme_desc = scheme if scheme else "active scheme"
    show_notification("Xcode MCP", f"Building {scheme_desc} in {os.path.basename(project_path)}")
    
    # Security check
    if not is_path_allowed(project_path):
        raise AccessDeniedError(f"Access to path '{project_path}' is not allowed. Set XCODEMCP_ALLOWED_FOLDERS environment variable.")
    
    if not os.path.exists(project_path):
        raise InvalidParameterError(f"Project path does not exist: {project_path}")
    
    # Build the AppleScript
    if scheme:
        # Use provided scheme
        script = f'''
set projectPath to "{project_path}"
set schemeName to "{scheme}"

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
set projectPath to "{project_path}"

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
            output_lines = output.split("\n")
            error_lines = [line for line in output_lines if "error" in line]
            
            # Limit to first 25 error lines
            if len(error_lines) > 25:
                error_lines = error_lines[:25]
                error_lines.append("... (truncated to first 25 error lines)")
                
            error_list = "\n".join(error_lines)
            return f"Build failed with errors:\n{error_list}"
    else:
        raise XCodeMCPError(f"Build failed to start for scheme {scheme} in project {project_path}: {output}")

@mcp.tool()
def run_project(project_path: str, 
               scheme: Optional[str] = None) -> str:
    """
    Run the specified Xcode project or workspace.
    
    Args:
        project_path: Path to an Xcode project/workspace directory.
        scheme: Optional scheme to run. If not provided, uses the active scheme.
        
    Returns:
        Output message
    """
    # Validate input
    if not project_path or project_path.strip() == "":
        raise InvalidParameterError("project_path cannot be empty")
    
    # Security check
    if not is_path_allowed(project_path):
        raise AccessDeniedError(f"Access to path '{project_path}' is not allowed. Set XCODEMCP_ALLOWED_FOLDERS environment variable.")
    
    if not os.path.exists(project_path):
        raise InvalidParameterError(f"Project path does not exist: {project_path}")
    
    # TODO: Implement run command using AppleScript
    script = f'''
    tell application "Xcode"
        open "{project_path}"
        delay 1
        set frontWindow to front window
        tell frontWindow
            set currentWorkspace to workspace
            run currentWorkspace
        end tell
    end tell
    '''
    
    success, output = run_applescript(script)
    
    if success:
        return "Run started successfully"
    else:
        raise XCodeMCPError(f"Run failed to start: {output}")

@mcp.tool()
def get_build_errors(project_path: str) -> str:
    """
    Get the build errors for the specified Xcode project or workspace.
    
    Args:
        project_path: Path to an Xcode project or workspace directory.
        
    Returns:
        A string containing the build errors or a message if there are none
    """
    # Validate input
    if not project_path or project_path.strip() == "":
        raise InvalidParameterError("project_path cannot be empty")
    
    # Security check
    if not is_path_allowed(project_path):
        raise AccessDeniedError(f"Access to path '{project_path}' is not allowed. Set XCODEMCP_ALLOWED_FOLDERS environment variable.")
    
    if not os.path.exists(project_path):
        raise InvalidParameterError(f"Project path does not exist: {project_path}")
    
    # TODO: Implement error retrieval using AppleScript or by parsing logs
    script = f'''
    tell application "Xcode"
        open "{project_path}"
        delay 1
        set frontWindow to front window
        tell frontWindow
            set currentWorkspace to workspace
            set issuesList to get issues
            set issuesText to ""
            set issueCount to 0
            
            repeat with anIssue in issuesList
                if issueCount ≥ 25 then exit repeat
                set issuesText to issuesText & "- " & message of anIssue & "\n"
                set issueCount to issueCount + 1
            end repeat
            
            return issuesText
        end tell
    end tell
    '''
    
    # This script syntax may need to be adjusted based on actual AppleScript capabilities
    success, output = run_applescript(script)
    
    if success and output:
        return output
    elif success:
        return "No build errors found."
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
    # Validate input
    if not project_path or project_path.strip() == "":
        raise InvalidParameterError("project_path cannot be empty")
    
    # Security check
    if not is_path_allowed(project_path):
        raise AccessDeniedError(f"Access to path '{project_path}' is not allowed. Set XCODEMCP_ALLOWED_FOLDERS environment variable.")
    
    if not os.path.exists(project_path):
        raise InvalidParameterError(f"Project path does not exist: {project_path}")
    
    # TODO: Implement clean command using AppleScript
    script = f'''
    tell application "Xcode"
        open "{project_path}"
        delay 1
        set frontWindow to front window
        tell frontWindow
            set currentWorkspace to workspace
            clean currentWorkspace
        end tell
    end tell
    '''
    
    success, output = run_applescript(script)
    
    if success:
        return "Clean completed successfully"
    else:
        raise XCodeMCPError(f"Clean failed: {output}")

@mcp.tool()
def get_runtime_output(project_path: str, 
                      max_lines: int = 25) -> str:
    """
    Get the runtime output from the console for the specified Xcode project.
    
    Args:
        project_path: Path to an Xcode project/workspace directory.
        max_lines: Maximum number of lines to retrieve. Defaults to 25.
        
    Returns:
        Console output as a string
    """
    # Validate input
    if not project_path or project_path.strip() == "":
        raise InvalidParameterError("project_path cannot be empty")
    
    # Security check
    if not is_path_allowed(project_path):
        raise AccessDeniedError(f"Access to path '{project_path}' is not allowed. Set XCODEMCP_ALLOWED_FOLDERS environment variable.")
    
    if not os.path.exists(project_path):
        raise InvalidParameterError(f"Project path does not exist: {project_path}")
    
    # TODO: Implement console output retrieval
    # This is a placeholder as you mentioned this functionality isn't available yet
    raise XCodeMCPError("Runtime output retrieval not yet implemented")

# Main entry point for the server
if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Xcode MCP Server")
    parser.add_argument("--version", action="version", version=f"xcode-mcp-server {__import__('xcode_mcp_server').__version__}")
    parser.add_argument("--allowed", action="append", help="Add an allowed folder path (can be used multiple times)")
    parser.add_argument("--show-notifications", action="store_true", help="Enable notifications for tool invocations")
    parser.add_argument("--hide-notifications", action="store_true", help="Disable notifications for tool invocations")
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
