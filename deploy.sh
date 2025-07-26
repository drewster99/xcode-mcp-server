#!/bin/sh
rm -rf dist
hatch version patch
python -m build
twine upload dist/*

echo "If the above was successful, run with:"
echo ""
echo "    uvx xcode-mcp-server"
echo ""
exit 0
