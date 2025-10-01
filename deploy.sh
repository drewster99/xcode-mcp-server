#!/bin/bash

# Deployment script for xcode-mcp-server
# This script builds and publishes the package to PyPI

set -e  # Exit on error

echo "🚀 Starting xcode-mcp-server deployment..."
echo ""

# Check dependencies
MISSING_DEPS=()

# Check for python or python3
if command -v python &> /dev/null; then
    PYTHON_CMD="python"
    echo "✅ python found: $(which python)"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    echo "✅ python3 found: $(which python3)"
else
    echo "❌ python/python3 is not installed or not in PATH"
    MISSING_DEPS+=("python")
fi

if ! $PYTHON_CMD -c "import hatch" &> /dev/null; then
    echo "❌ hatch is not installed"
    MISSING_DEPS+=("hatch")
else
    echo "✅ hatch found"
fi

if ! $PYTHON_CMD -c "import twine" &> /dev/null; then
    echo "❌ twine is not installed"
    MISSING_DEPS+=("twine")
else
    echo "✅ twine found"
fi

echo ""

# Handle missing dependencies
if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    for dep in "${MISSING_DEPS[@]}"; do
        if [ "$dep" = "python" ]; then
            echo "Python must be installed manually. Please install Python 3.8+ first."
            exit 1
        elif [ "$dep" = "hatch" ]; then
            read -p "Install hatch with pip? (y/n): " -r
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                $PYTHON_CMD -m pip install hatch
                echo "✅ hatch installed"
            else
                echo "Deployment cannot continue without hatch"
                exit 1
            fi
        elif [ "$dep" = "twine" ]; then
            read -p "Install twine with pip? (y/n): " -r
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                $PYTHON_CMD -m pip install twine
                echo "✅ twine installed"
            else
                echo "Deployment cannot continue without twine"
                exit 1
            fi
        fi
    done
    echo ""
fi

# Create dist-archive directory if it doesn't exist
mkdir -p dist-archive

# Archive any existing dist files
if [ -d "dist" ] && [ "$(ls -A dist 2>/dev/null)" ]; then
    echo "📦 Archiving previous dist files..."
    mv dist/* dist-archive/
    echo ""
fi

# Clean dist directory
echo "🧹 Cleaning dist directory..."
rm -rf dist
mkdir -p dist
echo ""

# Increment version
echo "📝 Incrementing patch version..."
$PYTHON_CMD -m hatch version patch
echo ""

# Build the package
echo "🔨 Building package..."
$PYTHON_CMD -m build
echo ""

# Copy new build to archive
echo "💾 Copying new build to archive..."
cp dist/* dist-archive/
echo ""

# Upload to PyPI
echo "📤 Uploading to PyPI..."
$PYTHON_CMD -m twine upload dist/*
echo ""

echo "Checking available xcode-mcp-server versions available on PyPi:"
$PYTHON_CMD -m pip index versions xcode-mcp-server
echo ""
echo "✅ Deployment complete!"
echo ""
echo "Test the deployed version with:"
echo ""
echo "    uvx xcode-mcp-server"

exit 0
