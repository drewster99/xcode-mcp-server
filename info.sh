#!/bin/sh

UVX=`which uvx`

LATEST_BETA=`pip index versions drews-xcode-mcp --pre 2> /dev/null | head -1 | sed -E 's/.*\(([^)]*)\).*/\1/'`

echo "Current release:"
pip index versions drews-xcode-mcp 2> /dev/null | head -n 1
echo ""
echo "Latest pre-release:"
pip index versions drews-xcode-mcp --pre 2> /dev/null | head -1
echo ""
echo "Other releases:"
pip index versions drews-xcode-mcp 2> /dev/null | tail -n +2

echo ""
echo ""
echo "Set Claude Code to use latest release:"
echo ""
echo "  claude mcp remove xcode-mcp-server"
echo "  claude mcp add --scope user --transport stdio -- xcode-mcp-server $UVX drews-xcode-mcp"
echo ""
echo ""
echo "Set Claude Code to use the latest beta ($LATEST_BETA):"
echo ""
echo "  claude mcp remove xcode-mcp-server"
echo "  claude mcp add --scope user --transport stdio -- xcode-mcp-server $UVX drews-xcode-mcp==$LATEST_BETA"
echo ""
echo ""
echo "Set Claude Code to use a specific version (including beta builds):"
echo "  claude mcp remove xcode-mcp-server"
echo "  claude mcp add --scope user --transport stdio -- xcode-mcp-server $UVX drews-xcode-mcp==1.3.0b6"
echo ""
echo ""

echo ""
exit 0
