#!/bin/bash
# Cleanup script for Xcode MCP Server tests

echo "=========================================="
echo "Cleaning up test environment"
echo "=========================================="

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$REPO_ROOT"

# Clean working directory
echo "Cleaning working directory..."
rm -rf test_projects/working/*

# Kill any hanging Xcode processes related to test projects
echo "Checking for hanging Xcode processes..."
if pgrep -f "test_projects/working" > /dev/null; then
    echo "Killing test-related Xcode processes..."
    pkill -f "test_projects/working" || true
fi

# Clear Xcode derived data for test projects (optional, commented out by default)
# echo "Clearing DerivedData for test projects..."
# rm -rf ~/Library/Developer/Xcode/DerivedData/*SimpleApp*
# rm -rf ~/Library/Developer/Xcode/DerivedData/*BrokenApp*
# rm -rf ~/Library/Developer/Xcode/DerivedData/*ConsoleApp*

echo ""
echo "=========================================="
echo "✅ Cleanup complete!"
echo "=========================================="