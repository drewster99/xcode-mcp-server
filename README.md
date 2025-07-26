# Xcode MCP Server

An MCP (Model Context Protocol) server for controlling and interacting with Xcode from AI assistants like Claude.

## Features

- Get project hierarchy
- Build and run projects
- Retrieve build errors
- Get runtime output (placeholder)
- Clean projects

## Security

The server implements path-based security to prevent unauthorized access to files outside of allowed directories:

- You must specify allowed folders using the environment variable:
  - `XCODEMCP_ALLOWED_FOLDERS=/path1:/path2:/path3`
- Otherwise, all files and subfolders from your home directory ($HOME) will be allowed.

Security requirements:
- All paths must be absolute (starting with /)
- No path components with `..` are allowed
- All paths must exist and be directories

Example:
```bash
# Set the environment variable
export XCODEMCP_ALLOWED_FOLDERS=/Users/username/Projects:/Users/username/checkouts
python3 xcode_mcp.py

# Or inline with the MCP command
XCODEMCP_ALLOWED_FOLDERS=/Users/username/Projects mcp dev xcode_mcp.py
```

If no allowed folders are specified, access will be restricted and tools will return error messages.

## Setup

1. Install dependencies:

```bash
# Using pip
pip install -r requirements.txt

# Or using uv (recommended)
uv pip install -r requirements.txt
```

If you don't have pip installed, you can do:
```
brew install pip
```

2. Configure Claude for Desktop:

Open/create your Claude for Desktop configuration file
- Open Claude Desktop --> Settings --> Developer --> Edit Config (to find the file in finder)
- It should be at `~/Library/Application Support/Claude/claude_desktop_config.json`
- Add the following:

```json
{
    "mcpServers": {
        "xcode-mcp-server": {
            "command": "uvx",
            "args": [
                "xcode-mcp-server"
            ],
            "env": {
                "XCODEMCP_ALLOWED_FOLDERS": "/path/to/projects:/path/to/other/projects"
            }
        }
    }
}
```

If you installed uv with 'pipx', you'll probably need to list the full path of the `uvx` command, above.

If you omit the `env` section, access will default to your $HOME directory.

## Usage

1. Open Xcode with a project
2. Start Claude for Desktop
3. Look for the hammer icon to find available Xcode tools
4. Use natural language to interact with Xcode, for example:
   - "Build the project at /path/to/MyProject.xcodeproj"
   - "Run the app in /path/to/MyProject"
   - "What build errors are there in /path/to/MyProject.xcodeproj?"
   - "Clean the project at /path/to/MyProject"

### Parameter Format

All tools require a `project_path` parameter pointing to an Xcode project/workspace directory:

```
"/path/to/your/project.xcodeproj"
```

or

```
"/path/to/your/project"
```

## Development

The server is built with the MCP Python SDK and uses AppleScript to communicate with Xcode.

To test the server locally without Claude, use:

```bash
# Set the environment variable first
export XCODEMCP_ALLOWED_FOLDERS=/Users/username/Projects
mcp dev xcode_mcp.py

# Or inline with the command
XCODEMCP_ALLOWED_FOLDERS=/Users/username/Projects mcp dev xcode_mcp.py
```

This will open the MCP Inspector interface where you can test the tools directly.

### Testing in MCP Inspector

When testing in the MCP Inspector, provide input values as quoted strings:

```
"/Users/username/Projects/MyApp"
```

## Limitations

- Runtime output retrieval is not yet implemented
- Project hierarchy is a simple file listing implementation
- AppleScript syntax may need adjustments for specific Xcode versions # xcode-mcp-server
