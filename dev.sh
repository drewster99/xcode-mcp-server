#!/bin/bash

# Development script for xcode-mcp-server
# This script sets up the environment and runs the MCP inspector for testing
#
# To connect a specific release or beta to the MCP Inspector, do like this:
#
#     npx @modelcontextprotocol/inspector uvx xcode-mcp-server==1.3.0b3
#
#
set -e  # Exit on error

echo "🔧 Starting xcode-mcp-server development environment..."
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Set up venv and install dev dependencies
source "$SCRIPT_DIR/_venv-setup.sh"
echo ""

echo "📥 Installing development dependencies..."
pip install -q -e .
pip install -q mcp
echo ""

# Check if npx is available (comes with Node.js)
if ! command -v npx &> /dev/null; then
    echo "❌ Error: npx is not installed"
    echo "Please install Node.js first: brew install node"
    exit 1
fi

# Set allowed folders to $HOME
export XCODEMCP_ALLOWED_FOLDERS="$HOME"

# Display environment info
echo "✅ Environment ready!"
echo ""
echo "📋 Configuration:"
echo "   Python: $(which python)"
echo "   Python version: $(python --version)"
echo "   venv: $VENV_DIR"
echo "   Allowed folders: ${XCODEMCP_ALLOWED_FOLDERS}"
echo "   Server path: ${SCRIPT_DIR}/xcode_mcp_server/__main__.py"
echo ""
echo "🚀 Starting MCP Inspector..."
echo "   The inspector will open in your browser at http://localhost:5173"
echo ""
echo "   Press Ctrl+C to stop"
echo ""

#
echo "If you need to run the inspector to a published PyPi beta:"
echo "   npx @modelcontextprotocol/inspector uvx xcode-mcp-server==1.3.0b3   <-- beta version"
echo ""
echo ""
echo "If you need to test with Claude, do this:"
echo "   claude mcp remove xcode-mcp-server"
echo "   claude mcp add --transport stdio --scope user xcode-mcp-server -- python3 -m `pwd`/xcode_mcp_server"
echo ""
echo "  or maybe..."
echo "   claude mcp add --transport stdio --scope user xcode-mcp-server `pwd`/run_local_for_claude.sh"
echo "   claude mcp add --transport stdio --scope user xcode-mcp-server -- /opt/homebrew/Caskroom/miniconda/base/envs/xcode-mcp-dev/bin/python -m `pwd`/xcode_mcp_server"
echo ""

# Run the MCP inspector
npx @modelcontextprotocol/inspector python -m xcode_mcp_server
