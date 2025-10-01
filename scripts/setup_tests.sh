#!/bin/bash
# Setup script for Xcode MCP Server tests

set -e  # Exit on error

echo "=========================================="
echo "Setting up Xcode MCP Server test environment"
echo "=========================================="

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$REPO_ROOT"

# Check if we're on macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo "Error: These tests require macOS with Xcode installed"
    exit 1
fi

# Check if Xcode is installed
if ! command -v xcodebuild &> /dev/null; then
    echo "Error: Xcode command line tools are not installed"
    echo "Please install Xcode and the command line tools"
    exit 1
fi

echo "✓ Xcode is installed"

# Create test directories if they don't exist
echo "Creating test directories..."
mkdir -p test_projects/templates
mkdir -p test_projects/working
mkdir -p tests
mkdir -p scripts

# Check if test projects exist, create them if not
if [ ! -d "test_projects/templates/SimpleApp" ]; then
    echo "Test projects not found. Creating them..."
    python scripts/create_projects.py
    if [ $? -ne 0 ]; then
        echo "Error: Failed to create test projects"
        exit 1
    fi
else
    echo "✓ Test projects already exist"
fi

# Set up Python virtual environment if needed
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
fi

echo "Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -e .

# Set environment variables for testing
export XCODEMCP_ALLOWED_FOLDERS="$REPO_ROOT/test_projects/working"
echo "Set XCODEMCP_ALLOWED_FOLDERS to: $XCODEMCP_ALLOWED_FOLDERS"

# Clean working directory
echo "Cleaning working directory..."
rm -rf test_projects/working/*

echo ""
echo "=========================================="
echo "✅ Test environment setup complete!"
echo "=========================================="
echo ""
echo "You can now run tests with:"
echo "  python tests/test_basic.py"
echo "  python tests/test_build.py"
echo ""
echo "Or run all tests with:"
echo "  ./scripts/run_all_tests.sh"
echo ""