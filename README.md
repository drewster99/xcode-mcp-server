# Xcode MCP Server

An MCP (Model Context Protocol) server for controlling and interacting with Xcode from AI assistants like Claude.

## Features

- Get project hierarchy
- Build and run projects
- Retrieve build errors and warnings
- Get runtime output from console logs
- Clean projects
- List booted iOS simulators
- Take screenshots of Xcode windows
- Take screenshots of running simulators

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

1. Configure Claude for Desktop:

First, using homebrew, install 'uv'. You might already have this on your system, but installing it via Homebrew usually ensures that `uvx` (part of `uv`)  is in the $PATH that Claude Desktop vends to on-device local MCP servers:

```brew install uv```

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
            ]
        }
    }
}
```

If you'd like to allow only certain projects or folders to be accessible by xcode-mcp-server, add the `env` option, with a colon-separated list of absolute folder paths, like this:

```json
{
    "mcpServers": {
        "xcode-mcp-server": {
            "command": "uvx",
            "args": [
                "xcode-mcp-server"
            ],
            "env": {
                "XCODEMCP_ALLOWED_FOLDERS": "/Users/andrew/my_project:/Users/andrew/Documents/source"
            }
        }
    }
}
```

If you omit the `env` section, access will default to your $HOME directory.

2. Add xcode-mcp-server to **Claude Code** (Anthropic's CLI-based agent)

- Install claude code 
- Add xcode-mcp-server:

  claude mcp add --scope user --transport stdio \`which uvx\` xcode-mcp-server
  
3. Add xcode-mcp-server to **Cursor AI**

- Install Cursor, of course
- In Cursor, navigate to: Cursor --> Settings --> Cursor Settings
- Then choose 'Tools & Integrations'
- Tap the + button for 'New MCP Server'

The steps above will get you editing the file ~/.cursor/mcp.json, which you could also edit directly, if you prefer.  Add a section for 'xcode-mcp-server' in the 'mcpServers' section - like this:

```json
{
    "mcpServers": {
        "xcode-mcp-server": {
            "command": "uvx",
            "args": [
                "xcode-mcp-server"
            ]
        }
    }
}
```

If you'd like to allow only certain projects or folders to be accessible by xcode-mcp-server, add the `env` option, with a colon-separated list of absolute folder paths, like this:

```json
{
    "mcpServers": {
        "xcode-mcp-server": {
            "command": "uvx",
            "args": [
                "xcode-mcp-server"
            ],
            "env": {
                "XCODEMCP_ALLOWED_FOLDERS": "/Users/andrew/my_project:/Users/andrew/Documents/source"
            }
        }
    }
}
```

Be sure to hit Command-S to save the file.

If you omit the `env` section, access will default to your $HOME directory.

### Test it out
- Open cursor to your favorite xcode project (just open the root folder of the project or git repo), and tell Cursor something like:

    build this project using xcode-mcp-server
    
You'll get a permission prompt from Cursor and then one from macOS, and after that you should be off and running.

## Usage

1. Open Xcode with a project
2. Start Claude for Desktop
   - If xcode-mcp-server failed to initialize properly, you'll see errors
3. Look for the hammer icon to find available Xcode tools
4. Use natural language to interact with Xcode, for example:
   - "Build the project at /path/to/MyProject.xcodeproj"
   - "Run the app in /path/to/MyProject"
   - "What build errors are there in /path/to/MyProject.xcodeproj?"
   - "Clean the project at /path/to/MyProject"
   - "List all booted simulators"
   - "Take a screenshot of the Xcode window for /path/to/MyProject"
   - "Take a screenshot of the running simulator"

### Parameter Format

All tools require a `project_path` parameter pointing to an Xcode project/workspace directory:

```
"/path/to/your/project.xcodeproj"
```

or

```
"/path/to/your/project"
```

## Configuration Options

### Command Line Arguments

The server supports several command line arguments for customization:

#### Build Warning Control
- `--no-build-warnings`: Exclude warnings from build output (only show errors)
- `--always-include-build-warnings`: Always include warnings in build output (default behavior)

Example usage:
```bash
# Exclude warnings from build output
xcode-mcp-server --no-build-warnings

# Explicitly enable warnings (default behavior)
xcode-mcp-server --always-include-build-warnings
```

#### Notification Control
- `--show-notifications`: Enable macOS notifications for tool invocations
- `--hide-notifications`: Disable macOS notifications

#### Allowed Folders
- `--allowed /path/to/folder`: Add an allowed folder path (can be used multiple times)

Example combining multiple options:
```bash
xcode-mcp-server --no-build-warnings --show-notifications --allowed /Users/me/Projects
```

### Build Output Behavior

By default, when a build fails:
1. The server collects both error and warning lines from the build output
2. Errors are prioritized and listed first, followed by warnings
3. The output is limited to the first 25 lines total (errors + warnings)
4. You can exclude warnings using `--no-build-warnings` to focus only on errors

The `build_project` tool also accepts an optional `include_warnings` parameter that overrides the global setting for individual build operations.

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

- Project hierarchy is a simple file listing implementation
- AppleScript syntax may need adjustments for specific Xcode versions # xcode-mcp-server
