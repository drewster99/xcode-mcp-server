#!/bin/bash

# Beta Deployment script for xcode-mcp-server
# This script builds and publishes BETA packages to PyPI

set -e  # Exit on error

echo "🚀 Starting xcode-mcp-server BETA deployment..."
echo ""
/bin/echo -n "Hit enter to continue:"
read foo

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

# Get current version and increment beta version
echo "📝 Incrementing beta version..."
CURRENT_VERSION=$($PYTHON_CMD -m hatch version)
echo "Current version: $CURRENT_VERSION"

# Check if current version is already a beta (e.g., 1.2.3b4)
if [[ $CURRENT_VERSION =~ ^([0-9]+\.[0-9]+\.[0-9]+)b([0-9]+)$ ]]; then
    # Already a beta - increment beta number
    BASE_VERSION="${BASH_REMATCH[1]}"
    BETA_NUM="${BASH_REMATCH[2]}"
    NEW_BETA_NUM=$((BETA_NUM + 1))
    NEW_VERSION="${BASE_VERSION}b${NEW_BETA_NUM}"
    echo "Incrementing beta: $CURRENT_VERSION -> $NEW_VERSION"
elif [[ $CURRENT_VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    # Release version - increment patch and add b1
    if [[ $CURRENT_VERSION =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
        MAJOR="${BASH_REMATCH[1]}"
        MINOR="${BASH_REMATCH[2]}"
        PATCH="${BASH_REMATCH[3]}"
        NEW_PATCH=$((PATCH + 1))
        NEW_VERSION="${MAJOR}.${MINOR}.${NEW_PATCH}b1"
        echo "Creating first beta of next patch: $CURRENT_VERSION -> $NEW_VERSION"
    else
        echo "❌ Could not parse version: $CURRENT_VERSION"
        exit 1
    fi
else
    echo "❌ Unexpected version format: $CURRENT_VERSION"
    echo "Expected formats: X.Y.Z or X.Y.ZbN"
    exit 1
fi

$PYTHON_CMD -m hatch version "$NEW_VERSION"
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
echo "✅ Beta deployment complete!"
echo ""
echo "Test the deployed beta version with:"
echo ""
echo "    uvx xcode-mcp-server==$NEW_VERSION"
echo ""

# Optional: Update Claude Code MCP server
read -p "Update Claude Code to use this beta version? (y/n): " -r
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🔄 Updating Claude Code MCP configuration..."

    # Remove existing xcode-mcp-server
    echo "Removing existing xcode-mcp-server..."
    claude mcp remove xcode-mcp-server || true

    # Add new beta version
    echo "Adding xcode-mcp-server $NEW_VERSION..."
    claude mcp add --scope user --transport stdio -- xcode-mcp-server `which uvx`  "xcode-mcp-server==$NEW_VERSION"

    echo ""
    echo "✅ Claude Code updated! Restart Claude Code for changes to take effect."
fi

exit 0
