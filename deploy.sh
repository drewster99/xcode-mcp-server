#!/bin/bash

# Deployment script for xcode-mcp-server
# This script builds and publishes the package to PyPI

# If you want to deploy a BETA, this script won't do it,
# but you can do it manually:
#
#   You can use pre-release version numbers following
#     https://peps.python.org/pep-0440/. PyPI will accept them, but pip won't
#     install them by default.
#
#     Pre-release version formats:
#     - 1.2.3b1 - beta 1
#     - 1.2.3a1 - alpha 1
#     - 1.2.3rc1 - release candidate 1
#
#     To publish a beta:
#     python -m hatch version 1.2.3b1  # Set beta version
#     python -m build
#     python -m twine upload dist/*
#
#     Users can install it with:
#     # Specific beta version (safest for testers)
#     pip install xcode-mcp-server==1.2.3b1
#     uvx xcode-mcp-server==1.2.3b1
#
#     Regular users doing pip install xcode-mcp-server will get the latest
#     stable version and skip all pre-releases automatically.

set -e  # Exit on error

echo "🚀 Starting xcode-mcp-server deployment..."
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

# Increment version
echo "📝 Incrementing patch version..."
hatch version patch
NEW_VERSION=$(hatch version)
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

echo "✅ Deployment complete! v$NEW_VERSION is live."
echo ""
echo "Test the deployed version with:"
echo ""
echo "    uvx xcode-mcp-server"

exit 0
