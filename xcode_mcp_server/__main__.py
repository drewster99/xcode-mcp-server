#!/usr/bin/env python3
import os
import sys
import subprocess
import json
from typing import Optional, Dict, List, Any, Tuple, Set
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP, Context

# Global variables for allowed folders
ALLOWED_FOLDERS: Set[str] = set()

class XCodeMCPError(Exception):
    def __init__(self, message, code=None):
        self.message = message
        self.code = code
        super().__init__(self.message)

class AccessDeniedError(XCodeMCPError):
    pass

class InvalidParameterError(XCodeMCPError):
    pass

def get_allowed_folders() -> Set[str]:
    """
    Get the allowed folders from environment variable.
    Validates that paths are absolute, exist, and are directories.
    """
    allowed_folders = set()
    
    # Get from environment variable
    folder_list_str = os.environ.get("XCODEMCP_ALLOWED_FOLDERS")
    
    if folder_list_str:
        print(f"Using allowed folders from environment: {folder_list_str}", file=sys.stderr)
    else:
        print("Warning: Allowed folders was not specified.", file=sys.stderr)
        print("Set XCODEMCP_ALLOWED_FOLDERS environment variable to a colon-separated list of allowed folders.", file=sys.stderr)
        home = os.environ.get("HOME", "/")
        print(f"Trying $HOME, {home}", file=sys.stderr)
        folder_list_str = home

    # Process the list
    folder_list = folder_list_str.split(":")
    for folder in folder_list:
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
        # try to fetch folder list
        ALLOWED_FOLDERS = get_allowed_folders()
        if not ALLOWED_FOLDERS:
            print(f"Warning: not ALLOWED_FOLDERS: {', '.join(ALLOWED_FOLDERS)}", file=sys.stderr)
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
mcp = FastMCP("Xcode MCP Server")

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

# MCP Tools for Xcode

# @mcp.tool()
# def reinit_dirs() -> str:
#     """
#     Reinitialize the allowed folders.
#     """
#     global ALLOWED_FOLDERS
#     ALLOWED_FOLDERS = get_allowed_folders()
#     return f"Allowed folders reinitialized to: {ALLOWED_FOLDERS}"


@mcp.tool()
def get_xcode_projects(search_path: str) -> str:
    """
    Search the given search_path to find .xcodeproj (Xcode project) and
     .xcworkspace (Xcode workspace) paths. If the search_path is empty,
     all paths to which this tool has been granted access are searched.
    
    Args:
        search_path: Path to searched.
        
    Returns:
        A string which is a newline-separated list of .xcodeproj and
        .xcworkspace paths found. If none are found, returns an empty string.
    """


    project_path = search_path

    # Validate input
    if not search_path or search_path.strip() == "":
        project_path = "/Users/andrew/Documents/ncc_source"
        # return "Error: project_path cannot be empty"

    
    # Security check
    if not is_path_allowed(project_path):
        raise AccessDeniedError(f"Access to path '{project_path}' is not allowed. Set XCODEMCP_ALLOWED_FOLDERS environment variable.")
        # return f"Error: Access to path '{project_path}' is not allowed. Set XCODEMCP_ALLOWED_FOLDERS environment variable."
    
    # Check if the path exists
    if os.path.exists(project_path):
        # Show the basic file structure
        try:
            #mdfind -onlyin /Users/andrew/Documents/ncc_source/cursor 'kMDItemFSName == "*.xcodeproj" || kMDItemFSName == "*.xcworkspace"' 
            mdfindResult = subprocess.run(['mdfind', '-onlyin', project_path, 'kMDItemFSName == "*.xcodeproj" || kMDItemFSName == "*.xcworkspace"'], 
                                   capture_output=True, text=True, check=True)
            result = mdfindResult.stdout.strip()
            return result
        except Exception as e:
            raise XCodeMCPError(f"Error listing files in {project_path}: {str(e)}")
            # return f"Error listing files in {project_path}: {str(e)}"
    else:
        raise InvalidParameterError(f"Project path does not exist: {project_path}")
        # return f"Project path does not exist: {project_path}"


@mcp.tool()
def get_project_hierarchy(project_path: str) -> str:
    """
    Get the hierarchy of the specified Xcode project or workspace.
    
    Args:
        project_path: Path to an Xcode project/workspace directory.
        
    Returns:
        A string representation of the project hierarchy
    """
    # Validate input
    if not project_path or project_path.strip() == "":
        raise InvalidParameterError("project_path cannot be empty")
        # return "Error: project_path cannot be empty"
    
    # Security check
    if not is_path_allowed(project_path):
        raise AccessDeniedError(f"Access to path '{project_path}' is not allowed. Set XCODEMCP_ALLOWED_FOLDERS environment variable.")
        # return f"Error: Access to path '{project_path}' is not allowed. Set XCODEMCP_ALLOWED_FOLDERS environment variable."
    
    # Check if the path exists
    if os.path.exists(project_path):
        # Show the basic file structure
        try:
            result = subprocess.run(['find', project_path, '-type', 'f', '-name', '*.swift', '-o', '-name', '*.h', '-o', '-name', '*.m'], 
                                   capture_output=True, text=True, check=True)
            files = result.stdout.strip().split('\n')
            if not files or (len(files) == 1 and files[0] == ''):
                raise InvalidParameterError(f"No source files found in {project_path}")
                # return f"No source files found in {project_path}"
            
            return f"Project at {project_path} contains {len(files)} source files:\n" + '\n'.join(files)
        except Exception as e:
            raise XCodeMCPError(f"Error listing files in {project_path}: {str(e)}")
            # return f"Error listing files in {project_path}: {str(e)}"
    else:
        raise InvalidParameterError(f"Project path does not exist: {project_path}")
        # return f"Project path does not exist: {project_path}"

@mcp.tool()
def build_project(project_path: str, 
                 scheme: str) -> str:
    """
    Build the specified Xcode project or workspace.
    
    Args:
        project_path: Path to an Xcode project workspace or directory.
        scheme: Name of the scheme to build.
        
    Returns:
        On success, returns "Build succeeded with 0 errors."
        On failure, returns the first (up to) 25 error lines from the build log.
    """
    # Validate input
    if not project_path or project_path.strip() == "":
        raise InvalidParameterError("project_path cannot be empty")
    
    # Security check
    if not is_path_allowed(project_path):
        raise AccessDeniedError(f"Access to path '{project_path}' is not allowed. Set XCODEMCP_ALLOWED_FOLDERS environment variable.")
    
    if not os.path.exists(project_path):
        raise InvalidParameterError(f"Project path does not exist: {project_path}")
    
    # TODO: Implement build command using AppleScript or shell
    script = f'''
set projectPath to "{project_path}"
set schemeName to "{scheme}"

--
-- Then run with: osascript <thisfilename>
--
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
                -- display dialog "Build succeeded"
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

# Run the server if executed directly
if __name__ == "__main__":
    # Initialize allowed folders
    ALLOWED_FOLDERS = get_allowed_folders()
    
    # Debug info
    print(f"Allowed folders: {ALLOWED_FOLDERS}", file=sys.stderr)
    
    # Run the server
    mcp.run() 
