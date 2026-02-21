#!/bin/bash
# Shared venv setup — sourced by deploy.sh, deploy-beta.sh, dev.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"

# Find python3 (preferred) or python
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "❌ python3/python not found in PATH"
    exit 1
fi
echo "✅ Using $PYTHON_CMD: $(command -v $PYTHON_CMD)"

# Create venv if needed
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating venv at $VENV_DIR..."
    $PYTHON_CMD -m venv "$VENV_DIR"
fi

# Activate
source "$VENV_DIR/bin/activate"
pip install -q --upgrade pip
echo "✅ venv activated: $(which python)"
