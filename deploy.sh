#!/bin/sh
rm -rf dist
python -m build
twine upload dist/*

echo "If the above was successful, run with: uvx xcode-mcp-server"
echo "If it failed, you probably have to bump the version number in pyproject.toml"
exit 0
