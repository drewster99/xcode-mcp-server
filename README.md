# Xcode MCP Server

An MCP (Model Context Protocol) server that enables AI assistants to control and interact with Xcode for Apple platform development.

## What It Does

This server allows AI assistants (like Claude, Cursor, or other MCP clients) to:

- **Discover and navigate** your Xcode projects and source files
- **Build and run** iOS, macOS, tvOS, and watchOS applications
- **Execute and monitor tests** with detailed results
- **Debug build failures** by retrieving errors and warnings
- **Capture console output** from running applications
- **Take screenshots** of Xcode windows and iOS simulators
- **Manage simulators** and view their status

The AI can perform complete development workflows - from finding a project, to building it, running tests, debugging failures, and capturing results.

## Requirements

- **macOS** - This server only works on macOS
- **Xcode** - Xcode must be installed
- **Python 3.8+** - For running the server

## Security

The server implements path-based security to control which directories are accessible:

- **With restrictions:** Set `XCODEMCP_ALLOWED_FOLDERS=/path1:/path2:/path3` to limit access to specific directories
- **Default:** If not specified, allows access to your home directory (`$HOME`)

Security requirements:
- All paths must be absolute (starting with `/`)
- No `..` path components allowed
- All paths must exist and be directories

## Setup

First, ensure `uv` is installed (required for all methods below):
```bash
which uv || brew install uv
```

### 1. Claude Code (Recommended)

```bash
claude mcp add --scope user --transport stdio -- xcode-mcp-server `which uvx` xcode-mcp-server
```

To run a specific version, use:
```bash
# Example: How to run v1.3.0b6
claude mcp add --scope user --transport stdio -- xcode-mcp-server `which uvx` xcode-mcp-server==1.3.0b6
```

That's it! Claude Code handles the rest automatically.

### 2. Claude Desktop

Edit your Claude Desktop config file (`~/Library/Application Support/Claude/claude_desktop_config.json`):

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

### 3. Cursor AI

In Cursor: Settings → Tools & Integrations → + New MCP Server

Or edit `~/.cursor/mcp.json` directly:

```json
{
    "mcpServers": {
        "xcode-mcp-server": {
            "command": "uvx",
            "args": ["xcode-mcp-server"]
        }
    }
}
```

**Optional:** Add folder restrictions with an `env` section (same format as Claude Desktop above).

## Usage

Once configured, simply ask your AI assistant to help with Xcode tasks:

- "Find all Xcode projects in my home directory"
- "Build the project at /path/to/MyProject.xcodeproj"
- "Run tests for this project and show me any failures"
- "What are the build errors in this project?"
- "Show me the directory structure of this project"
- "Take a screenshot of the Xcode window"

Most tools work with paths to `.xcodeproj` or `.xcworkspace` files, or with regular directory paths for browsing and navigation.

## Advanced Configuration

### Command Line Arguments

When running the server directly (for development or custom setups), these options are available:

**Build output control:**
- `--no-build-warnings` - Show only errors, exclude warnings
- `--always-include-build-warnings` - Always show warnings (default)

**Notifications:**
- `--show-notifications` - Enable macOS notifications for operations
- `--hide-notifications` - Disable notifications (default)

**Access control:**
- `--allowed /path` - Add allowed folder (can be repeated)

Example:
```bash
xcode-mcp-server --no-build-warnings --show-notifications --allowed ~/Projects
```

**Note:** When using MCP clients (Claude, Cursor), configure these via the `env` section in your client's config file instead.

## Development

The server is built with FastMCP and uses AppleScript to communicate with Xcode.

### Local Testing

Test with MCP Inspector:

```bash
export XCODEMCP_ALLOWED_FOLDERS=~/Projects
mcp dev xcode_mcp_server/__main__.py
```

This opens an inspector interface where you can test tools directly. Provide paths as quoted strings: `"/Users/you/Projects/MyApp.xcodeproj"`

## Limitations

- AppleScript syntax may need adjustments for specific Xcode versions
- Some operations require the project to be open in Xcode first
