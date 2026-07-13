# xcode-mcp-server → drews-xcode-mcp

**This package has been renamed to [drews-xcode-mcp](https://pypi.org/project/drews-xcode-mcp/).**

With several projects named "xcode-mcp-server" in the wild — and Xcode itself now
shipping a built-in MCP server — the old name had become ambiguous.

Nothing breaks: installing this package pulls in `drews-xcode-mcp` and forwards the
`xcode-mcp-server` command to it, so existing MCP client configurations keep working.
Your settings carry over automatically (`~/.xcode-mcp-server` is renamed to
`~/.drews-xcode-mcp` on first run), and `XCODEMCP_ALLOWED_FOLDERS` works as before.

When convenient, update your MCP configuration to run `drews-xcode-mcp` instead.
For Claude Code:

```bash
claude mcp remove xcode-mcp-server
claude mcp add --scope user --transport stdio -- drews-xcode-mcp `which uvx` drews-xcode-mcp
```

(If you have tool-permission allowlists tied to the old server name, you can keep
the old name instead — replace the first `drews-xcode-mcp` after `--` (the server
key) with `xcode-mcp-server`, leaving the package name at the end unchanged.)

Source, documentation, and issues: https://github.com/drewster99/drews-xcode-mcp
