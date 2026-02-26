#!/bin/sh
cd /Users/andrew/cursor/xcode-mcp-server
if [ -x /opt/miniconda3/bin/python ]; then
    PYTHON=/opt/miniconda3/bin/python
elif [ -x /opt/homebrew/Caskroom/miniconda/base/envs/xcode-mcp-dev/bin/python ]; then
    PYTHON=/opt/homebrew/Caskroom/miniconda/base/envs/xcode-mcp-dev/bin/python 
else
    echo "Can't find python." 1>&2
    exit 1
fi

exec "${PYTHON}" -m xcode_mcp_server
