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

# Conda environment name
CONDA_ENV_NAME="xcode-mcp-dev"

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "❌ Error: conda is not installed or not in PATH"
    echo "Please install Miniconda or Anaconda first"
    exit 1
fi

# Initialize conda for bash
eval "$(conda shell.bash hook)"

# Check if the conda environment exists
if ! conda env list | grep -q "^${CONDA_ENV_NAME} "; then
    echo "📦 Creating conda environment: ${CONDA_ENV_NAME}"
    conda create -y -n "${CONDA_ENV_NAME}" python=3.12
    echo ""
fi

# Activate the conda environment
echo "🐍 Activating conda environment: ${CONDA_ENV_NAME}"
conda activate "${CONDA_ENV_NAME}"
echo ""

# Install/upgrade dependencies
echo "📥 Installing Python dependencies..."
pip install -q --upgrade pip
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
echo "   Conda env: ${CONDA_ENV_NAME}"
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

# Run the MCP inspector
npx @modelcontextprotocol/inspector python -m xcode_mcp_server
