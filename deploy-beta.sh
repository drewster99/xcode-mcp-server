#!/bin/bash

# Beta Deployment script for xcode-mcp-server
# This script builds and publishes BETA packages to PyPI

set -e  # Exit on error

echo "🚀 Starting xcode-mcp-server BETA deployment..."
echo ""

# Pre-flight: ensure no unstaged changes
UNSTAGED=$(git diff --name-only)
if [ -n "$UNSTAGED" ]; then
    echo "❌ You have unstaged changes:"
    git diff --stat
    echo ""
    echo "Please stage ('git add') or commit your changes before deploying."
    exit 1
fi
echo "✅ No unstaged changes"
echo ""

/bin/echo -n "Hit enter to continue:"
read foo

# Set up venv and install deploy dependencies
source "$(dirname "${BASH_SOURCE[0]}")/_venv-setup.sh"
pip install -q hatch build twine
echo ""

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
CURRENT_VERSION=$(hatch version)
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

hatch version "$NEW_VERSION"
echo ""

# Build the package
echo "🔨 Building package..."
python -m build
echo ""

# Copy new build to archive
echo "💾 Copying new build to archive..."
cp dist/* dist-archive/
echo ""

# Upload to PyPI
echo "📤 Uploading to PyPI..."
twine upload dist/*
echo ""

# Verify on PyPI
echo "🔍 Verifying version $NEW_VERSION on PyPI..."
sleep 2
if curl -sf "https://pypi.org/pypi/xcode-mcp-server/$NEW_VERSION/json" > /dev/null 2>&1; then
    echo "✅ Version $NEW_VERSION confirmed on PyPI"
else
    echo "⚠️  Could not verify version $NEW_VERSION on PyPI."
    echo "Skipping auto-commit. Please verify manually and commit the version change."
    exit 1
fi
echo ""

# Commit and push the version bump
echo "📝 Committing version bump..."
git add xcode_mcp_server/__init__.py
git commit -m "v$NEW_VERSION"
git push
echo ""

echo "✅ Beta deployment complete! v$NEW_VERSION is live."
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
