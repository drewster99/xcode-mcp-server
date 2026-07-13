#!/bin/bash

# Beta Deployment script for drews-xcode-mcp
# Builds and publishes BETA packages to PyPI, together with a matching beta of
# the legacy 'xcode-mcp-server' compatibility shim (see shim/).

set -e  # Exit on error

echo "🚀 Starting drews-xcode-mcp BETA deployment..."
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

# Keep the legacy compatibility shim in lockstep: same version, exact pin.
# The exact pin matters because uvx resolves dependencies once and caches the
# result - a floating pin would strand shim users on whatever was current.
echo "🔗 Syncing legacy xcode-mcp-server shim to $NEW_VERSION..."
sed -i '' -E "s|^version = \".*\"$|version = \"$NEW_VERSION\"|" shim/pyproject.toml
sed -i '' -E "s|drews-xcode-mcp==[^\"]*|drews-xcode-mcp==$NEW_VERSION|" shim/pyproject.toml
echo ""

# Build both packages
echo "🔨 Building drews-xcode-mcp..."
python -m build
echo ""
echo "🔨 Building legacy xcode-mcp-server shim..."
python -m build shim --outdir dist
echo ""

# Copy new build to archive
echo "💾 Copying new build to archive..."
cp dist/* dist-archive/
echo ""

# Upload to PyPI
echo "📤 Uploading to PyPI..."
if ! twine upload --skip-existing dist/*; then
    echo "❌ twine upload failed. Some files may already be on PyPI."
    echo "   Recover with: twine upload --skip-existing dist/*"
    echo "   Then verify both packages at $NEW_VERSION on PyPI, and commit the"
    echo "   version bump manually (do not re-run this script: the unstaged"
    echo "   version changes will fail the pre-flight check)."
    exit 1
fi
echo ""

# Verify on PyPI
echo "🔍 Verifying version $NEW_VERSION on PyPI..."
MAX_ATTEMPTS=5
for PACKAGE in drews-xcode-mcp xcode-mcp-server; do
    VERIFIED=false
    for (( ATTEMPT=1; ATTEMPT<=MAX_ATTEMPTS; ATTEMPT++ )); do
        if curl -sf "https://pypi.org/pypi/$PACKAGE/$NEW_VERSION/json" > /dev/null 2>&1; then
            VERIFIED=true
            break
        fi
        if [ "$ATTEMPT" -lt "$MAX_ATTEMPTS" ]; then
            echo "   $PACKAGE $NEW_VERSION not visible yet (attempt $ATTEMPT/$MAX_ATTEMPTS), retrying in 5s..."
            sleep 5
        fi
    done
    if [ "$VERIFIED" = true ]; then
        echo "✅ $PACKAGE $NEW_VERSION confirmed on PyPI"
    else
        echo "⚠️  Could not verify $PACKAGE $NEW_VERSION on PyPI."
        echo "Skipping auto-commit. Please verify manually and commit the version change."
        exit 1
    fi
done
echo ""

# Commit and push the version bump
echo "📝 Committing version bump..."
git add drews_xcode_mcp/__init__.py
git add shim/pyproject.toml
git add dist
git add dist-archive
git commit -m "v$NEW_VERSION"
git push
echo ""

echo "✅ Beta deployment complete! v$NEW_VERSION is live."
echo ""
echo "Test the deployed beta version with:"
echo ""
echo "    uvx drews-xcode-mcp==$NEW_VERSION"
echo ""

# Optional: Update Claude Code MCP server
read -p "Update Claude Code to use this beta version? (y/n): " -r
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🔄 Updating Claude Code MCP configuration..."

    # Remove existing xcode-mcp-server
    echo "Removing existing xcode-mcp-server..."
    claude mcp remove xcode-mcp-server || true

    # Add new beta version (server key stays 'xcode-mcp-server' so tool names
    # and permission allowlists are unaffected)
    echo "Adding drews-xcode-mcp $NEW_VERSION..."
    claude mcp add --scope user --transport stdio -- xcode-mcp-server `which uvx`  "drews-xcode-mcp==$NEW_VERSION"

    echo ""
    echo "✅ Claude Code updated! Restart Claude Code for changes to take effect."
fi

exit 0
