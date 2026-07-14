# Drew's Xcode MCP Server (drews-xcode-mcp)

[![PyPI](https://img.shields.io/pypi/v/drews-xcode-mcp.svg)](https://pypi.org/project/drews-xcode-mcp/)
[![Python Versions](https://img.shields.io/pypi/pyversions/drews-xcode-mcp.svg)](https://pypi.org/project/drews-xcode-mcp/)
[![Downloads](https://static.pepy.tech/badge/drews-xcode-mcp)](https://pepy.tech/project/drews-xcode-mcp)
[![MCP](https://img.shields.io/badge/MCP-Server-blue)](https://modelcontextprotocol.io)
[![macOS Only](https://img.shields.io/badge/platform-macOS-lightgrey)](https://www.apple.com/macos/)
[![Xcode](https://img.shields.io/badge/Xcode-Required-blue)](https://developer.apple.com/xcode/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[![GitHub last commit](https://img.shields.io/github/last-commit/drewster99/drews-xcode-mcp)](https://github.com/drewster99/drews-xcode-mcp/commits)

An MCP (Model Context Protocol) server that enables AI assistants to control and interact with Xcode for Apple platform development.

> **Renamed from `xcode-mcp-server`.** With several unrelated projects sharing that
> name — and Xcode itself now shipping a built-in MCP server — this project is now
> `drews-xcode-mcp`. **Existing setups keep working:** the old PyPI name is a
> compatibility package that forwards to this one, and all settings carry over.
> When convenient, update your MCP configuration to run `drews-xcode-mcp`. If your
> server key/name is the old default `xcode-mcp-server`, rename it to
> `drews-xcode-mcp` too (tool permission allowlists referencing the old tool names
> will need updating); if you chose a custom key, keep it and tool permissions are
> unaffected.

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
- **Python 3.10+** - For running the server (uvx will fetch a compatible Python automatically if your system Python is older)

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
claude mcp add --scope user --transport stdio -- drews-xcode-mcp `which uvx` drews-xcode-mcp
```

To run a specific version, use:
```bash
# Example: How to run v1.3.0b6
claude mcp add --scope user --transport stdio -- drews-xcode-mcp `which uvx` drews-xcode-mcp==1.3.0b6
```

That's it! Claude Code handles the rest automatically.

### 2. Claude Desktop

Edit your Claude Desktop config file (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
    "mcpServers": {
        "drews-xcode-mcp": {
            "command": "uvx",
            "args": [
                "drews-xcode-mcp"
            ]
        }
    }
}
```

If you'd like to allow only certain projects or folders to be accessible by drews-xcode-mcp, add the `env` option, with a colon-separated list of absolute folder paths, like this:

```json
{
    "mcpServers": {
        "drews-xcode-mcp": {
            "command": "uvx",
            "args": [
                "drews-xcode-mcp"
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
        "drews-xcode-mcp": {
            "command": "uvx",
            "args": ["drews-xcode-mcp"]
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
drews-xcode-mcp --no-build-warnings --show-notifications --allowed ~/Projects
```

**Note:** When using MCP clients (Claude, Cursor), configure these via the `env` section in your client's config file instead.

## Development

The server is built with FastMCP and uses AppleScript to communicate with Xcode.

### Local Testing

Test with MCP Inspector:

```bash
export XCODEMCP_ALLOWED_FOLDERS=~/Projects
mcp dev drews_xcode_mcp/__main__.py
```

This opens an inspector interface where you can test tools directly. Provide paths as quoted strings: `"/Users/you/Projects/MyApp.xcodeproj"`

## Limitations

- AppleScript syntax may need adjustments for specific Xcode versions
- Some operations require the project to be open in Xcode first
